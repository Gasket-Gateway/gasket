"""Policy acceptance, reacceptance, and acceptance records tests."""


class TestPolicyProfileAssignment:
    def test_create_profile_with_policies(self, client):
        policy = client.post("/admin/api/policies", json={"name": "test-assign-policy", "content": "Assign me."}).json()
        profile = client.post("/admin/api/profiles", json={"name": "test-assign-profile", "policy_ids": [policy["id"]]})
        assert profile.status_code == 201
        data = profile.json()
        assert policy["id"] in data["policy_ids"]
        client.delete(f"/admin/api/profiles/{data['id']}")
        client.delete(f"/admin/api/policies/{policy['id']}")

    def test_update_profile_add_policy(self, client):
        policy = client.post("/admin/api/policies", json={"name": "test-add-policy-to-profile", "content": "Add me."}).json()
        profile = client.post("/admin/api/profiles", json={"name": "test-profile-add-policy"}).json()
        response = client.put(f"/admin/api/profiles/{profile['id']}", json={"policy_ids": [policy["id"]]})
        assert response.status_code == 200
        assert policy["id"] in response.json()["policy_ids"]
        client.delete(f"/admin/api/profiles/{profile['id']}")
        client.delete(f"/admin/api/policies/{policy['id']}")

    def test_update_profile_remove_policies(self, client):
        policy = client.post("/admin/api/policies", json={"name": "test-remove-policy", "content": "Remove me."}).json()
        profile = client.post("/admin/api/profiles", json={"name": "test-profile-remove", "policy_ids": [policy["id"]]}).json()
        response = client.put(f"/admin/api/profiles/{profile['id']}", json={"policy_ids": []})
        assert len(response.json()["policy_ids"]) == 0
        client.delete(f"/admin/api/profiles/{profile['id']}")
        client.delete(f"/admin/api/policies/{policy['id']}")

    def test_config_profile_has_config_policy(self, client):
        profiles = client.get("/admin/api/profiles").json()
        config_profile = next(p for p in profiles if p["name"] == "internal-standard")
        assert "acceptable-use" in config_profile["policy_names"]


class TestPolicyAcceptance:
    def _create_policy_and_profile(self, client):
        policy = client.post("/admin/api/policies", json={"name": "test-accept-policy", "content": "Accept me."}).json()
        profile = client.post("/admin/api/profiles", json={"name": "test-accept-profile", "policy_ids": [policy["id"]]}).json()
        return policy, profile

    def _cleanup(self, client, policy_id, profile_id):
        client.delete(f"/admin/api/profiles/{profile_id}")
        client.delete(f"/admin/api/policies/{policy_id}")

    def test_accept_policy(self, client):
        policy, profile = self._create_policy_and_profile(client)
        response = client.post(f"/admin/api/policies/{policy['id']}/accept", json={"profile_id": profile["id"]})
        assert response.status_code == 201
        assert response.json()["version_number"] == 1
        self._cleanup(client, policy["id"], profile["id"])

    def test_accept_records_correct_version(self, client):
        policy, profile = self._create_policy_and_profile(client)
        client.put(f"/admin/api/policies/{policy['id']}", json={"content": "Updated content."})
        response = client.post(f"/admin/api/policies/{policy['id']}/accept", json={"profile_id": profile["id"]})
        assert response.json()["version_number"] == 2
        self._cleanup(client, policy["id"], profile["id"])

    def test_check_all_accepted(self, client):
        policy, profile = self._create_policy_and_profile(client)
        client.post(f"/admin/api/policies/{policy['id']}/accept", json={"profile_id": profile["id"]})
        check = client.get(f"/admin/api/policies/acceptances/check/{profile['id']}").json()
        assert check["all_accepted"] is True
        assert len(check["pending"]) == 0
        self._cleanup(client, policy["id"], profile["id"])

    def test_check_incomplete(self, client):
        policy, profile = self._create_policy_and_profile(client)
        check = client.get(f"/admin/api/policies/acceptances/check/{profile['id']}").json()
        assert check["all_accepted"] is False
        assert len(check["pending"]) == 1
        self._cleanup(client, policy["id"], profile["id"])

    def test_accept_unassigned_policy_fails(self, client):
        policy = client.post("/admin/api/policies", json={"name": "test-unassigned", "content": "Not assigned."}).json()
        profile = client.post("/admin/api/profiles", json={"name": "test-unassigned-profile"}).json()
        response = client.post(f"/admin/api/policies/{policy['id']}/accept", json={"profile_id": profile["id"]})
        assert response.status_code == 400
        client.delete(f"/admin/api/profiles/{profile['id']}")
        client.delete(f"/admin/api/policies/{policy['id']}")


class TestPolicyReacceptance:
    def test_reacceptance_invalidates_old_acceptance(self, client):
        policy = client.post("/admin/api/policies", json={"name": "test-reaccept-policy", "content": "Version 1.", "enforce_reacceptance": True}).json()
        profile = client.post("/admin/api/profiles", json={"name": "test-reaccept-profile", "policy_ids": [policy["id"]]}).json()
        client.post(f"/admin/api/policies/{policy['id']}/accept", json={"profile_id": profile["id"]})
        check = client.get(f"/admin/api/policies/acceptances/check/{profile['id']}").json()
        assert check["all_accepted"] is True
        client.put(f"/admin/api/policies/{policy['id']}", json={"content": "Version 2."})
        check = client.get(f"/admin/api/policies/acceptances/check/{profile['id']}").json()
        assert check["all_accepted"] is False
        client.delete(f"/admin/api/profiles/{profile['id']}")
        client.delete(f"/admin/api/policies/{policy['id']}")

    def test_no_reacceptance_when_disabled(self, client):
        policy = client.post("/admin/api/policies", json={"name": "test-no-reaccept-policy", "content": "Version 1.", "enforce_reacceptance": False}).json()
        profile = client.post("/admin/api/profiles", json={"name": "test-no-reaccept-profile", "policy_ids": [policy["id"]]}).json()
        client.post(f"/admin/api/policies/{policy['id']}/accept", json={"profile_id": profile["id"]})
        client.put(f"/admin/api/policies/{policy['id']}", json={"content": "Version 2."})
        client.delete(f"/admin/api/profiles/{profile['id']}")
        client.delete(f"/admin/api/policies/{policy['id']}")


class TestPolicyAcceptanceRecords:
    def test_list_acceptances(self, client):
        response = client.get("/admin/api/policies/acceptances")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_my_acceptances(self, client):
        response = client.get("/admin/api/policies/my-acceptances")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_acceptances_with_user_filter(self, client):
        response = client.get("/admin/api/policies/acceptances?user=nonexistent@test.com")
        assert len(response.json()) == 0

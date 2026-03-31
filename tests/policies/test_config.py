"""Config-defined policy tests and policy lifecycle."""


class TestConfigPolicy:
    def test_config_policy_seeded(self, client):
        policies = client.get("/admin/api/policies").json()
        config_policy = next(p for p in policies if p["name"] == "acceptable-use")
        assert config_policy["source"] == "config"
        assert config_policy["enforce_reacceptance"] is False
        assert config_policy["current_version"] == 1

    def test_config_policy_is_read_only_update(self, client):
        config_policy = next(p for p in client.get("/admin/api/policies").json() if p["name"] == "acceptable-use")
        assert client.put(f"/admin/api/policies/{config_policy['id']}", json={"name": "renamed"}).status_code == 403

    def test_config_policy_is_read_only_delete(self, client):
        config_policy = next(p for p in client.get("/admin/api/policies").json() if p["name"] == "acceptable-use")
        assert client.delete(f"/admin/api/policies/{config_policy['id']}").status_code == 403


class TestPolicyLifecycle:
    def test_full_lifecycle(self, client):
        create_resp = client.post("/admin/api/policies", json={"name": "lifecycle-policy", "description": "Lifecycle test", "content": "Version 1 content.", "enforce_reacceptance": True})
        assert create_resp.status_code == 201
        policy = create_resp.json()
        policy_id = policy["id"]
        assert policy["current_version"] == 1

        profile = client.post("/admin/api/profiles", json={"name": "lifecycle-profile", "policy_ids": [policy_id]}).json()
        profile_id = profile["id"]

        check = client.get(f"/admin/api/policies/acceptances/check/{profile_id}").json()
        assert check["all_accepted"] is False

        accept = client.post(f"/admin/api/policies/{policy_id}/accept", json={"profile_id": profile_id})
        assert accept.status_code == 201
        assert accept.json()["version_number"] == 1

        check = client.get(f"/admin/api/policies/acceptances/check/{profile_id}").json()
        assert check["all_accepted"] is True

        update = client.put(f"/admin/api/policies/{policy_id}", json={"content": "Version 2 content."})
        assert update.json()["current_version"] == 2

        check = client.get(f"/admin/api/policies/acceptances/check/{profile_id}").json()
        assert check["all_accepted"] is False

        accept2 = client.post(f"/admin/api/policies/{policy_id}/accept", json={"profile_id": profile_id})
        assert accept2.json()["version_number"] == 2

        versions = client.get(f"/admin/api/policies/{policy_id}/versions").json()
        assert len(versions) == 2

        client.delete(f"/admin/api/profiles/{profile_id}")
        client.delete(f"/admin/api/policies/{policy_id}")

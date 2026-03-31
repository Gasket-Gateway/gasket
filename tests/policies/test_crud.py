"""Policy CRUD tests — list, create, read, update, delete."""


class TestPoliciesList:
    def test_list_policies_returns_200(self, client):
        response = client.get("/admin/api/policies")
        assert response.status_code == 200

    def test_list_policies_returns_json_list(self, client):
        data = client.get("/admin/api/policies").json()
        assert isinstance(data, list)

    def test_list_includes_config_policy(self, client):
        names = [p["name"] for p in client.get("/admin/api/policies").json()]
        assert "acceptable-use" in names


class TestPoliciesCreate:
    def test_create_policy(self, client):
        response = client.post("/admin/api/policies", json={"name": "test-policy-1", "description": "A test policy", "content": "You must follow all rules."})
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "test-policy-1"
        assert data["current_version"] == 1
        assert data["source"] == "admin"
        client.delete(f"/admin/api/policies/{data['id']}")

    def test_create_policy_with_reacceptance(self, client):
        response = client.post("/admin/api/policies", json={"name": "test-policy-reaccept", "content": "Policy with reacceptance.", "enforce_reacceptance": True})
        assert response.status_code == 201
        assert response.json()["enforce_reacceptance"] is True
        client.delete(f"/admin/api/policies/{response.json()['id']}")

    def test_create_policy_duplicate_name(self, client):
        client.post("/admin/api/policies", json={"name": "test-dup-policy", "content": "Content."})
        response = client.post("/admin/api/policies", json={"name": "test-dup-policy", "content": "Other content."})
        assert response.status_code == 409
        policies = client.get("/admin/api/policies").json()
        dup = next(p for p in policies if p["name"] == "test-dup-policy")
        client.delete(f"/admin/api/policies/{dup['id']}")

    def test_create_policy_missing_name(self, client):
        assert client.post("/admin/api/policies", json={"content": "Some content."}).status_code == 400

    def test_create_policy_missing_content(self, client):
        assert client.post("/admin/api/policies", json={"name": "test-no-content"}).status_code == 400


class TestPoliciesRead:
    def test_get_policy_by_id(self, client):
        create = client.post("/admin/api/policies", json={"name": "test-read-policy", "content": "Read me."})
        policy_id = create.json()["id"]
        response = client.get(f"/admin/api/policies/{policy_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "test-read-policy"
        assert "versions" in data
        assert len(data["versions"]) == 1
        client.delete(f"/admin/api/policies/{policy_id}")

    def test_get_policy_not_found(self, client):
        assert client.get("/admin/api/policies/99999").status_code == 404

    def test_get_policy_versions(self, client):
        create = client.post("/admin/api/policies", json={"name": "test-versions-policy", "content": "Version 1."})
        policy_id = create.json()["id"]
        client.put(f"/admin/api/policies/{policy_id}", json={"content": "Version 2."})
        response = client.get(f"/admin/api/policies/{policy_id}/versions")
        assert response.status_code == 200
        versions = response.json()
        assert len(versions) == 2
        assert versions[0]["content"] == "Version 1."
        assert versions[1]["content"] == "Version 2."
        client.delete(f"/admin/api/policies/{policy_id}")


class TestPoliciesUpdate:
    def test_update_description_no_new_version(self, client):
        create = client.post("/admin/api/policies", json={"name": "test-update-desc", "content": "Original."})
        policy_id = create.json()["id"]
        response = client.put(f"/admin/api/policies/{policy_id}", json={"description": "Updated description"})
        assert response.status_code == 200
        assert response.json()["current_version"] == 1
        client.delete(f"/admin/api/policies/{policy_id}")

    def test_update_content_creates_new_version(self, client):
        create = client.post("/admin/api/policies", json={"name": "test-update-content", "content": "Version 1."})
        policy_id = create.json()["id"]
        response = client.put(f"/admin/api/policies/{policy_id}", json={"content": "Version 2."})
        assert response.status_code == 200
        assert response.json()["current_version"] == 2
        client.delete(f"/admin/api/policies/{policy_id}")

    def test_update_same_content_no_new_version(self, client):
        create = client.post("/admin/api/policies", json={"name": "test-same-content", "content": "Same."})
        policy_id = create.json()["id"]
        response = client.put(f"/admin/api/policies/{policy_id}", json={"content": "Same."})
        assert response.json()["current_version"] == 1
        client.delete(f"/admin/api/policies/{policy_id}")

    def test_update_duplicate_name(self, client):
        p1 = client.post("/admin/api/policies", json={"name": "test-dup-name-1", "content": "Content."}).json()
        p2 = client.post("/admin/api/policies", json={"name": "test-dup-name-2", "content": "Content."}).json()
        assert client.put(f"/admin/api/policies/{p2['id']}", json={"name": "test-dup-name-1"}).status_code == 409
        client.delete(f"/admin/api/policies/{p1['id']}")
        client.delete(f"/admin/api/policies/{p2['id']}")


class TestPoliciesDelete:
    def test_delete_policy(self, client):
        create = client.post("/admin/api/policies", json={"name": "test-delete-policy", "content": "Delete me."})
        policy_id = create.json()["id"]
        assert client.delete(f"/admin/api/policies/{policy_id}").status_code == 200
        assert client.get(f"/admin/api/policies/{policy_id}").status_code == 404

    def test_delete_policy_not_found(self, client):
        assert client.delete("/admin/api/policies/99999").status_code == 404

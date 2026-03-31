"""API key lifecycle, config profile, and multi-policy tests."""

from .conftest import accept_all_policies, create_test_profile_with_policy, cleanup_test_resources


class TestApiKeyLifecycle:
    """Full lifecycle test: accept policies → create key → edit → revoke."""

    def test_full_lifecycle(self, client):
        policy = client.post("/admin/api/policies", json={"name": "lifecycle-key-policy", "content": "Accept this policy."}).json()
        profile = client.post("/admin/api/profiles", json={"name": "lifecycle-key-profile", "policy_ids": [policy["id"]], "max_keys_per_user": 5}).json()

        resp = client.post("/api/keys", json={"name": "lifecycle-key", "profile_id": profile["id"]})
        assert resp.status_code == 400

        accept_all_policies(client, profile["id"])

        create = client.post("/api/keys", json={"name": "lifecycle-key", "profile_id": profile["id"], "vscode_continue": False})
        assert create.status_code == 201
        key_data = create.json()
        key_id = key_data["id"]
        assert key_data["key_value"].startswith("gsk_")

        keys = client.get("/api/keys").json()
        assert key_id in [k["id"] for k in keys]

        detail = client.get(f"/api/keys/{key_id}").json()
        assert "key_value" not in detail

        revealed = client.get(f"/api/keys/{key_id}/reveal").json()
        assert revealed["key_value"] == key_data["key_value"]

        edit = client.put(f"/api/keys/{key_id}", json={"vscode_continue": True})
        assert edit.status_code == 200
        assert edit.json()["vscode_continue"] is True

        snapshots = client.get(f"/api/keys/{key_id}/policies").json()
        assert len(snapshots) >= 1

        admin_detail = client.get(f"/admin/api/keys/{key_id}").json()
        assert "key_value" not in admin_detail

        revoke = client.post(f"/api/keys/{key_id}/revoke")
        assert revoke.status_code == 200
        assert revoke.json()["revoked"] is True

        restore = client.post(f"/admin/api/keys/{key_id}/restore")
        assert restore.status_code == 200
        assert restore.json()["revoked"] is False

        client.post(f"/api/keys/{key_id}/revoke")
        client.delete(f"/admin/api/profiles/{profile['id']}")
        client.delete(f"/admin/api/policies/{policy['id']}")


class TestApiKeyWithConfigProfile:
    """Verify keys work with the config-seeded internal-standard profile."""

    def test_create_key_for_config_profile(self, client):
        profiles = client.get("/admin/api/profiles").json()
        config_profile = next(p for p in profiles if p["name"] == "internal-standard")
        accept_all_policies(client, config_profile["id"])
        response = client.post("/api/keys", json={"name": "config-profile-key", "profile_id": config_profile["id"]})
        assert response.status_code == 201
        key_data = response.json()
        assert key_data["profile_name"] == "internal-standard"
        assert key_data["key_value"].startswith("gsk_")
        client.post(f"/api/keys/{key_data['id']}/revoke")


class TestApiKeyMultiplePolicies:
    """Verify key creation and snapshots with multiple policies on a profile."""

    def test_create_key_requires_all_policies_accepted(self, client):
        p1 = client.post("/admin/api/policies", json={"name": "multi-pol-1", "content": "Policy 1."}).json()
        p2 = client.post("/admin/api/policies", json={"name": "multi-pol-2", "content": "Policy 2."}).json()
        profile = client.post("/admin/api/profiles", json={"name": "multi-pol-profile", "policy_ids": [p1["id"], p2["id"]], "max_keys_per_user": 3}).json()

        client.post(f"/admin/api/policies/{p1['id']}/accept", json={"profile_id": profile["id"]})
        response = client.post("/api/keys", json={"name": "partial-accept-key", "profile_id": profile["id"]})
        assert response.status_code == 400

        client.post(f"/admin/api/policies/{p2['id']}/accept", json={"profile_id": profile["id"]})
        response = client.post("/api/keys", json={"name": "full-accept-key", "profile_id": profile["id"]})
        assert response.status_code == 201

        snapshots = client.get(f"/api/keys/{response.json()['id']}/policies").json()
        assert len(snapshots) == 2
        snap_names = {s["policy_name"] for s in snapshots}
        assert "multi-pol-1" in snap_names
        assert "multi-pol-2" in snap_names

        client.post(f"/api/keys/{response.json()['id']}/revoke")
        client.delete(f"/admin/api/profiles/{profile['id']}")
        client.delete(f"/admin/api/policies/{p1['id']}")
        client.delete(f"/admin/api/policies/{p2['id']}")

    def test_policy_reacceptance_blocks_new_keys(self, client):
        policy = client.post("/admin/api/policies", json={"name": "reaccept-block-pol", "content": "Version 1.", "enforce_reacceptance": True}).json()
        profile = client.post("/admin/api/profiles", json={"name": "reaccept-block-profile", "policy_ids": [policy["id"]], "max_keys_per_user": 5}).json()

        accept_all_policies(client, profile["id"])
        key1 = client.post("/api/keys", json={"name": "pre-reaccept-key", "profile_id": profile["id"]}).json()
        assert key1["id"] is not None

        client.put(f"/admin/api/policies/{policy['id']}", json={"content": "Version 2."})
        response = client.post("/api/keys", json={"name": "post-reaccept-key", "profile_id": profile["id"]})
        assert response.status_code == 400

        accept_all_policies(client, profile["id"])
        response = client.post("/api/keys", json={"name": "after-reaccept-key", "profile_id": profile["id"]})
        assert response.status_code == 201

        client.post(f"/api/keys/{key1['id']}/revoke")
        client.post(f"/api/keys/{response.json()['id']}/revoke")
        client.delete(f"/admin/api/profiles/{profile['id']}")
        client.delete(f"/admin/api/policies/{policy['id']}")

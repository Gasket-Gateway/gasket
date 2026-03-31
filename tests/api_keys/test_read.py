"""API key read and reveal tests."""

from .conftest import create_test_profile_with_policy, cleanup_test_resources


class TestApiKeyRead:
    """Verify API key read operations."""

    def test_get_own_key(self, client):
        policy, profile = create_test_profile_with_policy(client, "read")
        create = client.post("/api/keys", json={"name": "read-test", "profile_id": profile["id"]}).json()
        response = client.get(f"/api/keys/{create['id']}")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "read-test"
        assert "key_value" not in data
        cleanup_test_resources(client, profile["id"], policy["id"], [create["id"]])

    def test_get_key_not_found(self, client):
        response = client.get("/api/keys/99999")
        assert response.status_code == 404


class TestApiKeyReveal:
    """Verify the key reveal endpoint."""

    def test_reveal_own_key(self, client):
        policy, profile = create_test_profile_with_policy(client, "reveal")
        create = client.post("/api/keys", json={"name": "reveal-test", "profile_id": profile["id"]}).json()
        original_key = create["key_value"]
        response = client.get(f"/api/keys/{create['id']}/reveal")
        assert response.status_code == 200
        data = response.json()
        assert "key_value" in data
        assert data["key_value"] == original_key
        assert data["key_value"].startswith("gsk_")
        cleanup_test_resources(client, profile["id"], policy["id"], [create["id"]])

    def test_reveal_not_found(self, client):
        response = client.get("/api/keys/99999/reveal")
        assert response.status_code == 404


class TestApiKeyReadEdgeCases:
    """Edge cases for API key reading."""

    def test_get_key_includes_profile_name(self, client):
        policy, profile = create_test_profile_with_policy(client, "read-profile")
        create = client.post("/api/keys", json={"name": "profile-name-test", "profile_id": profile["id"]}).json()
        detail = client.get(f"/api/keys/{create['id']}").json()
        assert detail["profile_name"] == "key-test-profile-read-profile"
        cleanup_test_resources(client, profile["id"], policy["id"], [create["id"]])

    def test_get_key_has_all_expected_fields(self, client):
        policy, profile = create_test_profile_with_policy(client, "fields")
        create = client.post("/api/keys", json={"name": "fields-test", "profile_id": profile["id"]}).json()
        detail = client.get(f"/api/keys/{create['id']}").json()
        expected_fields = ["id", "user_email", "name", "key_preview", "profile_id", "profile_name", "expires_at", "is_expired", "revoked", "revoked_at", "revoked_by", "vscode_continue", "open_webui", "created_at", "policy_snapshot_ids"]
        for field in expected_fields:
            assert field in detail, f"Missing field: {field}"
        cleanup_test_resources(client, profile["id"], policy["id"], [create["id"]])

    def test_reveal_revoked_key_still_works(self, client):
        policy, profile = create_test_profile_with_policy(client, "reveal-revoked")
        create = client.post("/api/keys", json={"name": "reveal-revoked-test", "profile_id": profile["id"]}).json()
        original_key = create["key_value"]
        client.post(f"/api/keys/{create['id']}/revoke")
        response = client.get(f"/api/keys/{create['id']}/reveal")
        assert response.status_code == 200
        assert response.json()["key_value"] == original_key
        cleanup_test_resources(client, profile["id"], policy["id"])

    def test_list_keys_includes_revoked(self, client):
        policy, profile = create_test_profile_with_policy(client, "list-revoked")
        create = client.post("/api/keys", json={"name": "list-revoked-test", "profile_id": profile["id"]}).json()
        client.post(f"/api/keys/{create['id']}/revoke")
        keys = client.get("/api/keys").json()
        our_key = next((k for k in keys if k["id"] == create["id"]), None)
        assert our_key is not None
        assert our_key["revoked"] is True
        cleanup_test_resources(client, profile["id"], policy["id"])

    def test_key_preview_matches_key_value_suffix(self, client):
        policy, profile = create_test_profile_with_policy(client, "preview-match")
        create = client.post("/api/keys", json={"name": "preview-match-test", "profile_id": profile["id"]}).json()
        full_key = create["key_value"]
        preview = create["key_preview"]
        assert preview == f"gsk_…{full_key[-4:]}"
        cleanup_test_resources(client, profile["id"], policy["id"], [create["id"]])

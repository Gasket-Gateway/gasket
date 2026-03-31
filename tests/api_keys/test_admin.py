"""Admin API key management tests."""

from .conftest import create_test_profile_with_policy, cleanup_test_resources


class TestApiKeyAdminManagement:
    """Verify admin API key management routes."""

    def test_admin_list_keys(self, client):
        response = client.get("/admin/api/keys")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_admin_list_keys_user_filter(self, client):
        response = client.get("/admin/api/keys?user=nonexistent@test.com")
        assert response.status_code == 200
        assert len(response.json()) == 0

    def test_admin_list_keys_profile_filter(self, client):
        response = client.get("/admin/api/keys?profile_id=99999")
        assert response.status_code == 200
        assert len(response.json()) == 0

    def test_admin_get_key_masked(self, client):
        policy, profile = create_test_profile_with_policy(client, "admin-get")
        create = client.post("/api/keys", json={"name": "admin-get-test", "profile_id": profile["id"]}).json()
        response = client.get(f"/admin/api/keys/{create['id']}")
        assert response.status_code == 200
        data = response.json()
        assert "key_value" not in data
        assert "key_preview" in data
        assert data["key_preview"].startswith("gsk_…")
        cleanup_test_resources(client, profile["id"], policy["id"], [create["id"]])

    def test_admin_list_keys_masked(self, client):
        policy, profile = create_test_profile_with_policy(client, "admin-list-mask")
        create = client.post("/api/keys", json={"name": "admin-list-mask-test", "profile_id": profile["id"]}).json()
        response = client.get("/admin/api/keys")
        keys = response.json()
        our_key = next(k for k in keys if k["id"] == create["id"])
        assert "key_value" not in our_key
        assert our_key["key_preview"].startswith("gsk_…")
        cleanup_test_resources(client, profile["id"], policy["id"], [create["id"]])

    def test_admin_get_key_not_found(self, client):
        response = client.get("/admin/api/keys/99999")
        assert response.status_code == 404

    def test_admin_revoke_key(self, client):
        policy, profile = create_test_profile_with_policy(client, "admin-revoke")
        create = client.post("/api/keys", json={"name": "admin-revoke-test", "profile_id": profile["id"]}).json()
        response = client.post(f"/admin/api/keys/{create['id']}/revoke")
        assert response.status_code == 200
        assert response.json()["revoked"] is True
        cleanup_test_resources(client, profile["id"], policy["id"])

    def test_admin_restore_key(self, client):
        policy, profile = create_test_profile_with_policy(client, "admin-restore")
        create = client.post("/api/keys", json={"name": "admin-restore-test", "profile_id": profile["id"]}).json()
        client.post(f"/admin/api/keys/{create['id']}/revoke")
        response = client.post(f"/admin/api/keys/{create['id']}/restore")
        assert response.status_code == 200
        data = response.json()
        assert data["revoked"] is False
        assert data["revoked_at"] is None
        assert data["revoked_by"] is None
        cleanup_test_resources(client, profile["id"], policy["id"], [create["id"]])

    def test_admin_restore_non_revoked_key(self, client):
        policy, profile = create_test_profile_with_policy(client, "restore-fail")
        create = client.post("/api/keys", json={"name": "restore-fail-test", "profile_id": profile["id"]}).json()
        response = client.post(f"/admin/api/keys/{create['id']}/restore")
        assert response.status_code == 400
        cleanup_test_resources(client, profile["id"], policy["id"], [create["id"]])

    def test_admin_restore_expired_key_fails(self, client):
        policy, profile = create_test_profile_with_policy(client, "restore-expired")
        response = client.post("/api/keys", json={"name": "expired-key", "profile_id": profile["id"], "expires_at": "2020-01-01T00:00:00+00:00"})
        assert response.status_code == 201
        key_id = response.json()["id"]
        client.post(f"/admin/api/keys/{key_id}/revoke")
        response = client.post(f"/admin/api/keys/{key_id}/restore")
        assert response.status_code == 400
        assert "expired" in response.json()["error"].lower()
        cleanup_test_resources(client, profile["id"], policy["id"])


class TestApiKeyAdminEdgeCases:
    """Edge cases for admin key management."""

    def test_admin_list_with_both_filters(self, client):
        policy, profile = create_test_profile_with_policy(client, "both-filters")
        create = client.post("/api/keys", json={"name": "both-filters-test", "profile_id": profile["id"]}).json()
        response = client.get(f"/admin/api/keys?user=user3@localhost&profile_id={profile['id']}")
        assert response.status_code == 200
        keys = response.json()
        assert any(k["id"] == create["id"] for k in keys)
        cleanup_test_resources(client, profile["id"], policy["id"], [create["id"]])

    def test_admin_list_user_filter_matches_keys(self, client):
        policy, profile = create_test_profile_with_policy(client, "user-filter")
        create = client.post("/api/keys", json={"name": "user-filter-test", "profile_id": profile["id"]}).json()
        response = client.get("/admin/api/keys?user=user3@localhost")
        keys = response.json()
        assert any(k["id"] == create["id"] for k in keys)
        cleanup_test_resources(client, profile["id"], policy["id"], [create["id"]])

    def test_admin_policy_snapshots_not_found(self, client):
        response = client.get("/admin/api/keys/99999/policies")
        assert response.status_code == 404

    def test_user_policy_snapshots_not_found(self, client):
        response = client.get("/api/keys/99999/policies")
        assert response.status_code == 404

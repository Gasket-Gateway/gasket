"""API key revocation tests."""

from .conftest import create_test_profile_with_policy, cleanup_test_resources


class TestApiKeyRevoke:
    """Verify API key revocation."""

    def test_revoke_own_key(self, client):
        policy, profile = create_test_profile_with_policy(client, "revoke")
        create = client.post("/api/keys", json={"name": "revoke-test", "profile_id": profile["id"]}).json()
        response = client.post(f"/api/keys/{create['id']}/revoke")
        assert response.status_code == 200
        data = response.json()
        assert data["revoked"] is True
        assert data["revoked_at"] is not None
        assert data["revoked_by"] is not None
        cleanup_test_resources(client, profile["id"], policy["id"])

    def test_revoke_already_revoked(self, client):
        policy, profile = create_test_profile_with_policy(client, "double-revoke")
        create = client.post("/api/keys", json={"name": "double-revoke-test", "profile_id": profile["id"]}).json()
        client.post(f"/api/keys/{create['id']}/revoke")
        response = client.post(f"/api/keys/{create['id']}/revoke")
        assert response.status_code == 400
        cleanup_test_resources(client, profile["id"], policy["id"])

    def test_revoke_not_found(self, client):
        response = client.post("/api/keys/99999/revoke")
        assert response.status_code == 404

    def test_revoked_key_doesnt_count_towards_max(self, client):
        policy, profile = create_test_profile_with_policy(client, "revoke-max")
        key_ids = []
        for i in range(3):
            resp = client.post("/api/keys", json={"name": f"revoke-max-{i}", "profile_id": profile["id"]})
            key_ids.append(resp.json()["id"])
        client.post(f"/api/keys/{key_ids[0]}/revoke")
        resp = client.post("/api/keys", json={"name": "revoke-max-replacement", "profile_id": profile["id"]})
        assert resp.status_code == 201
        key_ids.append(resp.json()["id"])
        cleanup_test_resources(client, profile["id"], policy["id"], key_ids[1:])


class TestApiKeyRevokeEdgeCases:
    """Edge cases for revocation and restoration."""

    def test_revoke_records_revoker_email(self, client):
        policy, profile = create_test_profile_with_policy(client, "revoker-email")
        create = client.post("/api/keys", json={"name": "revoker-test", "profile_id": profile["id"]}).json()
        revoke = client.post(f"/api/keys/{create['id']}/revoke")
        assert revoke.json()["revoked_by"] == "user3@localhost"
        cleanup_test_resources(client, profile["id"], policy["id"])

    def test_admin_revoke_records_admin_email(self, client):
        policy, profile = create_test_profile_with_policy(client, "admin-revoker")
        create = client.post("/api/keys", json={"name": "admin-revoker-test", "profile_id": profile["id"]}).json()
        revoke = client.post(f"/admin/api/keys/{create['id']}/revoke")
        assert revoke.json()["revoked_by"] == "user3@localhost"
        cleanup_test_resources(client, profile["id"], policy["id"])

    def test_restore_then_revoke_again(self, client):
        policy, profile = create_test_profile_with_policy(client, "re-revoke")
        create = client.post("/api/keys", json={"name": "re-revoke-test", "profile_id": profile["id"]}).json()
        client.post(f"/admin/api/keys/{create['id']}/revoke")
        client.post(f"/admin/api/keys/{create['id']}/restore")
        revoke2 = client.post(f"/api/keys/{create['id']}/revoke")
        assert revoke2.status_code == 200
        assert revoke2.json()["revoked"] is True
        cleanup_test_resources(client, profile["id"], policy["id"])

    def test_admin_revoke_not_found(self, client):
        response = client.post("/admin/api/keys/99999/revoke")
        assert response.status_code == 400

    def test_admin_restore_not_found(self, client):
        response = client.post("/admin/api/keys/99999/restore")
        assert response.status_code == 400

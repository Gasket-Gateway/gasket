"""RBAC tests — admin API write (POST/PUT/DELETE) endpoint access control.

Verifies that admin API write endpoints are restricted to
users in the gasket-admins group. Admin tests also verify the
operations succeed (create, update, delete).
"""

from .conftest import GASKET_URL

OLLAMA_EXTERNAL_URL = "https://ollama-external.gasket-dev.local"


class TestAdminApiWriteAsAdmin:
    """Admin user can perform write operations via admin API."""

    def test_create_backend(self, admin_client):
        """Admin can create a backend."""
        resp = admin_client.post(
            f"{GASKET_URL}/admin/api/backends",
            json={
                "name": "rbac-test-backend",
                "base_url": OLLAMA_EXTERNAL_URL,
                "skip_tls_verify": True,
            },
        )
        assert resp.status_code == 201
        backend_id = resp.json()["id"]

        # Clean up
        admin_client.delete(f"{GASKET_URL}/admin/api/backends/{backend_id}")

    def test_create_and_update_backend(self, admin_client):
        """Admin can create and update a backend."""
        resp = admin_client.post(
            f"{GASKET_URL}/admin/api/backends",
            json={
                "name": "rbac-test-update",
                "base_url": OLLAMA_EXTERNAL_URL,
                "skip_tls_verify": True,
            },
        )
        assert resp.status_code == 201
        backend_id = resp.json()["id"]

        update_resp = admin_client.put(
            f"{GASKET_URL}/admin/api/backends/{backend_id}",
            json={"name": "rbac-test-updated"},
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["name"] == "rbac-test-updated"

        # Clean up
        admin_client.delete(f"{GASKET_URL}/admin/api/backends/{backend_id}")

    def test_create_and_delete_backend(self, admin_client):
        """Admin can create and delete a backend."""
        resp = admin_client.post(
            f"{GASKET_URL}/admin/api/backends",
            json={
                "name": "rbac-test-delete",
                "base_url": OLLAMA_EXTERNAL_URL,
                "skip_tls_verify": True,
            },
        )
        assert resp.status_code == 201
        backend_id = resp.json()["id"]

        delete_resp = admin_client.delete(
            f"{GASKET_URL}/admin/api/backends/{backend_id}"
        )
        assert delete_resp.status_code == 200

    def test_create_profile(self, admin_client):
        """Admin can create a profile."""
        resp = admin_client.post(
            f"{GASKET_URL}/admin/api/profiles",
            json={"name": "rbac-test-profile"},
        )
        assert resp.status_code == 201
        profile_id = resp.json()["id"]

        # Clean up
        admin_client.delete(f"{GASKET_URL}/admin/api/profiles/{profile_id}")

    def test_create_policy(self, admin_client):
        """Admin can create a policy."""
        resp = admin_client.post(
            f"{GASKET_URL}/admin/api/policies",
            json={"name": "rbac-test-policy", "content": "Test policy content."},
        )
        assert resp.status_code == 201
        policy_id = resp.json()["id"]

        # Clean up
        admin_client.delete(f"{GASKET_URL}/admin/api/policies/{policy_id}")


class TestAdminApiWriteAsUser:
    """Regular user is denied all admin API write operations."""

    def test_create_backend_denied(self, user_client):
        resp = user_client.post(
            f"{GASKET_URL}/admin/api/backends",
            json={"name": "denied-backend", "base_url": "http://example.com"},
        )
        assert resp.status_code == 403

    def test_create_profile_denied(self, user_client):
        resp = user_client.post(
            f"{GASKET_URL}/admin/api/profiles",
            json={"name": "denied-profile"},
        )
        assert resp.status_code == 403

    def test_create_policy_denied(self, user_client):
        resp = user_client.post(
            f"{GASKET_URL}/admin/api/policies",
            json={"name": "denied-policy", "content": "test"},
        )
        assert resp.status_code == 403

    def test_update_backend_denied(self, user_client):
        """Regular user cannot update any backend (even if ID is known)."""
        resp = user_client.put(
            f"{GASKET_URL}/admin/api/backends/1",
            json={"name": "nope"},
        )
        assert resp.status_code == 403

    def test_delete_backend_denied(self, user_client):
        """Regular user cannot delete any backend."""
        resp = user_client.delete(f"{GASKET_URL}/admin/api/backends/1")
        assert resp.status_code == 403

    def test_update_profile_denied(self, user_client):
        resp = user_client.put(
            f"{GASKET_URL}/admin/api/profiles/1",
            json={"name": "nope"},
        )
        assert resp.status_code == 403

    def test_delete_profile_denied(self, user_client):
        resp = user_client.delete(f"{GASKET_URL}/admin/api/profiles/1")
        assert resp.status_code == 403

    def test_update_policy_denied(self, user_client):
        resp = user_client.put(
            f"{GASKET_URL}/admin/api/policies/1",
            json={"name": "nope", "content": "nope"},
        )
        assert resp.status_code == 403

    def test_delete_policy_denied(self, user_client):
        resp = user_client.delete(f"{GASKET_URL}/admin/api/policies/1")
        assert resp.status_code == 403

    def test_admin_revoke_key_denied(self, user_client):
        """Regular user cannot use admin revoke endpoint."""
        resp = user_client.post(f"{GASKET_URL}/admin/api/keys/1/revoke")
        assert resp.status_code == 403

    def test_admin_restore_key_denied(self, user_client):
        """Regular user cannot use admin restore endpoint."""
        resp = user_client.post(f"{GASKET_URL}/admin/api/keys/1/restore")
        assert resp.status_code == 403


class TestAdminApiWriteAsNoGroup:
    """No-group user is denied all admin API write operations."""

    def test_create_backend_denied(self, nogroup_client):
        resp = nogroup_client.post(
            f"{GASKET_URL}/admin/api/backends",
            json={"name": "denied-backend", "base_url": "http://example.com"},
        )
        assert resp.status_code == 403

    def test_create_profile_denied(self, nogroup_client):
        resp = nogroup_client.post(
            f"{GASKET_URL}/admin/api/profiles",
            json={"name": "denied-profile"},
        )
        assert resp.status_code == 403

    def test_create_policy_denied(self, nogroup_client):
        resp = nogroup_client.post(
            f"{GASKET_URL}/admin/api/policies",
            json={"name": "denied-policy", "content": "test"},
        )
        assert resp.status_code == 403

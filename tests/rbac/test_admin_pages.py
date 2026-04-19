"""RBAC tests — admin panel page access control.

Verifies that admin panel pages (/admin/*) are restricted to
users in the gasket-admins group.
"""

from .conftest import GASKET_URL

ADMIN_PAGES = [
    "/admin/status",
    "/admin/backends",
    "/admin/profiles",
    "/admin/keys",
    "/admin/policies",
    "/admin/audit",
    "/admin/usage",
    "/admin/quotas",
]


class TestAdminPagesAsAdmin:
    """Admin user can access all admin pages."""

    def test_admin_redirect(self, admin_client):
        """GET /admin redirects to /admin/status."""
        resp = admin_client.get(f"{GASKET_URL}/admin", allow_redirects=False)
        assert resp.status_code == 302
        assert "/admin/status" in resp.headers.get("Location", "")

    def test_admin_status(self, admin_client):
        resp = admin_client.get(f"{GASKET_URL}/admin/status")
        assert resp.status_code == 200

    def test_admin_backends(self, admin_client):
        resp = admin_client.get(f"{GASKET_URL}/admin/backends")
        assert resp.status_code == 200

    def test_admin_profiles(self, admin_client):
        resp = admin_client.get(f"{GASKET_URL}/admin/profiles")
        assert resp.status_code == 200

    def test_admin_keys(self, admin_client):
        resp = admin_client.get(f"{GASKET_URL}/admin/keys")
        assert resp.status_code == 200

    def test_admin_policies(self, admin_client):
        resp = admin_client.get(f"{GASKET_URL}/admin/policies")
        assert resp.status_code == 200

    def test_admin_audit(self, admin_client):
        resp = admin_client.get(f"{GASKET_URL}/admin/audit")
        assert resp.status_code == 200

    def test_admin_usage(self, admin_client):
        resp = admin_client.get(f"{GASKET_URL}/admin/usage")
        assert resp.status_code == 200

    def test_admin_quotas(self, admin_client):
        resp = admin_client.get(f"{GASKET_URL}/admin/quotas")
        assert resp.status_code == 200


class TestAdminPagesAsUser:
    """Regular user (gasket-users only) is denied all admin pages."""

    def test_admin_redirect_then_denied(self, user_client):
        """GET /admin should ultimately result in 403."""
        resp = user_client.get(f"{GASKET_URL}/admin", allow_redirects=True)
        assert resp.status_code == 403

    def test_admin_status_denied(self, user_client):
        resp = user_client.get(f"{GASKET_URL}/admin/status")
        assert resp.status_code == 403

    def test_admin_backends_denied(self, user_client):
        resp = user_client.get(f"{GASKET_URL}/admin/backends")
        assert resp.status_code == 403

    def test_admin_profiles_denied(self, user_client):
        resp = user_client.get(f"{GASKET_URL}/admin/profiles")
        assert resp.status_code == 403

    def test_admin_keys_denied(self, user_client):
        resp = user_client.get(f"{GASKET_URL}/admin/keys")
        assert resp.status_code == 403

    def test_admin_policies_denied(self, user_client):
        resp = user_client.get(f"{GASKET_URL}/admin/policies")
        assert resp.status_code == 403

    def test_admin_audit_denied(self, user_client):
        resp = user_client.get(f"{GASKET_URL}/admin/audit")
        assert resp.status_code == 403

    def test_admin_usage_denied(self, user_client):
        resp = user_client.get(f"{GASKET_URL}/admin/usage")
        assert resp.status_code == 403

    def test_admin_quotas_denied(self, user_client):
        resp = user_client.get(f"{GASKET_URL}/admin/quotas")
        assert resp.status_code == 403


class TestAdminPagesAsNoGroup:
    """User without gasket groups is denied all admin pages."""

    def test_admin_status_denied(self, nogroup_client):
        resp = nogroup_client.get(f"{GASKET_URL}/admin/status")
        assert resp.status_code == 403

    def test_admin_backends_denied(self, nogroup_client):
        resp = nogroup_client.get(f"{GASKET_URL}/admin/backends")
        assert resp.status_code == 403

    def test_admin_profiles_denied(self, nogroup_client):
        resp = nogroup_client.get(f"{GASKET_URL}/admin/profiles")
        assert resp.status_code == 403

    def test_admin_keys_denied(self, nogroup_client):
        resp = nogroup_client.get(f"{GASKET_URL}/admin/keys")
        assert resp.status_code == 403

    def test_admin_policies_denied(self, nogroup_client):
        resp = nogroup_client.get(f"{GASKET_URL}/admin/policies")
        assert resp.status_code == 403


class TestAdminPagesAsAnon:
    """Unauthenticated user is redirected to login for all admin pages."""

    def test_admin_redirects_to_login(self, anon_client):
        resp = anon_client.get(f"{GASKET_URL}/admin", allow_redirects=False)
        assert resp.status_code == 302
        assert "login" in resp.headers.get("Location", "").lower()

    def test_admin_status_redirects_to_login(self, anon_client):
        resp = anon_client.get(f"{GASKET_URL}/admin/status", allow_redirects=False)
        assert resp.status_code == 302
        assert "login" in resp.headers.get("Location", "").lower()

    def test_admin_backends_redirects_to_login(self, anon_client):
        resp = anon_client.get(f"{GASKET_URL}/admin/backends", allow_redirects=False)
        assert resp.status_code == 302
        assert "login" in resp.headers.get("Location", "").lower()

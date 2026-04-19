"""RBAC tests — admin API read (GET) endpoint access control.

Verifies that admin API GET endpoints are restricted to
users in the gasket-admins group.
"""

from .conftest import GASKET_URL


class TestAdminApiReadAsAdmin:
    """Admin user can access all admin API read endpoints."""

    def test_status_api(self, admin_client):
        """Admin can access the status API."""
        resp = admin_client.get(f"{GASKET_URL}/admin/api/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "postgresql" in data

    def test_backends_api(self, admin_client):
        """Admin can list backends."""
        resp = admin_client.get(f"{GASKET_URL}/admin/api/backends")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_profiles_api(self, admin_client):
        """Admin can list profiles."""
        resp = admin_client.get(f"{GASKET_URL}/admin/api/profiles")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_policies_api(self, admin_client):
        """Admin can list policies."""
        resp = admin_client.get(f"{GASKET_URL}/admin/api/policies")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_keys_api(self, admin_client):
        """Admin can list all API keys."""
        resp = admin_client.get(f"{GASKET_URL}/admin/api/keys")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_acceptances_api(self, admin_client):
        """Admin can list all policy acceptances."""
        resp = admin_client.get(f"{GASKET_URL}/admin/api/policies/acceptances")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestAdminApiReadAsUser:
    """Regular user is denied all admin API read endpoints."""

    def test_status_api_denied(self, user_client):
        resp = user_client.get(f"{GASKET_URL}/admin/api/status")
        assert resp.status_code == 403

    def test_backends_api_denied(self, user_client):
        resp = user_client.get(f"{GASKET_URL}/admin/api/backends")
        assert resp.status_code == 403

    def test_profiles_api_denied(self, user_client):
        resp = user_client.get(f"{GASKET_URL}/admin/api/profiles")
        assert resp.status_code == 403

    def test_policies_api_denied(self, user_client):
        resp = user_client.get(f"{GASKET_URL}/admin/api/policies")
        assert resp.status_code == 403

    def test_keys_api_denied(self, user_client):
        resp = user_client.get(f"{GASKET_URL}/admin/api/keys")
        assert resp.status_code == 403

    def test_acceptances_api_denied(self, user_client):
        resp = user_client.get(f"{GASKET_URL}/admin/api/policies/acceptances")
        assert resp.status_code == 403


class TestAdminApiReadAsNoGroup:
    """No-group user is denied all admin API read endpoints."""

    def test_status_api_denied(self, nogroup_client):
        resp = nogroup_client.get(f"{GASKET_URL}/admin/api/status")
        assert resp.status_code == 403

    def test_backends_api_denied(self, nogroup_client):
        resp = nogroup_client.get(f"{GASKET_URL}/admin/api/backends")
        assert resp.status_code == 403

    def test_profiles_api_denied(self, nogroup_client):
        resp = nogroup_client.get(f"{GASKET_URL}/admin/api/profiles")
        assert resp.status_code == 403

    def test_policies_api_denied(self, nogroup_client):
        resp = nogroup_client.get(f"{GASKET_URL}/admin/api/policies")
        assert resp.status_code == 403

    def test_keys_api_denied(self, nogroup_client):
        resp = nogroup_client.get(f"{GASKET_URL}/admin/api/keys")
        assert resp.status_code == 403


class TestAdminApiReadAsAnon:
    """Unauthenticated user is redirected to login for admin API endpoints."""

    def test_status_api_redirects(self, anon_client):
        resp = anon_client.get(f"{GASKET_URL}/admin/api/status", allow_redirects=False)
        assert resp.status_code == 302

    def test_backends_api_redirects(self, anon_client):
        resp = anon_client.get(f"{GASKET_URL}/admin/api/backends", allow_redirects=False)
        assert resp.status_code == 302

    def test_profiles_api_redirects(self, anon_client):
        resp = anon_client.get(f"{GASKET_URL}/admin/api/profiles", allow_redirects=False)
        assert resp.status_code == 302

    def test_policies_api_redirects(self, anon_client):
        resp = anon_client.get(f"{GASKET_URL}/admin/api/policies", allow_redirects=False)
        assert resp.status_code == 302

    def test_keys_api_redirects(self, anon_client):
        resp = anon_client.get(f"{GASKET_URL}/admin/api/keys", allow_redirects=False)
        assert resp.status_code == 302

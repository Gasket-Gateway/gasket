"""RBAC tests — portal page and user API access control.

Verifies that portal pages (/, /keys) and user-facing API endpoints
(/api/profiles, /api/keys) respect group-based access control.
"""

from .conftest import GASKET_URL


class TestAdminPortalAccess:
    """Admin user (gasket-users + gasket-admins) can access all portal pages."""

    def test_portal_page(self, admin_client):
        """Admin can access the portal page."""
        resp = admin_client.get(f"{GASKET_URL}/")
        assert resp.status_code == 200

    def test_keys_page(self, admin_client):
        """Admin can access the keys page."""
        resp = admin_client.get(f"{GASKET_URL}/keys")
        assert resp.status_code == 200

    def test_profiles_api(self, admin_client):
        """Admin can list profiles via portal API."""
        resp = admin_client.get(f"{GASKET_URL}/api/profiles")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_keys_api(self, admin_client):
        """Admin can list their own keys via portal API."""
        resp = admin_client.get(f"{GASKET_URL}/api/keys")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestUserPortalAccess:
    """Regular user (gasket-users only) can access all portal pages."""

    def test_portal_page(self, user_client):
        """Regular user can access the portal page."""
        resp = user_client.get(f"{GASKET_URL}/")
        assert resp.status_code == 200

    def test_keys_page(self, user_client):
        """Regular user can access the keys page."""
        resp = user_client.get(f"{GASKET_URL}/keys")
        assert resp.status_code == 200

    def test_profiles_api(self, user_client):
        """Regular user can list profiles via portal API."""
        resp = user_client.get(f"{GASKET_URL}/api/profiles")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_keys_api(self, user_client):
        """Regular user can list their own keys via portal API."""
        resp = user_client.get(f"{GASKET_URL}/api/keys")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestNoGroupPortalAccess:
    """User without gasket-users group is denied all portal pages."""

    def test_portal_page_denied(self, nogroup_client):
        """No-group user gets 403 on the portal page."""
        resp = nogroup_client.get(f"{GASKET_URL}/", allow_redirects=False)
        assert resp.status_code == 403

    def test_keys_page_denied(self, nogroup_client):
        """No-group user gets 403 on the keys page."""
        resp = nogroup_client.get(f"{GASKET_URL}/keys", allow_redirects=False)
        assert resp.status_code == 403

    def test_profiles_api_denied(self, nogroup_client):
        """No-group user gets 403 on portal profiles API."""
        resp = nogroup_client.get(f"{GASKET_URL}/api/profiles")
        assert resp.status_code == 403

    def test_keys_api_denied(self, nogroup_client):
        """No-group user gets 403 on portal keys API."""
        resp = nogroup_client.get(f"{GASKET_URL}/api/keys")
        assert resp.status_code == 403


class TestAnonPortalAccess:
    """Unauthenticated user is redirected to login for all portal pages."""

    def test_portal_redirects_to_login(self, anon_client):
        """Anon user is redirected to login from portal."""
        resp = anon_client.get(f"{GASKET_URL}/", allow_redirects=False)
        assert resp.status_code == 302
        assert "login" in resp.headers.get("Location", "").lower()

    def test_keys_redirects_to_login(self, anon_client):
        """Anon user is redirected to login from keys page."""
        resp = anon_client.get(f"{GASKET_URL}/keys", allow_redirects=False)
        assert resp.status_code == 302
        assert "login" in resp.headers.get("Location", "").lower()

    def test_profiles_api_redirects_to_login(self, anon_client):
        """Anon user is redirected to login from profiles API."""
        resp = anon_client.get(f"{GASKET_URL}/api/profiles", allow_redirects=False)
        assert resp.status_code == 302
        assert "login" in resp.headers.get("Location", "").lower()

    def test_keys_api_redirects_to_login(self, anon_client):
        """Anon user is redirected to login from keys API."""
        resp = anon_client.get(f"{GASKET_URL}/api/keys", allow_redirects=False)
        assert resp.status_code == 302
        assert "login" in resp.headers.get("Location", "").lower()

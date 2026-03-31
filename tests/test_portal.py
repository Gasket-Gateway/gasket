"""Portal and admin panel tests — run against the Gasket test environment (GASKET_TEST_MODE)."""


class TestPortalAccess:
    """Verify portal pages are accessible in test mode."""

    def test_portal_loads(self, client):
        """Portal page should return 200 for the test user."""
        response = client.get("/")
        assert response.status_code == 200

    def test_portal_contains_user_name(self, client):
        """Portal should display the test user's name."""
        response = client.get("/")
        assert "user3" in response.text

    def test_keys_page_loads(self, client):
        """API Keys page should return 200."""
        response = client.get("/keys")
        assert response.status_code == 200


class TestAdminPanel:
    """Verify admin panel access in test mode (user3 is an admin)."""

    def test_admin_redirects_to_status(self, client):
        """GET /admin should redirect to /admin/status."""
        response = client.get("/admin", allow_redirects=False)
        assert response.status_code == 302

    def test_admin_status_loads(self, client):
        """Admin status page should return 200."""
        response = client.get("/admin/status")
        assert response.status_code == 200

    def test_admin_status_contains_connection_status(self, client):
        """Admin status page should contain connection status section."""
        response = client.get("/admin/status")
        assert "Connection Status" in response.text or "connection-status" in response.text

    def test_admin_backends_loads(self, client):
        """Admin backends page should return 200."""
        response = client.get("/admin/backends")
        assert response.status_code == 200

    def test_admin_profiles_loads(self, client):
        """Admin profiles page should return 200."""
        response = client.get("/admin/profiles")
        assert response.status_code == 200

    def test_admin_keys_loads(self, client):
        """Admin keys page should return 200."""
        response = client.get("/admin/keys")
        assert response.status_code == 200

    def test_admin_policies_loads(self, client):
        """Admin policies page should return 200."""
        response = client.get("/admin/policies")
        assert response.status_code == 200


class TestUiDemo:
    """Verify UI demo page."""

    def test_ui_demo_loads(self, client):
        """UI demo page should return 200."""
        response = client.get("/ui-demo")
        assert response.status_code == 200

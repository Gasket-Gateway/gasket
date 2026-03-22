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


class TestAdminPanel:
    """Verify admin panel access in test mode (user3 is an admin)."""

    def test_admin_loads(self, client):
        """Admin panel should return 200 for the admin test user."""
        response = client.get("/admin")
        assert response.status_code == 200

    def test_admin_contains_connection_status(self, client):
        """Admin panel should contain connection status section."""
        response = client.get("/admin")
        assert "Connection Status" in response.text or "connection-status" in response.text


class TestUiDemo:
    """Verify UI demo page."""

    def test_ui_demo_loads(self, client):
        """UI demo page should return 200."""
        response = client.get("/ui-demo")
        assert response.status_code == 200

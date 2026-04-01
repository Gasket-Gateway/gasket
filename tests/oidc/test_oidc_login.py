"""OIDC login flow tests — requires a running dev environment with Authentik ROPC enabled."""

import time

import pytest
import requests

from .conftest import fetch_ropc_token, authentik_login, GASKET_URL


# ─── ROPC Token Tests ─────────────────────────────────────────────


class TestROPCTokenExchange:
    """Validate ROPC grant works for each test user."""

    def test_user2_gets_tokens(self, user2_token):
        """user2 (gasket-users) should receive valid tokens."""
        assert "access_token" in user2_token
        assert "id_token" in user2_token

    def test_user3_gets_tokens(self, user3_token):
        """user3 (gasket-users + gasket-admins) should receive valid tokens."""
        assert "access_token" in user3_token
        assert "id_token" in user3_token

    def test_user1_denied(self):
        """user1 (not in gasket-users) should be denied ROPC tokens.

        Authentik may return tokens but the app should reject at login,
        or Authentik may deny the grant if the user isn't bound to the app.
        """
        resp = fetch_ropc_token("user1", "password")
        # Authentik should deny since user1 is not bound to the gasket-gateway app
        assert resp.status_code in (400, 403), (
            f"Expected user1 to be denied, got {resp.status_code}: {resp.text}"
        )

    def test_invalid_password_denied(self):
        """Invalid credentials should be rejected."""
        resp = fetch_ropc_token("user2", "wrong-password")
        assert resp.status_code in (400, 401, 403), (
            f"Expected rejection, got {resp.status_code}"
        )


# ─── Portal Access Tests ──────────────────────────────────────────


class TestPortalAccess:
    """Validate portal access control via browser."""

    def test_unauthenticated_redirect(self, browser, gasket_url):
        """Unauthenticated users should be redirected to the login page."""
        browser.delete_all_cookies()
        browser.get(f"{gasket_url}/")
        time.sleep(2)
        # Should end up on the login page (either Gasket's or Authentik's)
        assert any(
            keyword in browser.current_url.lower()
            for keyword in ["login", "auth", "authentik"]
        ), f"Expected redirect to login, got: {browser.current_url}"

    def test_authenticated_portal_access(self, browser, gasket_url, user2_token):
        """user2 should be able to access the portal after OIDC login."""
        authentik_login(browser, gasket_url, "user2", "password")
        assert "gasket" in browser.current_url.lower(), (
            f"Expected portal page, got: {browser.current_url}"
        )

    def test_admin_panel_access(self, browser, gasket_url):
        """user3 (admin) should have access to the admin panel."""
        authentik_login(browser, gasket_url, "user3", "password")
        browser.get(f"{gasket_url}/admin")
        time.sleep(1)
        assert "/admin" in browser.current_url or "Admin" in browser.page_source, (
            f"Expected admin panel access, got: {browser.current_url}"
        )


# ─── Health Check Tests (against live environment) ────────────────


class TestLiveHealth:
    """Basic smoke tests against the running environment."""

    def test_health_endpoint(self, gasket_url):
        """Health endpoint should return 200."""
        resp = requests.get(f"{gasket_url}/health", verify=False)
        assert resp.status_code == 200

    def test_login_page_accessible(self, gasket_url):
        """Login page should be accessible without auth."""
        resp = requests.get(f"{gasket_url}/", verify=False, allow_redirects=True)
        assert resp.status_code == 200

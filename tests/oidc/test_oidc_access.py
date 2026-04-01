"""OIDC access control tests — validates user/group permission boundaries.

Tests exercise the full access control matrix:
- Unauthenticated → redirect to login
- user2 (gasket-users) → portal access, admin denied
- user3 (gasket-users + gasket-admins) → portal + admin access

Requires a running dev environment with Authentik provisioned.
"""

import pytest

from .conftest import GASKET_URL


# ─── Unauthenticated Access ──────────────────────────────────────


class TestUnauthenticatedAccess:
    """Unauthenticated requests should redirect to login for protected pages."""

    def test_portal_redirects_to_login(self, anon_session, gasket_url):
        """GET / without a session should redirect to the login page."""
        resp = anon_session.get(f"{gasket_url}/", allow_redirects=True)
        assert resp.status_code == 200  # Final page after redirect
        assert any(
            keyword in resp.url.lower()
            for keyword in ["login", "auth", "authentik"]
        ), f"Expected redirect to login, got: {resp.url}"

    def test_keys_page_redirects_to_login(self, anon_session, gasket_url):
        """GET /keys without a session should redirect to login."""
        resp = anon_session.get(f"{gasket_url}/keys", allow_redirects=True)
        assert any(
            keyword in resp.url.lower()
            for keyword in ["login", "auth", "authentik"]
        ), f"Expected redirect to login, got: {resp.url}"

    def test_admin_redirects_to_login(self, anon_session, gasket_url):
        """GET /admin without a session should redirect to login."""
        resp = anon_session.get(f"{gasket_url}/admin", allow_redirects=True)
        assert any(
            keyword in resp.url.lower()
            for keyword in ["login", "auth", "authentik"]
        ), f"Expected redirect to login, got: {resp.url}"

    def test_admin_status_api_redirects_to_login(self, anon_session, gasket_url):
        """GET /admin/api/status without a session should redirect to login."""
        resp = anon_session.get(f"{gasket_url}/admin/api/status", allow_redirects=True)
        assert any(
            keyword in resp.url.lower()
            for keyword in ["login", "auth", "authentik"]
        ), f"Expected redirect to login, got: {resp.url}"

    def test_admin_backends_api_redirects_to_login(self, anon_session, gasket_url):
        """GET /admin/api/backends without a session should redirect to login."""
        resp = anon_session.get(f"{gasket_url}/admin/api/backends", allow_redirects=True)
        assert any(
            keyword in resp.url.lower()
            for keyword in ["login", "auth", "authentik"]
        ), f"Expected redirect to login, got: {resp.url}"

    def test_admin_profiles_api_redirects_to_login(self, anon_session, gasket_url):
        """GET /admin/api/profiles without a session should redirect to login."""
        resp = anon_session.get(f"{gasket_url}/admin/api/profiles", allow_redirects=True)
        assert any(
            keyword in resp.url.lower()
            for keyword in ["login", "auth", "authentik"]
        ), f"Expected redirect to login, got: {resp.url}"

    def test_admin_policies_api_redirects_to_login(self, anon_session, gasket_url):
        """GET /admin/api/policies without a session should redirect to login."""
        resp = anon_session.get(f"{gasket_url}/admin/api/policies", allow_redirects=True)
        assert any(
            keyword in resp.url.lower()
            for keyword in ["login", "auth", "authentik"]
        ), f"Expected redirect to login, got: {resp.url}"

    def test_admin_keys_api_redirects_to_login(self, anon_session, gasket_url):
        """GET /admin/api/keys without a session should redirect to login."""
        resp = anon_session.get(f"{gasket_url}/admin/api/keys", allow_redirects=True)
        assert any(
            keyword in resp.url.lower()
            for keyword in ["login", "auth", "authentik"]
        ), f"Expected redirect to login, got: {resp.url}"

    def test_user_keys_api_redirects_to_login(self, anon_session, gasket_url):
        """GET /api/keys without a session should redirect to login."""
        resp = anon_session.get(f"{gasket_url}/api/keys", allow_redirects=True)
        assert any(
            keyword in resp.url.lower()
            for keyword in ["login", "auth", "authentik"]
        ), f"Expected redirect to login, got: {resp.url}"


# ─── User2 Access (gasket-users only) ────────────────────────────


class TestUser2PortalAccess:
    """user2 is in gasket-users but NOT gasket-admins.

    Should have full portal access but be denied all admin endpoints.
    """

    # ── Portal pages (allowed) ────────────────────────────────────

    def test_portal_page_accessible(self, user2_session, gasket_url):
        """user2 can access the main portal page."""
        resp = user2_session.get(f"{gasket_url}/", allow_redirects=True)
        assert resp.status_code == 200
        # Should NOT be redirected to login
        assert "login" not in resp.url.lower() or "auth/login" not in resp.url.lower()

    def test_keys_page_accessible(self, user2_session, gasket_url):
        """user2 can access the API keys page."""
        resp = user2_session.get(f"{gasket_url}/keys", allow_redirects=True)
        assert resp.status_code == 200

    # ── User API endpoints (allowed) ──────────────────────────────

    def test_user_keys_api_accessible(self, user2_session, gasket_url):
        """user2 can list their own API keys."""
        resp = user2_session.get(f"{gasket_url}/api/keys")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    # ── Admin pages (denied — 403) ────────────────────────────────

    def test_admin_page_denied(self, user2_session, gasket_url):
        """user2 should be denied access to the admin panel."""
        resp = user2_session.get(f"{gasket_url}/admin", allow_redirects=False)
        # Admin page first redirects to /admin/status (302), then
        # /admin/status checks groups. With allow_redirects=True the final
        # response should be 403.
        resp = user2_session.get(f"{gasket_url}/admin", allow_redirects=True)
        assert resp.status_code == 403, (
            f"Expected 403 for admin page, got {resp.status_code} at {resp.url}"
        )

    def test_admin_status_page_denied(self, user2_session, gasket_url):
        """user2 should be denied access to admin status page."""
        resp = user2_session.get(f"{gasket_url}/admin/status")
        assert resp.status_code == 403

    def test_admin_backends_page_denied(self, user2_session, gasket_url):
        """user2 should be denied access to admin backends page."""
        resp = user2_session.get(f"{gasket_url}/admin/backends")
        assert resp.status_code == 403

    def test_admin_profiles_page_denied(self, user2_session, gasket_url):
        """user2 should be denied access to admin profiles page."""
        resp = user2_session.get(f"{gasket_url}/admin/profiles")
        assert resp.status_code == 403

    def test_admin_keys_page_denied(self, user2_session, gasket_url):
        """user2 should be denied access to admin keys page."""
        resp = user2_session.get(f"{gasket_url}/admin/keys")
        assert resp.status_code == 403

    def test_admin_policies_page_denied(self, user2_session, gasket_url):
        """user2 should be denied access to admin policies page."""
        resp = user2_session.get(f"{gasket_url}/admin/policies")
        assert resp.status_code == 403

    # ── Admin API endpoints (denied — 403) ────────────────────────

    def test_admin_status_api_denied(self, user2_session, gasket_url):
        """user2 should be denied the admin status API."""
        resp = user2_session.get(f"{gasket_url}/admin/api/status")
        assert resp.status_code == 403

    def test_admin_backends_api_denied(self, user2_session, gasket_url):
        """user2 should be denied the admin backends API."""
        resp = user2_session.get(f"{gasket_url}/admin/api/backends")
        assert resp.status_code == 403

    def test_admin_profiles_api_denied(self, user2_session, gasket_url):
        """user2 should be denied the admin profiles API."""
        resp = user2_session.get(f"{gasket_url}/admin/api/profiles")
        assert resp.status_code == 403

    def test_admin_keys_api_denied(self, user2_session, gasket_url):
        """user2 should be denied the admin keys API."""
        resp = user2_session.get(f"{gasket_url}/admin/api/keys")
        assert resp.status_code == 403

    def test_admin_policies_api_denied(self, user2_session, gasket_url):
        """user2 should be denied the admin policies API."""
        resp = user2_session.get(f"{gasket_url}/admin/api/policies")
        assert resp.status_code == 403

    # ── Admin write operations (denied — 403) ─────────────────────

    def test_admin_create_backend_denied(self, user2_session, gasket_url):
        """user2 should not be able to create backends via admin API."""
        resp = user2_session.post(
            f"{gasket_url}/admin/api/backends",
            json={"name": "test-denied", "base_url": "http://example.com"},
        )
        assert resp.status_code == 403

    def test_admin_create_profile_denied(self, user2_session, gasket_url):
        """user2 should not be able to create profiles via admin API."""
        resp = user2_session.post(
            f"{gasket_url}/admin/api/profiles",
            json={"name": "test-denied"},
        )
        assert resp.status_code == 403

    def test_admin_create_policy_denied(self, user2_session, gasket_url):
        """user2 should not be able to create policies via admin API."""
        resp = user2_session.post(
            f"{gasket_url}/admin/api/policies",
            json={"name": "test-denied", "content": "test"},
        )
        assert resp.status_code == 403

    def test_admin_acceptances_list_denied(self, user2_session, gasket_url):
        """user2 should not be able to list all policy acceptances (admin-only)."""
        resp = user2_session.get(f"{gasket_url}/admin/api/policies/acceptances")
        assert resp.status_code == 403


# ─── User3 Access (gasket-admins) ────────────────────────────────


class TestUser3AdminAccess:
    """user3 is in gasket-users AND gasket-admins.

    Should have full portal and admin access.
    """

    # ── Portal pages (allowed) ────────────────────────────────────

    def test_portal_page_accessible(self, user3_session, gasket_url):
        """user3 can access the main portal page."""
        resp = user3_session.get(f"{gasket_url}/", allow_redirects=True)
        assert resp.status_code == 200

    def test_keys_page_accessible(self, user3_session, gasket_url):
        """user3 can access the API keys page."""
        resp = user3_session.get(f"{gasket_url}/keys", allow_redirects=True)
        assert resp.status_code == 200

    # ── User API endpoints (allowed) ──────────────────────────────

    def test_user_keys_api_accessible(self, user3_session, gasket_url):
        """user3 can list their own API keys."""
        resp = user3_session.get(f"{gasket_url}/api/keys")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    # ── Admin pages (allowed) ─────────────────────────────────────

    def test_admin_page_accessible(self, user3_session, gasket_url):
        """user3 can access the admin panel (redirects to /admin/status)."""
        resp = user3_session.get(f"{gasket_url}/admin", allow_redirects=True)
        assert resp.status_code == 200
        assert "admin" in resp.url.lower()

    def test_admin_status_page_accessible(self, user3_session, gasket_url):
        """user3 can access the admin status page."""
        resp = user3_session.get(f"{gasket_url}/admin/status")
        assert resp.status_code == 200

    def test_admin_backends_page_accessible(self, user3_session, gasket_url):
        """user3 can access the admin backends page."""
        resp = user3_session.get(f"{gasket_url}/admin/backends")
        assert resp.status_code == 200

    def test_admin_profiles_page_accessible(self, user3_session, gasket_url):
        """user3 can access the admin profiles page."""
        resp = user3_session.get(f"{gasket_url}/admin/profiles")
        assert resp.status_code == 200

    def test_admin_keys_page_accessible(self, user3_session, gasket_url):
        """user3 can access the admin keys page."""
        resp = user3_session.get(f"{gasket_url}/admin/keys")
        assert resp.status_code == 200

    def test_admin_policies_page_accessible(self, user3_session, gasket_url):
        """user3 can access the admin policies page."""
        resp = user3_session.get(f"{gasket_url}/admin/policies")
        assert resp.status_code == 200

    # ── Admin API endpoints (allowed) ─────────────────────────────

    def test_admin_status_api_accessible(self, user3_session, gasket_url):
        """user3 can access the admin status API."""
        resp = user3_session.get(f"{gasket_url}/admin/api/status")
        assert resp.status_code == 200
        data = resp.json()
        # Should contain at least postgresql and oidc checks
        assert "postgresql" in data
        assert "oidc" in data

    def test_admin_backends_api_accessible(self, user3_session, gasket_url):
        """user3 can list backends via admin API."""
        resp = user3_session.get(f"{gasket_url}/admin/api/backends")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_admin_profiles_api_accessible(self, user3_session, gasket_url):
        """user3 can list profiles via admin API."""
        resp = user3_session.get(f"{gasket_url}/admin/api/profiles")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_admin_keys_api_accessible(self, user3_session, gasket_url):
        """user3 can list all API keys via admin API."""
        resp = user3_session.get(f"{gasket_url}/admin/api/keys")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_admin_policies_api_accessible(self, user3_session, gasket_url):
        """user3 can list policies via admin API."""
        resp = user3_session.get(f"{gasket_url}/admin/api/policies")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_admin_acceptances_api_accessible(self, user3_session, gasket_url):
        """user3 can list all policy acceptances via admin API."""
        resp = user3_session.get(f"{gasket_url}/admin/api/policies/acceptances")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)


# ─── Policy Acceptance Access ─────────────────────────────────────


class TestPolicyAcceptanceAccess:
    """Validate policy acceptance endpoints respect group boundaries."""

    def test_user2_can_view_own_acceptances(self, user2_session, gasket_url):
        """user2 can view their own policy acceptances."""
        resp = user2_session.get(f"{gasket_url}/admin/api/policies/my-acceptances")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_user2_cannot_view_all_acceptances(self, user2_session, gasket_url):
        """user2 should be denied viewing all acceptances (admin-only)."""
        resp = user2_session.get(f"{gasket_url}/admin/api/policies/acceptances")
        assert resp.status_code == 403

    def test_user3_can_view_all_acceptances(self, user3_session, gasket_url):
        """user3 (admin) can view all policy acceptances."""
        resp = user3_session.get(f"{gasket_url}/admin/api/policies/acceptances")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_user3_can_view_own_acceptances(self, user3_session, gasket_url):
        """user3 can also view their own acceptances."""
        resp = user3_session.get(f"{gasket_url}/admin/api/policies/my-acceptances")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

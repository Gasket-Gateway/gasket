"""OIDC portal tests — validates user-facing profile/policy endpoints and portal UI.

Tests exercise:
- User-facing /api/profiles endpoint (group-filtered profile visibility)
- User-facing /api/policies/<id> endpoint (policy read access)
- Portal page rendering with real OIDC sessions (browser-level)
- Access control: unauthenticated users get no data, users only see
  profiles matching their OIDC groups

Requires a running dev environment with Authentik provisioned.
"""

import time

import pytest

from .conftest import GASKET_URL, authentik_login


# ─── User-Facing Profiles API ─────────────────────────────────────


class TestUserProfilesApi:
    """Validate the /api/profiles endpoint returns group-filtered profiles.

    user2 (gasket-users) should see profiles scoped to gasket-users.
    user3 (gasket-users + gasket-admins) should also see those profiles.
    Neither should see profiles scoped to groups they're not in.
    """

    def test_user2_can_list_own_profiles(self, user2_session, gasket_url):
        """user2 can access the user-facing profiles endpoint."""
        resp = user2_session.get(f"{gasket_url}/api/profiles")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_user2_sees_internal_standard(self, user2_session, gasket_url):
        """user2 (gasket-users) should see the internal-standard profile."""
        resp = user2_session.get(f"{gasket_url}/api/profiles")
        assert resp.status_code == 200
        profiles = resp.json()
        names = [p["name"] for p in profiles]
        assert "internal-standard" in names, (
            f"Expected 'internal-standard' in user2's profiles, got: {names}"
        )

    def test_user2_profile_has_expected_fields(self, user2_session, gasket_url):
        """User-facing profiles should include all fields needed by the portal UI."""
        resp = user2_session.get(f"{gasket_url}/api/profiles")
        assert resp.status_code == 200
        profiles = resp.json()
        profile = next(p for p in profiles if p["name"] == "internal-standard")

        expected_fields = [
            "id", "name", "description", "oidc_groups", "source",
            "metadata_audit", "content_audit", "max_keys_per_user",
            "backend_ids", "backend_names", "policy_ids", "policy_names",
        ]
        for field in expected_fields:
            assert field in profile, f"Missing field '{field}' in user profile response"

    def test_user2_profile_has_correct_group(self, user2_session, gasket_url):
        """The internal-standard profile should list gasket-users in oidc_groups."""
        resp = user2_session.get(f"{gasket_url}/api/profiles")
        assert resp.status_code == 200
        profiles = resp.json()
        profile = next(p for p in profiles if p["name"] == "internal-standard")
        assert "gasket-users" in profile["oidc_groups"]

    def test_user2_profile_has_backend(self, user2_session, gasket_url):
        """User-facing profile should include backend names."""
        resp = user2_session.get(f"{gasket_url}/api/profiles")
        assert resp.status_code == 200
        profiles = resp.json()
        profile = next(p for p in profiles if p["name"] == "internal-standard")
        assert "ollama-internal" in profile.get("backend_names", [])

    def test_user2_profile_has_policy(self, user2_session, gasket_url):
        """User-facing profile should include policy names."""
        resp = user2_session.get(f"{gasket_url}/api/profiles")
        assert resp.status_code == 200
        profiles = resp.json()
        profile = next(p for p in profiles if p["name"] == "internal-standard")
        assert "acceptable-use" in profile.get("policy_names", [])

    def test_user3_can_list_own_profiles(self, user3_session, gasket_url):
        """user3 can also access the user-facing profiles endpoint."""
        resp = user3_session.get(f"{gasket_url}/api/profiles")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_user3_sees_internal_standard(self, user3_session, gasket_url):
        """user3 (gasket-users + gasket-admins) should also see internal-standard."""
        resp = user3_session.get(f"{gasket_url}/api/profiles")
        assert resp.status_code == 200
        profiles = resp.json()
        names = [p["name"] for p in profiles]
        assert "internal-standard" in names

    def test_unauthenticated_profiles_denied(self, anon_session, gasket_url):
        """Unauthenticated requests to /api/profiles should redirect to login."""
        resp = anon_session.get(f"{gasket_url}/api/profiles", allow_redirects=True)
        assert any(
            keyword in resp.url.lower()
            for keyword in ["login", "auth", "authentik"]
        ), f"Expected redirect to login, got: {resp.url}"


# ─── User-Facing Policy API ──────────────────────────────────────


class TestUserPolicyApi:
    """Validate the /api/policies/<id> endpoint for regular users.

    Users need to read policy content to review before accepting.
    This endpoint should be accessible to any authenticated gasket-users member.
    """

    def _get_policy_id(self, user2_session, gasket_url):
        """Helper: get a policy ID from the user's profile."""
        resp = user2_session.get(f"{gasket_url}/api/profiles")
        profiles = resp.json()
        profile = next(p for p in profiles if p["name"] == "internal-standard")
        policy_ids = profile.get("policy_ids", [])
        assert len(policy_ids) > 0, "No policies found on internal-standard profile"
        return policy_ids[0]

    def test_user2_can_read_policy(self, user2_session, gasket_url):
        """user2 can read a policy's details via the user-facing endpoint."""
        policy_id = self._get_policy_id(user2_session, gasket_url)
        resp = user2_session.get(f"{gasket_url}/api/policies/{policy_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "name" in data
        assert "current_content" in data

    def test_user2_policy_has_content(self, user2_session, gasket_url):
        """The policy should have actual content for the user to review."""
        policy_id = self._get_policy_id(user2_session, gasket_url)
        resp = user2_session.get(f"{gasket_url}/api/policies/{policy_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "acceptable-use"
        assert data.get("current_content"), "Policy should have content"
        assert data.get("current_version") is not None

    def test_user2_policy_nonexistent_returns_404(self, user2_session, gasket_url):
        """Requesting a non-existent policy ID should return 404."""
        resp = user2_session.get(f"{gasket_url}/api/policies/99999")
        assert resp.status_code == 404

    def test_user3_can_read_policy(self, user3_session, gasket_url):
        """user3 can also read policies via the user-facing endpoint."""
        # Get policy ID via user3's profiles
        resp = user3_session.get(f"{gasket_url}/api/profiles")
        profiles = resp.json()
        profile = next(p for p in profiles if p["name"] == "internal-standard")
        policy_id = profile["policy_ids"][0]

        resp = user3_session.get(f"{gasket_url}/api/policies/{policy_id}")
        assert resp.status_code == 200

    def test_unauthenticated_policy_denied(self, anon_session, gasket_url):
        """Unauthenticated requests to /api/policies/<id> should redirect to login."""
        resp = anon_session.get(f"{gasket_url}/api/policies/1", allow_redirects=True)
        assert any(
            keyword in resp.url.lower()
            for keyword in ["login", "auth", "authentik"]
        ), f"Expected redirect to login, got: {resp.url}"


# ─── Portal UI Rendering ─────────────────────────────────────────


class TestPortalProfileRendering:
    """Validate the portal page renders profile cards in the browser.

    These are browser-level tests that verify the complete user experience,
    not just the API layer. They catch issues like the portal JS calling
    admin-only endpoints instead of user-facing ones.
    """

    def test_user2_portal_shows_profiles(self, browser, gasket_url):
        """user2's portal page should render at least one profile card."""
        authentik_login(browser, gasket_url, "user2", "password")
        browser.get(f"{gasket_url}/")
        time.sleep(3)  # Wait for JS to fetch and render profiles

        # Check that the "no profiles" message is NOT visible
        empty_el = browser.execute_script(
            "var el = document.getElementById('portal-profiles-empty');"
            "return el ? el.style.display : null;"
        )
        assert empty_el != "block", (
            "Portal shows 'No backend profiles' — user-facing profiles endpoint may be broken"
        )

        # Check that profile cards are rendered
        profile_cards = browser.execute_script(
            "var container = document.getElementById('portal-profiles');"
            "return container ? container.querySelectorAll('.card').length : 0;"
        )
        assert profile_cards >= 1, (
            f"Expected at least 1 profile card on user2's portal, got {profile_cards}"
        )

    def test_user2_portal_shows_internal_standard(self, browser, gasket_url):
        """user2's portal should show the internal-standard profile by name."""
        authentik_login(browser, gasket_url, "user2", "password")
        browser.get(f"{gasket_url}/")
        time.sleep(3)

        page_source = browser.page_source
        assert "internal-standard" in page_source, (
            "Expected 'internal-standard' profile name on user2's portal page"
        )

    def test_user3_portal_shows_profiles(self, browser, gasket_url):
        """user3's portal page should also render profile cards."""
        authentik_login(browser, gasket_url, "user3", "password")
        browser.get(f"{gasket_url}/")
        time.sleep(3)

        profile_cards = browser.execute_script(
            "var container = document.getElementById('portal-profiles');"
            "return container ? container.querySelectorAll('.card').length : 0;"
        )
        assert profile_cards >= 1, (
            f"Expected at least 1 profile card on user3's portal, got {profile_cards}"
        )

    def test_user3_portal_has_admin_link(self, browser, gasket_url):
        """user3 (admin) should see the Admin link in the navbar."""
        authentik_login(browser, gasket_url, "user3", "password")
        browser.get(f"{gasket_url}/")
        time.sleep(2)

        page_source = browser.page_source
        assert "Admin" in page_source or "admin" in page_source.lower(), (
            "Expected admin navigation link for user3"
        )

    def test_user2_portal_no_admin_link(self, browser, gasket_url):
        """user2 (non-admin) should NOT see the Admin link in the navbar."""
        authentik_login(browser, gasket_url, "user2", "password")
        browser.get(f"{gasket_url}/")
        time.sleep(2)

        # Check navbar specifically — the page may contain "admin" in other contexts
        admin_link = browser.execute_script(
            "var links = document.querySelectorAll('nav a, .navbar a');"
            "for (var i = 0; i < links.length; i++) {"
            "  if (links[i].textContent.toLowerCase().includes('admin')) return true;"
            "}"
            "return false;"
        )
        assert not admin_link, "user2 should not see an Admin link in the navbar"

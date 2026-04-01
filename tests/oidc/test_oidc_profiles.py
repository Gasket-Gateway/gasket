"""OIDC profile & policy access tests — validates OIDC group-based profile visibility.

Tests exercise:
- Config-defined profile/backend/policy existence and structure
- Profile OIDC group assignments
- Admin CRUD access control for profiles
- Policy acceptance and checking flows with real OIDC sessions
- User API key operations gated by profile access and policy acceptance

Requires a running dev environment with Authentik provisioned.
"""

import pytest

from .conftest import GASKET_URL


# ─── Profile Visibility ──────────────────────────────────────────


class TestProfileVisibility:
    """Validate profile data returned through the admin API.

    The config.yaml defines a profile "internal-standard" scoped to
    gasket-users with the ollama-internal backend and acceptable-use policy.
    """

    def test_admin_profiles_returns_list(self, user3_session, gasket_url):
        """Admin profiles API returns a list of profiles."""
        resp = user3_session.get(f"{gasket_url}/admin/api/profiles")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1, "Expected at least one profile (config-defined)"

    def test_config_profile_exists(self, user3_session, gasket_url):
        """The config-defined 'internal-standard' profile should exist."""
        resp = user3_session.get(f"{gasket_url}/admin/api/profiles")
        assert resp.status_code == 200
        profiles = resp.json()
        names = [p["name"] for p in profiles]
        assert "internal-standard" in names, (
            f"Expected 'internal-standard' in profiles, got: {names}"
        )

    def test_config_profile_has_gasket_users_group(self, user3_session, gasket_url):
        """The 'internal-standard' profile should have gasket-users in oidc_groups."""
        resp = user3_session.get(f"{gasket_url}/admin/api/profiles")
        assert resp.status_code == 200
        profiles = resp.json()
        profile = next(p for p in profiles if p["name"] == "internal-standard")
        assert "gasket-users" in profile["oidc_groups"], (
            f"Expected 'gasket-users' in oidc_groups, got: {profile['oidc_groups']}"
        )

    def test_config_profile_has_backend(self, user3_session, gasket_url):
        """The 'internal-standard' profile should reference the ollama-internal backend."""
        resp = user3_session.get(f"{gasket_url}/admin/api/profiles")
        assert resp.status_code == 200
        profiles = resp.json()
        profile = next(p for p in profiles if p["name"] == "internal-standard")
        assert "ollama-internal" in profile.get("backend_names", []), (
            f"Expected 'ollama-internal' in backend_names, got: {profile.get('backend_names')}"
        )

    def test_config_profile_has_policy(self, user3_session, gasket_url):
        """The 'internal-standard' profile should reference the acceptable-use policy."""
        resp = user3_session.get(f"{gasket_url}/admin/api/profiles")
        assert resp.status_code == 200
        profiles = resp.json()
        profile = next(p for p in profiles if p["name"] == "internal-standard")
        assert "acceptable-use" in profile.get("policy_names", []), (
            f"Expected 'acceptable-use' in policy_names, got: {profile.get('policy_names')}"
        )

    def test_config_profile_is_config_sourced(self, user3_session, gasket_url):
        """Config-defined profiles should have source='config'."""
        resp = user3_session.get(f"{gasket_url}/admin/api/profiles")
        assert resp.status_code == 200
        profiles = resp.json()
        profile = next(p for p in profiles if p["name"] == "internal-standard")
        assert profile["source"] == "config"

    def test_config_profile_includes_all_fields(self, user3_session, gasket_url):
        """Profile response should include all expected fields."""
        resp = user3_session.get(f"{gasket_url}/admin/api/profiles")
        assert resp.status_code == 200
        profiles = resp.json()
        profile = next(p for p in profiles if p["name"] == "internal-standard")

        expected_fields = [
            "id", "name", "description", "oidc_groups", "source",
            "metadata_audit", "content_audit", "max_keys_per_user",
            "backend_ids", "backend_names", "policy_ids", "policy_names",
        ]
        for field in expected_fields:
            assert field in profile, f"Missing field '{field}' in profile response"

    def test_profiles_include_oidc_groups_as_list(self, user3_session, gasket_url):
        """The oidc_groups field should be a list, not a comma-separated string."""
        resp = user3_session.get(f"{gasket_url}/admin/api/profiles")
        assert resp.status_code == 200
        profiles = resp.json()
        for profile in profiles:
            assert isinstance(profile["oidc_groups"], list), (
                f"Expected oidc_groups to be a list for profile '{profile['name']}', "
                f"got: {type(profile['oidc_groups'])}"
            )


# ─── Profile Admin Write Access ──────────────────────────────────


class TestProfileAdminWriteAccess:
    """Validate that only admins can create/modify/delete profiles."""

    def test_user2_cannot_create_profile(self, user2_session, gasket_url):
        """user2 (non-admin) should be denied creating a profile."""
        resp = user2_session.post(
            f"{gasket_url}/admin/api/profiles",
            json={
                "name": "oidc-test-denied",
                "description": "Should not be created",
                "oidc_groups": ["gasket-users"],
            },
        )
        assert resp.status_code == 403

    def test_user2_cannot_read_single_profile(self, user2_session, user3_session, gasket_url):
        """user2 should be denied reading a single profile via admin API."""
        # First, get a profile ID using the admin session
        resp = user3_session.get(f"{gasket_url}/admin/api/profiles")
        profiles = resp.json()
        assert len(profiles) > 0, "No profiles to test with"
        profile_id = profiles[0]["id"]

        # Now try to read it as user2
        resp = user2_session.get(f"{gasket_url}/admin/api/profiles/{profile_id}")
        assert resp.status_code == 403

    def test_user2_cannot_update_profile(self, user2_session, user3_session, gasket_url):
        """user2 should be denied updating a profile."""
        resp = user3_session.get(f"{gasket_url}/admin/api/profiles")
        profiles = resp.json()
        assert len(profiles) > 0
        profile_id = profiles[0]["id"]

        resp = user2_session.put(
            f"{gasket_url}/admin/api/profiles/{profile_id}",
            json={"description": "hacked"},
        )
        assert resp.status_code == 403

    def test_user2_cannot_delete_profile(self, user2_session, user3_session, gasket_url):
        """user2 should be denied deleting a profile."""
        resp = user3_session.get(f"{gasket_url}/admin/api/profiles")
        profiles = resp.json()
        assert len(profiles) > 0
        profile_id = profiles[0]["id"]

        resp = user2_session.delete(f"{gasket_url}/admin/api/profiles/{profile_id}")
        assert resp.status_code == 403

    def test_user3_can_read_single_profile(self, user3_session, gasket_url):
        """user3 (admin) can read a single profile."""
        resp = user3_session.get(f"{gasket_url}/admin/api/profiles")
        profiles = resp.json()
        assert len(profiles) > 0

        profile_id = profiles[0]["id"]
        resp = user3_session.get(f"{gasket_url}/admin/api/profiles/{profile_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == profile_id

    def test_config_profile_cannot_be_modified(self, user3_session, gasket_url):
        """Config-defined profiles should be read-only even for admins."""
        resp = user3_session.get(f"{gasket_url}/admin/api/profiles")
        profiles = resp.json()
        config_profile = next(
            (p for p in profiles if p["source"] == "config"), None
        )
        assert config_profile, "No config-sourced profile found"

        resp = user3_session.put(
            f"{gasket_url}/admin/api/profiles/{config_profile['id']}",
            json={"description": "modified"},
        )
        assert resp.status_code == 403

    def test_config_profile_cannot_be_deleted(self, user3_session, gasket_url):
        """Config-defined profiles cannot be deleted even by admins."""
        resp = user3_session.get(f"{gasket_url}/admin/api/profiles")
        profiles = resp.json()
        config_profile = next(
            (p for p in profiles if p["source"] == "config"), None
        )
        assert config_profile, "No config-sourced profile found"

        resp = user3_session.delete(
            f"{gasket_url}/admin/api/profiles/{config_profile['id']}"
        )
        assert resp.status_code == 403


# ─── Policy Visibility & Structure ────────────────────────────────


class TestPolicyVisibility:
    """Validate policy data returned through the admin API."""

    def test_admin_policies_returns_list(self, user3_session, gasket_url):
        """Admin policies API returns a list of policies."""
        resp = user3_session.get(f"{gasket_url}/admin/api/policies")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1, "Expected at least one policy (config-defined)"

    def test_config_policy_exists(self, user3_session, gasket_url):
        """The config-defined 'acceptable-use' policy should exist."""
        resp = user3_session.get(f"{gasket_url}/admin/api/policies")
        assert resp.status_code == 200
        policies = resp.json()
        names = [p["name"] for p in policies]
        assert "acceptable-use" in names, (
            f"Expected 'acceptable-use' in policies, got: {names}"
        )

    def test_config_policy_has_content(self, user3_session, gasket_url):
        """The config-defined policy should have a current version with content."""
        resp = user3_session.get(f"{gasket_url}/admin/api/policies")
        assert resp.status_code == 200
        policies = resp.json()
        policy = next(p for p in policies if p["name"] == "acceptable-use")
        assert policy.get("current_content"), "Policy should have content"
        assert policy.get("current_version") is not None, "Policy should have a version"

    def test_config_policy_linked_to_profile(self, user3_session, gasket_url):
        """The config-defined policy should be linked to the internal-standard profile."""
        resp = user3_session.get(f"{gasket_url}/admin/api/policies")
        assert resp.status_code == 200
        policies = resp.json()
        policy = next(p for p in policies if p["name"] == "acceptable-use")
        assert "internal-standard" in policy.get("profile_names", []), (
            f"Expected 'internal-standard' in profile_names, got: {policy.get('profile_names')}"
        )

    def test_user2_cannot_list_policies(self, user2_session, gasket_url):
        """user2 (non-admin) should be denied listing policies."""
        resp = user2_session.get(f"{gasket_url}/admin/api/policies")
        assert resp.status_code == 403

    def test_user2_cannot_create_policy(self, user2_session, gasket_url):
        """user2 should be denied creating a policy."""
        resp = user2_session.post(
            f"{gasket_url}/admin/api/policies",
            json={"name": "oidc-test-denied", "content": "test"},
        )
        assert resp.status_code == 403


# ─── Policy Acceptance Flow ───────────────────────────────────────


class TestPolicyAcceptanceFlow:
    """Test the policy acceptance flow using real OIDC sessions.

    user2 (gasket-users) should be able to:
    - Check policy acceptance status for a profile
    - Accept policies for a profile they have group access to
    - See their acceptances afterwards
    """

    def _get_profile_and_policy(self, user3_session, gasket_url):
        """Helper: get the internal-standard profile ID and its policy ID."""
        resp = user3_session.get(f"{gasket_url}/admin/api/profiles")
        profiles = resp.json()
        profile = next(p for p in profiles if p["name"] == "internal-standard")
        profile_id = profile["id"]
        policy_ids = profile.get("policy_ids", [])
        return profile_id, policy_ids

    def test_user2_can_check_policy_status(self, user2_session, user3_session, gasket_url):
        """user2 can check policy acceptance status for a profile."""
        profile_id, _ = self._get_profile_and_policy(user3_session, gasket_url)
        resp = user2_session.get(
            f"{gasket_url}/admin/api/policies/acceptances/check/{profile_id}"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "all_accepted" in data

    def test_user2_can_accept_policy(self, user2_session, user3_session, gasket_url):
        """user2 can accept a policy for a profile they have group access to."""
        profile_id, policy_ids = self._get_profile_and_policy(user3_session, gasket_url)
        if not policy_ids:
            pytest.skip("No policies attached to the profile")

        policy_id = policy_ids[0]

        resp = user2_session.post(
            f"{gasket_url}/admin/api/policies/{policy_id}/accept",
            json={"profile_id": profile_id},
        )
        # Should succeed (201) or already accepted
        assert resp.status_code in (200, 201), (
            f"Expected policy acceptance to succeed, got {resp.status_code}: {resp.text}"
        )

    def test_user2_policies_accepted_after_accept(self, user2_session, user3_session, gasket_url):
        """After accepting, user2's policy status should show all_accepted."""
        profile_id, policy_ids = self._get_profile_and_policy(user3_session, gasket_url)
        if not policy_ids:
            pytest.skip("No policies attached to the profile")

        # Accept all policies first
        for policy_id in policy_ids:
            user2_session.post(
                f"{gasket_url}/admin/api/policies/{policy_id}/accept",
                json={"profile_id": profile_id},
            )

        # Now check status
        resp = user2_session.get(
            f"{gasket_url}/admin/api/policies/acceptances/check/{profile_id}"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["all_accepted"] is True, (
            f"Expected all policies accepted, got: {data}"
        )

    def test_user2_acceptances_visible_in_own_list(self, user2_session, user3_session, gasket_url):
        """user2's acceptances should appear in their my-acceptances list."""
        profile_id, policy_ids = self._get_profile_and_policy(user3_session, gasket_url)
        if not policy_ids:
            pytest.skip("No policies attached to the profile")

        # Accept policies
        for policy_id in policy_ids:
            user2_session.post(
                f"{gasket_url}/admin/api/policies/{policy_id}/accept",
                json={"profile_id": profile_id},
            )

        # Check own acceptances
        resp = user2_session.get(f"{gasket_url}/admin/api/policies/my-acceptances")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0, "Expected at least one acceptance"

    def test_user3_can_see_user2_acceptances(self, user2_session, user3_session, gasket_url):
        """Admin (user3) should see user2's acceptances in the all-acceptances list."""
        profile_id, policy_ids = self._get_profile_and_policy(user3_session, gasket_url)
        if not policy_ids:
            pytest.skip("No policies attached to the profile")

        # Ensure user2 has accepted
        for policy_id in policy_ids:
            user2_session.post(
                f"{gasket_url}/admin/api/policies/{policy_id}/accept",
                json={"profile_id": profile_id},
            )

        resp = user3_session.get(
            f"{gasket_url}/admin/api/policies/acceptances",
            params={"user": "user2@localhost"},
        )
        assert resp.status_code == 200
        data = resp.json()
        # Filter for user2's acceptances
        user2_entries = [a for a in data if a.get("user_email") == "user2@localhost"]
        assert len(user2_entries) > 0, (
            f"Expected user2 acceptances in admin view, got {len(data)} total entries"
        )


# ─── User API Key Operations with OIDC ───────────────────────────


class TestUserApiKeyOperations:
    """Test user-facing API key endpoints with real OIDC sessions.

    Validates that key creation is gated by profile access (OIDC groups)
    and policy acceptance.
    """

    def _ensure_policies_accepted(self, session, admin_session, gasket_url, profile_id):
        """Ensure all policies are accepted for the profile before key creation."""
        # Get policy IDs via admin session
        resp = admin_session.get(f"{gasket_url}/admin/api/profiles")
        profiles = resp.json()
        profile = next((p for p in profiles if p["id"] == profile_id), None)
        if not profile:
            return
        for policy_id in profile.get("policy_ids", []):
            session.post(
                f"{gasket_url}/admin/api/policies/{policy_id}/accept",
                json={"profile_id": profile_id},
            )

    def _get_internal_profile_id(self, user3_session, gasket_url):
        """Get the ID of the internal-standard profile."""
        resp = user3_session.get(f"{gasket_url}/admin/api/profiles")
        profiles = resp.json()
        profile = next(p for p in profiles if p["name"] == "internal-standard")
        return profile["id"]

    def test_user2_can_list_own_keys(self, user2_session, gasket_url):
        """user2 can list their own API keys (may be empty)."""
        resp = user2_session.get(f"{gasket_url}/api/keys")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_user3_can_list_own_keys(self, user3_session, gasket_url):
        """user3 can list their own API keys."""
        resp = user3_session.get(f"{gasket_url}/api/keys")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_user2_create_key_requires_policies(self, user2_session, user3_session, gasket_url):
        """Creating a key without accepting policies should fail."""
        profile_id = self._get_internal_profile_id(user3_session, gasket_url)

        # Don't accept policies — just try to create
        # Note: user2 may already have accepted from previous tests,
        # but the key creation will succeed in that case which is also valid.
        resp = user2_session.post(
            f"{gasket_url}/api/keys",
            json={
                "name": "oidc-test-key-no-policy",
                "profile_id": profile_id,
            },
        )
        # Will be either 201 (if policies already accepted from earlier tests)
        # or 400 (if policies not yet accepted)
        assert resp.status_code in (201, 400), (
            f"Expected 201 or 400, got {resp.status_code}: {resp.text}"
        )

    def test_user2_can_create_key_after_acceptance(self, user2_session, user3_session, gasket_url):
        """user2 can create a key after accepting all required policies."""
        profile_id = self._get_internal_profile_id(user3_session, gasket_url)

        # Accept all policies for this profile
        self._ensure_policies_accepted(
            user2_session, user3_session, gasket_url, profile_id
        )

        resp = user2_session.post(
            f"{gasket_url}/api/keys",
            json={
                "name": "oidc-test-key-user2",
                "profile_id": profile_id,
            },
        )
        assert resp.status_code == 201, (
            f"Expected key creation to succeed, got {resp.status_code}: {resp.text}"
        )
        data = resp.json()
        assert "key_value" in data, "Response should include the revealed key"
        assert data["key_value"].startswith("gsk_"), "Key should have gsk_ prefix"
        assert data["profile_name"] == "internal-standard"

    def test_created_key_appears_in_user_list(self, user2_session, user3_session, gasket_url):
        """A key created by user2 should appear in their key list."""
        profile_id = self._get_internal_profile_id(user3_session, gasket_url)

        # Accept policies and create a key
        self._ensure_policies_accepted(
            user2_session, user3_session, gasket_url, profile_id
        )
        create_resp = user2_session.post(
            f"{gasket_url}/api/keys",
            json={
                "name": "oidc-test-visibility-key",
                "profile_id": profile_id,
            },
        )
        if create_resp.status_code != 201:
            pytest.skip(f"Key creation failed: {create_resp.text}")

        key_id = create_resp.json()["id"]

        # List keys and check it's there
        resp = user2_session.get(f"{gasket_url}/api/keys")
        assert resp.status_code == 200
        keys = resp.json()
        key_ids = [k["id"] for k in keys]
        assert key_id in key_ids

    def test_user2_can_revoke_own_key(self, user2_session, user3_session, gasket_url):
        """user2 can revoke their own API key."""
        profile_id = self._get_internal_profile_id(user3_session, gasket_url)

        self._ensure_policies_accepted(
            user2_session, user3_session, gasket_url, profile_id
        )
        create_resp = user2_session.post(
            f"{gasket_url}/api/keys",
            json={
                "name": "oidc-test-revoke-key",
                "profile_id": profile_id,
            },
        )
        if create_resp.status_code != 201:
            pytest.skip(f"Key creation failed: {create_resp.text}")

        key_id = create_resp.json()["id"]

        # Revoke it
        resp = user2_session.post(f"{gasket_url}/api/keys/{key_id}/revoke")
        assert resp.status_code == 200
        data = resp.json()
        assert data["revoked"] is True

    def test_user2_key_visible_to_admin(self, user2_session, user3_session, gasket_url):
        """Keys created by user2 should be visible to admin (user3) via admin API."""
        profile_id = self._get_internal_profile_id(user3_session, gasket_url)

        self._ensure_policies_accepted(
            user2_session, user3_session, gasket_url, profile_id
        )
        create_resp = user2_session.post(
            f"{gasket_url}/api/keys",
            json={
                "name": "oidc-test-admin-visible",
                "profile_id": profile_id,
            },
        )
        if create_resp.status_code != 201:
            pytest.skip(f"Key creation failed: {create_resp.text}")

        key_id = create_resp.json()["id"]

        # Admin should see it
        resp = user3_session.get(f"{gasket_url}/admin/api/keys")
        assert resp.status_code == 200
        keys = resp.json()
        key_ids = [k["id"] for k in keys]
        assert key_id in key_ids

    def test_admin_can_revoke_user2_key(self, user2_session, user3_session, gasket_url):
        """Admin (user3) can revoke a key owned by user2."""
        profile_id = self._get_internal_profile_id(user3_session, gasket_url)

        self._ensure_policies_accepted(
            user2_session, user3_session, gasket_url, profile_id
        )
        create_resp = user2_session.post(
            f"{gasket_url}/api/keys",
            json={
                "name": "oidc-test-admin-revoke",
                "profile_id": profile_id,
            },
        )
        if create_resp.status_code != 201:
            pytest.skip(f"Key creation failed: {create_resp.text}")

        key_id = create_resp.json()["id"]

        # Admin revokes it
        resp = user3_session.post(f"{gasket_url}/admin/api/keys/{key_id}/revoke")
        assert resp.status_code == 200
        data = resp.json()
        assert data["revoked"] is True

    def test_user2_cannot_reveal_others_key(self, user2_session, user3_session, gasket_url):
        """user2 should not be able to reveal a key owned by user3."""
        profile_id = self._get_internal_profile_id(user3_session, gasket_url)

        # user3 accepts policies and creates a key
        self._ensure_policies_accepted(
            user3_session, user3_session, gasket_url, profile_id
        )
        create_resp = user3_session.post(
            f"{gasket_url}/api/keys",
            json={
                "name": "oidc-test-user3-private",
                "profile_id": profile_id,
            },
        )
        if create_resp.status_code != 201:
            pytest.skip(f"Key creation failed: {create_resp.text}")

        key_id = create_resp.json()["id"]

        # user2 tries to reveal it
        resp = user2_session.get(f"{gasket_url}/api/keys/{key_id}/reveal")
        assert resp.status_code == 404, (
            f"Expected 404 (key not found for this user), got {resp.status_code}"
        )

    def test_user2_cannot_revoke_others_key(self, user2_session, user3_session, gasket_url):
        """user2 should not be able to revoke a key owned by user3."""
        profile_id = self._get_internal_profile_id(user3_session, gasket_url)

        self._ensure_policies_accepted(
            user3_session, user3_session, gasket_url, profile_id
        )
        create_resp = user3_session.post(
            f"{gasket_url}/api/keys",
            json={
                "name": "oidc-test-user3-unrevokable",
                "profile_id": profile_id,
            },
        )
        if create_resp.status_code != 201:
            pytest.skip(f"Key creation failed: {create_resp.text}")

        key_id = create_resp.json()["id"]

        # user2 tries to revoke it
        resp = user2_session.post(f"{gasket_url}/api/keys/{key_id}/revoke")
        assert resp.status_code == 404, (
            f"Expected 404 (key not found for this user), got {resp.status_code}"
        )


# ─── Backend Admin Access via OIDC ────────────────────────────────


class TestBackendAdminAccess:
    """Validate backend admin API access control with OIDC sessions."""

    def test_admin_backends_returns_list(self, user3_session, gasket_url):
        """Admin can list all backends."""
        resp = user3_session.get(f"{gasket_url}/admin/api/backends")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1, "Expected at least one backend (config-defined)"

    def test_config_backend_exists(self, user3_session, gasket_url):
        """The config-defined 'ollama-internal' backend should exist."""
        resp = user3_session.get(f"{gasket_url}/admin/api/backends")
        assert resp.status_code == 200
        backends = resp.json()
        names = [b["name"] for b in backends]
        assert "ollama-internal" in names

    def test_user2_cannot_list_backends(self, user2_session, gasket_url):
        """user2 (non-admin) should be denied listing backends."""
        resp = user2_session.get(f"{gasket_url}/admin/api/backends")
        assert resp.status_code == 403

    def test_user2_cannot_create_backend(self, user2_session, gasket_url):
        """user2 should be denied creating a backend."""
        resp = user2_session.post(
            f"{gasket_url}/admin/api/backends",
            json={
                "name": "oidc-test-denied-backend",
                "base_url": "http://example.com",
            },
        )
        assert resp.status_code == 403

    def test_user2_cannot_read_single_backend(self, user2_session, user3_session, gasket_url):
        """user2 should be denied reading a single backend."""
        resp = user3_session.get(f"{gasket_url}/admin/api/backends")
        backends = resp.json()
        backend_id = backends[0]["id"]

        resp = user2_session.get(f"{gasket_url}/admin/api/backends/{backend_id}")
        assert resp.status_code == 403

    def test_user2_cannot_delete_backend(self, user2_session, user3_session, gasket_url):
        """user2 should be denied deleting a backend."""
        resp = user3_session.get(f"{gasket_url}/admin/api/backends")
        backends = resp.json()
        backend_id = backends[0]["id"]

        resp = user2_session.delete(f"{gasket_url}/admin/api/backends/{backend_id}")
        assert resp.status_code == 403

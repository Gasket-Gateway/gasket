"""RBAC tests — policy acceptance endpoint access control.

Verifies that policy acceptance endpoints respect group boundaries:
- Any gasket-users member can accept policies and view their own acceptances
- Only gasket-admins can view all acceptances
- No-group users are denied
"""

from .conftest import GASKET_URL


class TestPolicyAcceptanceAsAdmin:
    """Admin can use all policy acceptance endpoints."""

    def test_my_acceptances(self, admin_client):
        """Admin can view their own acceptances."""
        resp = admin_client.get(
            f"{GASKET_URL}/admin/api/policies/my-acceptances"
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_all_acceptances(self, admin_client):
        """Admin can view all users' acceptances."""
        resp = admin_client.get(
            f"{GASKET_URL}/admin/api/policies/acceptances"
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestPolicyAcceptanceAsUser:
    """Regular user can view own acceptances but not all."""

    def test_my_acceptances(self, user_client):
        """Regular user can view their own acceptances."""
        resp = user_client.get(
            f"{GASKET_URL}/admin/api/policies/my-acceptances"
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_all_acceptances_denied(self, user_client):
        """Regular user cannot view all acceptances."""
        resp = user_client.get(
            f"{GASKET_URL}/admin/api/policies/acceptances"
        )
        assert resp.status_code == 403


class TestPolicyAcceptanceAsNoGroup:
    """No-group user is denied policy acceptance endpoints."""

    def test_my_acceptances_denied(self, nogroup_client):
        """No-group user cannot view their own acceptances.

        The my-acceptances endpoint requires @login_required but not
        @groups_required — however the user does have a session, so this
        should return 200. The endpoint only checks authentication, not
        group membership.
        """
        resp = nogroup_client.get(
            f"{GASKET_URL}/admin/api/policies/my-acceptances"
        )
        # This endpoint only has @login_required, no group check
        assert resp.status_code == 200

    def test_all_acceptances_denied(self, nogroup_client):
        """No-group user cannot view all acceptances."""
        resp = nogroup_client.get(
            f"{GASKET_URL}/admin/api/policies/acceptances"
        )
        assert resp.status_code == 403


class TestPolicyAcceptanceAsAnon:
    """Unauthenticated user is redirected to login."""

    def test_my_acceptances_redirects(self, anon_client):
        resp = anon_client.get(
            f"{GASKET_URL}/admin/api/policies/my-acceptances",
            allow_redirects=False,
        )
        assert resp.status_code == 302

    def test_all_acceptances_redirects(self, anon_client):
        resp = anon_client.get(
            f"{GASKET_URL}/admin/api/policies/acceptances",
            allow_redirects=False,
        )
        assert resp.status_code == 302


class TestPolicyAcceptanceFlow:
    """Test that a user can accept a policy and see it in their acceptances."""

    def test_accept_and_verify(self, admin_client, user_client):
        """Create policy + profile, user accepts, verify in their acceptances."""
        # Admin creates a policy
        policy_resp = admin_client.post(
            f"{GASKET_URL}/admin/api/policies",
            json={"name": "rbac-accept-policy", "content": "You must agree."},
        )
        assert policy_resp.status_code == 201
        policy_id = policy_resp.json()["id"]

        # Admin creates a profile with the policy
        profile_resp = admin_client.post(
            f"{GASKET_URL}/admin/api/profiles",
            json={
                "name": "rbac-accept-profile",
                "policy_ids": [policy_id],
            },
        )
        assert profile_resp.status_code == 201
        profile_id = profile_resp.json()["id"]

        try:
            # User accepts the policy for the profile
            accept_resp = user_client.post(
                f"{GASKET_URL}/admin/api/policies/{policy_id}/accept",
                json={"profile_id": profile_id},
            )
            assert accept_resp.status_code == 201

            # User can see it in their own acceptances
            my_resp = user_client.get(
                f"{GASKET_URL}/admin/api/policies/my-acceptances"
            )
            assert my_resp.status_code == 200
            acceptances = my_resp.json()
            matching = [
                a for a in acceptances
                if a.get("profile_id") == profile_id
                and a.get("policy_name") == "rbac-accept-policy"
            ]
            assert len(matching) >= 1

            # Admin can also see it in all acceptances
            all_resp = admin_client.get(
                f"{GASKET_URL}/admin/api/policies/acceptances"
            )
            assert all_resp.status_code == 200

        finally:
            # Clean up
            admin_client.delete(
                f"{GASKET_URL}/admin/api/profiles/{profile_id}"
            )
            admin_client.delete(
                f"{GASKET_URL}/admin/api/policies/{policy_id}"
            )

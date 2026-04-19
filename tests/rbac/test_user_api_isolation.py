"""RBAC tests — user API data isolation.

Verifies that users can only access their own API keys and that the
admin API shows keys across all users.
"""

import os

import requests

GASKET_URL = os.environ.get("GASKET_URL", "http://localhost:5000")


def _create_session(email, name, groups):
    """Create a fresh session with the given identity."""
    sess = requests.Session()
    sess.verify = False
    resp = sess.post(
        f"{GASKET_URL}/test/set-session",
        json={"email": email, "name": name, "groups": groups},
    )
    assert resp.status_code == 200
    return sess


class TestUserKeyIsolation:
    """Users can only see and manage their own API keys."""

    def test_user_cannot_see_other_users_keys(self, admin_client):
        """Create a key as one user, verify another user cannot see it."""
        # Create a profile for the key (admin creates it)
        profile_resp = admin_client.post(
            f"{GASKET_URL}/admin/api/profiles",
            json={"name": "isolation-test-profile"},
        )
        assert profile_resp.status_code == 201
        profile_id = profile_resp.json()["id"]

        try:
            # Create sessions for two different users
            user_a = _create_session(
                "usera@test.local", "usera", ["gasket-users"]
            )
            user_b = _create_session(
                "userb@test.local", "userb", ["gasket-users"]
            )

            # User A creates a key
            key_resp = user_a.post(
                f"{GASKET_URL}/api/keys",
                json={
                    "name": "usera-key",
                    "profile_id": profile_id,
                },
            )
            assert key_resp.status_code == 201
            key_id = key_resp.json()["id"]

            # User A can see it
            a_keys = user_a.get(f"{GASKET_URL}/api/keys").json()
            a_key_ids = [k["id"] for k in a_keys]
            assert key_id in a_key_ids

            # User B cannot see it
            b_keys = user_b.get(f"{GASKET_URL}/api/keys").json()
            b_key_ids = [k["id"] for k in b_keys]
            assert key_id not in b_key_ids

            # User B cannot access it directly
            b_get_resp = user_b.get(f"{GASKET_URL}/api/keys/{key_id}")
            assert b_get_resp.status_code == 404

            # Clean up — user A revokes their own key
            user_a.post(f"{GASKET_URL}/api/keys/{key_id}/revoke")

        finally:
            admin_client.delete(
                f"{GASKET_URL}/admin/api/profiles/{profile_id}"
            )

    def test_user_cannot_reveal_other_users_key(self, admin_client):
        """User B cannot reveal user A's key."""
        profile_resp = admin_client.post(
            f"{GASKET_URL}/admin/api/profiles",
            json={"name": "isolation-reveal-profile"},
        )
        assert profile_resp.status_code == 201
        profile_id = profile_resp.json()["id"]

        try:
            user_a = _create_session(
                "usera-reveal@test.local", "usera", ["gasket-users"]
            )
            user_b = _create_session(
                "userb-reveal@test.local", "userb", ["gasket-users"]
            )

            key_resp = user_a.post(
                f"{GASKET_URL}/api/keys",
                json={"name": "reveal-test-key", "profile_id": profile_id},
            )
            assert key_resp.status_code == 201
            key_id = key_resp.json()["id"]

            # User B cannot reveal it
            reveal_resp = user_b.get(f"{GASKET_URL}/api/keys/{key_id}/reveal")
            assert reveal_resp.status_code == 404

            # Clean up
            user_a.post(f"{GASKET_URL}/api/keys/{key_id}/revoke")

        finally:
            admin_client.delete(
                f"{GASKET_URL}/admin/api/profiles/{profile_id}"
            )

    def test_user_cannot_revoke_other_users_key(self, admin_client):
        """User B cannot revoke user A's key."""
        profile_resp = admin_client.post(
            f"{GASKET_URL}/admin/api/profiles",
            json={"name": "isolation-revoke-profile"},
        )
        assert profile_resp.status_code == 201
        profile_id = profile_resp.json()["id"]

        try:
            user_a = _create_session(
                "usera-revoke@test.local", "usera", ["gasket-users"]
            )
            user_b = _create_session(
                "userb-revoke@test.local", "userb", ["gasket-users"]
            )

            key_resp = user_a.post(
                f"{GASKET_URL}/api/keys",
                json={"name": "revoke-test-key", "profile_id": profile_id},
            )
            assert key_resp.status_code == 201
            key_id = key_resp.json()["id"]

            # User B cannot revoke it
            revoke_resp = user_b.post(f"{GASKET_URL}/api/keys/{key_id}/revoke")
            assert revoke_resp.status_code == 404

            # Clean up — user A revokes their own key
            user_a.post(f"{GASKET_URL}/api/keys/{key_id}/revoke")

        finally:
            admin_client.delete(
                f"{GASKET_URL}/admin/api/profiles/{profile_id}"
            )

    def test_user_cannot_edit_other_users_key(self, admin_client):
        """User B cannot edit user A's key."""
        profile_resp = admin_client.post(
            f"{GASKET_URL}/admin/api/profiles",
            json={"name": "isolation-edit-profile"},
        )
        assert profile_resp.status_code == 201
        profile_id = profile_resp.json()["id"]

        try:
            user_a = _create_session(
                "usera-edit@test.local", "usera", ["gasket-users"]
            )
            user_b = _create_session(
                "userb-edit@test.local", "userb", ["gasket-users"]
            )

            key_resp = user_a.post(
                f"{GASKET_URL}/api/keys",
                json={"name": "edit-test-key", "profile_id": profile_id},
            )
            assert key_resp.status_code == 201
            key_id = key_resp.json()["id"]

            # User B cannot edit it
            edit_resp = user_b.put(
                f"{GASKET_URL}/api/keys/{key_id}",
                json={"vscode_continue": True},
            )
            # Should be 404 (key not found for this user) or 403
            assert edit_resp.status_code in (403, 404)

            # Clean up
            user_a.post(f"{GASKET_URL}/api/keys/{key_id}/revoke")

        finally:
            admin_client.delete(
                f"{GASKET_URL}/admin/api/profiles/{profile_id}"
            )

    def test_admin_can_see_all_keys(self, admin_client):
        """Admin API keys list includes keys from all users."""
        profile_resp = admin_client.post(
            f"{GASKET_URL}/admin/api/profiles",
            json={"name": "isolation-admin-profile"},
        )
        assert profile_resp.status_code == 201
        profile_id = profile_resp.json()["id"]

        try:
            user_a = _create_session(
                "usera-admin@test.local", "usera", ["gasket-users"]
            )

            key_resp = user_a.post(
                f"{GASKET_URL}/api/keys",
                json={"name": "admin-vis-key", "profile_id": profile_id},
            )
            assert key_resp.status_code == 201
            key_id = key_resp.json()["id"]

            # Admin can see it in the admin keys list
            admin_keys = admin_client.get(f"{GASKET_URL}/admin/api/keys").json()
            admin_key_ids = [k["id"] for k in admin_keys]
            assert key_id in admin_key_ids

            # Clean up
            user_a.post(f"{GASKET_URL}/api/keys/{key_id}/revoke")

        finally:
            admin_client.delete(
                f"{GASKET_URL}/admin/api/profiles/{profile_id}"
            )

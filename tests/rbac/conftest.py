"""RBAC test fixtures — multi-role HTTP sessions via /test/set-session.

Provides four test personas:
- admin_client  — gasket-users + gasket-admins (full access)
- user_client   — gasket-users only (portal access, admin denied)
- nogroup_client — authenticated but no gasket groups (everything denied)
- anon_client   — no session at all (redirected to login)
"""

import os

import pytest
import requests


GASKET_URL = os.environ.get("GASKET_URL", "http://localhost:5000")


def _create_session_with_identity(base_url, email, name, groups):
    """Create a requests.Session and set its identity via /test/set-session."""
    sess = requests.Session()
    sess.verify = False

    resp = sess.post(
        f"{base_url}/test/set-session",
        json={"email": email, "name": name, "groups": groups},
    )
    assert resp.status_code == 200, (
        f"Failed to set test session for {email}: {resp.text}"
    )
    return sess


@pytest.fixture(scope="module")
def admin_client():
    """HTTP session as an admin user (gasket-users + gasket-admins)."""
    return _create_session_with_identity(
        GASKET_URL,
        email="admin@test.local",
        name="admin",
        groups=["gasket-users", "gasket-admins"],
    )


@pytest.fixture(scope="module")
def user_client():
    """HTTP session as a regular user (gasket-users only)."""
    return _create_session_with_identity(
        GASKET_URL,
        email="user@test.local",
        name="user",
        groups=["gasket-users"],
    )


@pytest.fixture(scope="module")
def nogroup_client():
    """HTTP session as a user with no gasket groups (authenticated but unauthorised)."""
    return _create_session_with_identity(
        GASKET_URL,
        email="nogroup@test.local",
        name="nogroup",
        groups=["some-other-group"],
    )


@pytest.fixture(scope="module")
def anon_client():
    """HTTP session with no user identity (unauthenticated).

    Uses /test/clear-session to set the _test_anon flag so the
    before_request hook doesn't auto-inject the default test user.
    """
    sess = requests.Session()
    sess.verify = False
    resp = sess.post(f"{GASKET_URL}/test/clear-session")
    assert resp.status_code == 200
    return sess


@pytest.fixture(scope="module")
def gasket_url():
    """Base URL for the Gasket instance."""
    return GASKET_URL

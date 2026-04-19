"""Integration tests for the /v1/* API key authentication middleware.

Tests validate that:
- Missing, malformed, invalid, revoked, and expired keys are rejected
- Valid keys pass authentication and receive the 501 stub response
- All error responses use the OpenAI-compatible JSON format
"""

import pytest
from datetime import datetime, timedelta, timezone


class TestProxyAuthNoKey:
    """Requests without a valid Authorization header."""

    def test_missing_auth_header(self, client):
        """Request with no Authorization header → 401."""
        resp = client.get("/v1/chat/completions")
        assert resp.status_code == 401
        data = resp.json()
        assert "error" in data
        assert data["error"]["code"] == "missing_api_key"

    def test_empty_auth_header(self, client):
        """Request with empty Authorization header → 401."""
        resp = client.get(
            "/v1/chat/completions",
            headers={"Authorization": ""},
        )
        assert resp.status_code == 401

    def test_no_bearer_prefix(self, client):
        """Authorization header without 'Bearer' prefix → 401."""
        resp = client.get(
            "/v1/chat/completions",
            headers={"Authorization": "Basic gsk_abc123"},
        )
        assert resp.status_code == 401
        data = resp.json()
        assert data["error"]["code"] == "malformed_auth_header"

    def test_bearer_no_token(self, client):
        """Authorization: Bearer with no token → 401."""
        resp = client.get(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer"},
        )
        assert resp.status_code == 401

    def test_non_gsk_token(self, client):
        """Bearer token without gsk_ prefix → 401."""
        resp = client.get(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer sk-not-a-gasket-key"},
        )
        assert resp.status_code == 401
        data = resp.json()
        assert data["error"]["code"] == "invalid_api_key"

    def test_nonexistent_key(self, client):
        """Bearer token with gsk_ prefix but not in database → 401."""
        resp = client.get(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer gsk_000000000000000000000000000000000000000000000000"},
        )
        assert resp.status_code == 401
        data = resp.json()
        assert data["error"]["code"] == "invalid_api_key"


class TestProxyAuthOpenAIFormat:
    """All proxy error responses must use the OpenAI error JSON format."""

    def test_error_response_structure(self, client):
        """Error response has the correct top-level structure."""
        resp = client.get("/v1/models")
        assert resp.status_code == 401
        data = resp.json()

        assert "error" in data
        error = data["error"]
        assert "message" in error
        assert "type" in error
        assert "code" in error

    def test_error_content_type_is_json(self, client):
        """Error responses have application/json content type."""
        resp = client.get("/v1/models")
        assert "application/json" in resp.headers.get("Content-Type", "")


class TestProxyAuthWithKey:
    """Tests that require creating an API key in the database first.

    Uses the admin API (available in GASKET_TEST_MODE) to create a
    backend, profile, and API key, then tests proxy auth against them.
    """

    @pytest.fixture(autouse=True)
    def setup_key(self, client):
        """Create a backend, profile, and API key for testing.

        Cleans up after the test completes.
        """
        # Create a backend
        resp = client.post(
            "/admin/api/backends",
            json={
                "name": "proxy-test-backend",
                "base_url": "http://localhost:9999",
                "api_key": "sk-test",
            },
        )
        assert resp.status_code == 201, f"Failed to create backend: {resp.text}"
        self.backend_id = resp.json()["id"]

        # Create a profile with that backend
        resp = client.post(
            "/admin/api/profiles",
            json={
                "name": "proxy-test-profile",
                "description": "Test profile for proxy auth",
                "oidc_groups": "gasket-users",
                "backend_ids": [self.backend_id],
                "max_keys_per_user": 10,
            },
        )
        assert resp.status_code == 201, f"Failed to create profile: {resp.text}"
        self.profile_id = resp.json()["id"]

        # Create an API key (as the test user)
        resp = client.post(
            "/api/keys",
            json={
                "name": "proxy-test-key",
                "profile_id": self.profile_id,
            },
        )
        assert resp.status_code == 201, f"Failed to create key: {resp.text}"
        key_data = resp.json()
        self.key_id = key_data["id"]
        self.key_value = key_data["key_value"]

        yield

        # Cleanup — delete in reverse order
        client.delete(f"/api/keys/{self.key_id}")
        client.delete(f"/admin/api/profiles/{self.profile_id}")
        client.delete(f"/admin/api/backends/{self.backend_id}")

    def test_valid_key_passes_auth(self, client):
        """A valid, active key passes authentication → 502 (backend unreachable)."""
        resp = client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.key_value}"},
            json={"model": "test", "messages": [{"role": "user", "content": "hello"}]},
        )
        # Backend at localhost:9999 is not running, so the proxy returns 502
        assert resp.status_code == 502
        data = resp.json()
        assert data["error"]["code"] == "upstream_connection_error"

    def test_valid_key_various_paths(self, client):
        """Valid key works on different /v1/* subpaths — auth passes, backend unreachable."""
        for path in ["/v1/models", "/v1/completions", "/v1/embeddings"]:
            resp = client.get(
                path,
                headers={"Authorization": f"Bearer {self.key_value}"},
            )
            # Auth succeeds but backend is unreachable → 502
            assert resp.status_code == 502, f"Unexpected status on {path}"

    def test_revoked_key_rejected(self, client):
        """A revoked key is rejected → 401."""
        # Revoke the key via portal API
        client.post(f"/api/keys/{self.key_id}/revoke")

        resp = client.get(
            "/v1/models",
            headers={"Authorization": f"Bearer {self.key_value}"},
        )
        assert resp.status_code == 401
        data = resp.json()
        assert data["error"]["code"] == "revoked_api_key"

        # Restore it for cleanup
        client.post(f"/admin/api/keys/{self.key_id}/restore")

    def test_case_insensitive_bearer(self, client):
        """Authorization header with 'bearer' (lowercase) is accepted."""
        resp = client.get(
            "/v1/models",
            headers={"Authorization": f"bearer {self.key_value}"},
        )
        # Auth succeeds but backend is unreachable → 502
        assert resp.status_code == 502


class TestProxyAuthExpiredKey:
    """Test expired key rejection.

    Uses a separate fixture to create a key with a past expiry date.
    """

    @pytest.fixture(autouse=True)
    def setup_expired_key(self, client):
        """Create a backend, profile, and already-expired API key."""
        # Create a backend
        resp = client.post(
            "/admin/api/backends",
            json={
                "name": "proxy-expiry-backend",
                "base_url": "http://localhost:9999",
                "api_key": "sk-test",
            },
        )
        assert resp.status_code == 201
        self.backend_id = resp.json()["id"]

        # Create a profile with enforced expiry (1 day)
        resp = client.post(
            "/admin/api/profiles",
            json={
                "name": "proxy-expiry-profile",
                "description": "Test profile for expired key",
                "oidc_groups": "gasket-users",
                "backend_ids": [self.backend_id],
                "default_expiry_days": 1,
                "enforce_expiry": True,
                "max_keys_per_user": 10,
            },
        )
        assert resp.status_code == 201
        self.profile_id = resp.json()["id"]

        # Create a key with an already-past expiry
        past_expiry = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        resp = client.post(
            "/api/keys",
            json={
                "name": "proxy-expired-key",
                "profile_id": self.profile_id,
                "expires_at": past_expiry,
            },
        )
        assert resp.status_code == 201
        key_data = resp.json()
        self.key_id = key_data["id"]
        self.key_value = key_data["key_value"]

        yield

        # Cleanup
        client.delete(f"/api/keys/{self.key_id}")
        client.delete(f"/admin/api/profiles/{self.profile_id}")
        client.delete(f"/admin/api/backends/{self.backend_id}")

    def test_expired_key_rejected(self, client):
        """An expired key is rejected → 401."""
        resp = client.get(
            "/v1/models",
            headers={"Authorization": f"Bearer {self.key_value}"},
        )
        assert resp.status_code == 401
        data = resp.json()
        assert data["error"]["code"] == "expired_api_key"

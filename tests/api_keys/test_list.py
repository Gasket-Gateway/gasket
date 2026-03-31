"""API key listing tests."""

from .conftest import create_test_profile_with_policy, cleanup_test_resources


class TestApiKeysList:
    """Verify the user key listing API."""

    def test_list_keys_returns_200(self, client):
        """GET /api/keys should return 200."""
        response = client.get("/api/keys")
        assert response.status_code == 200

    def test_list_keys_returns_json_list(self, client):
        """GET /api/keys should return a JSON list."""
        response = client.get("/api/keys")
        data = response.json()
        assert isinstance(data, list)

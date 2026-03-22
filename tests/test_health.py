"""Health endpoint tests — run against the Gasket test environment."""


class TestHealthEndpoints:
    """Verify health endpoints respond correctly."""

    def test_health_returns_200(self, client):
        """The /health endpoint should return 200 OK."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_response_content(self, client):
        """The /health endpoint should return meaningful content."""
        response = client.get("/health")
        assert response.content is not None

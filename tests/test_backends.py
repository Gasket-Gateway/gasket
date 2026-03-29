"""OpenAI backends CRUD tests — run against the Gasket test environment (GASKET_TEST_MODE).

Uses the development environment's Ollama instances:
  - ollama-internal: config-defined (read-only in admin), seeded on startup
  - ollama-external: used for testing admin CRUD flows (create/edit/delete)
"""

# The ollama-external URL reachable from the gasket/test containers via extra_hosts
OLLAMA_EXTERNAL_URL = "https://ollama-external.gasket-dev.local"


class TestConfigBackend:
    """Verify config-defined backends (ollama-internal) are seeded and read-only."""

    def test_config_backend_seeded(self, client):
        """ollama-internal should appear in the backends list with source=config."""
        response = client.get("/admin/api/backends")
        assert response.status_code == 200
        backends = response.json()
        matching = [b for b in backends if b["name"] == "ollama-internal"]
        assert len(matching) == 1
        assert matching[0]["source"] == "config"
        assert "ollama-internal" in matching[0]["base_url"]

    def test_config_backend_is_read_only_update(self, client):
        """Updating a config-sourced backend should return 403."""
        # Find the config backend's ID
        list_resp = client.get("/admin/api/backends")
        backends = list_resp.json()
        config_backend = next(b for b in backends if b["name"] == "ollama-internal")

        response = client.put(
            f"/admin/api/backends/{config_backend['id']}",
            json={"name": "renamed"},
        )
        assert response.status_code == 403

    def test_config_backend_is_read_only_delete(self, client):
        """Deleting a config-sourced backend should return 403."""
        list_resp = client.get("/admin/api/backends")
        backends = list_resp.json()
        config_backend = next(b for b in backends if b["name"] == "ollama-internal")

        response = client.delete(f"/admin/api/backends/{config_backend['id']}")
        assert response.status_code == 403


class TestBackendsList:
    """Verify the backends list API."""

    def test_list_backends_returns_200(self, client):
        """GET /admin/api/backends should return 200."""
        response = client.get("/admin/api/backends")
        assert response.status_code == 200

    def test_list_backends_returns_json_list(self, client):
        """GET /admin/api/backends should return a JSON list."""
        response = client.get("/admin/api/backends")
        data = response.json()
        assert isinstance(data, list)

    def test_list_includes_config_backend(self, client):
        """The config-seeded ollama-internal should be in the list."""
        response = client.get("/admin/api/backends")
        names = [b["name"] for b in response.json()]
        assert "ollama-internal" in names


class TestBackendsCreate:
    """Verify backend creation using ollama-external."""

    def test_create_backend(self, client):
        """POST /admin/api/backends should create a backend and return 201."""
        response = client.post(
            "/admin/api/backends",
            json={
                "name": "ollama-external",
                "base_url": OLLAMA_EXTERNAL_URL,
                "api_key": "",
                "skip_tls_verify": True,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "ollama-external"
        assert data["base_url"] == OLLAMA_EXTERNAL_URL
        assert data["source"] == "admin"
        assert data["skip_tls_verify"] is True

        # Clean up
        client.delete(f"/admin/api/backends/{data['id']}")

    def test_create_backend_duplicate_name(self, client):
        """Duplicate backend name should return 409."""
        payload = {
            "name": "test-duplicate-backend",
            "base_url": OLLAMA_EXTERNAL_URL,
        }
        resp1 = client.post("/admin/api/backends", json=payload)
        assert resp1.status_code == 201
        backend_id = resp1.json()["id"]

        resp2 = client.post("/admin/api/backends", json=payload)
        assert resp2.status_code == 409

        # Clean up
        client.delete(f"/admin/api/backends/{backend_id}")

    def test_create_backend_missing_name(self, client):
        """Missing name should return 400."""
        response = client.post(
            "/admin/api/backends",
            json={"base_url": OLLAMA_EXTERNAL_URL},
        )
        assert response.status_code == 400

    def test_create_backend_missing_url(self, client):
        """Missing base_url should return 400."""
        response = client.post(
            "/admin/api/backends",
            json={"name": "test-missing-url"},
        )
        assert response.status_code == 400

    def test_create_backend_empty_body(self, client):
        """Empty request body should return 400."""
        response = client.post(
            "/admin/api/backends",
            data="not json",
            headers={"Content-Type": "text/plain"},
        )
        assert response.status_code == 400


class TestBackendsRead:
    """Verify reading individual backends."""

    def test_get_backend(self, client):
        """GET /admin/api/backends/<id> should return the backend with full API key."""
        create_resp = client.post(
            "/admin/api/backends",
            json={
                "name": "test-get-backend",
                "base_url": OLLAMA_EXTERNAL_URL,
                "api_key": "secret-key-12345678",
                "skip_tls_verify": True,
            },
        )
        assert create_resp.status_code == 201
        backend_id = create_resp.json()["id"]

        # Fetch it — single GET returns full (unmasked) key
        response = client.get(f"/admin/api/backends/{backend_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "test-get-backend"
        assert data["api_key"] == "secret-key-12345678"

        # Clean up
        client.delete(f"/admin/api/backends/{backend_id}")

    def test_get_backend_not_found(self, client):
        """Non-existent backend ID should return 404."""
        response = client.get("/admin/api/backends/99999")
        assert response.status_code == 404

    def test_list_backends_masks_api_key(self, client):
        """List endpoint should mask API keys."""
        create_resp = client.post(
            "/admin/api/backends",
            json={
                "name": "test-mask-backend",
                "base_url": OLLAMA_EXTERNAL_URL,
                "api_key": "sk-1234567890abcdef",
            },
        )
        assert create_resp.status_code == 201
        backend_id = create_resp.json()["id"]

        # List should mask the key
        list_resp = client.get("/admin/api/backends")
        assert list_resp.status_code == 200
        backends = list_resp.json()
        matching = [b for b in backends if b["name"] == "test-mask-backend"]
        assert len(matching) == 1
        # Key should be masked (not the full value)
        assert matching[0]["api_key"] != "sk-1234567890abcdef"
        assert "…" in matching[0]["api_key"] or "••••" in matching[0]["api_key"]

        # Clean up
        client.delete(f"/admin/api/backends/{backend_id}")


class TestBackendsUpdate:
    """Verify backend updates."""

    def test_update_backend(self, client):
        """PUT /admin/api/backends/<id> should update and return 200."""
        create_resp = client.post(
            "/admin/api/backends",
            json={
                "name": "test-update-backend",
                "base_url": OLLAMA_EXTERNAL_URL,
                "skip_tls_verify": True,
            },
        )
        assert create_resp.status_code == 201
        backend_id = create_resp.json()["id"]

        update_resp = client.put(
            f"/admin/api/backends/{backend_id}",
            json={
                "name": "test-update-backend-renamed",
                "base_url": "http://new-host:11434",
            },
        )
        assert update_resp.status_code == 200
        data = update_resp.json()
        assert data["name"] == "test-update-backend-renamed"
        assert data["base_url"] == "http://new-host:11434"

        # Clean up
        client.delete(f"/admin/api/backends/{backend_id}")

    def test_update_backend_not_found(self, client):
        """Updating a non-existent backend should return 404."""
        response = client.put(
            "/admin/api/backends/99999",
            json={"name": "nope"},
        )
        assert response.status_code == 404


class TestBackendsDelete:
    """Verify backend deletion."""

    def test_delete_backend(self, client):
        """DELETE /admin/api/backends/<id> should delete and return 200."""
        create_resp = client.post(
            "/admin/api/backends",
            json={
                "name": "test-delete-backend",
                "base_url": OLLAMA_EXTERNAL_URL,
            },
        )
        assert create_resp.status_code == 201
        backend_id = create_resp.json()["id"]

        delete_resp = client.delete(f"/admin/api/backends/{backend_id}")
        assert delete_resp.status_code == 200

        # Verify it's gone
        get_resp = client.get(f"/admin/api/backends/{backend_id}")
        assert get_resp.status_code == 404

    def test_delete_backend_not_found(self, client):
        """Deleting a non-existent backend should return 404."""
        response = client.delete("/admin/api/backends/99999")
        assert response.status_code == 404


class TestBackendsLifecycle:
    """End-to-end lifecycle: create ollama-external, verify, update, delete."""

    def test_full_crud_lifecycle(self, client):
        """Full CRUD lifecycle with ollama-external as the admin-created backend."""
        # Create
        create_resp = client.post(
            "/admin/api/backends",
            json={
                "name": "ollama-external-lifecycle",
                "base_url": OLLAMA_EXTERNAL_URL,
                "api_key": "",
                "skip_tls_verify": True,
            },
        )
        assert create_resp.status_code == 201
        backend_id = create_resp.json()["id"]

        # List should contain both config and admin backends
        list_resp = client.get("/admin/api/backends")
        names = [b["name"] for b in list_resp.json()]
        assert "ollama-internal" in names           # config-defined
        assert "ollama-external-lifecycle" in names  # admin-created

        # Update
        update_resp = client.put(
            f"/admin/api/backends/{backend_id}",
            json={"name": "ollama-external-updated"},
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["name"] == "ollama-external-updated"

        # Delete
        delete_resp = client.delete(f"/admin/api/backends/{backend_id}")
        assert delete_resp.status_code == 200

        # Verify admin backend gone, config backend still present
        list_resp2 = client.get("/admin/api/backends")
        names2 = [b["name"] for b in list_resp2.json()]
        assert "ollama-external-updated" not in names2
        assert "ollama-internal" in names2


class TestBackendsAdminPage:
    """Verify the admin page includes backends content."""

    def test_backends_page_loads(self, client):
        """GET /admin should load and contain OpenAI Backends."""
        response = client.get("/admin")
        assert response.status_code == 200
        assert "OpenAI Backends" in response.text

    def test_status_includes_backends_key(self, client):
        """GET /admin/api/status should include openai_backends key."""
        response = client.get("/admin/api/status")
        assert response.status_code == 200
        data = response.json()
        assert "openai_backends" in data
        assert isinstance(data["openai_backends"], list)

    def test_status_includes_config_backend(self, client):
        """Connection status should include the config-defined ollama-internal backend."""
        response = client.get("/admin/api/status")
        data = response.json()
        backend_names = [b["name"] for b in data["openai_backends"]]
        assert "ollama-internal" in backend_names

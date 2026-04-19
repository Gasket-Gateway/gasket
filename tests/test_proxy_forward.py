"""Integration tests for /v1/* proxy forwarding to upstream backends.

Tests use a mock OpenAI backend (a minimal Flask app running in a
background thread) to verify that Gasket correctly proxies requests,
handles streaming, and translates upstream errors.
"""

import json
import os
import socket
import threading
import time

import pytest
import requests
from flask import Flask, Response, jsonify, request as flask_request


# ── Mock upstream OpenAI backend ───────────────────────────────────


def _find_free_port():
    """Find a free TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("0.0.0.0", 0))
        return s.getsockname()[1]


def _get_test_runner_hostname():
    """Get the hostname that the Gasket container can use to reach this container.

    In the Docker test environment the test-runner and Gasket are on the
    same compose network, so Docker DNS resolves the service name
    ``test-runner``.  We verify connectivity from this container first
    using our own hostname, falling back to ``127.0.0.1`` for local
    (non-Docker) runs.
    """
    hostname = socket.gethostname()
    try:
        # If the hostname resolves to a routable IP, use it
        ip = socket.gethostbyname(hostname)
        if ip and not ip.startswith("127."):
            return hostname
    except socket.gaierror:
        pass
    return "127.0.0.1"


def _create_mock_backend(port, api_key="sk-upstream-test"):
    """Create a minimal Flask app that mimics an OpenAI backend.

    The mock supports:
    - GET  /v1/models          — returns a model list
    - POST /v1/chat/completions — returns a completion (streaming or not)
    - POST /v1/completions      — returns a legacy completion
    - Any path with ?error=500  — returns HTTP 500
    - Any path with ?error=timeout — sleeps 30s (triggers client timeout)
    - Validates Authorization header matches the expected api_key
    """
    app = Flask(__name__)
    app.config["TESTING"] = True

    @app.route("/v1/models", methods=["GET"])
    def list_models():
        # Validate upstream auth
        auth = flask_request.headers.get("Authorization", "")
        if api_key and auth != f"Bearer {api_key}":
            return jsonify({"error": {"message": "Invalid auth", "type": "auth_error", "code": "invalid_api_key"}}), 401

        if flask_request.args.get("error") == "500":
            return jsonify({"error": {"message": "Internal error", "type": "server_error", "code": "internal"}}), 500

        return jsonify({
            "object": "list",
            "data": [
                {"id": "gpt-4", "object": "model", "owned_by": "openai"},
                {"id": "gpt-3.5-turbo", "object": "model", "owned_by": "openai"},
            ],
        })

    @app.route("/v1/chat/completions", methods=["POST"])
    def chat_completions():
        auth = flask_request.headers.get("Authorization", "")
        if api_key and auth != f"Bearer {api_key}":
            return jsonify({"error": {"message": "Invalid auth", "type": "auth_error", "code": "invalid_api_key"}}), 401

        if flask_request.args.get("error") == "500":
            return jsonify({"error": {"message": "Internal error", "type": "server_error", "code": "internal"}}), 500
        if flask_request.args.get("error") == "timeout":
            time.sleep(30)

        body = flask_request.get_json(silent=True) or {}

        if body.get("stream"):
            # Return SSE streaming response
            def generate():
                for i, word in enumerate(["Hello", " from", " upstream"]):
                    chunk = {
                        "id": f"chatcmpl-test-{i}",
                        "object": "chat.completion.chunk",
                        "choices": [{
                            "index": 0,
                            "delta": {"content": word},
                            "finish_reason": None,
                        }],
                    }
                    yield f"data: {json.dumps(chunk)}\n\n"
                yield "data: [DONE]\n\n"

            return Response(generate(), content_type="text/event-stream")

        # Non-streaming response
        return jsonify({
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": "Hello from upstream"},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        })

    @app.route("/v1/completions", methods=["POST"])
    def completions():
        auth = flask_request.headers.get("Authorization", "")
        if api_key and auth != f"Bearer {api_key}":
            return jsonify({"error": {"message": "Invalid auth", "type": "auth_error", "code": "invalid_api_key"}}), 401

        return jsonify({
            "id": "cmpl-test",
            "object": "text_completion",
            "choices": [{"text": "Hello from legacy completions", "index": 0, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10},
        })

    @app.route("/v1/embeddings", methods=["POST"])
    def embeddings():
        auth = flask_request.headers.get("Authorization", "")
        if api_key and auth != f"Bearer {api_key}":
            return jsonify({"error": {"message": "Invalid auth", "type": "auth_error", "code": "invalid_api_key"}}), 401

        return jsonify({
            "object": "list",
            "data": [{"object": "embedding", "index": 0, "embedding": [0.1, 0.2, 0.3]}],
            "usage": {"prompt_tokens": 5, "total_tokens": 5},
        })

    @app.route("/v1/echo-headers", methods=["GET"])
    def echo_headers():
        """Diagnostic endpoint — returns all received headers."""
        return jsonify(dict(flask_request.headers))

    return app


@pytest.fixture(scope="module")
def mock_upstream():
    """Start a mock OpenAI backend on a random port for the test module.

    Binds to ``0.0.0.0`` so the Gasket container can reach it via
    the Docker compose network.  The ``base_url`` uses the test-runner
    container's hostname so cross-container routing works.

    Yields a dict with ``port``, ``base_url``, and ``api_key``.
    """
    port = _find_free_port()
    api_key = "sk-upstream-test"
    app = _create_mock_backend(port, api_key=api_key)

    # Suppress Flask/werkzeug logging in test output
    import logging
    log = logging.getLogger("werkzeug")
    log.setLevel(logging.ERROR)

    server_thread = threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=port, use_reloader=False),
        daemon=True,
    )
    server_thread.start()

    # Wait for the mock server to be ready (check locally)
    deadline = time.time() + 10
    while time.time() < deadline:
        try:
            requests.get(f"http://127.0.0.1:{port}/v1/models", timeout=1)
            break
        except requests.ConnectionError:
            time.sleep(0.2)
    else:
        pytest.fail(f"Mock upstream did not start on port {port}")

    # Use the container hostname so Gasket can route to us
    hostname = _get_test_runner_hostname()
    base_url = f"http://{hostname}:{port}"

    yield {"port": port, "base_url": base_url, "api_key": api_key}


# ── Test fixtures ──────────────────────────────────────────────────


@pytest.fixture(scope="module")
def proxy_env(client, mock_upstream):
    """Create a backend, profile, and API key pointing at the mock upstream.

    Module-scoped so all tests share the same setup.
    """
    # Create backend pointing at mock upstream
    resp = client.post(
        "/admin/api/backends",
        json={
            "name": "proxy-fwd-backend",
            "base_url": mock_upstream["base_url"],
            "api_key": mock_upstream["api_key"],
        },
    )
    assert resp.status_code == 201, f"Failed to create backend: {resp.text}"
    backend_id = resp.json()["id"]

    # Create profile
    resp = client.post(
        "/admin/api/profiles",
        json={
            "name": "proxy-fwd-profile",
            "description": "Test profile for proxy forwarding",
            "oidc_groups": "gasket-users",
            "backend_ids": [backend_id],
            "max_keys_per_user": 10,
        },
    )
    assert resp.status_code == 201, f"Failed to create profile: {resp.text}"
    profile_id = resp.json()["id"]

    # Create API key
    resp = client.post(
        "/api/keys",
        json={
            "name": "proxy-fwd-key",
            "profile_id": profile_id,
        },
    )
    assert resp.status_code == 201, f"Failed to create key: {resp.text}"
    key_data = resp.json()
    key_id = key_data["id"]
    key_value = key_data["key_value"]

    yield {
        "backend_id": backend_id,
        "profile_id": profile_id,
        "key_id": key_id,
        "key_value": key_value,
        "mock": mock_upstream,
    }

    # Cleanup
    client.delete(f"/api/keys/{key_id}")
    client.delete(f"/admin/api/profiles/{profile_id}")
    client.delete(f"/admin/api/backends/{backend_id}")


def _auth_headers(key_value):
    """Build an Authorization header dict for a Gasket API key."""
    return {"Authorization": f"Bearer {key_value}"}


# ── Tests: Non-streaming proxy ────────────────────────────────────


class TestProxyForwardNonStreaming:
    """Non-streaming request proxying."""

    def test_chat_completions(self, client, proxy_env):
        """POST /v1/chat/completions returns upstream completion."""
        resp = client.post(
            "/v1/chat/completions",
            headers=_auth_headers(proxy_env["key_value"]),
            json={
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "hello"}],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["object"] == "chat.completion"
        assert data["choices"][0]["message"]["content"] == "Hello from upstream"
        assert data["usage"]["total_tokens"] == 15

    def test_legacy_completions(self, client, proxy_env):
        """POST /v1/completions returns upstream legacy completion."""
        resp = client.post(
            "/v1/completions",
            headers=_auth_headers(proxy_env["key_value"]),
            json={"model": "gpt-3.5-turbo", "prompt": "hello"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["object"] == "text_completion"

    def test_models_listing(self, client, proxy_env):
        """GET /v1/models returns upstream model list."""
        resp = client.get(
            "/v1/models",
            headers=_auth_headers(proxy_env["key_value"]),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["object"] == "list"
        model_ids = [m["id"] for m in data["data"]]
        assert "gpt-4" in model_ids
        assert "gpt-3.5-turbo" in model_ids

    def test_embeddings(self, client, proxy_env):
        """POST /v1/embeddings is proxied correctly."""
        resp = client.post(
            "/v1/embeddings",
            headers=_auth_headers(proxy_env["key_value"]),
            json={"model": "text-embedding-ada-002", "input": "hello"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["object"] == "list"
        assert len(data["data"][0]["embedding"]) == 3


# ── Tests: Streaming proxy ────────────────────────────────────────


class TestProxyForwardStreaming:
    """Streaming (SSE) request proxying."""

    def test_streaming_chat_completions(self, client, proxy_env):
        """POST /v1/chat/completions with stream=true returns SSE chunks."""
        resp = client.post(
            "/v1/chat/completions",
            headers=_auth_headers(proxy_env["key_value"]),
            json={
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "hello"}],
                "stream": True,
            },
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("Content-Type", "")

        # Parse SSE content
        text = resp.text
        lines = [l for l in text.strip().split("\n") if l.startswith("data: ")]
        assert len(lines) >= 3  # at least the content chunks

        # Verify the [DONE] sentinel
        assert lines[-1] == "data: [DONE]"

        # Verify content chunks are valid JSON
        content_parts = []
        for line in lines[:-1]:  # skip [DONE]
            chunk = json.loads(line[len("data: "):])
            assert chunk["object"] == "chat.completion.chunk"
            content_parts.append(chunk["choices"][0]["delta"]["content"])

        assert "".join(content_parts) == "Hello from upstream"


# ── Tests: Upstream errors ────────────────────────────────────────


class TestProxyUpstreamErrors:
    """Upstream error handling."""

    def test_upstream_500(self, client, proxy_env):
        """Upstream 500 is proxied back to the client."""
        resp = client.get(
            "/v1/models?error=500",
            headers=_auth_headers(proxy_env["key_value"]),
        )
        # The upstream returns 500 and our proxy passes it through
        assert resp.status_code == 500
        data = resp.json()
        assert "error" in data

    def test_upstream_connection_refused(self, client):
        """Backend pointing at a dead port returns 502."""
        # Create a backend on a port that is not listening
        dead_port = _find_free_port()
        resp = client.post(
            "/admin/api/backends",
            json={
                "name": "proxy-dead-backend",
                "base_url": f"http://127.0.0.1:{dead_port}",
                "api_key": "sk-dead",
            },
        )
        assert resp.status_code == 201
        backend_id = resp.json()["id"]

        resp = client.post(
            "/admin/api/profiles",
            json={
                "name": "proxy-dead-profile",
                "description": "Dead backend test",
                "oidc_groups": "gasket-users",
                "backend_ids": [backend_id],
                "max_keys_per_user": 10,
            },
        )
        assert resp.status_code == 201
        profile_id = resp.json()["id"]

        resp = client.post(
            "/api/keys",
            json={"name": "proxy-dead-key", "profile_id": profile_id},
        )
        assert resp.status_code == 201
        key_data = resp.json()
        key_id = key_data["id"]
        key_value = key_data["key_value"]

        try:
            resp = client.get(
                "/v1/models",
                headers=_auth_headers(key_value),
            )
            assert resp.status_code == 502
            data = resp.json()
            assert data["error"]["code"] == "upstream_connection_error"
        finally:
            client.delete(f"/api/keys/{key_id}")
            client.delete(f"/admin/api/profiles/{profile_id}")
            client.delete(f"/admin/api/backends/{backend_id}")


# ── Tests: Header handling ────────────────────────────────────────


class TestProxyHeaderHandling:
    """Verify correct header forwarding."""

    def test_upstream_gets_backend_api_key(self, client, proxy_env):
        """The upstream receives the backend's API key, not the Gasket key."""
        resp = client.get(
            "/v1/echo-headers",
            headers=_auth_headers(proxy_env["key_value"]),
        )
        assert resp.status_code == 200
        upstream_headers = resp.json()
        # The upstream should see the backend's API key
        assert upstream_headers.get("Authorization") == f"Bearer {proxy_env['mock']['api_key']}"

    def test_gasket_key_not_leaked(self, client, proxy_env):
        """The Gasket API key is not sent to the upstream."""
        resp = client.get(
            "/v1/echo-headers",
            headers=_auth_headers(proxy_env["key_value"]),
        )
        assert resp.status_code == 200
        upstream_headers = resp.json()
        auth = upstream_headers.get("Authorization", "")
        # Must NOT contain the gsk_ key
        assert "gsk_" not in auth


# ── Tests: Query string passthrough ───────────────────────────────


class TestProxyQueryString:
    """Verify query string passthrough."""

    def test_query_params_forwarded(self, client, proxy_env):
        """Query parameters are forwarded to the upstream."""
        # The mock /v1/models endpoint is simple — just verify it works
        # with query params (the ?error=500 test above implicitly tests this)
        resp = client.get(
            "/v1/models?some_param=value",
            headers=_auth_headers(proxy_env["key_value"]),
        )
        assert resp.status_code == 200

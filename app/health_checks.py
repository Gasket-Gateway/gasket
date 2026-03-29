"""Health-check probes for Gasket Gateway integrations."""

import time

import psycopg2
import requests


def _http_get(url, timeout=5, verify=True, headers=None):
    """Perform an HTTP GET and return (status, detail, latency_ms)."""
    # Suppress InsecureRequestWarning when skipping TLS verification
    if not verify:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    start = time.monotonic()
    try:
        resp = requests.get(url, timeout=timeout, verify=verify, headers=headers)
        latency_ms = round((time.monotonic() - start) * 1000)
        resp.raise_for_status()
        return ("connected", f"{resp.status_code} OK", latency_ms)
    except requests.exceptions.SSLError as exc:
        latency_ms = round((time.monotonic() - start) * 1000)
        return ("error", f"SSL/TLS error — check skip_tls_verify config\n\n{exc}", latency_ms)
    except requests.exceptions.ConnectionError as exc:
        latency_ms = round((time.monotonic() - start) * 1000)
        return ("error", f"Connection refused\n\n{exc}", latency_ms)
    except requests.exceptions.Timeout as exc:
        latency_ms = round((time.monotonic() - start) * 1000)
        return ("error", f"Request timed out\n\n{exc}", latency_ms)
    except requests.exceptions.HTTPError as exc:
        latency_ms = round((time.monotonic() - start) * 1000)
        return ("error", f"HTTP {exc.response.status_code}\n\n{exc}", latency_ms)
    except Exception as exc:
        latency_ms = round((time.monotonic() - start) * 1000)
        return ("error", str(exc), latency_ms)


def check_postgresql(config):
    """Test PostgreSQL connectivity with a simple SELECT 1 query."""
    db = config.get("database", {})
    start = time.monotonic()
    try:
        conn = psycopg2.connect(
            host=db.get("host", "localhost"),
            port=db.get("port", 5432),
            dbname=db.get("name", "gasket"),
            user=db.get("user", "gasket"),
            password=db.get("password", ""),
            connect_timeout=5,
        )
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()
        latency_ms = round((time.monotonic() - start) * 1000)
        return ("connected", "SELECT 1 succeeded", latency_ms)
    except Exception as exc:
        latency_ms = round((time.monotonic() - start) * 1000)
        return ("error", str(exc), latency_ms)


def check_oidc(config):
    """Test OIDC provider by fetching its discovery document."""
    oidc = config.get("oidc", {})
    provider_url = oidc.get("provider_url", "").rstrip("/")
    if not provider_url:
        return ("error", "No provider_url configured", 0)

    verify = not oidc.get("skip_tls_verify", False)
    url = f"{provider_url}/.well-known/openid-configuration"
    return _http_get(url, verify=verify)


def check_opensearch(config):
    """Test OpenSearch connectivity by hitting the root endpoint."""
    osearch = config.get("opensearch", {})
    base_url = osearch.get("url", "").rstrip("/")
    if not base_url:
        return ("error", "No OpenSearch URL configured", 0)

    verify = not osearch.get("skip_tls_verify", False)
    return _http_get(base_url, verify=verify)


def check_openai_backend(backend, default_verify=True):
    """Test a single OpenAI-compliant backend by listing models.

    Accepts either a dict or an OpenAIBackend model instance.
    """
    # Support both dict and ORM model
    if hasattr(backend, "base_url"):
        base_url = (backend.base_url or "").rstrip("/")
        name = backend.name or "unknown"
        api_key = backend.api_key or ""
        skip_tls = backend.skip_tls_verify
    else:
        base_url = backend.get("base_url", "").rstrip("/")
        name = backend.get("name", "unknown")
        api_key = backend.get("api_key", "")
        skip_tls = backend.get("skip_tls_verify", False)

    if not base_url:
        return {"name": name, "status": "error", "detail": "No base_url configured", "latency_ms": 0}

    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    verify = not skip_tls if skip_tls is not None else default_verify

    status, detail, latency_ms = _http_get(
        f"{base_url}/v1/models", verify=verify, headers=headers
    )
    return {"name": name, "status": status, "detail": detail, "latency_ms": latency_ms}


def check_openai_backends_from_db():
    """Test all OpenAI backends from the database."""
    from .backends import list_backends

    results = []
    for backend in list_backends():
        results.append(check_openai_backend(backend))
    return results


def check_openai_backends(config):
    """Test all config-defined OpenAI backends (legacy — use check_openai_backends_from_db)."""
    backends = config.get("openai_backends", [])
    results = []
    for backend in backends:
        results.append(check_openai_backend(backend))
    return results

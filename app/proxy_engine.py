"""Upstream proxy engine — forwards requests to OpenAI-compliant backends.

This module handles the actual HTTP forwarding of authenticated requests
to upstream OpenAI backends.  It is separated from the authentication
layer (:mod:`proxy`) and the route definitions (:mod:`routes.proxy`).

Responsibilities:
- Backend selection (currently first-backend; multi-backend routing later)
- Constructing and sending the upstream HTTP request
- Streaming SSE responses back to the client
- Converting upstream errors to OpenAI-compatible JSON responses
"""

import logging

import requests as upstream_requests

from flask import Response, jsonify

logger = logging.getLogger(__name__)

# Timeout for upstream requests (connect, read) in seconds.
UPSTREAM_TIMEOUT = (10, 120)

# Headers to strip when forwarding to/from the upstream backend.
# These are hop-by-hop or Gasket-internal headers.
_STRIP_REQUEST_HEADERS = frozenset({
    "host",
    "authorization",
    "connection",
    "keep-alive",
    "transfer-encoding",
    "te",
    "trailer",
    "upgrade",
    "proxy-authorization",
    "proxy-connection",
    "cookie",
})

_STRIP_RESPONSE_HEADERS = frozenset({
    "connection",
    "keep-alive",
    "transfer-encoding",
    "te",
    "trailer",
    "upgrade",
    "content-encoding",
    "content-length",
})


def select_backend(backends):
    """Select a backend from the list.

    Currently returns the first backend.  Multi-backend routing
    with sticky sessions will be implemented in a future task.

    Args:
        backends: A non-empty list of :class:`OpenAIBackend` instances.

    Returns:
        The selected :class:`OpenAIBackend`.
    """
    return backends[0]


def _build_upstream_url(backend, path, query_string):
    """Construct the full upstream URL.

    Args:
        backend: An :class:`OpenAIBackend` instance.
        path: The sub-path after ``/v1/`` (e.g. ``chat/completions``).
        query_string: The raw query string from the incoming request.

    Returns:
        The complete upstream URL string.
    """
    base = backend.base_url.rstrip("/")
    url = f"{base}/v1/{path}"
    if query_string:
        url = f"{url}?{query_string}"
    return url


def _forward_headers(incoming_headers):
    """Build a header dict to send upstream.

    Copies relevant headers from the incoming request, stripping
    hop-by-hop and Gasket-internal headers.

    Args:
        incoming_headers: The Flask request headers (a
            :class:`~werkzeug.datastructures.Headers` object).

    Returns:
        A plain dict of headers for the upstream request.
    """
    headers = {}
    for key, value in incoming_headers:
        if key.lower() not in _STRIP_REQUEST_HEADERS:
            headers[key] = value
    return headers


def _is_streaming_request(request_data):
    """Detect whether the client requested a streaming response.

    Checks for ``"stream": true`` in the request JSON body.

    Args:
        request_data: The raw request body bytes.

    Returns:
        True if the request asks for streaming.
    """
    if not request_data:
        return False
    try:
        import json

        body = json.loads(request_data)
        return bool(body.get("stream"))
    except (ValueError, AttributeError):
        return False


def _is_streaming_response(upstream_response):
    """Detect whether the upstream is sending a streaming response.

    Checks for ``text/event-stream`` content type.

    Args:
        upstream_response: A :class:`requests.Response` object.

    Returns:
        True if the upstream response is SSE.
    """
    ct = upstream_response.headers.get("Content-Type", "")
    return "text/event-stream" in ct


def _build_response_headers(upstream_response):
    """Build response headers to send back to the client.

    Strips hop-by-hop headers and headers that Flask should manage.

    Args:
        upstream_response: A :class:`requests.Response` object.

    Returns:
        A list of (key, value) tuples.
    """
    headers = []
    for key, value in upstream_response.headers.items():
        if key.lower() not in _STRIP_RESPONSE_HEADERS:
            headers.append((key, value))
    return headers


def _stream_upstream(upstream_response):
    """Generator that yields chunks from a streaming upstream response.

    Iterates over the upstream response content in 4KB chunks,
    yielding each as it arrives.

    Args:
        upstream_response: A :class:`requests.Response` object opened
            with ``stream=True``.

    Yields:
        Bytes chunks from the upstream response.
    """
    try:
        for chunk in upstream_response.iter_content(chunk_size=4096):
            if chunk:
                yield chunk
    except upstream_requests.exceptions.ChunkedEncodingError:
        logger.warning("Upstream stream closed unexpectedly")
    finally:
        upstream_response.close()


def make_upstream_error(exc):
    """Convert an upstream exception to an OpenAI-compatible error response.

    Args:
        exc: A :class:`requests.RequestException` or similar.

    Returns:
        A ``(response, status_code)`` tuple.
    """
    if isinstance(exc, upstream_requests.exceptions.ConnectTimeout):
        msg = "Upstream backend connection timed out"
        code = "upstream_timeout"
        status = 504
    elif isinstance(exc, upstream_requests.exceptions.ReadTimeout):
        msg = "Upstream backend read timed out"
        code = "upstream_timeout"
        status = 504
    elif isinstance(exc, upstream_requests.exceptions.ConnectionError):
        msg = "Could not connect to upstream backend"
        code = "upstream_connection_error"
        status = 502
    elif isinstance(exc, upstream_requests.exceptions.SSLError):
        msg = "SSL/TLS error connecting to upstream backend"
        code = "upstream_ssl_error"
        status = 502
    else:
        msg = f"Upstream request failed: {exc}"
        code = "upstream_error"
        status = 502

    logger.error("Upstream error: %s — %s", code, exc)

    return (
        jsonify(
            {
                "error": {
                    "message": msg,
                    "type": "server_error",
                    "code": code,
                }
            }
        ),
        status,
    )


def forward_request(backend, path, flask_request):
    """Forward an incoming request to the upstream backend.

    Constructs the upstream URL, copies relevant headers, sends
    the request, and returns either a buffered or streaming
    Flask response.

    Args:
        backend: An :class:`OpenAIBackend` instance.
        path: The sub-path after ``/v1/`` (e.g. ``chat/completions``).
        flask_request: The incoming :class:`flask.Request`.

    Returns:
        A Flask :class:`~flask.Response` (buffered or streaming).

    Raises:
        requests.RequestException: On upstream connection failures
            (callers should catch and convert via :func:`make_upstream_error`).
    """
    url = _build_upstream_url(backend, path, flask_request.query_string.decode("utf-8"))
    method = flask_request.method.upper()
    body = flask_request.get_data()
    headers = _forward_headers(flask_request.headers)

    # Set the upstream backend's API key
    if backend.api_key:
        headers["Authorization"] = f"Bearer {backend.api_key}"

    # Determine if the client wants streaming
    wants_stream = _is_streaming_request(body)

    verify_tls = not backend.skip_tls_verify

    logger.info(
        "Proxying %s /v1/%s → %s (stream=%s, tls_verify=%s)",
        method,
        path,
        url,
        wants_stream,
        verify_tls,
    )

    upstream_resp = upstream_requests.request(
        method=method,
        url=url,
        headers=headers,
        data=body,
        stream=wants_stream,
        timeout=UPSTREAM_TIMEOUT,
        verify=verify_tls,
    )

    response_headers = _build_response_headers(upstream_resp)

    if wants_stream and _is_streaming_response(upstream_resp):
        # Return a streaming response
        return Response(
            _stream_upstream(upstream_resp),
            status=upstream_resp.status_code,
            headers=response_headers,
            content_type=upstream_resp.headers.get("Content-Type", "text/event-stream"),
        )

    # Buffered response
    return Response(
        upstream_resp.content,
        status=upstream_resp.status_code,
        headers=response_headers,
        content_type=upstream_resp.headers.get("Content-Type", "application/json"),
    )

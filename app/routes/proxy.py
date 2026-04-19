"""Gasket Gateway — API proxy routes blueprint.

Handles ``/v1/*`` requests authenticated via ``gsk_*`` API keys.
The ``before_request`` hook validates the Bearer token and stores
the resolved context (user, profile, backends) on ``flask.g``.

Authenticated requests are forwarded to the upstream OpenAI backend
resolved from the API key's backend profile.
"""

import logging

import requests as upstream_requests

from flask import Blueprint, g, jsonify, request

from ..proxy import ProxyAuthError, validate_api_key
from ..proxy_engine import forward_request, make_upstream_error, select_backend

logger = logging.getLogger(__name__)

proxy_bp = Blueprint("proxy", __name__, url_prefix="/v1")


def _openai_error(message, error_type, code, status_code):
    """Return a JSON error response in OpenAI-compatible format.

    Format::

        {
            "error": {
                "message": "...",
                "type": "...",
                "code": "..."
            }
        }
    """
    return (
        jsonify(
            {
                "error": {
                    "message": message,
                    "type": error_type,
                    "code": code,
                }
            }
        ),
        status_code,
    )


@proxy_bp.before_request
def authenticate_api_key():
    """Extract and validate the Bearer token on every /v1/* request."""
    auth_header = request.headers.get("Authorization", "")

    if not auth_header:
        return _openai_error(
            "Missing Authorization header. Expected: Authorization: Bearer gsk_...",
            "invalid_request_error",
            "missing_api_key",
            401,
        )

    # Parse "Bearer <token>"
    parts = auth_header.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return _openai_error(
            "Malformed Authorization header. Expected: Authorization: Bearer gsk_...",
            "invalid_request_error",
            "malformed_auth_header",
            401,
        )

    token = parts[1].strip()

    try:
        context = validate_api_key(token)
    except ProxyAuthError as e:
        return _openai_error(e.message, "invalid_request_error", e.error_type, e.status_code)

    # Store resolved context for downstream route handlers
    g.proxy_context = context


@proxy_bp.route("/<path:path>", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
def proxy_catch_all(path):
    """Catch-all route for /v1/* — proxy to upstream backend.

    Authentication has already succeeded at this point (via
    before_request).  Selects a backend from the profile and
    forwards the request upstream.
    """
    ctx = g.proxy_context
    backend = select_backend(ctx["backends"])

    try:
        return forward_request(backend, path, request)
    except upstream_requests.exceptions.RequestException as exc:
        return make_upstream_error(exc)

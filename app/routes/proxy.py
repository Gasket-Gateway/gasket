"""Gasket Gateway — API proxy routes blueprint.

Handles ``/v1/*`` requests authenticated via ``gsk_*`` API keys.
The ``before_request`` hook validates the Bearer token and stores
the resolved context (user, profile, backends) on ``flask.g``.

Currently returns 501 for all authenticated requests — actual
proxying to upstream OpenAI backends will be added in a later task.
"""

import logging

from flask import Blueprint, g, jsonify, request

from ..proxy import ProxyAuthError, validate_api_key

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
    """Catch-all route for /v1/* — proxy not yet implemented.

    Authentication has already succeeded at this point (via
    before_request). Returns 501 until the upstream proxying
    logic is built.
    """
    ctx = g.proxy_context
    return _openai_error(
        f"Proxy not yet implemented. Authenticated as {ctx['user_email']} "
        f"via profile '{ctx['profile'].name}' "
        f"({len(ctx['backends'])} backend(s) available).",
        "server_error",
        "not_implemented",
        501,
    )

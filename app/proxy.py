"""API proxy authentication — key validation and context resolution.

Validates incoming ``gsk_*`` API keys against the database, checks
that the key is active (not revoked, not expired), and resolves
the associated user, backend profile, and upstream backends.

This module contains only the authentication/validation layer.
Actual request proxying to upstream backends will be added later.
"""

import logging
from datetime import datetime, timezone

from .models import ApiKey

logger = logging.getLogger(__name__)


class ProxyAuthError(Exception):
    """Raised when API key authentication fails.

    Carries structured error information for OpenAI-compatible
    JSON error responses.

    Attributes:
        status_code: HTTP status code (e.g. 401).
        error_type: Machine-readable error type string.
        message: Human-readable error description.
    """

    def __init__(self, message, status_code=401, error_type="invalid_api_key"):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_type = error_type


def validate_api_key(key_value):
    """Validate an API key and resolve its context.

    Looks up the key in the database, checks it is not revoked and
    not expired, then resolves the associated user, backend profile,
    and list of upstream backends.

    Args:
        key_value: The full API key string (e.g. ``gsk_abc123...``).

    Returns:
        A dict containing::

            {
                "api_key": <ApiKey instance>,
                "user_email": str,
                "profile": <BackendProfile instance>,
                "backends": [<OpenAIBackend>, ...],
            }

    Raises:
        ProxyAuthError: If the key is invalid, revoked, or expired.
    """
    if not key_value or not key_value.startswith("gsk_"):
        raise ProxyAuthError("Invalid API key format")

    api_key = ApiKey.query.filter_by(key_value=key_value).first()
    if not api_key:
        raise ProxyAuthError("Invalid API key")

    if api_key.revoked:
        logger.warning(
            "Rejected revoked API key %d (user: %s)",
            api_key.id,
            api_key.user_email,
        )
        raise ProxyAuthError(
            "API key has been revoked",
            error_type="revoked_api_key",
        )

    if api_key.expires_at and api_key.expires_at <= datetime.now(timezone.utc):
        logger.warning(
            "Rejected expired API key %d (user: %s, expired: %s)",
            api_key.id,
            api_key.user_email,
            api_key.expires_at.isoformat(),
        )
        raise ProxyAuthError(
            "API key has expired",
            error_type="expired_api_key",
        )

    profile = api_key.profile
    if not profile:
        logger.error(
            "API key %d has no associated profile (user: %s)",
            api_key.id,
            api_key.user_email,
        )
        raise ProxyAuthError(
            "API key configuration error — no backend profile",
            status_code=500,
            error_type="server_error",
        )

    backends = list(profile.backends)
    if not backends:
        logger.error(
            "Profile '%s' (id=%d) has no backends configured",
            profile.name,
            profile.id,
        )
        raise ProxyAuthError(
            "No backends configured for this profile",
            status_code=502,
            error_type="no_backends",
        )

    logger.info(
        "Authenticated API key %d (user: %s, profile: %s, backends: %d)",
        api_key.id,
        api_key.user_email,
        profile.name,
        len(backends),
    )

    return {
        "api_key": api_key,
        "user_email": api_key.user_email,
        "profile": profile,
        "backends": backends,
    }

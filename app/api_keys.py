"""API key data access — CRUD operations, revocation, and policy snapshots.

All functions operate within a Flask application context and use
the SQLAlchemy session from app.models.db.
"""

import logging
import secrets
from datetime import datetime, timedelta, timezone

from .models import (
    db,
    ApiKey,
    BackendProfile,
    PolicyAcceptance,
    api_key_policy_snapshots,
)
from .policies import check_all_policies_accepted

logger = logging.getLogger(__name__)


# ─── Key generation ────────────────────────────────────────────────


def _generate_key():
    """Generate a new API key with ``gsk_`` prefix.

    Returns:
        A string like ``gsk_<48 hex chars>``.
    """
    return f"gsk_{secrets.token_hex(24)}"


# ─── Read ──────────────────────────────────────────────────────────


def list_user_keys(user_email):
    """Return all API keys for a user, ordered by creation date descending."""
    return (
        ApiKey.query
        .filter_by(user_email=user_email)
        .order_by(ApiKey.created_at.desc())
        .all()
    )


def get_api_key(key_id):
    """Return a single API key by ID, or None."""
    return db.session.get(ApiKey, key_id)


def list_all_keys(user_email=None, profile_id=None):
    """Return all API keys, optionally filtered. For admin use."""
    query = ApiKey.query
    if user_email:
        query = query.filter_by(user_email=user_email)
    if profile_id is not None:
        query = query.filter_by(profile_id=profile_id)
    return query.order_by(ApiKey.created_at.desc()).all()


def get_key_policy_snapshots(key_id):
    """Return policy version snapshots for a key.

    Returns a list of dicts with policy and version info.
    """
    key = get_api_key(key_id)
    if not key:
        return []

    return [
        {
            "policy_version_id": pv.id,
            "policy_id": pv.policy_id,
            "policy_name": pv.policy.name if pv.policy else None,
            "version_number": pv.version_number,
            "content": pv.content,
        }
        for pv in key.policy_snapshots
    ]


# ─── Create ────────────────────────────────────────────────────────


def create_api_key(user_email, data):
    """Create a new API key for a user.

    Args:
        user_email: The user's email address.
        data: dict with key fields. Required: name, profile_id.
              Optional: expires_at, vscode_continue, open_webui.

    Returns:
        A tuple of (ApiKey instance, full_key_value).
        The full key is only available at creation time.

    Raises:
        ValueError: If validation fails.
    """
    name = (data.get("name") or "").strip()
    if not name:
        raise ValueError("Key name is required")

    profile_id = data.get("profile_id")
    if not profile_id:
        raise ValueError("profile_id is required")

    profile = db.session.get(BackendProfile, profile_id)
    if not profile:
        raise ValueError(f"Profile {profile_id} not found")

    # Check all policies are accepted
    policy_status = check_all_policies_accepted(user_email, profile_id)
    if not policy_status["all_accepted"]:
        pending_names = [p["policy_name"] for p in policy_status["pending"]]
        raise ValueError(
            f"All policies must be accepted before creating an API key. "
            f"Pending: {', '.join(pending_names)}"
        )

    # Check max keys per user for this profile (count non-revoked, non-expired keys)
    now = datetime.now(timezone.utc)
    active_count = (
        ApiKey.query
        .filter_by(user_email=user_email, profile_id=profile_id, revoked=False)
        .filter(
            db.or_(ApiKey.expires_at.is_(None), ApiKey.expires_at > now)
        )
        .count()
    )
    if active_count >= profile.max_keys_per_user:
        raise ValueError(
            f"Maximum of {profile.max_keys_per_user} active keys per user "
            f"for profile '{profile.name}'"
        )

    # Determine expiry
    expires_at = None
    if data.get("expires_at"):
        # User-provided expiry
        try:
            expires_at = datetime.fromisoformat(data["expires_at"])
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            raise ValueError("Invalid expires_at format; use ISO 8601")

        # Enforce profile expiry if set
        if profile.enforce_expiry and profile.default_expiry_days:
            max_expiry = now + timedelta(days=profile.default_expiry_days)
            if expires_at > max_expiry:
                raise ValueError(
                    f"Expiry cannot exceed {profile.default_expiry_days} days "
                    f"for profile '{profile.name}'"
                )
    elif profile.default_expiry_days:
        # Use profile default
        expires_at = now + timedelta(days=profile.default_expiry_days)

    # Validate open_webui opt-in
    open_webui = bool(data.get("open_webui", False))
    if open_webui and not profile.open_webui_enabled:
        raise ValueError(
            f"Open WebUI support is not enabled on profile '{profile.name}'"
        )

    # Generate the key
    key_value = _generate_key()

    api_key = ApiKey(
        user_email=user_email,
        name=name,
        key_value=key_value,
        key_preview=key_value[-4:],
        profile_id=profile_id,
        expires_at=expires_at,
        vscode_continue=bool(data.get("vscode_continue", False)),
        open_webui=open_webui,
    )

    # Snapshot the current accepted policy versions for this profile
    for entry in policy_status["accepted"]:
        # Find the PolicyAcceptance to get the actual policy_version_id
        acceptance = PolicyAcceptance.query.filter_by(
            user_email=user_email,
            profile_id=profile_id,
        ).join(PolicyAcceptance.policy_version).filter_by(
            policy_id=entry["policy_id"],
        ).first()
        if acceptance:
            api_key.policy_snapshots.append(acceptance.policy_version)

    db.session.add(api_key)
    db.session.commit()

    logger.info("Created API key '%s' for user %s (profile: %s)", name, user_email, profile.name)
    return api_key, key_value


# ─── Update ────────────────────────────────────────────────────────


def update_api_key(key_id, user_email, data):
    """Update API key settings.

    Only vscode_continue and open_webui can be edited.

    Args:
        key_id: ID of the key to update.
        user_email: The requesting user's email (must own the key).
        data: dict of fields to update.

    Returns:
        The updated ApiKey instance.

    Raises:
        ValueError: If key not found.
        PermissionError: If user doesn't own the key.
    """
    key = get_api_key(key_id)
    if not key:
        raise ValueError(f"API key {key_id} not found")
    if key.user_email != user_email:
        raise PermissionError("You can only edit your own API keys")

    if "vscode_continue" in data:
        key.vscode_continue = bool(data["vscode_continue"])

    if "open_webui" in data:
        open_webui = bool(data["open_webui"])
        if open_webui and not key.profile.open_webui_enabled:
            raise ValueError(
                f"Open WebUI support is not enabled on profile '{key.profile.name}'"
            )
        key.open_webui = open_webui

    db.session.commit()
    return key


# ─── Revoke / Restore ─────────────────────────────────────────────


def revoke_api_key(key_id, revoked_by):
    """Soft-revoke an API key.

    Args:
        key_id: ID of the key to revoke.
        revoked_by: Email of the person revoking (user or admin).

    Returns:
        The updated ApiKey instance.

    Raises:
        ValueError: If key not found or already revoked.
    """
    key = get_api_key(key_id)
    if not key:
        raise ValueError(f"API key {key_id} not found")
    if key.revoked:
        raise ValueError("API key is already revoked")

    key.revoked = True
    key.revoked_at = datetime.now(timezone.utc)
    key.revoked_by = revoked_by
    db.session.commit()

    logger.info("Revoked API key %d (by %s)", key_id, revoked_by)
    return key


def restore_api_key(key_id):
    """Restore a revoked API key (admin only).

    Expired keys cannot be restored.

    Args:
        key_id: ID of the key to restore.

    Returns:
        The restored ApiKey instance.

    Raises:
        ValueError: If key not found, not revoked, or expired.
    """
    key = get_api_key(key_id)
    if not key:
        raise ValueError(f"API key {key_id} not found")
    if not key.revoked:
        raise ValueError("API key is not revoked")

    # Check if expired
    if key.expires_at and key.expires_at <= datetime.now(timezone.utc):
        raise ValueError("Cannot restore an expired API key")

    key.revoked = False
    key.revoked_at = None
    key.revoked_by = None
    db.session.commit()

    logger.info("Restored API key %d", key_id)
    return key

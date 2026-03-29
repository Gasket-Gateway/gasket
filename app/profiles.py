"""Backend profile data access — CRUD operations.

All functions operate within a Flask application context and use
the SQLAlchemy session from app.models.db.
"""

import logging

from .models import db, BackendProfile, OpenAIBackend

logger = logging.getLogger(__name__)


# ─── Read ──────────────────────────────────────────────────────────


def list_profiles():
    """Return all backend profiles, ordered by name."""
    return BackendProfile.query.order_by(BackendProfile.name).all()


def get_profile(profile_id):
    """Return a single profile by ID, or None."""
    return db.session.get(BackendProfile, profile_id)


def get_profile_by_name(name):
    """Return a single profile by name, or None."""
    return BackendProfile.query.filter_by(name=name).first()


# ─── Create ────────────────────────────────────────────────────────


def create_profile(data):
    """Create a new backend profile.

    Args:
        data: dict with profile fields. Required: name.
              Optional: description, policy_text, oidc_groups,
              metadata_audit, content_audit, default_expiry_days,
              enforce_expiry, max_keys_per_user, open_webui_enabled,
              backend_ids (list of int).

    Returns:
        The created BackendProfile instance.

    Raises:
        ValueError: If name is missing or already exists, or if
                    a backend_id is invalid.
    """
    name = (data.get("name") or "").strip()
    if not name:
        raise ValueError("Profile name is required")

    if get_profile_by_name(name):
        raise ValueError(f"Profile with name '{name}' already exists")

    # Normalise oidc_groups: accept list or comma-separated string
    oidc_groups_raw = data.get("oidc_groups", "")
    if isinstance(oidc_groups_raw, list):
        oidc_groups = ",".join(g.strip() for g in oidc_groups_raw if g.strip())
    else:
        oidc_groups = ",".join(g.strip() for g in str(oidc_groups_raw).split(",") if g.strip())

    profile = BackendProfile(
        name=name,
        description=data.get("description", ""),
        policy_text=data.get("policy_text", ""),
        oidc_groups=oidc_groups,
        metadata_audit=data.get("metadata_audit", True),
        content_audit=data.get("content_audit", False),
        default_expiry_days=data.get("default_expiry_days"),
        enforce_expiry=data.get("enforce_expiry", False),
        max_keys_per_user=data.get("max_keys_per_user", 5),
        open_webui_enabled=data.get("open_webui_enabled", False),
    )

    # Attach backends
    backend_ids = data.get("backend_ids", [])
    if backend_ids:
        backends = OpenAIBackend.query.filter(OpenAIBackend.id.in_(backend_ids)).all()
        found_ids = {b.id for b in backends}
        missing = set(backend_ids) - found_ids
        if missing:
            raise ValueError(f"Backend IDs not found: {sorted(missing)}")
        profile.backends = backends

    db.session.add(profile)
    db.session.commit()
    return profile


# ─── Update ────────────────────────────────────────────────────────


def update_profile(profile_id, data):
    """Update an existing backend profile.

    Args:
        profile_id: ID of the profile to update.
        data: dict of fields to update.

    Returns:
        The updated BackendProfile instance.

    Raises:
        ValueError: If the profile doesn't exist, the name conflicts,
                    or a backend_id is invalid.
    """
    profile = get_profile(profile_id)
    if not profile:
        raise ValueError(f"Profile {profile_id} not found")

    # Check name uniqueness if changed
    if "name" in data:
        new_name = (data["name"] or "").strip()
        if not new_name:
            raise ValueError("Profile name is required")
        existing = get_profile_by_name(new_name)
        if existing and existing.id != profile_id:
            raise ValueError(f"Profile with name '{new_name}' already exists")

    allowed_scalars = {
        "name", "description", "policy_text",
        "metadata_audit", "content_audit", "default_expiry_days",
        "enforce_expiry", "max_keys_per_user", "open_webui_enabled",
    }

    for key, value in data.items():
        if key in allowed_scalars:
            setattr(profile, key, value)

    # Handle oidc_groups separately: accept list or comma-separated string
    if "oidc_groups" in data:
        oidc_groups_raw = data["oidc_groups"]
        if isinstance(oidc_groups_raw, list):
            profile.oidc_groups = ",".join(g.strip() for g in oidc_groups_raw if g.strip())
        else:
            profile.oidc_groups = ",".join(g.strip() for g in str(oidc_groups_raw).split(",") if g.strip())

    # Update backend associations if provided
    if "backend_ids" in data:
        backend_ids = data["backend_ids"]
        if backend_ids:
            backends = OpenAIBackend.query.filter(OpenAIBackend.id.in_(backend_ids)).all()
            found_ids = {b.id for b in backends}
            missing = set(backend_ids) - found_ids
            if missing:
                raise ValueError(f"Backend IDs not found: {sorted(missing)}")
            profile.backends = backends
        else:
            profile.backends = []

    db.session.commit()
    return profile


# ─── Delete ────────────────────────────────────────────────────────


def delete_profile(profile_id):
    """Delete a backend profile.

    Returns:
        True on success.

    Raises:
        ValueError: If the profile doesn't exist.
    """
    profile = get_profile(profile_id)
    if not profile:
        raise ValueError(f"Profile {profile_id} not found")

    db.session.delete(profile)
    db.session.commit()
    return True

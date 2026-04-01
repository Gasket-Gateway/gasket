"""Backend profile data access — CRUD operations.

All functions operate within a Flask application context and use
the SQLAlchemy session from app.models.db.
"""

import logging

from .models import db, BackendProfile, OpenAIBackend, Policy

logger = logging.getLogger(__name__)


# ─── Read ──────────────────────────────────────────────────────────


def list_profiles():
    """Return all backend profiles, ordered by name."""
    return BackendProfile.query.order_by(BackendProfile.name).all()


def list_profiles_for_groups(user_groups):
    """Return profiles whose oidc_groups overlap with the given user groups.

    The oidc_groups column stores a comma-separated string of group names.
    A profile matches if *any* of the user's groups appear in the profile's
    oidc_groups list.

    Args:
        user_groups: list of OIDC group name strings for the current user.

    Returns:
        List of matching BackendProfile instances, ordered by name.
    """
    if not user_groups:
        return []

    all_profiles = BackendProfile.query.order_by(BackendProfile.name).all()
    matched = []
    for profile in all_profiles:
        profile_groups = {
            g.strip() for g in (profile.oidc_groups or "").split(",") if g.strip()
        }
        if profile_groups & set(user_groups):
            matched.append(profile)
    return matched


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
              Optional: description, oidc_groups,
              metadata_audit, content_audit, default_expiry_days,
              enforce_expiry, max_keys_per_user, open_webui_enabled,
              backend_ids (list of int), policy_ids (list of int).

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
    oidc_groups = _normalise_oidc_groups(data.get("oidc_groups", ""))

    profile = BackendProfile(
        name=name,
        description=data.get("description", ""),
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

    # Attach policies
    policy_ids = data.get("policy_ids", [])
    if policy_ids:
        policies = Policy.query.filter(Policy.id.in_(policy_ids)).all()
        found_ids = {p.id for p in policies}
        missing = set(policy_ids) - found_ids
        if missing:
            raise ValueError(f"Policy IDs not found: {sorted(missing)}")
        profile.policies = policies

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
        "name", "description",
        "metadata_audit", "content_audit", "default_expiry_days",
        "enforce_expiry", "max_keys_per_user", "open_webui_enabled",
    }

    for key, value in data.items():
        if key in allowed_scalars:
            setattr(profile, key, value)

    # Handle oidc_groups separately: accept list or comma-separated string
    if "oidc_groups" in data:
        profile.oidc_groups = _normalise_oidc_groups(data["oidc_groups"])

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

    # Update policy associations if provided
    if "policy_ids" in data:
        policy_ids = data["policy_ids"]
        if policy_ids:
            policies = Policy.query.filter(Policy.id.in_(policy_ids)).all()
            found_ids = {p.id for p in policies}
            missing = set(policy_ids) - found_ids
            if missing:
                raise ValueError(f"Policy IDs not found: {sorted(missing)}")
            profile.policies = policies
        else:
            profile.policies = []

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


# ─── Helpers ───────────────────────────────────────────────────────


def _normalise_oidc_groups(raw):
    """Accept list or comma-separated string, return comma-separated string."""
    if isinstance(raw, list):
        return ",".join(g.strip() for g in raw if g.strip())
    return ",".join(g.strip() for g in str(raw).split(",") if g.strip())


# ─── Config seeding ───────────────────────────────────────────────


def seed_config_profiles(app):
    """Sync config-defined backend profiles into the database.

    - Upserts profiles listed in config.yaml under backend_profiles
    - Resolves backend associations by name (backends must already exist)
    - Removes config-sourced DB rows whose names are no longer in config
    - Admin-created profiles are never touched

    Must be called within a Flask application context.
    """
    config = app.config["GASKET"]
    config_profiles = config.get("backend_profiles", [])
    config_names = {p.get("name") for p in config_profiles if p.get("name")}

    with app.app_context():
        # Upsert config-defined profiles
        for entry in config_profiles:
            name = entry.get("name")
            if not name:
                logger.warning("Skipping config profile with no name: %s", entry)
                continue

            existing = get_profile_by_name(name)

            # Resolve backend associations by name
            backend_names = entry.get("backends", [])
            backends = []
            if backend_names:
                backends = OpenAIBackend.query.filter(
                    OpenAIBackend.name.in_(backend_names)
                ).all()
                found = {b.name for b in backends}
                missing = set(backend_names) - found
                if missing:
                    logger.warning(
                        "Config profile '%s' references unknown backends: %s — skipping them",
                        name,
                        sorted(missing),
                    )

            oidc_groups = _normalise_oidc_groups(entry.get("oidc_groups", ""))

            # Resolve policy associations by name
            policy_names = entry.get("policy_names", [])
            policies = []
            if policy_names:
                policies = Policy.query.filter(
                    Policy.name.in_(policy_names)
                ).all()
                found_policy_names = {p.name for p in policies}
                missing_policies = set(policy_names) - found_policy_names
                if missing_policies:
                    logger.warning(
                        "Config profile '%s' references unknown policies: %s — skipping them",
                        name,
                        sorted(missing_policies),
                    )

            if existing:
                if existing.source == "config":
                    # Update config-sourced profile to match config
                    existing.description = entry.get("description", existing.description)
                    existing.oidc_groups = oidc_groups or existing.oidc_groups
                    existing.metadata_audit = entry.get("metadata_audit", existing.metadata_audit)
                    existing.content_audit = entry.get("content_audit", existing.content_audit)
                    existing.default_expiry_days = entry.get("default_expiry_days", existing.default_expiry_days)
                    existing.enforce_expiry = entry.get("enforce_expiry", existing.enforce_expiry)
                    existing.max_keys_per_user = entry.get("max_keys_per_user", existing.max_keys_per_user)
                    existing.open_webui_enabled = entry.get("open_webui_enabled", existing.open_webui_enabled)
                    if backend_names:
                        existing.backends = backends
                    if policy_names:
                        existing.policies = policies
                    logger.info("Updated config profile: %s", name)
                else:
                    logger.warning(
                        "Config profile '%s' conflicts with admin-created profile — skipping",
                        name,
                    )
            else:
                profile = BackendProfile(
                    name=name,
                    description=entry.get("description", ""),
                    oidc_groups=oidc_groups,
                    source="config",
                    metadata_audit=entry.get("metadata_audit", True),
                    content_audit=entry.get("content_audit", False),
                    default_expiry_days=entry.get("default_expiry_days"),
                    enforce_expiry=entry.get("enforce_expiry", False),
                    max_keys_per_user=entry.get("max_keys_per_user", 5),
                    open_webui_enabled=entry.get("open_webui_enabled", False),
                )
                profile.backends = backends
                profile.policies = policies
                db.session.add(profile)
                logger.info("Seeded config profile: %s", name)

        # Remove stale config-sourced profiles
        stale = BackendProfile.query.filter(
            BackendProfile.source == "config",
            ~BackendProfile.name.in_(config_names) if config_names else True,
        ).all()
        for profile in stale:
            logger.info("Removing stale config profile: %s", profile.name)
            db.session.delete(profile)

        db.session.commit()


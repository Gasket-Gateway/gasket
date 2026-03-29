"""OpenAI backend data access — CRUD operations and config seeding.

All functions operate within a Flask application context and use
the SQLAlchemy session from app.models.db.
"""

import logging

from .models import db, OpenAIBackend

logger = logging.getLogger(__name__)


# ─── Read ──────────────────────────────────────────────────────────


def list_backends():
    """Return all OpenAI backends, ordered by name."""
    return OpenAIBackend.query.order_by(OpenAIBackend.name).all()


def get_backend(backend_id):
    """Return a single backend by ID, or None."""
    return db.session.get(OpenAIBackend, backend_id)


def get_backend_by_name(name):
    """Return a single backend by name, or None."""
    return OpenAIBackend.query.filter_by(name=name).first()


# ─── Create ────────────────────────────────────────────────────────


def create_backend(name, base_url, api_key="", skip_tls_verify=False):
    """Create a new admin-sourced backend.

    Returns:
        The created OpenAIBackend instance.

    Raises:
        ValueError: If a backend with that name already exists.
    """
    if get_backend_by_name(name):
        raise ValueError(f"Backend with name '{name}' already exists")

    backend = OpenAIBackend(
        name=name,
        base_url=base_url,
        api_key=api_key,
        skip_tls_verify=skip_tls_verify,
        source="admin",
    )
    db.session.add(backend)
    db.session.commit()
    return backend


# ─── Update ────────────────────────────────────────────────────────


def update_backend(backend_id, **fields):
    """Update an admin-sourced backend.

    Updatable fields: name, base_url, api_key, skip_tls_verify.

    Returns:
        The updated OpenAIBackend instance.

    Raises:
        ValueError: If the backend doesn't exist.
        PermissionError: If the backend is config-sourced (read-only).
    """
    backend = get_backend(backend_id)
    if not backend:
        raise ValueError(f"Backend {backend_id} not found")
    if backend.source == "config":
        raise PermissionError("Config-defined backends are read-only")

    allowed = {"name", "base_url", "api_key", "skip_tls_verify"}
    for key, value in fields.items():
        if key in allowed:
            setattr(backend, key, value)

    # Check uniqueness if name changed
    if "name" in fields:
        existing = get_backend_by_name(fields["name"])
        if existing and existing.id != backend_id:
            raise ValueError(f"Backend with name '{fields['name']}' already exists")

    db.session.commit()
    return backend


# ─── Delete ────────────────────────────────────────────────────────


def delete_backend(backend_id):
    """Delete an admin-sourced backend.

    Returns:
        True on success.

    Raises:
        ValueError: If the backend doesn't exist.
        PermissionError: If the backend is config-sourced (read-only).
    """
    backend = get_backend(backend_id)
    if not backend:
        raise ValueError(f"Backend {backend_id} not found")
    if backend.source == "config":
        raise PermissionError("Config-defined backends are read-only")

    db.session.delete(backend)
    db.session.commit()
    return True


# ─── Config seeding ────────────────────────────────────────────────


def seed_config_backends(app):
    """Sync config-defined backends into the database.

    - Upserts backends listed in config.yaml under openai_backends
    - Removes config-sourced DB rows whose names are no longer in config
    - Admin-created backends are never touched

    Must be called within a Flask application context.
    """
    config = app.config["GASKET"]
    config_backends = config.get("openai_backends", [])
    config_names = {b.get("name") for b in config_backends if b.get("name")}

    with app.app_context():
        # Upsert config-defined backends
        for entry in config_backends:
            name = entry.get("name")
            if not name:
                logger.warning("Skipping config backend with no name: %s", entry)
                continue

            existing = get_backend_by_name(name)
            if existing:
                if existing.source == "config":
                    # Update config-sourced backend to match config
                    existing.base_url = entry.get("base_url", existing.base_url)
                    existing.api_key = entry.get("api_key", existing.api_key)
                    existing.skip_tls_verify = entry.get("skip_tls_verify", existing.skip_tls_verify)
                    logger.info("Updated config backend: %s", name)
                else:
                    logger.warning(
                        "Config backend '%s' conflicts with admin-created backend — skipping",
                        name,
                    )
            else:
                backend = OpenAIBackend(
                    name=name,
                    base_url=entry.get("base_url", ""),
                    api_key=entry.get("api_key", ""),
                    skip_tls_verify=entry.get("skip_tls_verify", False),
                    source="config",
                )
                db.session.add(backend)
                logger.info("Seeded config backend: %s", name)

        # Remove stale config-sourced backends
        stale = OpenAIBackend.query.filter(
            OpenAIBackend.source == "config",
            ~OpenAIBackend.name.in_(config_names) if config_names else True,
        ).all()
        for backend in stale:
            logger.info("Removing stale config backend: %s", backend.name)
            db.session.delete(backend)

        db.session.commit()

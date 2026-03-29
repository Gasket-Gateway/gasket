"""Database initialisation and migration runner for Gasket Gateway.

Provides:
- get_database_url() — builds a PostgreSQL URL from Gasket config
- init_db()          — configures Flask-SQLAlchemy on the Flask app
- run_migrations()   — runs Alembic migrations on startup
"""

import os
import logging

from alembic import command
from alembic.config import Config

logger = logging.getLogger(__name__)


def get_database_url(config):
    """Build a PostgreSQL connection URL from Gasket's config dict.

    Args:
        config: The full Gasket configuration dict (from load_config).
    """
    db = config.get("database", {})
    return "postgresql://{user}:{password}@{host}:{port}/{name}".format(
        user=db.get("user", "gasket"),
        password=db.get("password", ""),
        host=db.get("host", "localhost"),
        port=db.get("port", 5432),
        name=db.get("name", "gasket"),
    )


def init_db(app):
    """Initialise Flask-SQLAlchemy on the Flask application.

    Must be called after app.config["GASKET"] is set.
    """
    from .models import db

    gasket_config = app.config["GASKET"]
    app.config["SQLALCHEMY_DATABASE_URI"] = get_database_url(gasket_config)
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)


def run_migrations():
    """Run any pending Alembic migrations.

    Reads GASKET_CONFIG to locate config.yaml, builds the database URL,
    and runs `alembic upgrade head`.
    """
    # Locate alembic.ini relative to this file
    gasket_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    alembic_ini = os.path.join(gasket_root, "alembic.ini")

    if not os.path.isfile(alembic_ini):
        logger.warning("alembic.ini not found at %s — skipping migrations", alembic_ini)
        return

    alembic_cfg = Config(alembic_ini)

    try:
        logger.info("Running database migrations...")
        command.upgrade(alembic_cfg, "head")
        logger.info("Database migrations complete.")
    except Exception as e:
        logger.error("Database migration failed: %s", e)
        raise

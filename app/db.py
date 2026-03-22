"""Database migration runner for Gasket Gateway.

Runs Alembic migrations programmatically using Gasket's config.yaml
for database connection settings. Called during app startup to ensure
the schema is up to date.
"""

import os
import logging

from alembic import command
from alembic.config import Config

logger = logging.getLogger(__name__)


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

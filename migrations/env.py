"""Alembic environment configuration for Gasket Gateway.

Reads database connection settings from Gasket's config.yaml
(via GASKET_CONFIG env var) so migrations use the same DB as the app.
"""

import os
import sys
from logging.config import fileConfig

from alembic import context

# Add the gasket root to the path so we can import app.config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import load_config

# Alembic Config object
config = context.config

# Set up logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# No SQLAlchemy models — we use raw SQL migrations
target_metadata = None


def get_database_url():
    """Build a PostgreSQL URL from Gasket's config.yaml."""
    config_path = os.environ.get("GASKET_CONFIG", "/etc/gasket/config.yaml")
    gasket_config = load_config(config_path)
    db = gasket_config.get("database", {})
    return "postgresql://{user}:{password}@{host}:{port}/{name}".format(
        user=db.get("user", "gasket"),
        password=db.get("password", ""),
        host=db.get("host", "localhost"),
        port=db.get("port", 5432),
        name=db.get("name", "gasket"),
    )


def run_migrations_offline():
    """Run migrations in 'offline' mode — generates SQL without connecting."""
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations against a live database connection."""
    from sqlalchemy import engine_from_config, pool

    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_database_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

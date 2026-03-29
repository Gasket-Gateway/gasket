"""Initial database schema — creates the Gasket database structure.

Revision ID: 0001
Revises: -
Create Date: 2026-03-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the initial Gasket database schema."""
    op.create_table(
        "openai_backends",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=False),
        sa.Column("api_key", sa.Text(), nullable=False, server_default=""),
        sa.Column("skip_tls_verify", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("source", sa.Text(), nullable=False, server_default="admin"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "backend_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("policy_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("oidc_groups", sa.Text(), nullable=False, server_default=""),
        sa.Column("metadata_audit", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("content_audit", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("default_expiry_days", sa.Integer(), nullable=True),
        sa.Column("enforce_expiry", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("max_keys_per_user", sa.Integer(), nullable=False, server_default=sa.text("5")),
        sa.Column("open_webui_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "profile_backends",
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("backend_profiles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("backend_id", sa.Integer(), sa.ForeignKey("openai_backends.id", ondelete="CASCADE"), primary_key=True),
    )


def downgrade() -> None:
    """Remove the initial Gasket database schema."""
    op.drop_table("profile_backends")
    op.drop_table("backend_profiles")
    op.drop_table("openai_backends")

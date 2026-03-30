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
        sa.Column("oidc_groups", sa.Text(), nullable=False, server_default=""),
        sa.Column("source", sa.Text(), nullable=False, server_default="admin"),
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

    # ── Policies ──

    op.create_table(
        "policies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("source", sa.Text(), nullable=False, server_default="admin"),
        sa.Column("enforce_reacceptance", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "policy_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("policy_id", sa.Integer(), sa.ForeignKey("policies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("policy_id", "version_number"),
    )

    op.create_table(
        "profile_policies",
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("backend_profiles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("policy_id", sa.Integer(), sa.ForeignKey("policies.id", ondelete="CASCADE"), primary_key=True),
    )

    op.create_table(
        "policy_acceptances",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_email", sa.Text(), nullable=False),
        sa.Column("policy_version_id", sa.Integer(), sa.ForeignKey("policy_versions.id"), nullable=False),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("backend_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # ── API Keys ──

    op.create_table(
        "api_keys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_email", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("key_value", sa.Text(), nullable=False),
        sa.Column("key_preview", sa.Text(), nullable=False),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("backend_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.Text(), nullable=True),
        sa.Column("vscode_continue", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("open_webui", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("key_value"),
    )

    op.create_table(
        "api_key_policy_snapshots",
        sa.Column("api_key_id", sa.Integer(), sa.ForeignKey("api_keys.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("policy_version_id", sa.Integer(), sa.ForeignKey("policy_versions.id"), primary_key=True),
    )


def downgrade() -> None:
    """Remove the initial Gasket database schema."""
    op.drop_table("api_key_policy_snapshots")
    op.drop_table("api_keys")
    op.drop_table("policy_acceptances")
    op.drop_table("profile_policies")
    op.drop_table("policy_versions")
    op.drop_table("policies")
    op.drop_table("profile_backends")
    op.drop_table("backend_profiles")
    op.drop_table("openai_backends")

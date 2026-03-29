"""Gasket Gateway — SQLAlchemy ORM model definitions.

All database tables are defined here as SQLAlchemy models.
The `db` instance is imported by other modules for session access.
"""

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class OpenAIBackend(db.Model):
    """An upstream OpenAI-compliant inference endpoint.

    Backends can be created via the admin portal (source='admin') or
    pre-defined in config.yaml (source='config'). Config-defined backends
    are read-only in the admin UI.
    """

    __tablename__ = "openai_backends"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False, unique=True)
    base_url = db.Column(db.Text, nullable=False)
    api_key = db.Column(db.Text, nullable=False, server_default="")
    skip_tls_verify = db.Column(db.Boolean, nullable=False, server_default=db.text("false"))
    source = db.Column(db.Text, nullable=False, server_default="admin")
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=db.func.now(),
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=db.func.now(),
        onupdate=db.func.now(),
    )

    def to_dict(self, mask_key=True):
        """Serialise to a JSON-safe dict.

        Args:
            mask_key: If True, mask the API key in the output.
        """
        api_key = self.api_key or ""
        if mask_key and api_key:
            if len(api_key) > 8:
                api_key = api_key[:4] + "…" + api_key[-4:]
            else:
                api_key = "••••"

        return {
            "id": self.id,
            "name": self.name,
            "base_url": self.base_url,
            "api_key": api_key,
            "skip_tls_verify": self.skip_tls_verify,
            "source": self.source,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<OpenAIBackend {self.name!r} ({self.source})>"


# ── Association table: many-to-many between profiles and backends ──

profile_backends = db.Table(
    "profile_backends",
    db.Column("profile_id", db.Integer, db.ForeignKey("backend_profiles.id", ondelete="CASCADE"), primary_key=True),
    db.Column("backend_id", db.Integer, db.ForeignKey("openai_backends.id", ondelete="CASCADE"), primary_key=True),
)


class BackendProfile(db.Model):
    """A backend profile governing access to one or more OpenAI backends.

    Profiles define policy text, audit settings, expiry rules, quotas,
    and which OIDC group grants access.
    """

    __tablename__ = "backend_profiles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False, unique=True)
    description = db.Column(db.Text, nullable=False, server_default="")
    policy_text = db.Column(db.Text, nullable=False, server_default="")
    oidc_groups = db.Column(db.Text, nullable=False, server_default="")

    # Audit settings
    metadata_audit = db.Column(db.Boolean, nullable=False, server_default=db.text("true"))
    content_audit = db.Column(db.Boolean, nullable=False, server_default=db.text("false"))

    # API key settings
    default_expiry_days = db.Column(db.Integer, nullable=True)
    enforce_expiry = db.Column(db.Boolean, nullable=False, server_default=db.text("false"))
    max_keys_per_user = db.Column(db.Integer, nullable=False, server_default=db.text("5"))

    # Open WebUI
    open_webui_enabled = db.Column(db.Boolean, nullable=False, server_default=db.text("false"))

    # Timestamps
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=db.func.now(),
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=db.func.now(),
        onupdate=db.func.now(),
    )

    # Relationships
    backends = db.relationship(
        "OpenAIBackend",
        secondary=profile_backends,
        backref=db.backref("profiles", lazy="dynamic"),
        lazy="selectin",
    )

    def to_dict(self):
        """Serialise to a JSON-safe dict."""
        # Split comma-separated groups into a list, filtering blanks
        groups_raw = self.oidc_groups or ""
        groups_list = [g.strip() for g in groups_raw.split(",") if g.strip()]

        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "policy_text": self.policy_text,
            "oidc_groups": groups_list,
            "metadata_audit": self.metadata_audit,
            "content_audit": self.content_audit,
            "default_expiry_days": self.default_expiry_days,
            "enforce_expiry": self.enforce_expiry,
            "max_keys_per_user": self.max_keys_per_user,
            "open_webui_enabled": self.open_webui_enabled,
            "backend_ids": [b.id for b in self.backends],
            "backend_names": [b.name for b in self.backends],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<BackendProfile {self.name!r}>"

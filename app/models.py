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


# ── Association table: many-to-many between profiles and policies ──

profile_policies = db.Table(
    "profile_policies",
    db.Column("profile_id", db.Integer, db.ForeignKey("backend_profiles.id", ondelete="CASCADE"), primary_key=True),
    db.Column("policy_id", db.Integer, db.ForeignKey("policies.id", ondelete="CASCADE"), primary_key=True),
)


class BackendProfile(db.Model):
    """A backend profile governing access to one or more OpenAI backends.

    Profiles define audit settings, expiry rules, quotas,
    and which OIDC group grants access. Policies are assigned separately.
    """

    __tablename__ = "backend_profiles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False, unique=True)
    description = db.Column(db.Text, nullable=False, server_default="")
    oidc_groups = db.Column(db.Text, nullable=False, server_default="")
    source = db.Column(db.Text, nullable=False, server_default="admin")

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

    policies = db.relationship(
        "Policy",
        secondary=profile_policies,
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
            "oidc_groups": groups_list,
            "source": self.source,
            "metadata_audit": self.metadata_audit,
            "content_audit": self.content_audit,
            "default_expiry_days": self.default_expiry_days,
            "enforce_expiry": self.enforce_expiry,
            "max_keys_per_user": self.max_keys_per_user,
            "open_webui_enabled": self.open_webui_enabled,
            "backend_ids": [b.id for b in self.backends],
            "backend_names": [b.name for b in self.backends],
            "policy_ids": [p.id for p in self.policies],
            "policy_names": [p.name for p in self.policies],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<BackendProfile {self.name!r}>"


class Policy(db.Model):
    """A policy that users must accept before creating API keys.

    Policies can be created via the admin portal (source='admin') or
    pre-defined in config.yaml (source='config'). Config-defined policies
    are read-only and always have enforce_reacceptance=False.
    """

    __tablename__ = "policies"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False, unique=True)
    description = db.Column(db.Text, nullable=False, server_default="")
    source = db.Column(db.Text, nullable=False, server_default="admin")
    enforce_reacceptance = db.Column(db.Boolean, nullable=False, server_default=db.text("false"))
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
    versions = db.relationship(
        "PolicyVersion",
        backref="policy",
        lazy="selectin",
        order_by="PolicyVersion.version_number",
        cascade="all, delete-orphan",
    )

    def current_version(self):
        """Return the latest PolicyVersion, or None."""
        if self.versions:
            return self.versions[-1]
        return None

    def to_dict(self, include_versions=False):
        """Serialise to a JSON-safe dict."""
        current = self.current_version()
        result = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "source": self.source,
            "enforce_reacceptance": self.enforce_reacceptance,
            "current_version": current.version_number if current else None,
            "current_content": current.content if current else None,
            "profile_ids": [p.id for p in self.profiles],
            "profile_names": [p.name for p in self.profiles],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_versions:
            result["versions"] = [v.to_dict() for v in self.versions]
        return result

    def __repr__(self):
        return f"<Policy {self.name!r} ({self.source})>"


class PolicyVersion(db.Model):
    """An immutable snapshot of a policy's content at a point in time."""

    __tablename__ = "policy_versions"

    id = db.Column(db.Integer, primary_key=True)
    policy_id = db.Column(db.Integer, db.ForeignKey("policies.id", ondelete="CASCADE"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    version_number = db.Column(db.Integer, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=db.func.now(),
    )

    __table_args__ = (
        db.UniqueConstraint("policy_id", "version_number"),
    )

    def to_dict(self):
        """Serialise to a JSON-safe dict."""
        return {
            "id": self.id,
            "policy_id": self.policy_id,
            "content": self.content,
            "version_number": self.version_number,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<PolicyVersion policy_id={self.policy_id} v{self.version_number}>"


class PolicyAcceptance(db.Model):
    """A record of a user accepting a specific policy version for a profile."""

    __tablename__ = "policy_acceptances"

    id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.Text, nullable=False)
    policy_version_id = db.Column(db.Integer, db.ForeignKey("policy_versions.id"), nullable=False)
    profile_id = db.Column(db.Integer, db.ForeignKey("backend_profiles.id", ondelete="CASCADE"), nullable=False)
    accepted_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=db.func.now(),
    )

    # Relationships
    policy_version = db.relationship("PolicyVersion", lazy="selectin")
    profile = db.relationship("BackendProfile", lazy="selectin")

    def to_dict(self):
        """Serialise to a JSON-safe dict."""
        return {
            "id": self.id,
            "user_email": self.user_email,
            "policy_version_id": self.policy_version_id,
            "policy_name": self.policy_version.policy.name if self.policy_version and self.policy_version.policy else None,
            "version_number": self.policy_version.version_number if self.policy_version else None,
            "profile_id": self.profile_id,
            "profile_name": self.profile.name if self.profile else None,
            "accepted_at": self.accepted_at.isoformat() if self.accepted_at else None,
        }

    def __repr__(self):
        return f"<PolicyAcceptance user={self.user_email!r} version_id={self.policy_version_id}>"

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

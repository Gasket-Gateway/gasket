"""Health check endpoint."""

from flask import Blueprint

health_bp = Blueprint("health", __name__)


@health_bp.route("/health")
def health():
    """Return 200 OK for load balancer health checks."""
    return "OK", 200

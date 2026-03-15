"""Lightweight metrics server on a separate port.

Serves /health and /metrics endpoints on the metrics port (default 9050).
In production, metrics are aggregated across all instances via PostgreSQL.
"""

from flask import Flask


def create_metrics_app(app_config=None):
    """Create a minimal Flask app for the metrics endpoint."""
    metrics_app = Flask(__name__)

    @metrics_app.route("/health")
    def health():
        return "OK", 200

    @metrics_app.route("/metrics")
    def metrics():
        # Stub — will be replaced with prometheus_client + PostgreSQL aggregation
        return "# HELP gasket_up Gasket instance is running\n# TYPE gasket_up gauge\ngasket_up 1\n", 200, {"Content-Type": "text/plain; charset=utf-8"}

    return metrics_app

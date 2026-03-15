"""Gasket Gateway — Flask application factory."""

import os
import threading

from flask import Flask

from .config import load_config


def create_app(config_path=None):
    """Create and configure the Flask application."""
    app = Flask(
        __name__,
        static_folder="static",
        template_folder="templates",
    )

    # Load configuration
    if config_path is None:
        config_path = os.environ.get("GASKET_CONFIG", "/etc/gasket/config.yaml")
    app_config = load_config(config_path)
    app.config["GASKET"] = app_config

    # Register blueprints
    from .routes.health import health_bp
    from .routes.ui_demo import ui_demo_bp
    from .routes.errors import errors_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(ui_demo_bp)
    app.register_blueprint(errors_bp)

    # Inject template context
    @app.context_processor
    def inject_gasket_config():
        return {
            "gasket_config": app_config,
            "default_theme": app_config.get("default_theme", "light"),
            "banner": app_config.get("banner", {}),
        }

    return app


def start_metrics_server(app_config):
    """Start the metrics server in a background thread."""
    from .metrics_server import create_metrics_app

    metrics_app = create_metrics_app(app_config)
    port = app_config.get("server", {}).get("metrics_port", 9050)

    def run():
        metrics_app.run(host="0.0.0.0", port=port, use_reloader=False)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread

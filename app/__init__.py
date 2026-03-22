"""Gasket Gateway — Flask application factory."""

import os
import threading

from flask import Flask, session

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

    # Run database migrations on startup
    from .db import run_migrations

    run_migrations()

    # Initialise OIDC authentication
    from .auth import init_oidc, auth_bp

    init_oidc(app)

    # Register blueprints
    from .routes.health import health_bp
    from .routes.portal import portal_bp
    from .routes.admin import admin_bp
    from .routes.ui_demo import ui_demo_bp
    from .routes.errors import errors_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(portal_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(ui_demo_bp)
    app.register_blueprint(errors_bp)

    # Inject template context
    @app.context_processor
    def inject_gasket_config():
        admin_group = (
            app_config.get("oidc", {})
            .get("groups", {})
            .get("admin_access", "gasket-admins")
        )
        user_groups = session.get("user_groups", [])
        return {
            "gasket_config": app_config,
            "default_theme": app_config.get("default_theme", "light"),
            "banners": app_config.get("banners", []),
            "is_admin": admin_group in user_groups,
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

"""Gasket Gateway — Flask application factory."""

import logging
import os
import threading
import time
from logging.handlers import RotatingFileHandler

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

    # Configure file logging if the logs directory exists
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
    if os.path.isdir(log_dir):
        file_handler = RotatingFileHandler(
            os.path.join(log_dir, "gasket.log"),
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
        )
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s [%(name)s] %(message)s"
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)

        # Also send werkzeug (Flask request) logs to the file
        logging.getLogger("werkzeug").addHandler(file_handler)

        # Log each request with method, path, status, and duration
        @app.before_request
        def _log_request_start():
            from flask import g, request as req
            g._request_start = time.time()

        @app.after_request
        def _log_request(response):
            from flask import g, request as req
            duration = (time.time() - getattr(g, "_request_start", time.time())) * 1000
            app.logger.info(
                "%s %s %s (%.1fms)",
                req.method, req.path, response.status_code, duration,
            )
            return response

    # Initialise SQLAlchemy
    from .db import init_db, run_migrations

    init_db(app)

    # Run database migrations on startup
    run_migrations()

    # Seed config-defined backends into the database
    from .backends import seed_config_backends

    seed_config_backends(app)

    # Seed config-defined policies into the database
    from .policies import seed_config_policies

    seed_config_policies(app)

    # Seed config-defined backend profiles into the database
    from .profiles import seed_config_profiles

    seed_config_profiles(app)

    # Test mode — bypass OIDC and inject a mock admin session
    if os.environ.get("GASKET_TEST_MODE"):
        app.secret_key = "test-secret-key"

        @app.before_request
        def inject_test_session():
            from flask import request as req

            # Don't auto-inject on test control endpoints
            if req.path.startswith("/test/"):
                return
            # Don't auto-inject if session was deliberately cleared
            if session.get("_test_anon"):
                return
            if "user_email" not in session:
                session["user_email"] = "user3@localhost"
                session["user_name"] = "user3"
                session["user_groups"] = ["gasket-users", "gasket-admins"]
                session["login_time"] = time.time()
    else:
        # Initialise OIDC authentication
        from .auth import init_oidc

        init_oidc(app)

    # Register blueprints (auth_bp is always needed for route definitions)
    from .auth import auth_bp
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

    # Test session control — only in test mode
    if os.environ.get("GASKET_TEST_MODE"):
        from .routes.test_session import test_session_bp

        app.register_blueprint(test_session_bp)

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

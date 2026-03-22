"""Admin panel — restricted to gasket-admins group."""

from concurrent.futures import ThreadPoolExecutor

from flask import Blueprint, current_app, jsonify, render_template

from ..auth import login_required, groups_required
from ..health_checks import (
    check_postgresql,
    check_oidc,
    check_opensearch,
    check_openai_backends,
)

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/admin")
@login_required
@groups_required("gasket-admins")
def admin_page():
    """Render the admin panel page."""
    return render_template("admin.html")


@admin_bp.route("/admin/api/status")
@login_required
@groups_required("gasket-admins")
def admin_status():
    """Return connection status for all integrations as JSON."""
    config = current_app.config["GASKET"]

    checks = {
        "postgresql": lambda: check_postgresql(config),
        "oidc": lambda: check_oidc(config),
        "opensearch": lambda: check_opensearch(config),
    }

    results = {}
    with ThreadPoolExecutor(max_workers=len(checks)) as pool:
        futures = {name: pool.submit(fn) for name, fn in checks.items()}
        for name, future in futures.items():
            status, detail, latency_ms = future.result(timeout=10)
            results[name] = {"status": status, "detail": detail, "latency_ms": latency_ms}

    # OpenAI backends checked separately (variable count)
    results["openai_backends"] = check_openai_backends(config)

    return jsonify(results)


@admin_bp.route("/admin/api/status/<service>")
@login_required
@groups_required("gasket-admins")
def admin_status_single(service):
    """Return connection status for a single integration as JSON."""
    config = current_app.config["GASKET"]

    checks = {
        "postgresql": lambda: check_postgresql(config),
        "oidc": lambda: check_oidc(config),
        "opensearch": lambda: check_opensearch(config),
    }

    if service in checks:
        status, detail, latency_ms = checks[service]()
        return jsonify({"status": status, "detail": detail, "latency_ms": latency_ms})

    # Check if it's an OpenAI backend by name
    from ..health_checks import check_openai_backend
    for backend in config.get("openai_backends", []):
        if backend.get("name") == service:
            return jsonify(check_openai_backend(backend))

    return jsonify({"status": "error", "detail": f"Unknown service: {service}", "latency_ms": 0}), 404

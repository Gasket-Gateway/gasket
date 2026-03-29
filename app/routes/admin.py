"""Admin panel — restricted to gasket-admins group."""

from concurrent.futures import ThreadPoolExecutor

from flask import Blueprint, current_app, jsonify, render_template, request

from ..auth import login_required, groups_required
from ..health_checks import (
    check_postgresql,
    check_oidc,
    check_opensearch,
    check_openai_backends_from_db,
    check_openai_backend,
)

admin_bp = Blueprint("admin", __name__)


# ─── Pages ─────────────────────────────────────────────────────────


@admin_bp.route("/admin")
@login_required
@groups_required("gasket-admins")
def admin_page():
    """Render the admin panel page."""
    return render_template("admin.html")


# ─── System status ─────────────────────────────────────────────────


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

    # OpenAI backends checked from the database
    results["openai_backends"] = check_openai_backends_from_db()

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
    from ..backends import get_backend_by_name

    backend = get_backend_by_name(service)
    if backend:
        return jsonify(check_openai_backend(backend))

    return jsonify({"status": "error", "detail": f"Unknown service: {service}", "latency_ms": 0}), 404


# ─── OpenAI Backends CRUD ──────────────────────────────────────────


@admin_bp.route("/admin/api/backends")
@login_required
@groups_required("gasket-admins")
def list_backends_api():
    """List all OpenAI backends."""
    from ..backends import list_backends

    backends = list_backends()
    return jsonify([b.to_dict(mask_key=True) for b in backends])


@admin_bp.route("/admin/api/backends", methods=["POST"])
@login_required
@groups_required("gasket-admins")
def create_backend_api():
    """Create a new admin-sourced OpenAI backend."""
    from ..backends import create_backend

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    name = (data.get("name") or "").strip()
    base_url = (data.get("base_url") or "").strip()
    if not name or not base_url:
        return jsonify({"error": "name and base_url are required"}), 400

    api_key = data.get("api_key", "")
    skip_tls_verify = bool(data.get("skip_tls_verify", False))

    try:
        backend = create_backend(name, base_url, api_key, skip_tls_verify)
    except ValueError as e:
        return jsonify({"error": str(e)}), 409

    current_app.logger.info("Admin created backend: %s", name)
    return jsonify(backend.to_dict(mask_key=False)), 201


@admin_bp.route("/admin/api/backends/<int:backend_id>")
@login_required
@groups_required("gasket-admins")
def get_backend_api(backend_id):
    """Get a single OpenAI backend (full API key for edit form)."""
    from ..backends import get_backend

    backend = get_backend(backend_id)
    if not backend:
        return jsonify({"error": "Backend not found"}), 404

    return jsonify(backend.to_dict(mask_key=False))


@admin_bp.route("/admin/api/backends/<int:backend_id>", methods=["PUT"])
@login_required
@groups_required("gasket-admins")
def update_backend_api(backend_id):
    """Update an admin-sourced backend."""
    from ..backends import update_backend

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    try:
        backend = update_backend(backend_id, **data)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404 if "not found" in str(e).lower() else 409
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403

    current_app.logger.info("Admin updated backend: %s", backend.name)
    return jsonify(backend.to_dict(mask_key=False))


@admin_bp.route("/admin/api/backends/<int:backend_id>", methods=["DELETE"])
@login_required
@groups_required("gasket-admins")
def delete_backend_api(backend_id):
    """Delete an admin-sourced backend."""
    from ..backends import get_backend, delete_backend

    backend = get_backend(backend_id)
    if not backend:
        return jsonify({"error": "Backend not found"}), 404

    try:
        delete_backend(backend_id)
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403

    current_app.logger.info("Admin deleted backend: %s", backend.name)
    return jsonify({"message": f"Backend '{backend.name}' deleted"})


# ─── Backend Profiles CRUD ─────────────────────────────────────────


@admin_bp.route("/admin/api/profiles")
@login_required
@groups_required("gasket-admins")
def list_profiles_api():
    """List all backend profiles."""
    from ..profiles import list_profiles

    profiles = list_profiles()
    return jsonify([p.to_dict() for p in profiles])


@admin_bp.route("/admin/api/profiles", methods=["POST"])
@login_required
@groups_required("gasket-admins")
def create_profile_api():
    """Create a new backend profile."""
    from ..profiles import create_profile

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400

    try:
        profile = create_profile(data)
    except ValueError as e:
        msg = str(e)
        if "already exists" in msg:
            return jsonify({"error": msg}), 409
        if "not found" in msg.lower():
            return jsonify({"error": msg}), 400
        return jsonify({"error": msg}), 400

    current_app.logger.info("Admin created profile: %s", name)
    return jsonify(profile.to_dict()), 201


@admin_bp.route("/admin/api/profiles/<int:profile_id>")
@login_required
@groups_required("gasket-admins")
def get_profile_api(profile_id):
    """Get a single backend profile."""
    from ..profiles import get_profile

    profile = get_profile(profile_id)
    if not profile:
        return jsonify({"error": "Profile not found"}), 404

    return jsonify(profile.to_dict())


@admin_bp.route("/admin/api/profiles/<int:profile_id>", methods=["PUT"])
@login_required
@groups_required("gasket-admins")
def update_profile_api(profile_id):
    """Update a backend profile."""
    from ..profiles import get_profile, update_profile

    # Guard: config-defined profiles are read-only
    profile = get_profile(profile_id)
    if not profile:
        return jsonify({"error": "Profile not found"}), 404
    if profile.source == "config":
        return jsonify({"error": "Config-defined profiles cannot be modified"}), 403

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    try:
        profile = update_profile(profile_id, data)
    except ValueError as e:
        msg = str(e)
        if "not found" in msg.lower() and "profile" in msg.lower():
            return jsonify({"error": msg}), 404
        if "already exists" in msg:
            return jsonify({"error": msg}), 409
        return jsonify({"error": msg}), 400

    current_app.logger.info("Admin updated profile: %s", profile.name)
    return jsonify(profile.to_dict())


@admin_bp.route("/admin/api/profiles/<int:profile_id>", methods=["DELETE"])
@login_required
@groups_required("gasket-admins")
def delete_profile_api(profile_id):
    """Delete a backend profile."""
    from ..profiles import get_profile, delete_profile

    profile = get_profile(profile_id)
    if not profile:
        return jsonify({"error": "Profile not found"}), 404
    if profile.source == "config":
        return jsonify({"error": "Config-defined profiles cannot be deleted"}), 403

    delete_profile(profile_id)

    current_app.logger.info("Admin deleted profile: %s", profile.name)
    return jsonify({"message": f"Profile '{profile.name}' deleted"})

"""Admin panel — restricted to gasket-admins group."""

from concurrent.futures import ThreadPoolExecutor

from flask import Blueprint, current_app, jsonify, render_template, request, session

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


# ─── Policies CRUD ─────────────────────────────────────────────────


@admin_bp.route("/admin/api/policies")
@login_required
@groups_required("gasket-admins")
def list_policies_api():
    """List all policies."""
    from ..policies import list_policies

    policies = list_policies()
    return jsonify([p.to_dict() for p in policies])


@admin_bp.route("/admin/api/policies", methods=["POST"])
@login_required
@groups_required("gasket-admins")
def create_policy_api():
    """Create a new policy."""
    from ..policies import create_policy

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400

    content = (data.get("content") or "").strip()
    if not content:
        return jsonify({"error": "content is required"}), 400

    try:
        policy = create_policy(data)
    except ValueError as e:
        msg = str(e)
        if "already exists" in msg:
            return jsonify({"error": msg}), 409
        return jsonify({"error": msg}), 400

    current_app.logger.info("Admin created policy: %s", name)
    return jsonify(policy.to_dict(include_versions=True)), 201


@admin_bp.route("/admin/api/policies/<int:policy_id>")
@login_required
@groups_required("gasket-admins")
def get_policy_api(policy_id):
    """Get a single policy with all versions."""
    from ..policies import get_policy

    policy = get_policy(policy_id)
    if not policy:
        return jsonify({"error": "Policy not found"}), 404

    return jsonify(policy.to_dict(include_versions=True))


@admin_bp.route("/admin/api/policies/<int:policy_id>", methods=["PUT"])
@login_required
@groups_required("gasket-admins")
def update_policy_api(policy_id):
    """Update a policy."""
    from ..policies import get_policy, update_policy

    # Guard: config-defined policies are read-only
    policy = get_policy(policy_id)
    if not policy:
        return jsonify({"error": "Policy not found"}), 404
    if policy.source == "config":
        return jsonify({"error": "Config-defined policies cannot be modified"}), 403

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    try:
        policy = update_policy(policy_id, data)
    except ValueError as e:
        msg = str(e)
        if "not found" in msg.lower() and "policy" in msg.lower():
            return jsonify({"error": msg}), 404
        if "already exists" in msg:
            return jsonify({"error": msg}), 409
        return jsonify({"error": msg}), 400

    current_app.logger.info("Admin updated policy: %s", policy.name)
    return jsonify(policy.to_dict(include_versions=True))


@admin_bp.route("/admin/api/policies/<int:policy_id>", methods=["DELETE"])
@login_required
@groups_required("gasket-admins")
def delete_policy_api(policy_id):
    """Delete a policy."""
    from ..policies import get_policy, delete_policy

    policy = get_policy(policy_id)
    if not policy:
        return jsonify({"error": "Policy not found"}), 404
    if policy.source == "config":
        return jsonify({"error": "Config-defined policies cannot be deleted"}), 403

    delete_policy(policy_id)

    current_app.logger.info("Admin deleted policy: %s", policy.name)
    return jsonify({"message": f"Policy '{policy.name}' deleted"})


@admin_bp.route("/admin/api/policies/<int:policy_id>/versions")
@login_required
@groups_required("gasket-admins")
def policy_versions_api(policy_id):
    """List all versions for a policy."""
    from ..policies import get_policy, get_policy_versions

    policy = get_policy(policy_id)
    if not policy:
        return jsonify({"error": "Policy not found"}), 404

    versions = get_policy_versions(policy_id)
    return jsonify([v.to_dict() for v in versions])


# ─── Policy Acceptance ─────────────────────────────────────────────


@admin_bp.route("/admin/api/policies/<int:policy_id>/accept", methods=["POST"])
@login_required
def accept_policy_api(policy_id):
    """Accept a policy for a profile."""
    from ..policies import accept_policy

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    profile_id = data.get("profile_id")
    if not profile_id:
        return jsonify({"error": "profile_id is required"}), 400

    user_email = session.get("user_email")
    if not user_email:
        return jsonify({"error": "Not authenticated"}), 401

    try:
        acceptance = accept_policy(user_email, policy_id, profile_id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    current_app.logger.info(
        "User %s accepted policy %d for profile %d", user_email, policy_id, profile_id
    )
    return jsonify(acceptance.to_dict()), 201


@admin_bp.route("/admin/api/policies/acceptances/check/<int:profile_id>")
@login_required
def check_policies_api(profile_id):
    """Check if current user has accepted all policies for a profile."""
    from ..policies import check_all_policies_accepted

    user_email = session.get("user_email")
    if not user_email:
        return jsonify({"error": "Not authenticated"}), 401

    result = check_all_policies_accepted(user_email, profile_id)
    return jsonify(result)


@admin_bp.route("/admin/api/policies/acceptances")
@login_required
@groups_required("gasket-admins")
def list_acceptances_api():
    """List all policy acceptances (admin view). Supports ?user= filter."""
    from ..policies import get_all_acceptances

    user_email = request.args.get("user")
    acceptances = get_all_acceptances(user_email=user_email)
    return jsonify([a.to_dict() for a in acceptances])


@admin_bp.route("/admin/api/policies/my-acceptances")
@login_required
def my_acceptances_api():
    """List current user's policy acceptances."""
    from ..policies import get_user_acceptances

    user_email = session.get("user_email")
    if not user_email:
        return jsonify({"error": "Not authenticated"}), 401

    profile_id = request.args.get("profile_id", type=int)
    acceptances = get_user_acceptances(user_email, profile_id=profile_id)
    return jsonify([a.to_dict() for a in acceptances])

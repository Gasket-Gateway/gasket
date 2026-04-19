"""Portal page — main user landing page after OIDC login."""

from flask import Blueprint, jsonify, render_template, request, session

from ..auth import login_required, groups_required

portal_bp = Blueprint("portal", __name__)


@portal_bp.route("/login")
def login_page():
    """Render the login/landing page."""
    # If already authenticated, redirect to portal
    if "user_email" in session:
        return render_template("portal/profiles.html")
    denied = request.args.get("denied")
    return render_template("login.html", access_denied=denied)


@portal_bp.route("/")
@login_required
@groups_required("gasket-users")
def portal_page():
    """Render the main portal dashboard."""
    return render_template("portal/dashboard.html")


@portal_bp.route("/profiles")
@login_required
@groups_required("gasket-users")
def portal_profiles_page():
    """Render the backend profiles page."""
    return render_template("portal/profiles.html")


@portal_bp.route("/keys")
@login_required
@groups_required("gasket-users")
def portal_keys_page():
    """Render the API keys management page."""
    return render_template("portal/keys.html")


# ─── User-facing Profile & Policy API ─────────────────────────────


@portal_bp.route("/api/profiles")
@login_required
@groups_required("gasket-users")
def list_my_profiles():
    """List profiles the current user has access to, based on OIDC groups."""
    from ..profiles import list_profiles_for_groups

    user_groups = session.get("user_groups", [])
    profiles = list_profiles_for_groups(user_groups)
    return jsonify([p.to_dict() for p in profiles])


@portal_bp.route("/api/policies/<int:policy_id>")
@login_required
@groups_required("gasket-users")
def get_policy_for_user(policy_id):
    """Get a single policy's details (for the acceptance modal).

    Regular users can read policy content so they can review before accepting.
    """
    from ..policies import get_policy

    policy = get_policy(policy_id)
    if not policy:
        return jsonify({"error": "Policy not found"}), 404

    return jsonify(policy.to_dict(include_versions=False))


# ─── User API Key Management ──────────────────────────────────────


@portal_bp.route("/api/keys")
@login_required
@groups_required("gasket-users")
def list_my_keys():
    """List current user's API keys."""
    from ..api_keys import list_user_keys

    user_email = session.get("user_email")
    keys = list_user_keys(user_email)
    return jsonify([k.to_dict() for k in keys])


@portal_bp.route("/api/keys", methods=["POST"])
@login_required
@groups_required("gasket-users")
def create_key():
    """Create a new API key for the current user."""
    from ..api_keys import create_api_key

    user_email = session.get("user_email")
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    try:
        api_key, full_key_value = create_api_key(user_email, data)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    # Return with the full key revealed — this is the only time
    result = api_key.to_dict(reveal_key=True)
    return jsonify(result), 201


@portal_bp.route("/api/keys/<int:key_id>")
@login_required
@groups_required("gasket-users")
def get_my_key(key_id):
    """Get a single API key (own keys only, masked by default)."""
    from ..api_keys import get_api_key

    user_email = session.get("user_email")
    key = get_api_key(key_id)
    if not key:
        return jsonify({"error": "API key not found"}), 404
    if key.user_email != user_email:
        return jsonify({"error": "API key not found"}), 404

    return jsonify(key.to_dict())


@portal_bp.route("/api/keys/<int:key_id>/reveal")
@login_required
@groups_required("gasket-users")
def reveal_my_key(key_id):
    """Reveal the full value of an API key (own keys only)."""
    from ..api_keys import get_api_key

    user_email = session.get("user_email")
    key = get_api_key(key_id)
    if not key:
        return jsonify({"error": "API key not found"}), 404
    if key.user_email != user_email:
        return jsonify({"error": "API key not found"}), 404

    return jsonify(key.to_dict(reveal_key=True))


@portal_bp.route("/api/keys/<int:key_id>", methods=["PUT"])
@login_required
@groups_required("gasket-users")
def edit_my_key(key_id):
    """Edit an API key's opt-in flags (own keys only)."""
    from ..api_keys import update_api_key

    user_email = session.get("user_email")
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    try:
        key = update_api_key(key_id, user_email, data)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403

    return jsonify(key.to_dict())


@portal_bp.route("/api/keys/<int:key_id>/revoke", methods=["POST"])
@login_required
@groups_required("gasket-users")
def revoke_my_key(key_id):
    """Revoke one of the current user's API keys."""
    from ..api_keys import get_api_key, revoke_api_key

    user_email = session.get("user_email")
    key = get_api_key(key_id)
    if not key:
        return jsonify({"error": "API key not found"}), 404
    if key.user_email != user_email:
        return jsonify({"error": "API key not found"}), 404

    try:
        key = revoke_api_key(key_id, user_email)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify(key.to_dict())


@portal_bp.route("/api/keys/<int:key_id>/policies")
@login_required
@groups_required("gasket-users")
def my_key_policies(key_id):
    """View policy version snapshots for an owned API key."""
    from ..api_keys import get_api_key, get_key_policy_snapshots

    user_email = session.get("user_email")
    key = get_api_key(key_id)
    if not key:
        return jsonify({"error": "API key not found"}), 404
    if key.user_email != user_email:
        return jsonify({"error": "API key not found"}), 404

    snapshots = get_key_policy_snapshots(key_id)
    return jsonify(snapshots)

"""Test session control — only available when GASKET_TEST_MODE=1.

Provides endpoints to switch the active user identity on the fly,
enabling RBAC testing without restarting the server or needing a
live OIDC provider.
"""

import time

from flask import Blueprint, jsonify, request, session

test_session_bp = Blueprint("test_session", __name__, url_prefix="/test")


@test_session_bp.route("/set-session", methods=["POST"])
def set_session():
    """Set the active session to the provided user identity.

    Expects JSON body: {"email": "...", "name": "...", "groups": [...]}
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    email = data.get("email")
    if not email:
        return jsonify({"error": "email is required"}), 400

    session["user_email"] = email
    session["user_name"] = data.get("name", email.split("@")[0])
    session["user_groups"] = data.get("groups", [])
    session["login_time"] = time.time()

    return jsonify({
        "message": "Session updated",
        "user_email": session["user_email"],
        "user_name": session["user_name"],
        "user_groups": session["user_groups"],
    })


@test_session_bp.route("/clear-session", methods=["POST"])
def clear_session():
    """Clear the current session (become anonymous)."""
    session.clear()
    # Mark as deliberately anonymous so the before_request hook
    # doesn't auto-inject the default test user
    session["_test_anon"] = True
    return jsonify({"message": "Session cleared"})


@test_session_bp.route("/whoami")
def whoami():
    """Return the current session identity."""
    if "user_email" not in session:
        return jsonify({"authenticated": False})

    return jsonify({
        "authenticated": True,
        "user_email": session.get("user_email"),
        "user_name": session.get("user_name"),
        "user_groups": session.get("user_groups", []),
    })

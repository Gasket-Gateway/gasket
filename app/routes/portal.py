"""Portal page — main user landing page after OIDC login."""

from flask import Blueprint, render_template, request, session

from ..auth import login_required, groups_required

portal_bp = Blueprint("portal", __name__)


@portal_bp.route("/login")
def login_page():
    """Render the login/landing page."""
    # If already authenticated, redirect to portal
    if "user_email" in session:
        return render_template("portal.html")
    denied = request.args.get("denied")
    return render_template("login.html", access_denied=denied)


@portal_bp.route("/")
@login_required
@groups_required("gasket-users")
def portal_page():
    """Render the main portal page."""
    return render_template("portal.html")

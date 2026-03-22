"""Gasket Gateway — OIDC authentication and session management."""

import functools
import secrets
import time

from authlib.integrations.flask_client import OAuth
from flask import (
    Blueprint,
    current_app,
    redirect,
    request,
    session,
    url_for,
)

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

oauth = OAuth()


def init_oidc(app):
    """Initialise the Authlib OAuth client from Gasket config."""
    oidc_cfg = app.config["GASKET"].get("oidc", {})

    # Flask session secret — generate one if not configured
    app.secret_key = app.config["GASKET"].get(
        "secret_key", secrets.token_hex(32)
    )

    # Determine TLS verification setting
    skip_tls = oidc_cfg.get("skip_tls_verify", False)

    # Suppress urllib3 InsecureRequestWarning when TLS verification is disabled
    if skip_tls:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    oauth.init_app(app, fetch_token=lambda: None)

    provider_url = oidc_cfg.get("provider_url", "").rstrip("/")

    oauth.register(
        name="authentik",
        client_id=oidc_cfg.get("client_id", ""),
        client_secret=oidc_cfg.get("client_secret", ""),
        server_metadata_url=f"{provider_url}/.well-known/openid-configuration",
        client_kwargs={
            "scope": "openid email profile entitlements",
            "token_endpoint_auth_method": "client_secret_post",
        },
    )

    # When skip_tls_verify is enabled, wrap the OAuth client's session class
    # so that every HTTP session it creates has verify=False.
    # Authlib creates raw sessions in load_server_metadata(), fetch_jwk_set(),
    # and _get_oauth_client() — this wrapper catches all of them.
    if skip_tls:
        client = oauth.authentik
        original_cls = client.client_cls

        class NoVerifySession(original_cls):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.verify = False

        client.client_cls = NoVerifySession

    # Store TLS skip flag for reference
    app.config["OIDC_SKIP_TLS"] = skip_tls


# ─── Decorators ────────────────────────────────────────────────────


def login_required(f):
    """Require a valid OIDC session. Redirects to login if absent or expired."""

    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if "user_email" not in session:
            return redirect(url_for("portal.login_page"))

        # Check session timeout
        timeout_hours = (
            current_app.config["GASKET"]
            .get("oidc", {})
            .get("session_timeout_hours", 8)
        )
        login_time = session.get("login_time", 0)
        if time.time() - login_time > timeout_hours * 3600:
            session.clear()
            return redirect(url_for("portal.login_page"))

        return f(*args, **kwargs)

    return decorated


def groups_required(*required_groups):
    """Require the user to be in at least one of the specified OIDC groups."""

    def decorator(f):
        @functools.wraps(f)
        def decorated(*args, **kwargs):
            user_groups = session.get("user_groups", [])
            if not any(g in user_groups for g in required_groups):
                from flask import abort

                abort(403)
            return f(*args, **kwargs)

        return decorated

    return decorator


# ─── Routes ────────────────────────────────────────────────────────


@auth_bp.route("/login")
def login():
    """Redirect to the OIDC provider for authentication."""
    oidc_cfg = current_app.config["GASKET"].get("oidc", {})
    redirect_uri = oidc_cfg.get("redirect_url") or url_for(
        "auth.callback", _external=True
    )
    return oauth.authentik.authorize_redirect(redirect_uri)


@auth_bp.route("/callback")
def callback():
    """Handle the OIDC callback, extract user info, establish session."""
    token = oauth.authentik.authorize_access_token()
    userinfo = token.get("userinfo", {})

    # If userinfo wasn't in the token, fetch it from the userinfo endpoint
    if not userinfo:
        userinfo = oauth.authentik.userinfo()

    # Extract groups — Authentik puts them in the entitlements or groups claim
    groups = userinfo.get("groups", [])
    if not groups:
        groups = userinfo.get("entitlements", [])

    # Check user has at least the base user access group
    oidc_cfg = current_app.config["GASKET"].get("oidc", {})
    user_access_group = oidc_cfg.get("groups", {}).get(
        "user_access", "gasket-users"
    )

    if user_access_group not in groups:
        session.clear()
        return redirect(url_for("portal.login_page", denied=1))

    # Establish session
    session["user_email"] = userinfo.get("email", "unknown")
    session["user_name"] = userinfo.get(
        "preferred_username", userinfo.get("name", "Unknown User")
    )
    session["user_groups"] = groups
    session["login_time"] = time.time()

    current_app.logger.info(
        "User logged in: %s (groups: %s)",
        session["user_email"],
        ", ".join(groups),
    )

    return redirect(url_for("portal.portal_page"))


@auth_bp.route("/logout")
def logout():
    """Clear the session and redirect to the OIDC logout URL."""
    user = session.get("user_email", "unknown")
    session.clear()
    current_app.logger.info("User logged out: %s", user)

    logout_url = (
        current_app.config["GASKET"].get("oidc", {}).get("logout_url", "/")
    )
    return redirect(logout_url or "/")

"""Gasket Gateway — Error handlers blueprint."""

from flask import Blueprint, render_template

errors_bp = Blueprint("errors", __name__)

# ─── Error definitions ─────────────────────────────────────────────
ERROR_PAGES = {
    400: {
        "title": "Bad Request",
        "message": "The server could not understand your request. Check the syntax and try again.",
    },
    403: {
        "title": "Forbidden",
        "message": "You don't have permission to access this resource. Contact your administrator if you believe this is an error.",
    },
    404: {
        "title": "Not Found",
        "message": "The page you're looking for doesn't exist or has been moved.",
    },
    405: {
        "title": "Method Not Allowed",
        "message": "The HTTP method used is not allowed for this endpoint.",
    },
    429: {
        "title": "Too Many Requests",
        "message": "You've exceeded the rate limit. Please wait a moment and try again.",
    },
    500: {
        "title": "Internal Server Error",
        "message": "Something went wrong on our end. The issue has been logged and we're looking into it.",
    },
    502: {
        "title": "Bad Gateway",
        "message": "The upstream backend returned an invalid response. It may be temporarily unavailable.",
    },
    503: {
        "title": "Service Unavailable",
        "message": "Gasket Gateway is temporarily unavailable for maintenance. Please try again shortly.",
    },
}


def _render_error(code):
    """Render an error page for the given HTTP status code."""
    info = ERROR_PAGES.get(code, {"title": "Error", "message": "An unexpected error occurred."})
    return (
        render_template(
            "error.html",
            error_code=code,
            error_title=info["title"],
            error_message=info["message"],
        ),
        code,
    )


# ─── Register Flask error handlers ────────────────────────────────
@errors_bp.app_errorhandler(400)
def handle_400(e):
    return _render_error(400)


@errors_bp.app_errorhandler(403)
def handle_403(e):
    return _render_error(403)


@errors_bp.app_errorhandler(404)
def handle_404(e):
    return _render_error(404)


@errors_bp.app_errorhandler(405)
def handle_405(e):
    return _render_error(405)


@errors_bp.app_errorhandler(429)
def handle_429(e):
    return _render_error(429)


@errors_bp.app_errorhandler(500)
def handle_500(e):
    return _render_error(500)


@errors_bp.app_errorhandler(502)
def handle_502(e):
    return _render_error(502)


@errors_bp.app_errorhandler(503)
def handle_503(e):
    return _render_error(503)


# ─── Preview routes (for UI demo) ─────────────────────────────────
@errors_bp.route("/error/<int:code>")
def preview_error(code):
    """Preview an error page without actually triggering the error."""
    if code not in ERROR_PAGES:
        return _render_error(404)
    info = ERROR_PAGES[code]
    return render_template(
        "error.html",
        error_code=code,
        error_title=info["title"],
        error_message=info["message"],
    )

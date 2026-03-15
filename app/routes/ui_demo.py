"""UI Demo page — showcases all neo-brutalism UI components."""

from flask import Blueprint, render_template

ui_demo_bp = Blueprint("ui_demo", __name__)


@ui_demo_bp.route("/ui-demo")
def ui_demo():
    """Render the UI component showcase page."""
    return render_template("ui_demo.html")

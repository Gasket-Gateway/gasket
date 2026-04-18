"""UI Demo page — showcases all neo-brutalism UI components."""

import os
from flask import Blueprint, render_template, abort

ui_demo_bp = Blueprint("ui_demo", __name__)


@ui_demo_bp.route("/ui-demo")
def ui_demo():
    """Render the UI component showcase page. Only available in test mode."""
    if os.environ.get("GASKET_TEST_MODE") != "1":
        abort(404)
        
    return render_template("ui_demo.html")

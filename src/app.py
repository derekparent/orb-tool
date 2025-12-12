"""Oil Record Book Tool - Flask Application."""

import os
from flask import Flask, render_template

from config import config
from models import db


def create_app(config_name: str | None = None) -> Flask:
    """Application factory."""
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "development")

    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )
    app.config.from_object(config[config_name])

    # Initialize extensions
    db.init_app(app)

    # Create tables
    with app.app_context():
        db.create_all()

    # Register blueprints
    from routes.api import api_bp

    app.register_blueprint(api_bp, url_prefix="/api")

    # Main routes
    @app.route("/")
    def dashboard():
        """Main dashboard view."""
        return render_template("dashboard.html")

    @app.route("/soundings")
    def weekly_soundings():
        """Weekly soundings entry form."""
        return render_template("soundings.html")

    @app.route("/history")
    def history():
        """View sounding history and ORB entries."""
        return render_template("history.html")

    @app.route("/fuel")
    def fuel_tickets():
        """Daily fuel ticket entry and tracking."""
        return render_template("fuel.html")

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=5001)


"""Oil Record Book Tool - Flask Application."""

import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, g, jsonify, flash, redirect, url_for
from flask_login import LoginManager, login_required, current_user
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS

# Load environment variables from .env file
load_dotenv()

from config import config
from models import db, User
from flask_migrate import Migrate
from security import SecurityConfig


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
    migrate = Migrate(app, db)

    # Initialize security extensions
    csrf = CSRFProtect(app)
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=[SecurityConfig.RATE_LIMIT_PER_HOUR],
        storage_uri=app.config.get("RATELIMIT_STORAGE_URL", "memory://")
    )

    # CORS configuration
    CORS(app,
         origins=app.config["CORS_ORIGINS"],
         methods=SecurityConfig.CORS_METHODS,
         allow_headers=SecurityConfig.CORS_HEADERS,
         supports_credentials=True)

    # Configure Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "info"

    @login_manager.user_loader
    def load_user(user_id):
        """Load user by ID for Flask-Login."""
        return User.query.get(int(user_id))

    # Security headers middleware
    @app.after_request
    def add_security_headers(response):
        """Add security headers to all responses."""
        for header, value in SecurityConfig.SECURITY_HEADERS.items():
            response.headers[header] = value

        # Content Security Policy
        response.headers["Content-Security-Policy"] = SecurityConfig.CSP_POLICY

        return response

    # Request size validation
    @app.before_request
    def validate_request_size():
        """Validate request size before processing."""
        if request.content_length and request.content_length > app.config["MAX_CONTENT_LENGTH"]:
            return jsonify({"error": "Request entity too large"}), 413

    # CSRF error handler
    @app.errorhandler(400)
    def csrf_error(error):
        """Handle CSRF errors."""
        if error.description and "csrf" in error.description.lower():
            return jsonify({"error": f"CSRF token error: {error.description}"}), 400
        return jsonify({"error": "Bad request"}), 400

    # Rate limit error handler
    @app.errorhandler(429)
    def ratelimit_handler(e):
        """Handle rate limit errors."""
        return jsonify({"error": "Rate limit exceeded. Please try again later."}), 429

    # Note: db.create_all() removed - use migrations instead

    # Register blueprints
    from routes.api import api_bp
    from routes.auth import auth_bp
    from routes.secure_api import secure_api_bp, init_secure_api

    # Register all APIs
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(secure_api_bp, url_prefix="/api/v1")
    
    # Initialize secure API rate limiter with app
    init_secure_api(app)

    # Main routes
    @app.route("/")
    @login_required
    def dashboard():
        """Main dashboard view."""
        return render_template("dashboard.html")

    @app.route("/soundings")
    @login_required
    def weekly_soundings():
        """Weekly soundings entry form."""
        # Only engineers and chiefs can enter soundings
        if not current_user.can_access_route("write"):
            flash("Access denied. Engineer role required.", "error")
            return redirect(url_for("dashboard"))
        return render_template("soundings.html")

    @app.route("/history")
    @login_required
    def history():
        """View sounding history and ORB entries."""
        return render_template("history.html")

    @app.route("/fuel")
    @login_required
    def fuel_tickets():
        """Daily fuel ticket entry and tracking."""
        # Only engineers and chiefs can enter fuel tickets
        if not current_user.can_access_route("write"):
            flash("Access denied. Engineer role required.", "error")
            return redirect(url_for("dashboard"))
        return render_template("fuel.html")

    @app.route("/new-hitch")
    @login_required
    def new_hitch():
        """Start new hitch / import baseline."""
        # Only chief engineers can start new hitch
        if not current_user.can_access_route("admin"):
            flash("Access denied. Chief Engineer role required.", "error")
            return redirect(url_for("dashboard"))
        return render_template("new_hitch.html")

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=5001)


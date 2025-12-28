"""Authentication routes for Oil Record Book Tool."""

from datetime import datetime, UTC
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash

from models import db, User, UserRole

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """User login page and handler."""
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        # Handle both form and API login
        if request.is_json:
            data = request.get_json()
            username = data.get("username", "").strip()
            password = data.get("password", "")
            remember = data.get("remember", False)
        else:
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            remember = bool(request.form.get("remember"))

        if not username or not password:
            error = "Username and password are required."
            if request.is_json:
                return jsonify({"success": False, "error": error}), 400
            flash(error, "error")
            return render_template("login.html")

        # Look up user
        user = User.query.filter_by(username=username).first()

        if user and user.is_active and user.check_password(password):
            # Update last login
            user.last_login = datetime.now(UTC)
            db.session.commit()

            # Log in user
            login_user(user, remember=remember)

            if request.is_json:
                return jsonify({
                    "success": True,
                    "user": user.to_dict(),
                    "redirect_url": url_for("dashboard")
                })

            # Redirect to next page or dashboard
            next_page = request.args.get("next")
            if not next_page or not next_page.startswith("/"):
                next_page = url_for("dashboard")
            return redirect(next_page)
        else:
            error = "Invalid username or password."
            if request.is_json:
                return jsonify({"success": False, "error": error}), 401
            flash(error, "error")

    return render_template("login.html")


@auth_bp.route("/logout", methods=["GET", "POST"])
@login_required
def logout():
    """User logout."""
    logout_user()
    if request.is_json:
        return jsonify({"success": True, "redirect_url": url_for("auth.login")})

    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/profile", methods=["GET"])
@login_required
def profile():
    """User profile page."""
    return render_template("profile.html", user=current_user)


@auth_bp.route("/api/current-user", methods=["GET"])
@login_required
def current_user_api():
    """API endpoint to get current user info."""
    return jsonify({
        "success": True,
        "user": current_user.to_dict()
    })


@auth_bp.route("/api/check-auth", methods=["GET"])
def check_auth():
    """API endpoint to check authentication status."""
    if current_user.is_authenticated:
        return jsonify({
            "authenticated": True,
            "user": current_user.to_dict()
        })
    else:
        return jsonify({"authenticated": False}), 401


# Admin-only user management routes
@auth_bp.route("/admin/users", methods=["GET"])
@login_required
def manage_users():
    """User management page (Chief Engineer only)."""
    if not current_user.can_access_route("admin"):
        flash("Access denied. Chief Engineer role required.", "error")
        return redirect(url_for("dashboard"))

    users = User.query.all()
    return render_template("manage_users.html", users=users)


@auth_bp.route("/admin/users", methods=["POST"])
@login_required
def create_user():
    """Create new user (Chief Engineer only)."""
    if not current_user.can_access_route("admin"):
        return jsonify({"success": False, "error": "Access denied"}), 403

    data = request.get_json() if request.is_json else request.form

    username = data.get("username", "").strip()
    password = data.get("password", "")
    email = data.get("email", "").strip() or None
    full_name = data.get("full_name", "").strip() or None
    role = data.get("role", "engineer")

    # Validation
    if not username or not password:
        error = "Username and password are required"
        if request.is_json:
            return jsonify({"success": False, "error": error}), 400
        flash(error, "error")
        return redirect(url_for("auth.manage_users"))

    # Check if user exists
    if User.query.filter_by(username=username).first():
        error = "Username already exists"
        if request.is_json:
            return jsonify({"success": False, "error": error}), 400
        flash(error, "error")
        return redirect(url_for("auth.manage_users"))

    # Validate role
    try:
        user_role = UserRole(role)
    except ValueError:
        error = "Invalid role"
        if request.is_json:
            return jsonify({"success": False, "error": error}), 400
        flash(error, "error")
        return redirect(url_for("auth.manage_users"))

    # Create user
    user = User(
        username=username,
        email=email,
        full_name=full_name,
        role=user_role
    )
    user.set_password(password)

    db.session.add(user)
    db.session.commit()

    if request.is_json:
        return jsonify({"success": True, "user": user.to_dict()})

    flash(f"User '{username}' created successfully", "success")
    return redirect(url_for("auth.manage_users"))


@auth_bp.route("/admin/users/<int:user_id>/toggle", methods=["POST"])
@login_required
def toggle_user_status(user_id):
    """Toggle user active/inactive status (Chief Engineer only)."""
    if not current_user.can_access_route("admin"):
        return jsonify({"success": False, "error": "Access denied"}), 403

    if user_id == current_user.id:
        return jsonify({"success": False, "error": "Cannot disable your own account"}), 400

    user = User.query.get_or_404(user_id)
    user.is_active = not user.is_active
    db.session.commit()

    return jsonify({
        "success": True,
        "user": user.to_dict(),
        "message": f"User {'activated' if user.is_active else 'deactivated'}"
    })
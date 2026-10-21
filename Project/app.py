import os
import logging
from datetime import timedelta, datetime

from flask import Flask, session, request, redirect, url_for, jsonify
from dotenv import load_dotenv
from werkzeug.exceptions import HTTPException

from routes.asset_routes import asset_bp
from routes.auth_routes import auth_bp
from routes.dashboard_routes import dashboard_bp
from routes.maintenance_routes import maintenance_bp
from routes.inventory_routes import inventory_bp
from routes.readiness_routes import readiness_bp
from routes.audit_routes import audit_bp
from routes.main_dashboard_routes import main_dashboard_bp


load_dotenv()

app = Flask(__name__)

# ============================================================
# APPLICATION CONFIGURATION
# ============================================================

app.secret_key = os.getenv("FLASK_SECRET_KEY")

if not app.secret_key:
    raise RuntimeError(
        "FLASK_SECRET_KEY is missing. "
        "Set a long random value in your environment variables."
    )

app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=15)
app.config["SESSION_REFRESH_EACH_REQUEST"] = True
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

app.config["SESSION_COOKIE_SECURE"] = (
    os.getenv("FLASK_COOKIE_SECURE", "0").lower()
    in ("1", "true", "yes")
)

# ============================================================
# LOGGING CONFIGURATION
# ============================================================

logging.basicConfig(level=logging.INFO)

app.logger.setLevel(logging.INFO)


# ============================================================
# ERROR HANDLING
# ============================================================

@app.errorhandler(Exception)
def handle_unexpected_error(error):

    # Preserve Flask's normal handling of HTTP exceptions,
    # such as 404 Not Found.
    if isinstance(error, HTTPException):
        return error

    # Record the complete traceback in the server logs.
    app.logger.error(
        "Unhandled exception: %s %s",
        request.method,
        request.path,
        exc_info=(
            type(error),
            error,
            error.__traceback__
        )
    )

    # Never expose internal exception details to visitors.
    return jsonify({
        "error": "Internal Server Error",
        "message": "An unexpected server error occurred."
    }), 500


# ============================================================
# SESSION INACTIVITY TIMEOUT
# ============================================================

@app.before_request
def enforce_inactivity_timeout():

    pending = "pending_mfa_user_id" in session
    authenticated = "user_id" in session

    if not (pending or authenticated):
        return None

    now = datetime.now().timestamp()

    last_activity = session.get("last_activity", now)

    if now - float(last_activity) > 15 * 60:

        session.clear()

        if request.endpoint not in ("auth.login", "static"):
            return redirect(
                url_for("auth.login", timeout=1)
            )

        return None

    session["last_activity"] = now
    session.permanent = True

    return None


# ============================================================
# SESSION ACTIVITY ENDPOINT
# ============================================================

@app.post("/session/activity")
def session_activity():

    """Refresh the inactivity timer for an authenticated session."""

    if "user_id" not in session:
        return jsonify({
            "ok": False,
            "reason": "unauthenticated"
        }), 401

    session["last_activity"] = datetime.now().timestamp()
    session.permanent = True

    return jsonify({"ok": True})


# ============================================================
# REGISTER BLUEPRINTS
# ============================================================

app.register_blueprint(main_dashboard_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(asset_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(maintenance_bp)
app.register_blueprint(inventory_bp)
app.register_blueprint(readiness_bp)
app.register_blueprint(audit_bp)


# ============================================================
# APPLICATION STARTUP
# ============================================================

if __name__ == "__main__":

    # Do not enable debug mode on a public production deployment.
    app.run(
        debug=os.getenv("FLASK_DEBUG", "0").lower()
        in ("1", "true", "yes")
    )
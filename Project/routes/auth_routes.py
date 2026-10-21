from base64 import b64encode
from datetime import datetime
from io import BytesIO

import pyotp
import qrcode
from flask import Blueprint, render_template, request, redirect, url_for, session, current_app
from werkzeug.security import check_password_hash

from models.user_model import (
    get_user_by_username,
    get_user_by_id,
    record_failed_login,
    clear_login_failures,
    save_totp_secret,
)

auth_bp = Blueprint("auth", __name__)


def _locked_message(user):
    locked_until = user.get("locked_until")
    if locked_until and locked_until > datetime.now():
        return True
    return False


def _make_qr_data_uri(uri):
    qr = qrcode.QRCode(box_size=5, border=2)
    qr.add_data(uri)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + b64encode(buffer.getvalue()).decode("ascii")


def _complete_login(user):
    # Clear pre-authentication state to reduce session-fixation risk.
    session.clear()
    session.permanent = True
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["role"] = user["role"]
    session["last_activity"] = datetime.now().timestamp()
    return redirect(url_for("main_dashboard.main_dashboard"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = get_user_by_username(username)

        if user and _locked_message(user):
            return render_template(
                "auth/login.html",
                error="Account temporarily locked after repeated failed attempts. Try again in 15 minutes.",
            ), 429

        if not user or not check_password_hash(user["password_hash"], password):
            if user:
                record_failed_login(user["id"])
                refreshed_user = get_user_by_id(user["id"])
                if refreshed_user and _locked_message(refreshed_user):
                    message = "Too many failed attempts. This account is locked for 15 minutes."
                    return render_template("auth/login.html", error=message), 429
            return render_template("auth/login.html", error="Invalid username or password."), 401

        clear_login_failures(user["id"])
        session.clear()
        session.permanent = True
        session["pending_mfa_user_id"] = user["id"]
        session["last_activity"] = datetime.now().timestamp()

        if not user.get("totp_secret"):
            # First login after deployment: require authenticator enrollment before access.
            secret = pyotp.random_base32()
            session["pending_totp_secret"] = secret
            return redirect(url_for("auth.mfa_setup"))

        return redirect(url_for("auth.mfa_verify"))

    return render_template("auth/login.html")


@auth_bp.route("/mfa/setup", methods=["GET", "POST"])
def mfa_setup():
    user_id = session.get("pending_mfa_user_id")
    secret = session.get("pending_totp_secret")
    if not user_id or not secret:
        return redirect(url_for("auth.login"))

    user = get_user_by_id(user_id)
    if not user:
        session.clear()
        return redirect(url_for("auth.login"))

    totp = pyotp.TOTP(secret)
    if request.method == "POST":
        code = request.form.get("code", "").strip().replace(" ", "")
        if totp.verify(code, valid_window=1):
            save_totp_secret(user_id, secret)
            session.pop("pending_totp_secret", None)
            return _complete_login(user)
        return render_template(
            "auth/mfa_setup.html",
            secret=secret,
            qr_data_uri=_make_qr_data_uri(totp.provisioning_uri(name=user["username"], issuer_name="MLERMS")),
            error="Invalid code. Check your authenticator app and try again.",
        ), 401

    return render_template(
        "auth/mfa_setup.html",
        secret=secret,
        qr_data_uri=_make_qr_data_uri(totp.provisioning_uri(name=user["username"], issuer_name="MLERMS")),
    )


@auth_bp.route("/mfa/verify", methods=["GET", "POST"])
def mfa_verify():
    user_id = session.get("pending_mfa_user_id")
    if not user_id:
        return redirect(url_for("auth.login"))

    user = get_user_by_id(user_id)
    if not user or not user.get("totp_secret"):
        session.clear()
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        code = request.form.get("code", "").strip().replace(" ", "")
        if pyotp.TOTP(user["totp_secret"]).verify(code, valid_window=1):
            clear_login_failures(user_id)
            return _complete_login(user)
        return render_template("auth/mfa_verify.html", error="Invalid authenticator code."), 401

    return render_template("auth/mfa_verify.html")


@auth_bp.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    return redirect(url_for("auth.login"))

from flask import Blueprint, render_template, redirect, url_for, session

from models.main_dashboard_model import get_main_dashboard_data


main_dashboard_bp = Blueprint(
    "main_dashboard",
    __name__
)


@main_dashboard_bp.route("/")
def main_dashboard():

    if "user_id" not in session:
        return redirect(
            url_for("auth.login")
        )

    data = get_main_dashboard_data()

    return render_template(
        "main_dashboard/index.html",
        main_dashboard=data
    )
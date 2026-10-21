from flask import Blueprint, render_template, redirect, url_for, session

from models.asset_model import get_all_units
from models.readiness_model import (
    refresh_readiness,
    get_unit_readiness_summary,
    get_readiness_by_unit,
    get_category_readiness
)


readiness_bp = Blueprint(
    "readiness",
    __name__,
    url_prefix="/readiness"
)


@readiness_bp.route("/")
def readiness_home():

    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    units = get_all_units()

    if not units:
        return "No units found in the database.", 500

    selected_unit_id = session.get(
        "selected_unit_id",
        units[0]["unit_id"]
    )

    valid_unit_ids = {
        unit["unit_id"]
        for unit in units
    }

    if selected_unit_id not in valid_unit_ids:
        selected_unit_id = units[0]["unit_id"]

    return redirect(
        url_for(
            "readiness.unit_readiness",
            unit_id=selected_unit_id
        )
    )


@readiness_bp.route("/<unit_id>")
def unit_readiness(unit_id):

    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    units = get_all_units()

    selected_unit = None

    for unit in units:
        if unit["unit_id"] == unit_id:
            selected_unit = unit
            break

    if selected_unit is None:
        return "Unit not found.", 404

    # Keep the selected unit synchronized with the dashboard.
    session["selected_unit_id"] = unit_id

    # Recalculate readiness from the current asset/maintenance data.
    refresh_readiness(unit_id)

    summary = get_unit_readiness_summary(unit_id)
    asset_readiness = get_readiness_by_unit(unit_id)
    category_readiness = get_category_readiness(unit_id)

    return render_template(
        "readiness/index.html",
        units=units,
        selected_unit=selected_unit,
        summary=summary,
        asset_readiness=asset_readiness,
        category_readiness=category_readiness
    )
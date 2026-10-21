from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    session
)

from models.dashboard_model import (
    get_unit_dashboard_summary,
    get_unit_asset_status_summary,
    get_unit_condition_summary,
    get_unit_maintenance_summary,
    get_unit_maintenance_status_summary,
    get_unit_dashboard_asset_details,
    get_unit_inventory_summary
)

from models.asset_model import (
    get_all_units
)

from models.readiness_model import (
    refresh_readiness,
    get_unit_readiness_summary,
    get_readiness_by_unit,
    get_category_readiness
)


dashboard_bp = Blueprint(
    "dashboard",
    __name__,
    url_prefix="/dashboard"
)


@dashboard_bp.route("/")
def dashboard():

    if "user_id" not in session:
        return redirect(
            url_for("auth.login")
        )

    units = get_all_units()

    if not units:
        return (
            "No units found in the database.",
            500
        )

    selected_unit_id = units[0]["unit_id"]

    return redirect(
        url_for(
            "dashboard.unit_dashboard",
            unit_id=selected_unit_id
        )
    )


@dashboard_bp.route("/<unit_id>")
def unit_dashboard(unit_id):

    if "user_id" not in session:
        return redirect(
            url_for("auth.login")
        )

    units = get_all_units()

    selected_unit = None

    for unit in units:

        if unit["unit_id"] == unit_id:

            selected_unit = unit

            break

    if selected_unit is None:

        return "Unit not found.", 404

    # Remember the unit currently selected on the dashboard.
    # Inventory will use this same unit context.
    session["selected_unit_id"] = unit_id

    summary = get_unit_dashboard_summary(
        unit_id
    )

    status_summary = (
        get_unit_asset_status_summary(
            unit_id
        )
    )

    condition_summary = (
        get_unit_condition_summary(
            unit_id
        )
    )

    maintenance_summary = (
        get_unit_maintenance_summary(
            unit_id
        )
    )

    maintenance_status_summary = (
        get_unit_maintenance_status_summary(
            unit_id
        )
    )

    asset_details = (
        get_unit_dashboard_asset_details(
            unit_id
        )
    )

    inventory_summary = get_unit_inventory_summary(
        unit_id
    )

    # ==========================================
    # READINESS DATA
    # ==========================================

    refresh_readiness(unit_id)

    readiness_summary = get_unit_readiness_summary(
        unit_id
    )

    readiness_assets = get_readiness_by_unit(
        unit_id
    )

    readiness_categories = get_category_readiness(
        unit_id
    )

    return render_template(
        "dashboard/index.html",

        units=units,

        selected_unit=selected_unit,

        summary=summary,

        status_summary=status_summary,

        condition_summary=condition_summary,

        maintenance_summary=(
            maintenance_summary
        ),

        maintenance_status_summary=(
            maintenance_status_summary
        ),

        asset_details=asset_details,

        inventory_summary=inventory_summary,

        readiness_summary=readiness_summary,

        readiness_assets=readiness_assets,

        readiness_categories=readiness_categories
    )
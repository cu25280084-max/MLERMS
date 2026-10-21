from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session
)

from models.asset_model import (
    get_all_categories,
    get_all_units,
    get_all_asset_types,
    get_allocations_by_unit,
    get_allocation_by_id,
    allocation_exists,
    create_allocation,
    update_allocation,
    delete_allocation,
    decommission_allocation,
    recommission_allocation
)

from models.audit_model import create_audit_log


asset_bp = Blueprint(
    "assets",
    __name__,
    url_prefix="/assets"
)


def login_required():

    if "user_id" not in session:
        return redirect(
            url_for("auth.login")
        )

    return None


# ==========================================================
# ASSET MANAGEMENT HOME
# ==========================================================

@asset_bp.route("/")
def asset_home():

    authentication_check = login_required()

    if authentication_check:
        return authentication_check

    units = get_all_units()

    if not units:
        return (
            "No units found in the database.",
            500
        )

    return redirect(
        url_for(
            "assets.unit_assets",
            unit_id=units[0]["unit_id"]
        )
    )


# ==========================================================
# UNIT-WISE ASSET MANAGEMENT
# ==========================================================

@asset_bp.route("/<unit_id>")
def unit_assets(unit_id):

    authentication_check = login_required()

    if authentication_check:
        return authentication_check

    units = get_all_units()

    selected_unit = None

    for unit in units:

        if unit["unit_id"] == unit_id:

            selected_unit = unit

            break

    if selected_unit is None:

        return "Unit not found.", 404

    allocations = get_allocations_by_unit(
        unit_id
    )

    return render_template(
        "assets/list.html",
        units=units,
        selected_unit=selected_unit,
        allocations=allocations
    )


# ==========================================================
# ADD ASSET
# ==========================================================

@asset_bp.route(
    "/add",
    methods=["GET", "POST"]
)
def add_asset():

    authentication_check = login_required()

    if authentication_check:
        return authentication_check

    categories = get_all_categories()

    units = get_all_units()

    asset_types = get_all_asset_types()

    selected_unit_id = request.args.get(
        "unit_id"
    )

    # If no unit was supplied,
    # use the first available unit.

    if (
        selected_unit_id is None
        and units
    ):

        selected_unit_id = units[0]["unit_id"]

    # Validate the selected unit.

    valid_unit = False

    for unit in units:

        if unit["unit_id"] == selected_unit_id:

            valid_unit = True

            break

    if not valid_unit:

        if units:

            selected_unit_id = units[0]["unit_id"]

        else:

            return (
                "No units found in the database.",
                500
            )

    if request.method == "POST":

        asset_type_id = request.form[
            "asset_type_id"
        ]

        unit_id = request.form[
            "unit_id"
        ]

        quantity = int(
            request.form["quantity"]
        )

        acquisition_date = request.form[
            "acquisition_date"
        ]

        condition = request.form[
            "condition"
        ]

        # New assets always start
        # as Operational.

        status = "Operational"

        # Make sure the submitted unit exists.

        valid_post_unit = False

        for unit in units:

            if unit["unit_id"] == unit_id:

                valid_post_unit = True

                break

        if not valid_post_unit:

            return render_template(
                "assets/add.html",
                categories=categories,
                units=units,
                asset_types=asset_types,
                selected_unit_id=selected_unit_id,
                error="Selected unit was not found."
            )

        # Prevent duplicate allocation.

        if allocation_exists(
            asset_type_id,
            unit_id
        ):

            return render_template(
                "assets/add.html",
                categories=categories,
                units=units,
                asset_types=asset_types,
                selected_unit_id=unit_id,
                error=(
                    "This asset type is already "
                    "assigned to the selected unit."
                )
            )

        create_allocation(
            asset_type_id,
            unit_id,
            quantity,
            status,
            acquisition_date,
            condition
        )

        create_audit_log(
            user_id=session.get("user_id"),
            action="CREATE",
            module="ASSET",
            record_id=f"{asset_type_id}:{unit_id}",
            description=(
                f"Created asset allocation for "
                f"asset type '{asset_type_id}' in "
                f"unit '{unit_id}' with quantity {quantity}."
            )
        )

        return redirect(
            url_for(
                "assets.unit_assets",
                unit_id=unit_id
            )
        )

    return render_template(
        "assets/add.html",
        categories=categories,
        units=units,
        asset_types=asset_types,
        selected_unit_id=selected_unit_id
    )


# ==========================================================
# EDIT ASSET
# ==========================================================

@asset_bp.route(
    "/edit/<int:allocation_id>",
    methods=["GET", "POST"]
)
def edit_asset(allocation_id):

    authentication_check = login_required()

    if authentication_check:
        return authentication_check

    allocation = get_allocation_by_id(
        allocation_id
    )

    if allocation is None:

        return (
            "Asset allocation not found",
            404
        )

    categories = get_all_categories()

    units = get_all_units()

    asset_types = get_all_asset_types()

    if request.method == "POST":

        asset_type_id = request.form[
            "asset_type_id"
        ]

        unit_id = request.form[
            "unit_id"
        ]

        quantity = int(
            request.form["quantity"]
        )

        acquisition_date = request.form[
            "acquisition_date"
        ]

        condition = request.form[
            "condition"
        ]

        # Preserve the existing lifecycle status.

        status = allocation["status"]

        # Prevent duplicate allocation.

        allocation_changed = (
            asset_type_id
            != allocation["asset_type_id"]
            or
            unit_id
            != allocation["unit_id"]
        )

        if (
            allocation_changed
            and
            allocation_exists(
                asset_type_id,
                unit_id
            )
        ):

            return render_template(
                "assets/edit.html",
                allocation=allocation,
                categories=categories,
                units=units,
                asset_types=asset_types,
                error=(
                    "This asset type is already "
                    "assigned to the selected unit."
                )
            )

        update_allocation(
            allocation_id,
            asset_type_id,
            unit_id,
            quantity,
            status,
            acquisition_date,
            condition
        )

        create_audit_log(
            user_id=session.get("user_id"),
            action="UPDATE",
            module="ASSET",
            record_id=str(allocation_id),
            description=(
                f"Updated asset allocation "
                f"{allocation_id}."
            )
        )

        return redirect(
            url_for(
                "assets.unit_assets",
                unit_id=unit_id
            )
        )

    return render_template(
        "assets/edit.html",
        allocation=allocation,
        categories=categories,
        units=units,
        asset_types=asset_types
    )


# ==========================================================
# DECOMMISSION ASSET
# ==========================================================

@asset_bp.route(
    "/decommission/<int:allocation_id>",
    methods=["POST"]
)
def decommission_asset_route(
    allocation_id
):

    authentication_check = login_required()

    if authentication_check:
        return authentication_check

    allocation = get_allocation_by_id(
        allocation_id
    )

    if allocation is None:

        return (
            "Asset allocation not found",
            404
        )

    if allocation["status"] == "Decommissioned":

        return redirect(
            url_for(
                "assets.unit_assets",
                unit_id=allocation["unit_id"]
            )
        )

    decommission_allocation(
        allocation_id
    )

    create_audit_log(
        user_id=session.get("user_id"),
        action="DECOMMISSION",
        module="ASSET",
        record_id=str(allocation_id),
        description=(
            f"Decommissioned asset allocation "
            f"{allocation_id}."
        )
    )

    return redirect(
        url_for(
            "assets.unit_assets",
            unit_id=allocation["unit_id"]
        )
    )


# ==========================================================
# RECOMMISSION ASSET
# ==========================================================

@asset_bp.route(
    "/recommission/<int:allocation_id>",
    methods=["POST"]
)
def recommission_asset_route(
    allocation_id
):

    authentication_check = login_required()

    if authentication_check:
        return authentication_check

    allocation = get_allocation_by_id(
        allocation_id
    )

    if allocation is None:

        return (
            "Asset allocation not found",
            404
        )

    if allocation["status"] != "Decommissioned":

        return redirect(
            url_for(
                "assets.unit_assets",
                unit_id=allocation["unit_id"]
            )
        )

    recommission_allocation(
        allocation_id
    )

    create_audit_log(
        user_id=session.get("user_id"),
        action="RECOMMISSION",
        module="ASSET",
        record_id=str(allocation_id),
        description=(
            f"Recommissioned asset allocation "
            f"{allocation_id}."
        )
    )

    return redirect(
        url_for(
            "assets.unit_assets",
            unit_id=allocation["unit_id"]
        )
    )


# ==========================================================
# DELETE ASSET
# ==========================================================

@asset_bp.route(
    "/delete/<int:allocation_id>",
    methods=["POST"]
)
def delete_asset_route(
    allocation_id
):

    authentication_check = login_required()

    if authentication_check:
        return authentication_check

    allocation = get_allocation_by_id(
        allocation_id
    )

    if allocation is None:

        return (
            "Asset allocation not found",
            404
        )

    unit_id = allocation["unit_id"]

    delete_allocation(
        allocation_id
    )

    create_audit_log(
        user_id=session.get("user_id"),
        action="DELETE",
        module="ASSET",
        record_id=str(allocation_id),
        description=(
            f"Deleted asset allocation "
            f"{allocation_id}."
        )
    )

    return redirect(
        url_for(
            "assets.unit_assets",
            unit_id=unit_id
        )
    )
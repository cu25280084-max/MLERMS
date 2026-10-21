from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session
)

from datetime import date

from models.maintenance_model import (
    get_all_maintenance,
    create_maintenance,
    get_maintenance_by_id,
    update_maintenance,
    delete_maintenance,
    get_current_maintenance_quantity,
    get_allocations_for_maintenance,
    get_date_based_status,
    refresh_maintenance_statuses,
    mark_maintenance_completed,
    mark_maintenance_overdue
)

from models.asset_model import (
    get_all_units,
    get_allocation_by_id
)
from models.audit_model import create_audit_log


maintenance_bp = Blueprint(
    "maintenance",
    __name__,
    url_prefix="/maintenance"
)


ALLOWED_MAINTENANCE_TYPES = {
    "Preventive Maintenance",
    "Corrective Maintenance",
    "Inspection",
    "Overhaul",
    "Emergency Maintenance"
}


def login_required():

    if "user_id" not in session:

        return redirect(
            url_for("auth.login")
        )

    return None


def get_selected_unit(unit_id):

    units = get_all_units()

    selected_unit = None

    for unit in units:

        if str(unit["unit_id"]) == str(unit_id):

            selected_unit = unit

            break

    return units, selected_unit


@maintenance_bp.route("/")
def list_maintenance():

    authentication_check = login_required()

    if authentication_check:
        return authentication_check

    units = get_all_units()

    if not units:

        return "No units found.", 404

    return redirect(
        url_for(
            "maintenance.unit_maintenance",
            unit_id=units[0]["unit_id"]
        )
    )


@maintenance_bp.route("/<unit_id>")
def unit_maintenance(unit_id):

    authentication_check = login_required()

    if authentication_check:
        return authentication_check

    refresh_maintenance_statuses()

    units, selected_unit = get_selected_unit(
        unit_id
    )

    if selected_unit is None:

        return "Unit not found.", 404

    maintenance_records = get_all_maintenance(
        unit_id
    )

    pending_confirmations = []

    for record in maintenance_records:

        if record["status"] == "Pending Confirmation":

            pending_confirmations.append(
                record
            )

    return render_template(
        "maintenance/list.html",
        units=units,
        selected_unit=selected_unit,
        maintenance_records=maintenance_records,
        pending_confirmations=pending_confirmations,
        current_date=date.today()
    )


@maintenance_bp.route(
    "/add",
    methods=["GET", "POST"]
)
def add_maintenance():

    authentication_check = login_required()

    if authentication_check:
        return authentication_check

    units = get_all_units()

    if not units:

        return "No units found.", 404

    requested_unit_id = request.args.get(
        "unit_id"
    )

    if requested_unit_id:

        selected_unit = None

        for unit in units:

            if str(unit["unit_id"]) == str(
                requested_unit_id
            ):

                selected_unit = unit
                break

        if selected_unit is None:

            return "Unit not found.", 404

    else:

        selected_unit = units[0]

    unit_id = selected_unit["unit_id"]

    allocations = get_allocations_for_maintenance(
        unit_id
    )

    today = date.today()

    if request.method == "POST":

        try:

            allocation_id = int(
                request.form[
                    "allocation_id"
                ]
            )

            maintenance_date = date.fromisoformat(
                request.form[
                    "maintenance_date"
                ]
            )

            expected_completion_date = (
                date.fromisoformat(
                    request.form[
                        "expected_completion_date"
                    ]
                )
            )

            maintenance_type = (
                request.form["type"].strip()
            )

            quantity_under_maintenance = int(
                request.form[
                    "quantity_under_maintenance"
                ]
            )

            next_due_date = date.fromisoformat(
                request.form[
                    "next_due_date"
                ]
            )

        except (
            KeyError,
            ValueError
        ):

            return render_template(
                "maintenance/add.html",
                units=units,
                selected_unit=selected_unit,
                allocations=allocations,
                current_date=today,
                error=(
                    "Please enter all maintenance "
                    "details correctly."
                )
            )

        selected_allocation = (
            get_allocation_by_id(
                allocation_id
            )
        )

        if selected_allocation is None:

            return render_template(
                "maintenance/add.html",
                units=units,
                selected_unit=selected_unit,
                allocations=allocations,
                current_date=today,
                error="Selected asset was not found."
            )

        if (
            selected_allocation["unit_id"]
            != unit_id
        ):

            return render_template(
                "maintenance/add.html",
                units=units,
                selected_unit=selected_unit,
                allocations=allocations,
                current_date=today,
                error=(
                    "Selected asset does not "
                    "belong to this unit."
                )
            )

        if (
            selected_allocation["status"]
            == "Decommissioned"
        ):

            return render_template(
                "maintenance/add.html",
                units=units,
                selected_unit=selected_unit,
                allocations=allocations,
                current_date=today,
                error=(
                    "A decommissioned asset "
                    "cannot be placed into maintenance."
                )
            )

        if maintenance_date < today:

            return render_template(
                "maintenance/add.html",
                units=units,
                selected_unit=selected_unit,
                allocations=allocations,
                current_date=today,
                error=(
                    "Maintenance start date "
                    "cannot be before today."
                )
            )

        if (
            expected_completion_date
            < maintenance_date
        ):

            return render_template(
                "maintenance/add.html",
                units=units,
                selected_unit=selected_unit,
                allocations=allocations,
                current_date=today,
                error=(
                    "Expected completion date "
                    "cannot be before the "
                    "maintenance start date."
                )
            )

        if not maintenance_type:

            return render_template(
                "maintenance/add.html",
                units=units,
                selected_unit=selected_unit,
                allocations=allocations,
                current_date=today,
                error="Maintenance type is required."
            )

        if maintenance_type not in ALLOWED_MAINTENANCE_TYPES:

            return render_template(
                "maintenance/add.html",
                units=units,
                selected_unit=selected_unit,
                allocations=allocations,
                current_date=today,
                error="Please select a valid maintenance type."
            )

        if quantity_under_maintenance <= 0:

            return render_template(
                "maintenance/add.html",
                units=units,
                selected_unit=selected_unit,
                allocations=allocations,
                current_date=today,
                error=(
                    "Maintenance quantity "
                    "must be greater than zero."
                )
            )

        total_quantity = int(
            selected_allocation["quantity"]
        )

        current_quantity = (
            get_current_maintenance_quantity(
                allocation_id
            )
        )

        available_quantity = (
            total_quantity
            - current_quantity
        )

        if (
            quantity_under_maintenance
            > available_quantity
        ):

            return render_template(
                "maintenance/add.html",
                units=units,
                selected_unit=selected_unit,
                allocations=allocations,
                current_date=today,
                error=(
                    f"Only {available_quantity} "
                    "quantity is currently available "
                    "for maintenance."
                )
            )

        status = get_date_based_status(
            maintenance_date,
            expected_completion_date
        )

        quantity_not_under_maintenance = (
            total_quantity
            - current_quantity
            - quantity_under_maintenance
        )

        create_maintenance(
            allocation_id,
            maintenance_date,
            expected_completion_date,
            maintenance_type,
            quantity_under_maintenance,
            quantity_not_under_maintenance,
            status,
            next_due_date
        )

        create_audit_log(
            user_id=session.get("user_id"),
            action="CREATE",
            module="MAINTENANCE",
            record_id=None,
            description=(
                f"Created maintenance record for "
                f"allocation {allocation_id}, "
                f"type '{maintenance_type}', "
                f"quantity {quantity_under_maintenance}, "
                f"status '{status}'."
            )
        )

        return redirect(
            url_for(
                "maintenance.unit_maintenance",
                unit_id=unit_id
            )
        )

    return render_template(
        "maintenance/add.html",
        units=units,
        selected_unit=selected_unit,
        allocations=allocations,
        current_date=today
    )


@maintenance_bp.route(
    "/edit/<int:maintenance_id>",
    methods=["GET", "POST"]
)
def edit_maintenance(maintenance_id):

    authentication_check = login_required()

    if authentication_check:
        return authentication_check

    refresh_maintenance_statuses()

    maintenance_record = (
        get_maintenance_by_id(
            maintenance_id
        )
    )

    if maintenance_record is None:

        return (
            "Maintenance record not found.",
            404
        )

    unit_id = maintenance_record[
        "unit_id"
    ]

    units, selected_unit = get_selected_unit(
        unit_id
    )

    if selected_unit is None:

        return "Unit not found.", 404

    allocations = get_allocations_for_maintenance(
        unit_id
    )

    today = date.today()

    if request.method == "POST":

        try:

            allocation_id = int(
                request.form[
                    "allocation_id"
                ]
            )

            maintenance_date = date.fromisoformat(
                request.form[
                    "maintenance_date"
                ]
            )

            expected_completion_date = (
                date.fromisoformat(
                    request.form[
                        "expected_completion_date"
                    ]
                )
            )

            maintenance_type = (
                request.form["type"].strip()
            )

            quantity_under_maintenance = int(
                request.form[
                    "quantity_under_maintenance"
                ]
            )

            next_due_date = date.fromisoformat(
                request.form[
                    "next_due_date"
                ]
            )

        except (
            KeyError,
            ValueError
        ):

            return render_template(
                "maintenance/edit.html",
                units=units,
                selected_unit=selected_unit,
                allocations=allocations,
                maintenance=maintenance_record,
                current_date=today,
                error=(
                    "Please enter all maintenance "
                    "details correctly."
                )
            )

        selected_allocation = (
            get_allocation_by_id(
                allocation_id
            )
        )

        if selected_allocation is None:

            return render_template(
                "maintenance/edit.html",
                units=units,
                selected_unit=selected_unit,
                allocations=allocations,
                maintenance=maintenance_record,
                current_date=today,
                error="Selected asset was not found."
            )

        if (
            selected_allocation["unit_id"]
            != unit_id
        ):

            return render_template(
                "maintenance/edit.html",
                units=units,
                selected_unit=selected_unit,
                allocations=allocations,
                maintenance=maintenance_record,
                current_date=today,
                error=(
                    "Selected asset does not "
                    "belong to this unit."
                )
            )

        if (
            selected_allocation["status"]
            == "Decommissioned"
        ):

            return render_template(
                "maintenance/edit.html",
                units=units,
                selected_unit=selected_unit,
                allocations=allocations,
                maintenance=maintenance_record,
                current_date=today,
                error=(
                    "A decommissioned asset "
                    "cannot be placed into maintenance."
                )
            )

        if maintenance_date < today:

            if (
                maintenance_record["status"]
                == "Scheduled"
            ):

                return render_template(
                    "maintenance/edit.html",
                    units=units,
                    selected_unit=selected_unit,
                    allocations=allocations,
                    maintenance=maintenance_record,
                    current_date=today,
                    error=(
                        "A Scheduled maintenance "
                        "cannot have a start date "
                        "before today."
                    )
                )

        if (
            expected_completion_date
            < maintenance_date
        ):

            return render_template(
                "maintenance/edit.html",
                units=units,
                selected_unit=selected_unit,
                allocations=allocations,
                maintenance=maintenance_record,
                current_date=today,
                error=(
                    "Expected completion date "
                    "cannot be before the "
                    "maintenance start date."
                )
            )

        if quantity_under_maintenance <= 0:

            return render_template(
                "maintenance/edit.html",
                units=units,
                selected_unit=selected_unit,
                allocations=allocations,
                maintenance=maintenance_record,
                current_date=today,
                error=(
                    "Maintenance quantity "
                    "must be greater than zero."
                )
            )

        if maintenance_type not in ALLOWED_MAINTENANCE_TYPES:

            return render_template(
                "maintenance/edit.html",
                units=units,
                selected_unit=selected_unit,
                allocations=allocations,
                maintenance=maintenance_record,
                current_date=today,
                error="Please select a valid maintenance type."
            )

        total_quantity = int(
            selected_allocation["quantity"]
        )

        current_quantity = (
            get_current_maintenance_quantity(
                allocation_id,
                maintenance_id
            )
        )

        available_quantity = (
            total_quantity
            - current_quantity
        )

        if (
            maintenance_record["status"]
            in (
                "Scheduled",
                "In Progress",
                "Pending Confirmation",
                "Overdue"
            )
            and allocation_id
            == maintenance_record[
                "allocation_id"
            ]
        ):

            available_quantity += int(
                maintenance_record[
                    "quantity_under_maintenance"
                ]
            )

        if (
            quantity_under_maintenance
            > available_quantity
        ):

            return render_template(
                "maintenance/edit.html",
                units=units,
                selected_unit=selected_unit,
                allocations=allocations,
                maintenance=maintenance_record,
                current_date=today,
                error=(
                    f"Only {available_quantity} "
                    "quantity is available."
                )
            )

        if maintenance_record["status"] in (
            "Completed",
            "Overdue"
        ):

            status = maintenance_record[
                "status"
            ]

        else:

            status = get_date_based_status(
                maintenance_date,
                expected_completion_date
            )

        quantity_not_under_maintenance = (
            total_quantity
            - current_quantity
            - (
                quantity_under_maintenance
                if status in (
                    "Scheduled",
                    "In Progress",
                    "Pending Confirmation",
                    "Overdue"
                )
                else 0
            )
        )

        update_maintenance(
            maintenance_id,
            allocation_id,
            maintenance_date,
            expected_completion_date,
            maintenance_type,
            quantity_under_maintenance,
            quantity_not_under_maintenance,
            status,
            next_due_date
        )

        create_audit_log(
            user_id=session.get("user_id"),
            action="UPDATE",
            module="MAINTENANCE",
            record_id=str(maintenance_id),
            description=(
                f"Updated maintenance record "
                f"{maintenance_id}."
            )
        )

        return redirect(
            url_for(
                "maintenance.unit_maintenance",
                unit_id=selected_allocation[
                    "unit_id"
                ]
            )
        )

    return render_template(
        "maintenance/edit.html",
        units=units,
        selected_unit=selected_unit,
        allocations=allocations,
        maintenance=maintenance_record,
        current_date=today
    )


@maintenance_bp.route(
    "/complete/<int:maintenance_id>",
    methods=["POST"]
)
def complete_maintenance(maintenance_id):

    authentication_check = login_required()

    if authentication_check:
        return authentication_check

    refresh_maintenance_statuses()

    record = get_maintenance_by_id(
        maintenance_id
    )

    if record is None:

        return (
            "Maintenance record not found.",
            404
        )

    if record["status"] != "Pending Confirmation":

        return (
            "This maintenance record is not "
            "ready for completion confirmation.",
            400
        )

    mark_maintenance_completed(
        maintenance_id
    )

    create_audit_log(
        user_id=session.get("user_id"),
        action="COMPLETE",
        module="MAINTENANCE",
        record_id=str(maintenance_id),
        description=(
            f"Maintenance record {maintenance_id} "
            f"was marked as completed."
        )
    )

    return redirect(
        url_for(
            "maintenance.unit_maintenance",
            unit_id=record["unit_id"]
        )
    )


@maintenance_bp.route(
    "/overdue/<int:maintenance_id>",
    methods=["POST"]
)
def overdue_maintenance(maintenance_id):

    authentication_check = login_required()

    if authentication_check:
        return authentication_check

    refresh_maintenance_statuses()

    record = get_maintenance_by_id(
        maintenance_id
    )

    if record is None:

        return (
            "Maintenance record not found.",
            404
        )

    if record["status"] != "Pending Confirmation":

        return (
            "This maintenance record is not "
            "ready to be marked overdue.",
            400
        )

    mark_maintenance_overdue(
        maintenance_id
    )

    create_audit_log(
        user_id=session.get("user_id"),
        action="MARK_OVERDUE",
        module="MAINTENANCE",
        record_id=str(maintenance_id),
        description=(
            f"Maintenance record {maintenance_id} "
            f"was marked as overdue."
        )
    )

    return redirect(
        url_for(
            "maintenance.unit_maintenance",
            unit_id=record["unit_id"]
        )
    )


@maintenance_bp.route(
    "/delete/<int:maintenance_id>",
    methods=["POST"]
)
def delete_maintenance_route(
    maintenance_id
):

    authentication_check = login_required()

    if authentication_check:
        return authentication_check

    record = get_maintenance_by_id(
        maintenance_id
    )

    if record is None:

        return (
            "Maintenance record not found.",
            404
        )

    unit_id = record["unit_id"]

    create_audit_log(
        user_id=session.get("user_id"),
        action="DELETE",
        module="MAINTENANCE",
        record_id=str(maintenance_id),
        description=(
            f"Deleted maintenance record "
            f"{maintenance_id}."
        )
    )

    delete_maintenance(
        maintenance_id
    )

    return redirect(
        url_for(
            "maintenance.unit_maintenance",
            unit_id=unit_id
        )
    )
from flask import Blueprint, render_template, request, redirect, url_for, session

from models.inventory_model import (
    get_inventory_by_unit,
    get_inventory_by_id,
    create_inventory_item,
    update_inventory_item,
    delete_inventory_item
)

from models.asset_model import get_all_units
from models.audit_model import create_audit_log


inventory_bp = Blueprint(
    "inventory",
    __name__,
    url_prefix="/inventory"
)


# ==========================================================
# LOGIN CHECK
# ==========================================================

def login_required():

    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    return None


# ==========================================================
# SELECTED UNIT
# ==========================================================

def get_selected_unit():

    """
    Get the Army Unit currently selected on the dashboard.
    """

    unit_id = session.get("selected_unit_id")

    if not unit_id:
        return None

    units = get_all_units()

    for unit in units:

        if unit["unit_id"] == unit_id:
            return unit

    return None


# ==========================================================
# INVENTORY HOME
# ==========================================================

@inventory_bp.route("/")
def inventory_home():

    auth_check = login_required()

    if auth_check:
        return auth_check

    selected_unit = get_selected_unit()

    if selected_unit is None:
        return redirect(
            url_for("dashboard.dashboard")
        )

    return redirect(
        url_for(
            "inventory.unit_inventory",
            unit_id=selected_unit["unit_id"]
        )
    )


# ==========================================================
# UNIT-SPECIFIC INVENTORY
# ==========================================================

@inventory_bp.route("/<unit_id>")
def unit_inventory(unit_id):

    auth_check = login_required()

    if auth_check:
        return auth_check

    units = get_all_units()

    selected_unit = None

    for unit in units:

        if unit["unit_id"] == unit_id:
            selected_unit = unit
            break

    if selected_unit is None:
        return "Unit not found.", 404

    # Keep dashboard and inventory unit selection synchronized.
    session["selected_unit_id"] = unit_id

    inventory = get_inventory_by_unit(
        unit_id
    )

    return render_template(
        "inventory/list.html",
        units=units,
        inventory=inventory,
        selected_unit=selected_unit
    )


# ==========================================================
# ADD INVENTORY
# ==========================================================

@inventory_bp.route("/add", methods=["GET", "POST"])
def add_inventory():

    auth_check = login_required()

    if auth_check:
        return auth_check

    selected_unit = get_selected_unit()

    if selected_unit is None:
        return redirect(
            url_for("dashboard.dashboard")
        )

    # Get all units for the dashboard-style sidebar.
    units = get_all_units()

    # ------------------------------------------------------
    # POST
    # ------------------------------------------------------

    if request.method == "POST":

        item_name = request.form.get(
            "item_name",
            ""
        ).strip()

        category = request.form.get(
            "category",
            ""
        ).strip()

        measurement_unit = request.form.get(
            "unit",
            ""
        ).strip()

        location = request.form.get(
            "location",
            ""
        ).strip()

        supplier = request.form.get(
            "supplier",
            ""
        ).strip()

        # --------------------------------------------------
        # NUMBER VALIDATION
        # --------------------------------------------------

        try:

            quantity = int(
                request.form.get(
                    "quantity",
                    0
                )
            )

            minimum_quantity = int(
                request.form.get(
                    "minimum_quantity",
                    0
                )
            )

            unit_cost = float(
                request.form.get(
                    "unit_cost",
                    0
                )
            )

        except ValueError:

            return render_template(
                "inventory/add.html",
                units=units,
                selected_unit=selected_unit,
                error=(
                    "Quantity, minimum quantity and "
                    "unit cost must contain valid numbers."
                )
            )

        # --------------------------------------------------
        # REQUIRED FIELD VALIDATION
        # --------------------------------------------------

        if not item_name:

            return render_template(
                "inventory/add.html",
                units=units,
                selected_unit=selected_unit,
                error="Item name is required."
            )

        if not category:

            return render_template(
                "inventory/add.html",
                units=units,
                selected_unit=selected_unit,
                error="Category is required."
            )

        if not measurement_unit:

            return render_template(
                "inventory/add.html",
                units=units,
                selected_unit=selected_unit,
                error="Measurement unit is required."
            )

        if not location:

            return render_template(
                "inventory/add.html",
                units=units,
                selected_unit=selected_unit,
                error="Storage location is required."
            )

        if not supplier:

            return render_template(
                "inventory/add.html",
                units=units,
                selected_unit=selected_unit,
                error="Supplier is required."
            )

        # --------------------------------------------------
        # RANGE VALIDATION
        # --------------------------------------------------

        if quantity < 0:

            return render_template(
                "inventory/add.html",
                units=units,
                selected_unit=selected_unit,
                error="Quantity cannot be negative."
            )

        if minimum_quantity < 0:

            return render_template(
                "inventory/add.html",
                units=units,
                selected_unit=selected_unit,
                error="Minimum quantity cannot be negative."
            )

        if unit_cost < 0:

            return render_template(
                "inventory/add.html",
                units=units,
                selected_unit=selected_unit,
                error="Unit cost cannot be negative."
            )

        # --------------------------------------------------
        # CREATE INVENTORY ITEM
        # --------------------------------------------------

        create_inventory_item(
            item_name=item_name,
            category=category,
            quantity=quantity,
            measurement_unit=measurement_unit,
            minimum_quantity=minimum_quantity,
            unit_id=selected_unit["unit_id"],
            location=location,
            supplier=supplier,
            unit_cost=unit_cost
        )

        create_audit_log(
            user_id=session.get("user_id"),
            action="CREATE",
            module="INVENTORY",
            record_id=None,
            description=(
                f"Created inventory item "
                f"'{item_name}' for unit "
                f"'{selected_unit['unit_id']}' "
                f"with quantity {quantity}."
            )
        )

        return redirect(
            url_for(
                "inventory.inventory_home"
            )
        )

    # ------------------------------------------------------
    # GET
    # ------------------------------------------------------

    return render_template(
        "inventory/add.html",
        units=units,
        selected_unit=selected_unit
    )


# ==========================================================
# EDIT INVENTORY
# ==========================================================

@inventory_bp.route(
    "/edit/<int:item_id>",
    methods=["GET", "POST"]
)
def edit_inventory(item_id):

    auth_check = login_required()

    if auth_check:
        return auth_check

    selected_unit = get_selected_unit()

    if selected_unit is None:
        return redirect(
            url_for("dashboard.dashboard")
        )

    # Get all units for the dashboard-style sidebar.
    units = get_all_units()

    # ------------------------------------------------------
    # GET EXISTING ITEM
    # ------------------------------------------------------

    item = get_inventory_by_id(
        item_id
    )

    if not item:
        return "Inventory item not found.", 404

    # ------------------------------------------------------
    # UNIT ISOLATION
    # ------------------------------------------------------

    if item["unit_id"] != selected_unit["unit_id"]:

        return (
            "Inventory item does not belong "
            "to the selected unit."
        ), 403

    # ------------------------------------------------------
    # POST
    # ------------------------------------------------------

    if request.method == "POST":

        item_name = request.form.get(
            "item_name",
            ""
        ).strip()

        category = request.form.get(
            "category",
            ""
        ).strip()

        measurement_unit = request.form.get(
            "unit",
            ""
        ).strip()

        location = request.form.get(
            "location",
            ""
        ).strip()

        supplier = request.form.get(
            "supplier",
            ""
        ).strip()

        # --------------------------------------------------
        # NUMBER VALIDATION
        # --------------------------------------------------

        try:

            quantity = int(
                request.form.get(
                    "quantity",
                    0
                )
            )

            minimum_quantity = int(
                request.form.get(
                    "minimum_quantity",
                    0
                )
            )

            unit_cost = float(
                request.form.get(
                    "unit_cost",
                    0
                )
            )

        except ValueError:

            return render_template(
                "inventory/edit.html",
                units=units,
                item=item,
                selected_unit=selected_unit,
                error=(
                    "Quantity, minimum quantity and "
                    "unit cost must contain valid numbers."
                )
            )

        # --------------------------------------------------
        # REQUIRED FIELD VALIDATION
        # --------------------------------------------------

        if not item_name:

            return render_template(
                "inventory/edit.html",
                units=units,
                item=item,
                selected_unit=selected_unit,
                error="Item name is required."
            )

        if not category:

            return render_template(
                "inventory/edit.html",
                units=units,
                item=item,
                selected_unit=selected_unit,
                error="Category is required."
            )

        if not measurement_unit:

            return render_template(
                "inventory/edit.html",
                units=units,
                item=item,
                selected_unit=selected_unit,
                error="Measurement unit is required."
            )

        if not location:

            return render_template(
                "inventory/edit.html",
                units=units,
                item=item,
                selected_unit=selected_unit,
                error="Storage location is required."
            )

        if not supplier:

            return render_template(
                "inventory/edit.html",
                units=units,
                item=item,
                selected_unit=selected_unit,
                error="Supplier is required."
            )

        # --------------------------------------------------
        # RANGE VALIDATION
        # --------------------------------------------------

        if quantity < 0:

            return render_template(
                "inventory/edit.html",
                units=units,
                item=item,
                selected_unit=selected_unit,
                error="Quantity cannot be negative."
            )

        if minimum_quantity < 0:

            return render_template(
                "inventory/edit.html",
                units=units,
                item=item,
                selected_unit=selected_unit,
                error="Minimum quantity cannot be negative."
            )

        if unit_cost < 0:

            return render_template(
                "inventory/edit.html",
                units=units,
                item=item,
                selected_unit=selected_unit,
                error="Unit cost cannot be negative."
            )

        # --------------------------------------------------
        # UPDATE INVENTORY ITEM
        # --------------------------------------------------

        update_inventory_item(
            item_id=item_id,
            item_name=item_name,
            category=category,
            quantity=quantity,
            measurement_unit=measurement_unit,
            minimum_quantity=minimum_quantity,
            location=location,
            supplier=supplier,
            unit_cost=unit_cost
        )

        create_audit_log(
            user_id=session.get("user_id"),
            action="UPDATE",
            module="INVENTORY",
            record_id=str(item_id),
            description=(
                f"Updated inventory item "
                f"{item_id} ('{item_name}')."
            )
        )

        return redirect(
            url_for(
                "inventory.inventory_home"
            )
        )

    # ------------------------------------------------------
    # GET
    # ------------------------------------------------------

    return render_template(
        "inventory/edit.html",
        units=units,
        item=item,
        selected_unit=selected_unit
    )


# ==========================================================
# DELETE INVENTORY
# ==========================================================

@inventory_bp.route(
    "/delete/<int:item_id>",
    methods=["POST"]
)
def delete_inventory(item_id):

    auth_check = login_required()

    if auth_check:
        return auth_check

    selected_unit = get_selected_unit()

    if selected_unit is None:
        return redirect(
            url_for("dashboard.dashboard")
        )

    # ------------------------------------------------------
    # GET EXISTING ITEM
    # ------------------------------------------------------

    item = get_inventory_by_id(
        item_id
    )

    if not item:
        return "Inventory item not found.", 404

    # ------------------------------------------------------
    # UNIT ISOLATION
    # ------------------------------------------------------

    if item["unit_id"] != selected_unit["unit_id"]:

        return (
            "Inventory item does not belong "
            "to the selected unit."
        ), 403

    # ------------------------------------------------------
    # DELETE
    # ------------------------------------------------------

    delete_inventory_item(
        item_id
    )

    create_audit_log(
        user_id=session.get("user_id"),
        action="DELETE",
        module="INVENTORY",
        record_id=str(item_id),
        description=(
            f"Deleted inventory item "
            f"{item_id} ('{item['item_name']}')."
        )
    )

    delete_inventory_item(
        item_id
    )


    return redirect(
        url_for(
            "inventory.inventory_home"
        )
    )
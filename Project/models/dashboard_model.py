from datetime import date

from config import get_db_connection
from models.maintenance_model import refresh_maintenance_statuses


ACTIVE_MAINTENANCE_STATUSES = (
    "Scheduled",
    "In Progress",
    "Pending Confirmation",
    "Overdue"
)


CURRENT_MAINTENANCE_STATUSES = (
    "Scheduled",
    "In Progress",
    "Pending Confirmation"
)


def get_unit_dashboard_summary(unit_id):

    refresh_maintenance_statuses()

    connection = get_db_connection()

    try:

        cursor = connection.cursor(dictionary=True)

        allocation_query = """
            SELECT

                COALESCE(
                    SUM(aa.quantity),
                    0
                ) AS total_assets,

                COALESCE(
                    SUM(
                        CASE
                            WHEN aa.status = 'Decommissioned'
                            THEN aa.quantity
                            ELSE 0
                        END
                    ),
                    0
                ) AS decommissioned_assets

            FROM asset_allocations aa

            WHERE aa.unit_id = %s
        """

        cursor.execute(
            allocation_query,
            (unit_id,)
        )

        allocation_data = cursor.fetchone()

        maintenance_query = """
            SELECT

                COALESCE(
                    SUM(
                        CASE
                            WHEN m.status IN (
                                'Scheduled',
                                'In Progress',
                                'Pending Confirmation'
                            )
                            THEN m.quantity_under_maintenance
                            ELSE 0
                        END
                    ),
                    0
                ) AS under_maintenance_assets,

                COALESCE(
                    SUM(
                        CASE
                            WHEN m.status = 'Overdue'
                            THEN m.quantity_under_maintenance
                            ELSE 0
                        END
                    ),
                    0
                ) AS overdue_assets

            FROM maintenance m

            INNER JOIN asset_allocations aa
                ON m.allocation_id = aa.allocation_id

            WHERE aa.unit_id = %s
        """

        cursor.execute(
            maintenance_query,
            (unit_id,)
        )

        maintenance_data = cursor.fetchone()

        total_assets = int(
            allocation_data["total_assets"]
        )

        decommissioned = int(
            allocation_data["decommissioned_assets"]
        )

        under_maintenance = int(
            maintenance_data["under_maintenance_assets"]
        )

        overdue = int(
            maintenance_data["overdue_assets"]
        )

        operational = max(
            0,
            total_assets
            - under_maintenance
            - overdue
            - decommissioned
        )

        non_operational = (
            under_maintenance
            + overdue
            + decommissioned
        )

        return {
            "total_assets": total_assets,
            "operational_assets": operational,
            "non_operational_assets": non_operational,
            "decommissioned_assets": decommissioned,
            "under_maintenance_assets": under_maintenance,
            "overdue_assets": overdue
        }

    finally:

        cursor.close()
        connection.close()


def get_unit_inventory_summary(unit_id):

    """Return inventory KPIs and item-level details for one unit."""

    connection = get_db_connection()

    try:

        cursor = connection.cursor(dictionary=True)

        summary_query = """
            SELECT

                COUNT(*) AS total_items,

                COALESCE(SUM(quantity), 0) AS total_quantity,

                COALESCE(
                    SUM(
                        CASE
                            WHEN quantity <= minimum_quantity
                            THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS low_stock_items,

                COALESCE(
                    SUM(quantity * unit_cost),
                    0
                ) AS inventory_value

            FROM inventory

            WHERE unit_id = %s
        """

        cursor.execute(
            summary_query,
            (unit_id,)
        )

        summary = cursor.fetchone() or {}

        details_query = """
            SELECT
                item_id,
                item_name,
                category,
                quantity,
                unit,
                minimum_quantity,
                location,
                supplier,
                unit_cost,
                (quantity * unit_cost) AS item_value

            FROM inventory

            WHERE unit_id = %s

            ORDER BY item_name
        """

        cursor.execute(
            details_query,
            (unit_id,)
        )

        details = cursor.fetchall()

        inventory_value = float(
            summary.get("inventory_value", 0) or 0
        )

        if inventory_value >= 10000000:
            inventory_value_display = (
                f"₹{inventory_value / 10000000:.1f} Crore"
            )
        elif inventory_value >= 100000:
            inventory_value_display = (
                f"₹{inventory_value / 100000:.1f} Lakh"
            )
        elif inventory_value >= 1000:
            inventory_value_display = (
                f"₹{inventory_value / 1000:.1f}K"
            )
        else:
            inventory_value_display = (
                f"₹{inventory_value:,.0f}"
            )

        return {
            "total_items": int(summary.get("total_items", 0) or 0),
            "total_quantity": int(summary.get("total_quantity", 0) or 0),
            "low_stock_items": int(summary.get("low_stock_items", 0) or 0),
            "inventory_value": inventory_value,
            "inventory_value_display": inventory_value_display,
            "details": details
        }

    finally:

        cursor.close()
        connection.close()


def get_unit_asset_status_summary(unit_id):

    summary = get_unit_dashboard_summary(
        unit_id
    )

    return [
        {
            "status": "Operational",
            "asset_count": summary[
                "operational_assets"
            ]
        },
        {
            "status": "Non-Operational",
            "asset_count": summary[
                "non_operational_assets"
            ]
        },
        {
            "status": "Decommissioned",
            "asset_count": summary[
                "decommissioned_assets"
            ]
        }
    ]


def get_unit_condition_summary(unit_id):

    connection = get_db_connection()

    try:

        cursor = connection.cursor(
            dictionary=True
        )

        query = """
            SELECT

                `condition`,

                COALESCE(
                    SUM(quantity),
                    0
                ) AS asset_count

            FROM asset_allocations

            WHERE unit_id = %s

            GROUP BY `condition`

            ORDER BY `condition`
        """

        cursor.execute(
            query,
            (unit_id,)
        )

        return cursor.fetchall()

    finally:

        cursor.close()
        connection.close()


def get_unit_maintenance_summary(unit_id):

    refresh_maintenance_statuses()

    connection = get_db_connection()

    try:

        cursor = connection.cursor(
            dictionary=True
        )

        query = """
            SELECT

                COUNT(*) AS total_maintenance,

                COALESCE(
                    SUM(
                        CASE
                            WHEN m.status = 'Completed'
                            THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS completed_maintenance,

                COALESCE(
                    SUM(
                        CASE
                            WHEN m.status = 'In Progress'
                            THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS in_progress_maintenance,

                COALESCE(
                    SUM(
                        CASE
                            WHEN m.status = 'Scheduled'
                            THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS scheduled_maintenance,

                COALESCE(
                    SUM(
                        CASE
                            WHEN m.status = 'Pending Confirmation'
                            THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS pending_confirmation_maintenance,

                COALESCE(
                    SUM(
                        CASE
                            WHEN m.status = 'Overdue'
                            THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS overdue_maintenance

            FROM maintenance m

            INNER JOIN asset_allocations aa
                ON m.allocation_id = aa.allocation_id

            WHERE aa.unit_id = %s
        """

        cursor.execute(
            query,
            (unit_id,)
        )

        return cursor.fetchone()

    finally:

        cursor.close()
        connection.close()


def get_unit_maintenance_status_summary(unit_id):

    refresh_maintenance_statuses()

    connection = get_db_connection()

    try:

        cursor = connection.cursor(
            dictionary=True
        )

        query = """
            SELECT

                m.status AS display_status,

                COUNT(*) AS maintenance_count

            FROM maintenance m

            INNER JOIN asset_allocations aa
                ON m.allocation_id = aa.allocation_id

            WHERE aa.unit_id = %s

            GROUP BY m.status

            ORDER BY
                CASE m.status
                    WHEN 'Scheduled' THEN 1
                    WHEN 'In Progress' THEN 2
                    WHEN 'Pending Confirmation' THEN 3
                    WHEN 'Completed' THEN 4
                    WHEN 'Overdue' THEN 5
                    ELSE 6
                END
        """

        cursor.execute(
            query,
            (unit_id,)
        )

        return cursor.fetchall()

    finally:

        cursor.close()
        connection.close()


def get_unit_dashboard_asset_details(unit_id):

    refresh_maintenance_statuses()

    connection = get_db_connection()

    try:

        cursor = connection.cursor(
            dictionary=True
        )

        # --------------------------------------------------
        # Asset allocation details
        # --------------------------------------------------

        allocation_query = """
            SELECT

                aa.allocation_id,
                aa.asset_type_id,
                at.asset_name,

                aa.quantity,
                aa.status,

                COALESCE(
                    (
                        SELECT
                            SUM(
                                m.quantity_under_maintenance
                            )

                        FROM maintenance m

                        WHERE
                            m.allocation_id =
                                aa.allocation_id

                            AND m.status IN (
                                'Scheduled',
                                'In Progress',
                                'Pending Confirmation'
                            )

                    ),
                    0
                ) AS maintenance_quantity,

                COALESCE(
                    (
                        SELECT
                            SUM(
                                m.quantity_under_maintenance
                            )

                        FROM maintenance m

                        WHERE
                            m.allocation_id =
                                aa.allocation_id

                            AND m.status = 'Overdue'

                    ),
                    0
                ) AS overdue_quantity

            FROM asset_allocations aa

            INNER JOIN asset_types at
                ON aa.asset_type_id =
                   at.asset_type_id

            WHERE aa.unit_id = %s

            ORDER BY
                aa.allocation_id
        """

        cursor.execute(
            allocation_query,
            (unit_id,)
        )

        allocations = cursor.fetchall()

        total_assets = []
        operational_assets = []
        non_operational_assets = []
        decommissioned_assets = []

        for allocation in allocations:

            quantity = int(
                allocation["quantity"]
            )

            maintenance_quantity = int(
                allocation[
                    "maintenance_quantity"
                ] or 0
            )

            overdue_quantity = int(
                allocation[
                    "overdue_quantity"
                ] or 0
            )

            total_assets.append({
                "asset_type_id":
                    allocation["asset_type_id"],
                "asset_name":
                    allocation["asset_name"],
                "quantity":
                    quantity
            })

            if allocation["status"] == "Decommissioned":

                decommissioned_assets.append({
                    "asset_type_id":
                        allocation["asset_type_id"],
                    "asset_name":
                        allocation["asset_name"],
                    "quantity":
                        quantity
                })

                non_operational_assets.append({
                    "asset_type_id":
                        allocation["asset_type_id"],
                    "asset_name":
                        allocation["asset_name"],
                    "quantity":
                        quantity
                })

                continue

            # Overdue has priority over normal maintenance
            # for the displayed asset status.

            non_operational_quantity = (
                maintenance_quantity
                + overdue_quantity
            )

            operational_quantity = max(
                0,
                quantity
                - non_operational_quantity
            )

            if operational_quantity > 0:

                operational_assets.append({
                    "asset_type_id":
                        allocation["asset_type_id"],
                    "asset_name":
                        allocation["asset_name"],
                    "quantity":
                        operational_quantity
                })

            if non_operational_quantity > 0:

                non_operational_assets.append({
                    "asset_type_id":
                        allocation["asset_type_id"],
                    "asset_name":
                        allocation["asset_name"],
                    "quantity":
                        non_operational_quantity
                })

        # --------------------------------------------------
        # Maintenance records
        # --------------------------------------------------

        maintenance_query = """
            SELECT

                m.maintenance_id,
                m.allocation_id,

                aa.asset_type_id,
                at.asset_name,

                m.quantity_under_maintenance,
                m.status,
                m.next_due_date

            FROM maintenance m

            INNER JOIN asset_allocations aa
                ON m.allocation_id =
                   aa.allocation_id

            INNER JOIN asset_types at
                ON aa.asset_type_id =
                   at.asset_type_id

            WHERE aa.unit_id = %s

            ORDER BY
                m.next_due_date,
                m.maintenance_id
        """

        cursor.execute(
            maintenance_query,
            (unit_id,)
        )

        maintenance_records = (
            cursor.fetchall()
        )

        under_maintenance = []
        scheduled = []
        in_progress = []
        overdue = []

        for record in maintenance_records:

            quantity = int(
                record[
                    "quantity_under_maintenance"
                ]
            )

            if quantity <= 0:
                continue

            maintenance_item = {
                "maintenance_id":
                    record["maintenance_id"],
                "allocation_id":
                    record["allocation_id"],
                "asset_type_id":
                    record["asset_type_id"],
                "asset_name":
                    record["asset_name"],
                "quantity":
                    quantity,
                "status":
                    record["status"],
                "next_due_date":
                    record["next_due_date"]
            }

            if record["status"] in (
                "Scheduled",
                "In Progress",
                "Pending Confirmation"
            ):

                under_maintenance.append(
                    maintenance_item
                )

            if record["status"] == "Scheduled":

                scheduled.append(
                    maintenance_item
                )

            if record["status"] == "In Progress":

                in_progress.append(
                    maintenance_item
                )

            if record["status"] == "Overdue":

                overdue.append(
                    maintenance_item
                )

        return {
            "total_assets": total_assets,
            "operational_assets":
                operational_assets,
            "non_operational_assets":
                non_operational_assets,
            "decommissioned_assets":
                decommissioned_assets,
            "under_maintenance":
                under_maintenance,
            "scheduled":
                scheduled,
            "in_progress":
                in_progress,
            "overdue":
                overdue
        }

    finally:

        cursor.close()
        connection.close()

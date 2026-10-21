from config import get_db_connection

from models.maintenance_model import (
    refresh_maintenance_statuses
)

from models.readiness_model import (
    refresh_readiness
)


def get_main_dashboard_data():

    # Keep maintenance and readiness data current.
    refresh_maintenance_statuses()
    refresh_readiness()

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:

        # ==================================================
        # ASSET STATUS BY ASSET TYPE
        # ==================================================
        #
        # This is the single source of truth for the main
        # dashboard asset-status numbers.
        #
        # The table, gauge, KPI cards, and asset-status list
        # all use the totals calculated from this result.
        # ==================================================

        cursor.execute("""
            SELECT
                at.asset_type_id,
                at.asset_name,

                COALESCE(
                    SUM(
                        CASE
                            WHEN aa.status <> 'Decommissioned'
                            THEN aa.quantity
                            ELSE 0
                        END
                    ),
                    0
                ) AS allocated_quantity,

                COALESCE(
                    SUM(
                        CASE
                            WHEN aa.status <> 'Decommissioned'
                            THEN COALESCE(m.under_maintenance, 0)
                            ELSE 0
                        END
                    ),
                    0
                ) AS under_maintenance,

                COALESCE(
                    SUM(
                        CASE
                            WHEN aa.status <> 'Decommissioned'
                            THEN COALESCE(m.overdue, 0)
                            ELSE 0
                        END
                    ),
                    0
                ) AS overdue,

                COALESCE(
                    SUM(
                        CASE
                            WHEN aa.status = 'Decommissioned'
                            THEN aa.quantity
                            ELSE 0
                        END
                    ),
                    0
                ) AS decommissioned

            FROM asset_types at

            INNER JOIN asset_allocations aa
                ON at.asset_type_id = aa.asset_type_id

            LEFT JOIN (
                SELECT
                    allocation_id,

                    COALESCE(
                        SUM(
                            CASE
                                WHEN status IN (
                                    'Scheduled',
                                    'In Progress',
                                    'Pending Confirmation'
                                )
                                THEN quantity_under_maintenance
                                ELSE 0
                            END
                        ),
                        0
                    ) AS under_maintenance,

                    COALESCE(
                        SUM(
                            CASE
                                WHEN status = 'Overdue'
                                THEN quantity_under_maintenance
                                ELSE 0
                            END
                        ),
                        0
                    ) AS overdue

                FROM maintenance

                GROUP BY allocation_id
            ) m
                ON aa.allocation_id = m.allocation_id

            GROUP BY
                at.asset_type_id,
                at.asset_name

            ORDER BY
                at.asset_type_id
        """)

        asset_status_by_type = cursor.fetchall()


        # Normalize each row to integers and calculate the
        # operational quantity from the same row.
        for asset in asset_status_by_type:

            allocated_quantity = int(
                asset["allocated_quantity"] or 0
            )

            under_maintenance = int(
                asset["under_maintenance"] or 0
            )

            overdue = int(
                asset["overdue"] or 0
            )

            decommissioned = int(
                asset["decommissioned"] or 0
            )

            asset["operational"] = max(
                0,
                allocated_quantity
                - under_maintenance
                - overdue
            )

            asset["under_maintenance"] = under_maintenance
            asset["overdue"] = overdue
            asset["decommissioned"] = decommissioned


        # ==================================================
        # SYSTEM ASSET TOTALS
        # ==================================================
        #
        # IMPORTANT:
        # Do NOT calculate these values independently from
        # maintenance and allocation tables. That caused the
        # main dashboard to disagree with its own asset table.
        #
        # These totals are now calculated directly from the
        # same asset-status rows displayed in the dashboard.
        # ==================================================

        total_assets = sum(
            int(asset["operational"])
            + int(asset["under_maintenance"])
            + int(asset["overdue"])
            + int(asset["decommissioned"])
            for asset in asset_status_by_type
        )

        operational_assets = sum(
            int(asset["operational"])
            for asset in asset_status_by_type
        )

        under_maintenance = sum(
            int(asset["under_maintenance"])
            for asset in asset_status_by_type
        )

        overdue = sum(
            int(asset["overdue"])
            for asset in asset_status_by_type
        )

        decommissioned = sum(
            int(asset["decommissioned"])
            for asset in asset_status_by_type
        )

        non_operational_assets = (
            under_maintenance
            + overdue
        )


        # ==================================================
        # ASSET STATUS SUMMARY
        # ==================================================

        asset_status = [
            {
                "status": "Operational",
                "count": operational_assets
            },
            {
                "status": "Under Maintenance",
                "count": under_maintenance
            },
            {
                "status": "Overdue",
                "count": overdue
            },
            {
                "status": "Decommissioned",
                "count": decommissioned
            }
        ]


        # ==================================================
        # ASSET CONDITION
        # ==================================================

        cursor.execute("""
            SELECT
                `condition`,
                COALESCE(SUM(quantity), 0) AS asset_count

            FROM asset_allocations

            GROUP BY `condition`

            ORDER BY
                CASE `condition`
                    WHEN 'Excellent' THEN 1
                    WHEN 'Good' THEN 2
                    WHEN 'Fair' THEN 3
                    WHEN 'Poor' THEN 4
                    ELSE 5
                END
        """)

        condition_summary = cursor.fetchall()


        # ==================================================
        # MAINTENANCE SUMMARY
        # ==================================================

        cursor.execute("""
            SELECT

                COUNT(*) AS total_records,

                COALESCE(
                    SUM(
                        CASE
                            WHEN status = 'Scheduled'
                            THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS scheduled,

                COALESCE(
                    SUM(
                        CASE
                            WHEN status = 'In Progress'
                            THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS in_progress,

                COALESCE(
                    SUM(
                        CASE
                            WHEN status = 'Pending Confirmation'
                            THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS pending_confirmation,

                COALESCE(
                    SUM(
                        CASE
                            WHEN status = 'Completed'
                            THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS completed,

                COALESCE(
                    SUM(
                        CASE
                            WHEN status = 'Overdue'
                            THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS overdue

            FROM maintenance
        """)

        maintenance_summary = cursor.fetchone()


        # ==================================================
        # INVENTORY SUMMARY
        # ==================================================

        cursor.execute("""
            SELECT

                COUNT(*) AS total_items,

                COALESCE(
                    SUM(quantity),
                    0
                ) AS total_quantity,

                COALESCE(
                    SUM(
                        CASE
                            WHEN quantity <= minimum_quantity
                            THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS low_stock_items

            FROM inventory
        """)

        inventory_summary = cursor.fetchone()


        # ==================================================
        # INVENTORY BY CATEGORY
        # ==================================================

        cursor.execute("""
            SELECT
                category,
                COALESCE(SUM(quantity), 0) AS quantity

            FROM inventory

            GROUP BY category

            ORDER BY quantity DESC
        """)

        inventory_by_category = cursor.fetchall()


        # ==================================================
        # INVENTORY BY UNIT
        # ==================================================

        cursor.execute("""
            SELECT
                unit_id,
                COALESCE(SUM(quantity), 0) AS quantity

            FROM inventory

            GROUP BY unit_id

            ORDER BY unit_id
        """)

        inventory_by_unit = cursor.fetchall()


        # ==================================================
        # OVERALL READINESS
        # ==================================================

        cursor.execute("""
            SELECT

                COALESCE(
                    AVG(availability_score),
                    0
                ) AS availability,

                COALESCE(
                    AVG(serviceability_score),
                    0
                ) AS serviceability,

                COALESCE(
                    AVG(maintenance_score),
                    0
                ) AS maintenance_compliance,

                COALESCE(
                    AVG(readiness_score),
                    0
                ) AS readiness

            FROM readiness
        """)

        readiness_summary = cursor.fetchone()


        # ==================================================
        # UNIT LIST
        # ==================================================

        cursor.execute("""
            SELECT
                unit_id,
                unit_name

            FROM units

            ORDER BY unit_id
        """)

        units = cursor.fetchall()


        # ==================================================
        # UNIT COMPARISON
        #
        # IMPORTANT:
        # This query retrieves all values required by the
        # Unit Comparison table.
        # ==================================================

        cursor.execute("""
            SELECT

                u.unit_id,
                u.unit_name,

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
                ) AS decommissioned_assets,

                COALESCE(
                    AVG(r.availability_score),
                    0
                ) AS availability,

                COALESCE(
                    AVG(r.serviceability_score),
                    0
                ) AS serviceability,

                COALESCE(
                    AVG(r.maintenance_score),
                    0
                ) AS maintenance_compliance,

                COALESCE(
                    AVG(r.readiness_score),
                    0
                ) AS readiness

            FROM units u

            LEFT JOIN asset_allocations aa
                ON u.unit_id = aa.unit_id

            LEFT JOIN readiness r
                ON aa.allocation_id = r.allocation_id

            GROUP BY
                u.unit_id,
                u.unit_name

            ORDER BY
                u.unit_id
        """)

        unit_asset_summary = cursor.fetchall()


        # Convert numeric values to predictable Python types.
        for unit in unit_asset_summary:

            unit["total_assets"] = int(
                unit["total_assets"] or 0
            )

            unit["decommissioned_assets"] = int(
                unit["decommissioned_assets"] or 0
            )

            unit["availability"] = float(
                unit["availability"] or 0
            )

            unit["serviceability"] = float(
                unit["serviceability"] or 0
            )

            unit["maintenance_compliance"] = float(
                unit["maintenance_compliance"] or 0
            )

            unit["readiness"] = float(
                unit["readiness"] or 0
            )


        # ==================================================
        # FINAL DATA
        # ==================================================

        return {

            "total_assets":
                total_assets,

            "operational_assets":
                operational_assets,

            "non_operational_assets":
                non_operational_assets,

            "decommissioned_assets":
                decommissioned,

            "under_maintenance_assets":
                under_maintenance,

            "overdue_assets":
                overdue,

            "asset_status":
                asset_status,

            "asset_status_by_type":
                asset_status_by_type,

            "condition_summary":
                condition_summary,

            "maintenance_summary":
                maintenance_summary,

            "inventory_summary":
                inventory_summary,

            "inventory_by_category":
                inventory_by_category,

            "inventory_by_unit":
                inventory_by_unit,

            "readiness_summary":
                readiness_summary,

            "units":
                units,

            "unit_asset_summary":
                unit_asset_summary
        }


    finally:

        cursor.close()
        connection.close()
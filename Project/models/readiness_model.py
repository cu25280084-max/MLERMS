from config import get_db_connection

from models.maintenance_model import refresh_maintenance_statuses


# ============================================================
# READINESS SCORING CONSTANTS
# ============================================================

CONDITION_SCORES = {
    "Excellent": 100.00,
    "Good": 80.00,
    "Fair": 60.00,
    "Poor": 40.00,
}


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def calculate_availability_score(total_quantity, maintenance_quantity, status):
    """
    Calculate availability as the percentage of an allocation
    that is currently operational.

    Decommissioned allocations receive 0 availability.
    """

    total_quantity = int(total_quantity or 0)
    maintenance_quantity = int(maintenance_quantity or 0)

    if status == "Decommissioned":
        return 0.00

    if total_quantity <= 0:
        return 0.00

    operational_quantity = total_quantity - maintenance_quantity

    if operational_quantity < 0:
        operational_quantity = 0

    score = (operational_quantity / total_quantity) * 100

    return round(min(score, 100.00), 2)


def calculate_serviceability_score(condition):
    """
    Convert the existing asset condition into a
    0-100 serviceability score.
    """

    return CONDITION_SCORES.get(
        condition,
        0.00
    )


def calculate_maintenance_score(overdue_count):
    """
    Maintenance compliance is 100 when the allocation has
    no overdue maintenance and 0 when overdue maintenance exists.
    """

    if int(overdue_count or 0) > 0:
        return 0.00

    return 100.00


def calculate_readiness_score(
    availability_score,
    serviceability_score,
    maintenance_score
):
    """
    Apply the project-defined weighted readiness formula.

    40% Availability
    35% Serviceability
    25% Maintenance Compliance
    """

    score = (
        (0.40 * availability_score)
        + (0.35 * serviceability_score)
        + (0.25 * maintenance_score)
    )

    return round(min(max(score, 0.00), 100.00), 2)


def get_readiness_classification(readiness_score):
    """
    Classify the final readiness score according to
    the ranges defined in the project synopsis.
    """

    score = float(readiness_score or 0)

    if score >= 90:
        return "Fully Ready"

    if score >= 75:
        return "Operational"

    if score >= 50:
        return "Limited Readiness"

    return "Not Ready"


# ============================================================
# DATA RETRIEVAL
# ============================================================

def get_allocation_readiness_data(unit_id=None):
    """
    Retrieve asset allocation data required for readiness
    calculation.

    Maintenance statuses are refreshed before calculation.
    """

    refresh_maintenance_statuses()

    connection = get_db_connection()

    try:
        cursor = connection.cursor(dictionary=True)

        query = """
            SELECT
                aa.allocation_id,
                aa.asset_type_id,
                at.asset_name,

                c.category_id,
                c.category_name,

                aa.unit_id,
                u.unit_name,

                aa.quantity,
                aa.status,
                aa.`condition`,

                COALESCE(
                    (
                        SELECT SUM(
                            m.quantity_under_maintenance
                        )
                        FROM maintenance m
                        WHERE m.allocation_id = aa.allocation_id
                          AND m.status IN (
                              'Scheduled',
                              'In Progress',
                              'Pending Confirmation',
                              'Overdue'
                          )
                    ),
                    0
                ) AS maintenance_quantity,

                (
                    SELECT COUNT(*)
                    FROM maintenance m
                    WHERE m.allocation_id = aa.allocation_id
                      AND m.status = 'Overdue'
                ) AS overdue_count

            FROM asset_allocations aa

            INNER JOIN asset_types at
                ON aa.asset_type_id = at.asset_type_id

            INNER JOIN categories c
                ON at.category_id = c.category_id

            INNER JOIN units u
                ON aa.unit_id = u.unit_id

            WHERE (
                %s IS NULL
                OR aa.unit_id = %s
            )

            ORDER BY
                aa.allocation_id
        """

        cursor.execute(
            query,
            (unit_id, unit_id)
        )

        return cursor.fetchall()

    finally:
        cursor.close()
        connection.close()


# ============================================================
# READINESS CALCULATION
# ============================================================

def calculate_allocation_readiness(allocation):
    """
    Calculate all readiness components for one allocation.
    """

    availability_score = calculate_availability_score(
        allocation["quantity"],
        allocation["maintenance_quantity"],
        allocation["status"]
    )

    serviceability_score = calculate_serviceability_score(
        allocation["condition"]
    )

    maintenance_score = calculate_maintenance_score(
        allocation["overdue_count"]
    )

    readiness_score = calculate_readiness_score(
        availability_score,
        serviceability_score,
        maintenance_score
    )

    classification = get_readiness_classification(
        readiness_score
    )

    return {
        "allocation_id": allocation["allocation_id"],
        "asset_type_id": allocation["asset_type_id"],
        "asset_name": allocation["asset_name"],
        "category_id": allocation["category_id"],
        "category_name": allocation["category_name"],
        "unit_id": allocation["unit_id"],
        "unit_name": allocation["unit_name"],
        "quantity": int(allocation["quantity"]),
        "status": allocation["status"],
        "condition": allocation["condition"],
        "maintenance_quantity": int(
            allocation["maintenance_quantity"] or 0
        ),
        "overdue_count": int(
            allocation["overdue_count"] or 0
        ),
        "availability_score": availability_score,
        "serviceability_score": serviceability_score,
        "maintenance_score": maintenance_score,
        "readiness_score": readiness_score,
        "classification": classification,
    }


def calculate_unit_readiness(unit_id):
    """
    Calculate readiness for every allocation belonging
    to the selected unit.
    """

    allocations = get_allocation_readiness_data(unit_id)

    return [
        calculate_allocation_readiness(allocation)
        for allocation in allocations
    ]


# ============================================================
# SAVE READINESS RESULTS
# ============================================================

def save_readiness_results(readiness_records):
    """
    Insert or update calculated readiness results
    in the readiness table.
    """

    if not readiness_records:
        return

    connection = get_db_connection()

    try:
        cursor = connection.cursor()

        query = """
            INSERT INTO readiness (
                allocation_id,
                availability_score,
                serviceability_score,
                maintenance_score,
                readiness_score
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s
            )
            ON DUPLICATE KEY UPDATE
                availability_score = VALUES(
                    availability_score
                ),
                serviceability_score = VALUES(
                    serviceability_score
                ),
                maintenance_score = VALUES(
                    maintenance_score
                ),
                readiness_score = VALUES(
                    readiness_score
                )
        """

        values = [
            (
                record["allocation_id"],
                record["availability_score"],
                record["serviceability_score"],
                record["maintenance_score"],
                record["readiness_score"],
            )
            for record in readiness_records
        ]

        cursor.executemany(
            query,
            values
        )

        connection.commit()

    finally:
        cursor.close()
        connection.close()


def refresh_readiness(unit_id=None):
    """
    Recalculate readiness and store the results
    in the readiness table.
    """

    records = calculate_unit_readiness(unit_id)

    save_readiness_results(records)

    return records

# ============================================================
# READINESS RETRIEVAL
# ============================================================

def get_readiness_by_allocation(allocation_id):
    """
    Retrieve readiness information for one asset allocation.
    """

    connection = get_db_connection()

    try:
        cursor = connection.cursor(dictionary=True)

        query = """
            SELECT
                r.allocation_id,

                aa.asset_type_id,
                at.asset_name,

                c.category_id,
                c.category_name,

                aa.unit_id,
                u.unit_name,

                aa.quantity,
                aa.status,
                aa.`condition`,

                r.availability_score,
                r.serviceability_score,
                r.maintenance_score,
                r.readiness_score

            FROM readiness r

            INNER JOIN asset_allocations aa
                ON r.allocation_id = aa.allocation_id

            INNER JOIN asset_types at
                ON aa.asset_type_id = at.asset_type_id

            INNER JOIN categories c
                ON at.category_id = c.category_id

            INNER JOIN units u
                ON aa.unit_id = u.unit_id

            WHERE r.allocation_id = %s
        """

        cursor.execute(
            query,
            (allocation_id,)
        )

        record = cursor.fetchone()

        if record:
            record["classification"] = (
                get_readiness_classification(
                    record["readiness_score"]
                )
            )

        return record

    finally:
        cursor.close()
        connection.close()


def get_readiness_by_unit(unit_id):
    """
    Retrieve all stored readiness results for one unit.
    """

    connection = get_db_connection()

    try:
        cursor = connection.cursor(dictionary=True)

        query = """
            SELECT
                r.allocation_id,

                aa.asset_type_id,
                at.asset_name,

                c.category_id,
                c.category_name,

                aa.unit_id,
                u.unit_name,

                aa.quantity,
                aa.status,
                aa.`condition`,

                r.availability_score,
                r.serviceability_score,
                r.maintenance_score,
                r.readiness_score

            FROM readiness r

            INNER JOIN asset_allocations aa
                ON r.allocation_id = aa.allocation_id

            INNER JOIN asset_types at
                ON aa.asset_type_id = at.asset_type_id

            INNER JOIN categories c
                ON at.category_id = c.category_id

            INNER JOIN units u
                ON aa.unit_id = u.unit_id

            WHERE aa.unit_id = %s

            ORDER BY r.readiness_score DESC
        """

        cursor.execute(
            query,
            (unit_id,)
        )

        records = cursor.fetchall()

        for record in records:
            record["classification"] = (
                get_readiness_classification(
                    record["readiness_score"]
                )
            )

        return records

    finally:
        cursor.close()
        connection.close()


def get_category_readiness(unit_id):
    """
    Calculate average readiness by category for a unit.
    """

    records = get_readiness_by_unit(unit_id)

    category_data = {}

    for record in records:

        category_id = record["category_id"]

        if category_id not in category_data:
            category_data[category_id] = {
                "category_id": category_id,
                "category_name": record["category_name"],
                "total_score": 0.0,
                "asset_count": 0,
            }

        category_data[category_id]["total_score"] += float(
            record["readiness_score"]
        )

        category_data[category_id]["asset_count"] += 1

    results = []

    for category in category_data.values():

        average_score = (
            category["total_score"]
            / category["asset_count"]
        )

        results.append({
            "category_id": category["category_id"],
            "category_name": category["category_name"],
            "asset_count": category["asset_count"],
            "readiness_score": round(
                average_score,
                2
            ),
            "classification": get_readiness_classification(
                average_score
            ),
        })

    results.sort(
        key=lambda item: item["readiness_score"],
        reverse=True
    )

    return results


def get_unit_readiness_summary(unit_id):
    """
    Calculate the overall average readiness for a unit.
    """

    records = get_readiness_by_unit(unit_id)

    if not records:
        return {
            "unit_id": unit_id,
            "asset_count": 0,
            "readiness_score": 0.0,
            "classification": "Not Ready",
        }

    total_score = sum(
        float(record["readiness_score"])
        for record in records
    )

    average_score = (
        total_score / len(records)
    )

    return {
        "unit_id": unit_id,
        "unit_name": records[0]["unit_name"],
        "asset_count": len(records),
        "readiness_score": round(
            average_score,
            2
        ),
        "classification": get_readiness_classification(
            average_score
        ),
    }
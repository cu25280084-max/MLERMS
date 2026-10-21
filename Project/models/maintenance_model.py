from config import get_db_connection


ACTIVE_MAINTENANCE_STATUSES = (
    "Scheduled",
    "In Progress",
    "Pending Confirmation",
    "Overdue"
)


def get_date_based_status(
    maintenance_date,
    expected_completion_date
):

    from datetime import date

    today = date.today()

    if maintenance_date > today:
        return "Scheduled"

    if today < expected_completion_date:
        return "In Progress"

    return "Pending Confirmation"


def refresh_maintenance_statuses():

    connection = get_db_connection()

    try:

        cursor = connection.cursor()

        query = """
            UPDATE maintenance

            SET status =
                CASE

                    WHEN status = 'Completed'
                        THEN 'Completed'

                    WHEN status = 'Overdue'
                        THEN 'Overdue'

                    WHEN expected_completion_date IS NULL
                        THEN status

                    WHEN CURDATE() < maintenance_date
                        THEN 'Scheduled'

                    WHEN CURDATE() < expected_completion_date
                        THEN 'In Progress'

                    ELSE
                        'Pending Confirmation'

                END

            WHERE status NOT IN (
                'Completed',
                'Overdue'
            )
        """

        cursor.execute(query)

        connection.commit()

    finally:

        cursor.close()
        connection.close()


def get_all_maintenance(unit_id=None):

    refresh_maintenance_statuses()

    connection = get_db_connection()

    try:

        cursor = connection.cursor(dictionary=True)

        query = """
            SELECT

                m.maintenance_id,
                m.allocation_id,

                aa.asset_type_id,
                at.asset_name,

                c.category_name,

                aa.unit_id,
                u.unit_name,

                aa.quantity AS total_quantity,

                m.maintenance_date,
                m.expected_completion_date,

                m.type,

                m.quantity_under_maintenance,
                m.quantity_not_under_maintenance,

                m.status,
                m.next_due_date

            FROM maintenance m

            INNER JOIN asset_allocations aa
                ON m.allocation_id = aa.allocation_id

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

            ORDER BY m.maintenance_id DESC
        """

        cursor.execute(
            query,
            (unit_id, unit_id)
        )

        return cursor.fetchall()

    finally:

        cursor.close()
        connection.close()


def get_current_maintenance_quantity(
    allocation_id,
    exclude_maintenance_id=None
):

    refresh_maintenance_statuses()

    connection = get_db_connection()

    try:

        cursor = connection.cursor()

        query = """
            SELECT
                COALESCE(
                    SUM(quantity_under_maintenance),
                    0
                )

            FROM maintenance

            WHERE allocation_id = %s

              AND status IN (
                  'Scheduled',
                  'In Progress',
                  'Pending Confirmation',
                  'Overdue'
              )
        """

        values = [allocation_id]

        if exclude_maintenance_id is not None:

            query += """
                AND maintenance_id != %s
            """

            values.append(
                exclude_maintenance_id
            )

        cursor.execute(
            query,
            tuple(values)
        )

        result = cursor.fetchone()

        return int(result[0])

    finally:

        cursor.close()
        connection.close()


def get_allocations_for_maintenance(unit_id):

    refresh_maintenance_statuses()

    connection = get_db_connection()

    try:

        cursor = connection.cursor(dictionary=True)

        query = """
            SELECT

                aa.allocation_id,

                aa.asset_type_id,

                at.asset_name,

                c.category_name,

                aa.unit_id,
                u.unit_name,

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
                                'Pending Confirmation',
                                'Overdue'
                            )

                    ),
                    0
                ) AS current_maintenance_quantity

            FROM asset_allocations aa

            INNER JOIN asset_types at
                ON aa.asset_type_id =
                   at.asset_type_id

            INNER JOIN categories c
                ON at.category_id =
                   c.category_id

            INNER JOIN units u
                ON aa.unit_id =
                   u.unit_id

            WHERE aa.unit_id = %s

              AND aa.status != 'Decommissioned'

            ORDER BY
                c.category_name,
                at.asset_name
        """

        cursor.execute(
            query,
            (unit_id,)
        )

        allocations = cursor.fetchall()

        for allocation in allocations:

            total_quantity = int(
                allocation["quantity"]
            )

            current_quantity = int(
                allocation[
                    "current_maintenance_quantity"
                ] or 0
            )

            allocation["available_quantity"] = (
                total_quantity
                - current_quantity
            )

        return allocations

    finally:

        cursor.close()
        connection.close()


def create_maintenance(
    allocation_id,
    maintenance_date,
    expected_completion_date,
    maintenance_type,
    quantity_under_maintenance,
    quantity_not_under_maintenance,
    status,
    next_due_date
):

    connection = get_db_connection()

    try:

        cursor = connection.cursor()

        query = """
            INSERT INTO maintenance
            (
                allocation_id,
                maintenance_date,
                expected_completion_date,
                type,
                quantity_under_maintenance,
                quantity_not_under_maintenance,
                status,
                next_due_date
            )

            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            )
        """

        values = (
            allocation_id,
            maintenance_date,
            expected_completion_date,
            maintenance_type,
            quantity_under_maintenance,
            quantity_not_under_maintenance,
            status,
            next_due_date
        )

        cursor.execute(
            query,
            values
        )

        connection.commit()

        return cursor.lastrowid

    finally:

        cursor.close()
        connection.close()


def get_maintenance_by_id(
    maintenance_id
):

    refresh_maintenance_statuses()

    connection = get_db_connection()

    try:

        cursor = connection.cursor(
            dictionary=True
        )

        query = """
            SELECT

                m.maintenance_id,
                m.allocation_id,

                aa.asset_type_id,
                at.asset_name,

                c.category_name,

                aa.unit_id,
                u.unit_name,

                aa.quantity AS total_quantity,
                aa.status AS allocation_status,

                m.maintenance_date,
                m.expected_completion_date,

                m.type,

                m.quantity_under_maintenance,
                m.quantity_not_under_maintenance,

                m.status,
                m.next_due_date

            FROM maintenance m

            INNER JOIN asset_allocations aa
                ON m.allocation_id =
                   aa.allocation_id

            INNER JOIN asset_types at
                ON aa.asset_type_id =
                   at.asset_type_id

            INNER JOIN categories c
                ON at.category_id =
                   c.category_id

            INNER JOIN units u
                ON aa.unit_id =
                   u.unit_id

            WHERE m.maintenance_id = %s
        """

        cursor.execute(
            query,
            (maintenance_id,)
        )

        return cursor.fetchone()

    finally:

        cursor.close()
        connection.close()


def update_maintenance(
    maintenance_id,
    allocation_id,
    maintenance_date,
    expected_completion_date,
    maintenance_type,
    quantity_under_maintenance,
    quantity_not_under_maintenance,
    status,
    next_due_date
):

    connection = get_db_connection()

    try:

        cursor = connection.cursor()

        query = """
            UPDATE maintenance

            SET

                allocation_id = %s,

                maintenance_date = %s,

                expected_completion_date = %s,

                type = %s,

                quantity_under_maintenance = %s,

                quantity_not_under_maintenance = %s,

                status = %s,

                next_due_date = %s

            WHERE maintenance_id = %s
        """

        values = (
            allocation_id,
            maintenance_date,
            expected_completion_date,
            maintenance_type,
            quantity_under_maintenance,
            quantity_not_under_maintenance,
            status,
            next_due_date,
            maintenance_id
        )

        cursor.execute(
            query,
            values
        )

        connection.commit()

    finally:

        cursor.close()
        connection.close()


def mark_maintenance_completed(
    maintenance_id
):

    connection = get_db_connection()

    try:

        cursor = connection.cursor()

        query = """
            UPDATE maintenance

            SET status = 'Completed'

            WHERE maintenance_id = %s
              AND status = 'Pending Confirmation'
        """

        cursor.execute(
            query,
            (maintenance_id,)
        )

        connection.commit()

        return cursor.rowcount > 0

    finally:

        cursor.close()
        connection.close()


def mark_maintenance_overdue(
    maintenance_id
):

    connection = get_db_connection()

    try:

        cursor = connection.cursor()

        query = """
            UPDATE maintenance

            SET status = 'Overdue'

            WHERE maintenance_id = %s
              AND status = 'Pending Confirmation'
        """

        cursor.execute(
            query,
            (maintenance_id,)
        )

        connection.commit()

        return cursor.rowcount > 0

    finally:

        cursor.close()
        connection.close()


def delete_maintenance(
    maintenance_id
):

    connection = get_db_connection()

    try:

        cursor = connection.cursor()

        query = """
            DELETE FROM maintenance

            WHERE maintenance_id = %s
        """

        cursor.execute(
            query,
            (maintenance_id,)
        )

        connection.commit()

    finally:

        cursor.close()
        connection.close()
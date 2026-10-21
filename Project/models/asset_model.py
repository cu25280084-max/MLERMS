from config import get_db_connection


def get_all_categories():
    connection = get_db_connection()

    try:
        cursor = connection.cursor(dictionary=True)

        query = """
            SELECT
                category_id,
                category_name
            FROM categories
            ORDER BY category_name
        """

        cursor.execute(query)

        return cursor.fetchall()

    finally:
        cursor.close()
        connection.close()


def get_all_units():
    connection = get_db_connection()

    try:
        cursor = connection.cursor(dictionary=True)

        query = """
            SELECT
                unit_id,
                unit_name
            FROM units
            ORDER BY unit_id
        """

        cursor.execute(query)

        return cursor.fetchall()

    finally:
        cursor.close()
        connection.close()


def get_all_asset_types():
    connection = get_db_connection()

    try:
        cursor = connection.cursor(dictionary=True)

        query = """
            SELECT
                asset_type_id,
                category_id,
                asset_name
            FROM asset_types
            ORDER BY asset_type_id
        """

        cursor.execute(query)

        return cursor.fetchall()

    finally:
        cursor.close()
        connection.close()


def get_asset_types_by_category(category_id):
    connection = get_db_connection()

    try:
        cursor = connection.cursor(dictionary=True)

        query = """
            SELECT
                asset_type_id,
                category_id,
                asset_name
            FROM asset_types
            WHERE category_id = %s
            ORDER BY asset_type_id
        """

        cursor.execute(query, (category_id,))

        return cursor.fetchall()

    finally:
        cursor.close()
        connection.close()


def get_all_allocations():
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
                aa.acquisition_date,
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
                ) AS maintenance_quantity

            FROM asset_allocations aa

            INNER JOIN asset_types at
                ON aa.asset_type_id = at.asset_type_id

            INNER JOIN categories c
                ON at.category_id = c.category_id

            INNER JOIN units u
                ON aa.unit_id = u.unit_id

            ORDER BY aa.allocation_id DESC
        """

        cursor.execute(query)

        allocations = cursor.fetchall()

        # Calculate the current display status.
        for allocation in allocations:

            maintenance_quantity = int(
                allocation["maintenance_quantity"]
            )

            quantity = int(
                allocation["quantity"]
            )

            if allocation["status"] == "Decommissioned":

                allocation["display_status"] = "Decommissioned"

            elif overdue_quantity > 0:

                allocation["display_status"] = "Overdue"

            elif maintenance_quantity > 0:

                allocation["display_status"] = "Under Maintenance"

            else:

                allocation["display_status"] = "Operational"

        return allocations

    finally:
        cursor.close()
        connection.close()


def get_allocations_by_unit(unit_id):

    connection = get_db_connection()

    try:

        cursor = connection.cursor(
            dictionary=True
        )

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
                aa.acquisition_date,
                aa.`condition`,

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
                ) AS maintenance_quantity

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

            ORDER BY
                aa.allocation_id DESC
        """

        cursor.execute(
            query,
            (unit_id,)
        )

        allocations = cursor.fetchall()

        for allocation in allocations:

            maintenance_quantity = int(
                allocation["maintenance_quantity"]
            )

            quantity = int(
                allocation["quantity"]
            )

            if allocation["status"] == "Decommissioned":

                allocation["display_status"] = (
                    "Decommissioned"
                )

            elif maintenance_quantity > 0:

                allocation["display_status"] = (
                    "Under Maintenance"
                )

            else:

                allocation["display_status"] = (
                    "Operational"
                )

            allocation["operational_quantity"] = (
                quantity - maintenance_quantity
            )

        return allocations

    finally:

        cursor.close()
        connection.close()


def get_allocation_by_id(allocation_id):
    connection = get_db_connection()

    try:
        cursor = connection.cursor(dictionary=True)

        query = """
            SELECT
                allocation_id,
                asset_type_id,
                unit_id,
                quantity,
                status,
                acquisition_date,
                `condition`
            FROM asset_allocations
            WHERE allocation_id = %s
        """

        cursor.execute(query, (allocation_id,))

        return cursor.fetchone()

    finally:
        cursor.close()
        connection.close()


def allocation_exists(asset_type_id, unit_id):
    connection = get_db_connection()

    try:
        cursor = connection.cursor()

        query = """
            SELECT 1
            FROM asset_allocations
            WHERE asset_type_id = %s
              AND unit_id = %s
            LIMIT 1
        """

        cursor.execute(
            query,
            (asset_type_id, unit_id)
        )

        return cursor.fetchone() is not None

    finally:
        cursor.close()
        connection.close()


def create_allocation(
    asset_type_id,
    unit_id,
    quantity,
    status,
    acquisition_date,
    condition
):
    connection = get_db_connection()

    try:
        cursor = connection.cursor()

        query = """
            INSERT INTO asset_allocations
            (
                asset_type_id,
                unit_id,
                quantity,
                status,
                acquisition_date,
                `condition`
            )
            VALUES (%s, %s, %s, %s, %s, %s)
        """

        values = (
            asset_type_id,
            unit_id,
            quantity,
            status,
            acquisition_date,
            condition
        )

        cursor.execute(query, values)

        connection.commit()

        return cursor.lastrowid

    finally:
        cursor.close()
        connection.close()


def update_allocation(
    allocation_id,
    asset_type_id,
    unit_id,
    quantity,
    status,
    acquisition_date,
    condition
):
    connection = get_db_connection()

    try:
        cursor = connection.cursor()

        query = """
            UPDATE asset_allocations
            SET
                asset_type_id = %s,
                unit_id = %s,
                quantity = %s,
                status = %s,
                acquisition_date = %s,
                `condition` = %s
            WHERE allocation_id = %s
        """

        values = (
            asset_type_id,
            unit_id,
            quantity,
            status,
            acquisition_date,
            condition,
            allocation_id
        )

        cursor.execute(query, values)

        connection.commit()

    finally:
        cursor.close()
        connection.close()


def delete_allocation(allocation_id):
    connection = get_db_connection()

    try:
        cursor = connection.cursor()

        query = """
            DELETE FROM asset_allocations
            WHERE allocation_id = %s
        """

        cursor.execute(query, (allocation_id,))

        connection.commit()

    finally:
        cursor.close()
        connection.close()


def decommission_allocation(allocation_id):
    connection = get_db_connection()

    try:
        cursor = connection.cursor()

        query = """
            UPDATE asset_allocations
            SET status = 'Decommissioned'
            WHERE allocation_id = %s
              AND status = 'Operational'
        """

        cursor.execute(
            query,
            (allocation_id,)
        )

        connection.commit()

    finally:
        cursor.close()
        connection.close()


def recommission_allocation(allocation_id):
    connection = get_db_connection()

    try:
        cursor = connection.cursor()

        query = """
            UPDATE asset_allocations
            SET status = 'Operational'
            WHERE allocation_id = %s
              AND status = 'Decommissioned'
        """

        cursor.execute(
            query,
            (allocation_id,)
        )

        connection.commit()

    finally:
        cursor.close()
        connection.close()
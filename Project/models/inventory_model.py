from config import get_db_connection


def get_inventory_by_unit(unit_id):
    connection = get_db_connection()

    try:
        cursor = connection.cursor(dictionary=True)

        query = """
            SELECT
                i.item_id,
                i.item_name,
                i.category,
                i.quantity,
                i.unit AS measurement_unit,
                i.minimum_quantity,
                i.unit_id,
                u.unit_name,
                i.location,
                i.supplier,
                i.unit_cost,
                i.last_updated,
                CASE
                    WHEN i.quantity <= i.minimum_quantity
                    THEN 'Low Stock'
                    ELSE 'Sufficient'
                END AS stock_status
            FROM inventory i
            INNER JOIN units u
                ON i.unit_id = u.unit_id
            WHERE i.unit_id = %s
            ORDER BY i.item_id DESC
        """

        cursor.execute(query, (unit_id,))

        return cursor.fetchall()

    finally:
        cursor.close()
        connection.close()


def get_inventory_by_id(item_id):
    connection = get_db_connection()

    try:
        cursor = connection.cursor(dictionary=True)

        query = """
            SELECT
                i.item_id,
                i.item_name,
                i.category,
                i.quantity,
                i.unit AS measurement_unit,
                i.minimum_quantity,
                i.unit_id,
                u.unit_name,
                i.location,
                i.supplier,
                i.unit_cost,
                i.last_updated,
                CASE
                    WHEN i.quantity <= i.minimum_quantity
                    THEN 'Low Stock'
                    ELSE 'Sufficient'
                END AS stock_status
            FROM inventory i
            INNER JOIN units u
                ON i.unit_id = u.unit_id
            WHERE i.item_id = %s
        """

        cursor.execute(query, (item_id,))

        return cursor.fetchone()

    finally:
        cursor.close()
        connection.close()


def create_inventory_item(
    item_name,
    category,
    quantity,
    measurement_unit,
    minimum_quantity,
    unit_id,
    location,
    supplier,
    unit_cost
):
    connection = get_db_connection()

    try:
        cursor = connection.cursor()

        query = """
            INSERT INTO inventory (
                item_name,
                category,
                quantity,
                unit,
                minimum_quantity,
                unit_id,
                location,
                supplier,
                unit_cost
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        values = (
            item_name,
            category,
            quantity,
            measurement_unit,
            minimum_quantity,
            unit_id,
            location,
            supplier,
            unit_cost
        )

        cursor.execute(query, values)

        connection.commit()

        return cursor.lastrowid

    finally:
        cursor.close()
        connection.close()


def update_inventory_item(
    item_id,
    item_name,
    category,
    quantity,
    measurement_unit,
    minimum_quantity,
    location,
    supplier,
    unit_cost
):
    connection = get_db_connection()

    try:
        cursor = connection.cursor()

        query = """
            UPDATE inventory
            SET
                item_name = %s,
                category = %s,
                quantity = %s,
                unit = %s,
                minimum_quantity = %s,
                location = %s,
                supplier = %s,
                unit_cost = %s
            WHERE item_id = %s
        """

        values = (
            item_name,
            category,
            quantity,
            measurement_unit,
            minimum_quantity,
            location,
            supplier,
            unit_cost,
            item_id
        )

        cursor.execute(query, values)

        connection.commit()

    finally:
        cursor.close()
        connection.close()


def delete_inventory_item(item_id):
    connection = get_db_connection()

    try:
        cursor = connection.cursor()

        query = """
            DELETE FROM inventory
            WHERE item_id = %s
        """

        cursor.execute(query, (item_id,))

        connection.commit()

    finally:
        cursor.close()
        connection.close()


def get_low_stock_items_by_unit(unit_id):
    connection = get_db_connection()

    try:
        cursor = connection.cursor(dictionary=True)

        query = """
            SELECT
                i.item_id,
                i.item_name,
                i.category,
                i.quantity,
                i.unit AS measurement_unit,
                i.minimum_quantity,
                i.unit_id,
                u.unit_name,
                i.location,
                i.supplier,
                i.unit_cost,
                i.last_updated
            FROM inventory i
            INNER JOIN units u
                ON i.unit_id = u.unit_id
            WHERE i.unit_id = %s
              AND i.quantity <= i.minimum_quantity
            ORDER BY i.quantity ASC, i.item_name ASC
        """

        cursor.execute(query, (unit_id,))

        return cursor.fetchall()

    finally:
        cursor.close()
        connection.close()


def get_low_stock_count_by_unit(unit_id):
    connection = get_db_connection()

    try:
        cursor = connection.cursor()

        query = """
            SELECT COUNT(*)
            FROM inventory
            WHERE unit_id = %s
              AND quantity <= minimum_quantity
        """

        cursor.execute(query, (unit_id,))

        result = cursor.fetchone()

        return result[0]

    finally:
        cursor.close()
        connection.close()
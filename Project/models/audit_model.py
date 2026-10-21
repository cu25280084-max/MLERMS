from config import get_db_connection


def create_audit_log(
    user_id,
    action,
    module,
    record_id=None,
    description=""
):
    connection = get_db_connection()
    cursor = connection.cursor()

    query = """
        INSERT INTO audit_logs
        (
            user_id,
            action,
            module,
            record_id,
            description
        )
        VALUES (%s, %s, %s, %s, %s)
    """

    values = (
        user_id,
        action,
        module,
        record_id,
        description
    )

    try:
        cursor.execute(query, values)
        connection.commit()
    finally:
        cursor.close()
        connection.close()


def get_audit_logs(
    limit=200,
    module=None,
    action=None,
    user_id=None,
    date_from=None,
    date_to=None
):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    query = """
        SELECT
            audit_logs.audit_id,
            audit_logs.user_id,
            users.username,
            audit_logs.action,
            audit_logs.module,
            audit_logs.record_id,
            audit_logs.description,
            audit_logs.created_at
        FROM audit_logs
        LEFT JOIN users
            ON audit_logs.user_id = users.id
        WHERE 1=1
    """

    values = []

    if module:
        query += " AND audit_logs.module = %s"
        values.append(module)

    if action:
        query += " AND audit_logs.action = %s"
        values.append(action)

    if user_id:
        query += " AND audit_logs.user_id = %s"
        values.append(user_id)

    if date_from:
        query += " AND DATE(audit_logs.created_at) >= %s"
        values.append(date_from)

    if date_to:
        query += " AND DATE(audit_logs.created_at) <= %s"
        values.append(date_to)

    query += """
        ORDER BY audit_logs.audit_id DESC
        LIMIT %s
    """

    values.append(limit)

    try:
        cursor.execute(query, tuple(values))
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def get_audit_summary():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    summary = {
        "total": 0,
        "by_module": [],
        "by_action": []
    }

    try:
        # Total audit records
        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM audit_logs
        """)

        result = cursor.fetchone()
        summary["total"] = result["total"]


        # Records by module
        cursor.execute("""
            SELECT
                module,
                COUNT(*) AS total
            FROM audit_logs
            GROUP BY module
            ORDER BY total DESC
        """)

        summary["by_module"] = cursor.fetchall()


        # Records by action
        cursor.execute("""
            SELECT
                action,
                COUNT(*) AS total
            FROM audit_logs
            GROUP BY action
            ORDER BY total DESC
        """)

        summary["by_action"] = cursor.fetchall()

        return summary

    finally:
        cursor.close()
        connection.close()
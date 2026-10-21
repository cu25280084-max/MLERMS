from werkzeug.security import generate_password_hash, check_password_hash
from config import get_db_connection


# Keep the existing password-hashing behavior and extend the user helpers
# for login lockout and TOTP-based two-factor authentication.
def create_user(username, password, role="Administrator"):
    connection = get_db_connection()
    cursor = None
    try:
        cursor = connection.cursor()
        password_hash = generate_password_hash(password)
        cursor.execute(
            """INSERT INTO users (username, password_hash, role)
               VALUES (%s, %s, %s)""",
            (username, password_hash, role),
        )
        connection.commit()
        return cursor.lastrowid
    finally:
        if cursor:
            cursor.close()
        connection.close()


def get_user_by_username(username):
    connection = get_db_connection()
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """SELECT id, username, password_hash, role,
                      totp_secret, failed_login_attempts, locked_until
               FROM users WHERE username = %s""",
            (username,),
        )
        return cursor.fetchone()
    finally:
        if cursor:
            cursor.close()
        connection.close()


def get_user_by_id(user_id):
    connection = get_db_connection()
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """SELECT id, username, password_hash, role,
                      totp_secret, failed_login_attempts, locked_until
               FROM users WHERE id = %s""",
            (user_id,),
        )
        return cursor.fetchone()
    finally:
        if cursor:
            cursor.close()
        connection.close()


def record_failed_login(user_id, max_attempts=5):
    """Increment failed attempts and lock the account for 15 minutes at threshold."""
    connection = get_db_connection()
    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute(
            """UPDATE users
               SET failed_login_attempts = failed_login_attempts + 1,
                   locked_until = CASE
                       WHEN failed_login_attempts + 1 >= %s
                       THEN DATE_ADD(NOW(), INTERVAL 15 MINUTE)
                       ELSE locked_until
                   END
               WHERE id = %s""",
            (max_attempts, user_id),
        )
        connection.commit()
    finally:
        if cursor:
            cursor.close()
        connection.close()


def clear_login_failures(user_id):
    connection = get_db_connection()
    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE users SET failed_login_attempts = 0, locked_until = NULL WHERE id = %s",
            (user_id,),
        )
        connection.commit()
    finally:
        if cursor:
            cursor.close()
        connection.close()


def save_totp_secret(user_id, secret):
    connection = get_db_connection()
    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute("UPDATE users SET totp_secret = %s WHERE id = %s", (secret, user_id))
        connection.commit()
    finally:
        if cursor:
            cursor.close()
        connection.close()


def verify_password(password, password_hash):
    return check_password_hash(password_hash, password)

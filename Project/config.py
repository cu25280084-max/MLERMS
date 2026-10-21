import os

from dotenv import load_dotenv
import mysql.connector

load_dotenv()


def get_db_connection():
    connection = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        connection_timeout=15,
        read_timeout=30,
        write_timeout=30,
    )

    return connection
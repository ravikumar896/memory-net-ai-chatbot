import os
import psycopg2
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

mcp = FastMCP("Company-Postgres-Agent")

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT", "5432"),
    "database": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
}

def get_connection():
    return psycopg2.connect(**DB_CONFIG)


@mcp.tool()
def get_database_schema() -> str:
    """Fetch database schema (tables + columns)"""

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public';
        """)

        tables = cursor.fetchall()
        schema_text = []

        for (table_name,) in tables:
            cursor.execute("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = %s
                ORDER BY ordinal_position;
            """, (table_name,))

            columns = cursor.fetchall()

            schema_text.append(f"\nTable: {table_name}")
            for col_name, data_type in columns:
                schema_text.append(f"  - {col_name}: {data_type}")

        conn.close()

        return "--- SCHEMA ---\n" + "\n".join(schema_text)

    except Exception as e:
        return f"Database Error: {str(e)}"


@mcp.tool()
def execute_sql_query(sql_query: str) -> str:
    """Execute ONLY safe SELECT queries"""

    clean_query = sql_query.strip().upper()

    # सुरक्षा check
    for keyword in [
        "DROP", "DELETE", "UPDATE",
        "INSERT", "ALTER", "CREATE", "TRUNCATE"
    ]:
        if keyword in clean_query:
            return f"Security Error: '{keyword}' is prohibited."

    if not clean_query.startswith("SELECT"):
        return "Security Error: Only SELECT queries allowed."

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(sql_query)

        rows = cursor.fetchall()
        headers = [desc[0] for desc in cursor.description]

        conn.close()

        if not rows:
            return "Data not found in database."

        result = f"Columns: {', '.join(headers)}\n\nRows:\n"

        for row in rows:
            result += f"{list(row)}\n"

        return result

    except Exception as e:
        return f"SQL Error: {str(e)}"


if __name__ == "__main__":
    mcp.run()
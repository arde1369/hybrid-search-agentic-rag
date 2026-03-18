
import mysql.connector
from mysql.connector import Error
import os
import json
from dotenv import load_dotenv
load_dotenv()
from langchain.tools import tool

class SQLDAO:
    def __init__(self):
        self.host = os.getenv('sql_db_host')
        self.database = os.getenv('sql_db_name')
        self.user = os.getenv('sql_db_user')
        self.password = os.getenv('sql_db_password')
        self.port = int(os.getenv('sql_db_port'))

    def create_connection(self):
        try:
            connection = mysql.connector.connect(
                host=self.host,
                database=self.database,
                user=self.user,
                password=self.password,
                port=self.port
            )
            if connection.is_connected():
                print("Connection to MySQL database was successful")
                return connection
        except Error as e:
            print(f"Error while connecting to MySQL: {e}")
            return None
    
    def select(self, query, params=None):
        """Execute a SELECT query and return the results as a list of dictionaries."""
        conn = self.create_connection()
        if not conn: return []
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(query, params)
            return cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def _row_get(row, key):
        """Case-insensitive dictionary getter for connector metadata rows."""
        if not isinstance(row, dict):
            return None

        if key in row:
            return row[key]

        lower_key = key.lower()
        upper_key = key.upper()

        if lower_key in row:
            return row[lower_key]
        if upper_key in row:
            return row[upper_key]

        for existing_key, value in row.items():
            if isinstance(existing_key, str) and existing_key.lower() == lower_key:
                return value

        return None

    def get_full_schema(self):
        """Return the full schema for the configured database."""
        tables_query = """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = %s
              AND table_type = 'BASE TABLE'
            ORDER BY table_name;
        """
        columns_query = """
            SELECT
                table_name,
                column_name,
                data_type,
                column_type,
                is_nullable,
                column_default,
                extra,
                ordinal_position
            FROM information_schema.columns
            WHERE table_schema = %s
            ORDER BY table_name, ordinal_position;
        """
        primary_keys_query = """
            SELECT
                kcu.table_name,
                kcu.column_name,
                kcu.ordinal_position
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
             AND tc.table_name = kcu.table_name
            WHERE tc.table_schema = %s
              AND tc.constraint_type = 'PRIMARY KEY'
            ORDER BY kcu.table_name, kcu.ordinal_position;
        """
        foreign_keys_query = """
            SELECT
                kcu.table_name,
                kcu.column_name,
                kcu.constraint_name,
                kcu.referenced_table_name,
                kcu.referenced_column_name,
                kcu.ordinal_position
            FROM information_schema.key_column_usage kcu
            JOIN information_schema.table_constraints tc
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
             AND tc.table_name = kcu.table_name
            WHERE kcu.table_schema = %s
              AND tc.constraint_type = 'FOREIGN KEY'
            ORDER BY kcu.table_name, kcu.constraint_name, kcu.ordinal_position;
        """

        tables = self.select(tables_query, (self.database,))
        columns = self.select(columns_query, (self.database,))
        primary_keys = self.select(primary_keys_query, (self.database,))
        foreign_keys = self.select(foreign_keys_query, (self.database,))

        schema = {
            "database": self.database,
            "tables": {}
        }

        for table in tables:
            table_name = self._row_get(table, "table_name")
            if not table_name:
                continue
            schema["tables"][table_name] = {
                "columns": [],
                "primary_key": [],
                "foreign_keys": []
            }

        for column in columns:
            table_name = self._row_get(column, "table_name")
            if table_name in schema["tables"]:
                schema["tables"][table_name]["columns"].append({
                    "name": self._row_get(column, "column_name"),
                    "data_type": self._row_get(column, "data_type"),
                    "column_type": self._row_get(column, "column_type"),
                    "is_nullable": self._row_get(column, "is_nullable") == "YES",
                    "default": self._row_get(column, "column_default"),
                    "extra": self._row_get(column, "extra")
                })

        for pk in primary_keys:
            table_name = self._row_get(pk, "table_name")
            if table_name in schema["tables"]:
                column_name = self._row_get(pk, "column_name")
                if column_name:
                    schema["tables"][table_name]["primary_key"].append(column_name)

        for fk in foreign_keys:
            table_name = self._row_get(fk, "table_name")
            if table_name in schema["tables"]:
                schema["tables"][table_name]["foreign_keys"].append({
                    "constraint_name": self._row_get(fk, "constraint_name"),
                    "column": self._row_get(fk, "column_name"),
                    "referenced_table": self._row_get(fk, "referenced_table_name"),
                    "referenced_column": self._row_get(fk, "referenced_column_name")
                })

        return schema

    def get_full_schema_json(self, indent=2):
        """Return the full schema as a JSON string."""
        schema = self.get_full_schema()
        return json.dumps(schema, indent=indent)

    def close(self):
        if self.connection and self.connection.is_connected():
            self.connection.close()

    def get_sql_tools(self):
        """Return the tools for interacting with the SQL database."""
        select_tool = tool("select")(self.select)
        get_full_schema_tool = tool("get_full_schema")(self.get_full_schema)
        get_full_schema_json_tool = tool("get_full_schema_json")(self.get_full_schema_json)
        return [select_tool, get_full_schema_tool, get_full_schema_json_tool]
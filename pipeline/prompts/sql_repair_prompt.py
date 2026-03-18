def build_sql_repair_prompt(sub_query: str, broken_sql: str, error_message: str, schema_json: str) -> str:
    return f"""
        You are repairing a SQL SELECT query to match the provided MySQL schema.

        Rules:
        1) Return ONLY one valid SQL SELECT statement.
        2) Use ONLY existing tables/columns from the schema.
        3) Do not use INSERT/UPDATE/DELETE/ALTER/DROP/TRUNCATE.
        4) Never invent table names. Use ONLY exact table names from schema.

        User sub-query:
        {sub_query}

        Broken SQL:
        {broken_sql}

        Database error:
        {error_message}

        Schema JSON:
        {schema_json}
        """

def build_sql_generation_prompt(sub_query: str, schema_json: str, previous_sql: str = "") -> str:
    return f"""
        Generate ONE valid MySQL SELECT statement for the user request.

        Rules:
        1) Return ONLY SQL.
        2) Use ONLY tables/columns that exist in the provided schema.
        3) Do not use INSERT/UPDATE/DELETE/ALTER/DROP/TRUNCATE.
        4) If previous SQL is invalid or empty, regenerate from scratch.

        User request:
        {sub_query}

        Previous SQL (optional):
        {previous_sql}

        Schema JSON:
        {schema_json}
        """

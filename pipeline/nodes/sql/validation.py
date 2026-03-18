import json
import re

from pipeline.nodes.sql.generation import generate_sql_with_schema, repair_sql_query_with_schema


def is_schema_resolution_error(error_message: str) -> bool:
    lowered = (error_message or "").lower()
    error_fragment_list = ["unknown column", "unknown table", "doesn't exist"]
    return any(fragment in lowered for fragment in error_fragment_list)


def validate_sql_schema_alignment(sql_query: str, schema: dict) -> tuple[bool, str]:
    if not sql_query or not schema:
        return False, "Empty query or schema"

    try:
        valid_tables = {t.lower() for t in schema.get("tables", {}).keys()}
        if not valid_tables:
            return False, "No tables found in schema"

        from_pattern = r"FROM\s+([\w]+)(?:\s|;|WHERE|ORDER|GROUP|LIMIT|$)"
        from_matches = re.findall(from_pattern, sql_query, re.IGNORECASE)

        for table_ref in from_matches:
            if table_ref.lower() not in valid_tables:
                valid_table_list = ", ".join(sorted(valid_tables))
                return False, f"Table '{table_ref}' does not exist in schema. Valid tables: {valid_table_list}"

        where_pattern = r"WHERE\s+(.+?)(?:\s+(?:GROUP|ORDER|LIMIT|;)|$)"
        where_matches = re.findall(where_pattern, sql_query, re.IGNORECASE | re.DOTALL)

        if where_matches and from_matches:
            table_ref = from_matches[0]
            tables_dict = schema.get("tables", {})
            table_name = next((t for t in tables_dict if t.lower() == table_ref.lower()), None)
            table_meta = tables_dict.get(table_name) if table_name else None

            if table_meta:
                valid_columns = {c.get("name", "").lower() for c in table_meta.get("columns", [])}

                for where_clause in where_matches:
                    col_pattern = r"\b([a-zA-Z_][\w]*)\s*(?:=|<>|!=|<=|>=|<|>|LIKE|IN)"
                    potential_cols = re.findall(col_pattern, where_clause, re.IGNORECASE)

                    for col in potential_cols:
                        if col.lower() not in valid_columns and col.lower() not in ["and", "or", "not"]:
                            valid_col_list = ", ".join(sorted(valid_columns))
                            return False, f"Column '{col}' does not exist in table '{table_name}'. Valid columns: {valid_col_list}"

        return True, ""
    except Exception as e:
        return False, f"Error validating SQL: {str(e)}"


def validate_and_refine_routes(pipeline, routes: list, schema: dict) -> list:
    if not schema or not isinstance(routes, list):
        return routes

    refined_routes = []
    for route in routes:
        if not isinstance(route, dict):
            refined_routes.append(route)
            continue

        if route.get("route") != "sql":
            refined_routes.append(route)
            continue

        sql_query = route.get("tool_input", {}).get("query", "") if isinstance(route.get("tool_input"), dict) else ""

        if not sql_query:
            refined_routes.append(route)
            continue

        is_valid, error_msg = validate_sql_schema_alignment(sql_query, schema)

        if is_valid:
            route["validation_status"] = "valid"
            refined_routes.append(route)
            continue

        candidate_sql = sql_query
        validated_sql = ""
        last_error = error_msg

        try:
            schema_json = json.dumps(schema, indent=2)
            for _ in range(3):
                regenerated_sql = generate_sql_with_schema(
                    pipeline,
                    sub_query=route.get("sub_query", ""),
                    schema_json=schema_json,
                    previous_sql=candidate_sql,
                )
                if regenerated_sql:
                    candidate_sql = regenerated_sql

                is_candidate_valid, candidate_error = validate_sql_schema_alignment(candidate_sql, schema)
                if is_candidate_valid:
                    validated_sql = candidate_sql
                    break

                last_error = candidate_error
                repaired_sql = repair_sql_query_with_schema(
                    pipeline,
                    sub_query=route.get("sub_query", ""),
                    broken_sql=candidate_sql,
                    error_message=candidate_error,
                )
                if repaired_sql:
                    candidate_sql = repaired_sql

                is_candidate_valid, candidate_error = validate_sql_schema_alignment(candidate_sql, schema)
                if is_candidate_valid:
                    validated_sql = candidate_sql
                    break

                last_error = candidate_error

            if validated_sql:
                route = dict(route)
                tool_input = dict(route.get("tool_input", {})) if isinstance(route.get("tool_input"), dict) else {}
                tool_input["query"] = validated_sql
                route["tool_input"] = tool_input
                route["validation_status"] = "regenerated_and_valid"
            else:
                route = dict(route)
                route["validation_status"] = f"blocked_invalid_sql: {last_error}"
                route["tool_name"] = ""
                route["tool_input"] = {}
        except Exception as regen_error:
            route = dict(route)
            route["validation_status"] = f"regeneration_error: {str(regen_error)}"
            route["tool_name"] = ""
            route["tool_input"] = {}

        refined_routes.append(route)

    return refined_routes

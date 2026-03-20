import json
import os
import re
from concurrent.futures import ThreadPoolExecutor

from pipeline.nodes.sql.generation import generate_sql_with_schema, repair_sql_query_with_schema


def is_schema_resolution_error(error_message: str) -> bool:
    lowered = (error_message or "").lower()
    error_fragment_list = ["unknown column", "unknown table", "doesn't exist"]
    return any(fragment in lowered for fragment in error_fragment_list)


_SQL_RESERVED_WORDS = {
    "select", "from", "join", "left", "right", "inner", "outer", "full", "cross", "on", "where",
    "group", "by", "order", "having", "limit", "offset", "union", "all", "distinct", "as",
    "and", "or", "not", "in", "is", "null", "like", "between", "exists", "case", "when", "then",
    "else", "end", "asc", "desc", "true", "false"
}


def _strip_sql_literals(sql_query: str) -> str:
    # Remove quoted strings so token checks don't treat literal content as identifiers.
    stripped = re.sub(r"'[^']*'", "''", str(sql_query or ""))
    stripped = re.sub(r'"[^"]*"', '""', stripped)
    stripped = re.sub(r"`([^`]*)`", r"\1", stripped)
    return stripped


def _extract_table_aliases(sql_query: str):
    table_aliases = {}
    cleaned = _strip_sql_literals(sql_query)
    pattern = re.compile(
        r"\b(?:FROM|JOIN)\s+([a-zA-Z_][\w]*)(?:\s+(?:AS\s+)?([a-zA-Z_][\w]*))?",
        flags=re.IGNORECASE,
    )
    for table_name, alias in pattern.findall(cleaned):
        table_key = str(table_name or "").strip().lower()
        if not table_key:
            continue
        table_aliases[table_key] = table_key
        alias_key = str(alias or "").strip().lower()
        if alias_key and alias_key not in _SQL_RESERVED_WORDS:
            table_aliases[alias_key] = table_key
    return table_aliases


def _extract_unqualified_predicate_columns(sql_query: str):
    cleaned = _strip_sql_literals(sql_query)
    candidates = set()
    pattern = re.compile(
        r"(?<!\.)\b([a-zA-Z_][\w]*)\b\s*(?:=|<>|!=|<=|>=|<|>|LIKE\b|IN\b|IS\b|BETWEEN\b)",
        flags=re.IGNORECASE,
    )
    for col in pattern.findall(cleaned):
        lowered = str(col or "").strip().lower()
        if lowered and lowered not in _SQL_RESERVED_WORDS:
            candidates.add(lowered)
    return candidates


def _extract_group_order_columns(sql_query: str):
    cleaned = _strip_sql_literals(sql_query)
    candidates = set()

    clause_patterns = [
        re.compile(r"\bGROUP\s+BY\s+(.+?)(?:\bHAVING\b|\bORDER\s+BY\b|\bLIMIT\b|;|$)", re.IGNORECASE | re.DOTALL),
        re.compile(r"\bORDER\s+BY\s+(.+?)(?:\bLIMIT\b|;|$)", re.IGNORECASE | re.DOTALL),
    ]

    for clause_pattern in clause_patterns:
        for clause in clause_pattern.findall(cleaned):
            parts = [segment.strip() for segment in str(clause or "").split(",") if segment.strip()]
            for part in parts:
                normalized = re.sub(r"\bASC\b|\bDESC\b", "", part, flags=re.IGNORECASE).strip()
                # Skip function calls like COUNT(*), DATE(col), etc.
                if "(" in normalized and ")" in normalized:
                    continue

                qualified_match = re.match(r"^([a-zA-Z_][\w]*)\.([a-zA-Z_][\w]*)$", normalized)
                if qualified_match:
                    candidates.add(f"{qualified_match.group(1).lower()}.{qualified_match.group(2).lower()}")
                    continue

                token_match = re.match(r"^([a-zA-Z_][\w]*)$", normalized)
                if token_match:
                    token = token_match.group(1).lower()
                    if token not in _SQL_RESERVED_WORDS:
                        candidates.add(token)

    return candidates


def validate_sql_schema_alignment(sql_query: str, schema: dict) -> tuple[bool, str]:
    if not sql_query or not schema:
        return False, "Empty query or schema"

    try:
        tables_dict = schema.get("tables", {}) if isinstance(schema.get("tables", {}), dict) else {}
        valid_tables = {t.lower() for t in tables_dict.keys()}
        if not valid_tables:
            return False, "No tables found in schema"

        table_aliases = _extract_table_aliases(sql_query)
        referenced_tables = {table_name for table_name in table_aliases.values()}

        if not referenced_tables:
            from_pattern = r"FROM\s+([\w]+)(?:\s|;|WHERE|ORDER|GROUP|LIMIT|$)"
            from_matches = [match.lower() for match in re.findall(from_pattern, sql_query, re.IGNORECASE)]
            referenced_tables = set(from_matches)

        for table_ref in referenced_tables:
            if table_ref not in valid_tables:
                valid_table_list = ", ".join(sorted(valid_tables))
                return False, f"Table '{table_ref}' does not exist in schema. Valid tables: {valid_table_list}"

        table_columns = {}
        all_referenced_columns = set()
        for table_name in referenced_tables:
            actual_table_name = next((name for name in tables_dict.keys() if str(name).lower() == table_name), None)
            table_meta = tables_dict.get(actual_table_name) if actual_table_name else None
            valid_columns = set()
            if table_meta and isinstance(table_meta, dict):
                for column in table_meta.get("columns", []):
                    col_name = str(column.get("name", "") or "").strip().lower()
                    if col_name:
                        valid_columns.add(col_name)
            table_columns[table_name] = valid_columns
            all_referenced_columns.update(valid_columns)

        qualified_refs = re.findall(r"\b([a-zA-Z_][\w]*)\.([a-zA-Z_][\w]*)\b", _strip_sql_literals(sql_query))
        for alias_or_table, column_name in qualified_refs:
            left = str(alias_or_table or "").strip().lower()
            right = str(column_name or "").strip().lower()

            resolved_table = table_aliases.get(left)
            if not resolved_table:
                if left in valid_tables:
                    resolved_table = left
                else:
                    return False, f"Table or alias '{alias_or_table}' is not present in the live schema context."

            valid_columns_for_table = table_columns.get(resolved_table, set())
            if right not in valid_columns_for_table:
                valid_col_list = ", ".join(sorted(valid_columns_for_table))
                return (
                    False,
                    f"Column '{column_name}' does not exist in table '{resolved_table}'. "
                    f"Valid columns: {valid_col_list}",
                )

        for unqualified_column in _extract_unqualified_predicate_columns(sql_query):
            if unqualified_column not in all_referenced_columns:
                valid_col_list = ", ".join(sorted(all_referenced_columns))
                return (
                    False,
                    f"Column '{unqualified_column}' is not present in referenced table columns. "
                    f"Valid columns: {valid_col_list}",
                )

        for group_or_order_column in _extract_group_order_columns(sql_query):
            if "." in group_or_order_column:
                alias_or_table, column = group_or_order_column.split(".", 1)
                resolved_table = table_aliases.get(alias_or_table, alias_or_table)
                valid_columns_for_table = table_columns.get(resolved_table, set())
                if column not in valid_columns_for_table:
                    valid_col_list = ", ".join(sorted(valid_columns_for_table))
                    return (
                        False,
                        f"Column '{column}' does not exist in table '{resolved_table}' for GROUP/ORDER BY. "
                        f"Valid columns: {valid_col_list}",
                    )
            elif group_or_order_column not in all_referenced_columns:
                valid_col_list = ", ".join(sorted(all_referenced_columns))
                return (
                    False,
                    f"Column '{group_or_order_column}' is not present in referenced table columns for GROUP/ORDER BY. "
                    f"Valid columns: {valid_col_list}",
                )

        return True, ""
    except Exception as e:
        return False, f"Error validating SQL: {str(e)}"


def _refine_sql_route(pipeline, route: dict, schema: dict, schema_json: str) -> dict:
    sql_query = route.get("tool_input", {}).get("query", "") if isinstance(route.get("tool_input"), dict) else ""
    if not sql_query:
        return route

    route = dict(route)
    is_valid, error_msg = validate_sql_schema_alignment(sql_query, schema)

    if is_valid:
        route["validation_status"] = "valid"
        return route

    candidate_sql = sql_query
    validated_sql = ""
    last_error = error_msg

    try:
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
            tool_input = dict(route.get("tool_input", {})) if isinstance(route.get("tool_input"), dict) else {}
            tool_input["query"] = validated_sql
            route["tool_input"] = tool_input
            route["validation_status"] = "regenerated_and_valid"
        else:
            route["validation_status"] = f"blocked_invalid_sql: {last_error}"
            route["tool_name"] = ""
            route["tool_input"] = {}
    except Exception as regen_error:
        route["validation_status"] = f"regeneration_error: {str(regen_error)}"
        route["tool_name"] = ""
        route["tool_input"] = {}

    return route


def validate_and_refine_routes(pipeline, routes: list, schema: dict) -> list:
    if not schema or not isinstance(routes, list):
        return routes

    try:
        schema_json = json.dumps(schema, indent=2)
    except Exception:
        schema_json = "{}"

    refined_routes = [None] * len(routes)
    sql_route_indexes = []

    for index, route in enumerate(routes):
        if not isinstance(route, dict):
            refined_routes[index] = route
            continue

        if route.get("route") != "sql":
            refined_routes[index] = route
            continue

        sql_query = route.get("tool_input", {}).get("query", "") if isinstance(route.get("tool_input"), dict) else ""
        if not sql_query:
            refined_routes[index] = route
            continue

        sql_route_indexes.append(index)

    configured_workers = os.getenv("concurrency_worker_count", "4")
    try:
        worker_count = max(1, int(configured_workers))
    except ValueError:
        worker_count = 4

    worker_count = min(worker_count, len(sql_route_indexes)) if sql_route_indexes else 1

    # Refine SQL routes in parallel but block until all refinements complete.
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        future_by_index = {
            index: executor.submit(_refine_sql_route, pipeline, routes[index], schema, schema_json)
            for index in sql_route_indexes
        }

        for index in sql_route_indexes:
            refined_routes[index] = future_by_index[index].result()

    return refined_routes

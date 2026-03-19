import re


def build_schema_terms(schema):
    schema_terms = set()
    if not isinstance(schema, dict):
        return schema_terms

    tables = schema.get("tables", {})
    for table_name, table_meta in tables.items():
        table_name_text = str(table_name).lower()
        schema_terms.add(table_name_text)
        for part in re.split(r"[_\W]+", table_name_text):
            if part:
                schema_terms.add(part)

        for column in table_meta.get("columns", []):
            column_name = str(column.get("name", "")).lower()
            if column_name:
                schema_terms.add(column_name)
            for part in re.split(r"[_\W]+", column_name):
                if part:
                    schema_terms.add(part)

    return schema_terms


def _has_schema_overlap(text: str, schema_terms) -> bool:
    if not schema_terms:
        return False
    query_terms = {token.lower() for token in re.findall(r"[A-Za-z0-9_]+", str(text or "")) if token}
    return any(term in schema_terms for term in query_terms)


def _extract_sql_subqueries_with_no_results(state):
    answer = state.get("answer", {}) if isinstance(state, dict) else {}
    if not isinstance(answer, dict):
        return set()

    results = answer.get("results", [])
    if not isinstance(results, list):
        return set()

    no_result_subqueries = set()
    for result in results:
        if not isinstance(result, dict):
            continue
        if result.get("route") != "sql":
            continue

        sub_query = str(result.get("query", "") or "").strip()
        documents = result.get("documents", [])
        if sub_query and (not isinstance(documents, list) or len(documents) == 0):
            no_result_subqueries.add(sub_query)

    return no_result_subqueries


def apply_sql_no_result_safeguard(state, routes, vector_tool_name, schema_terms):
    no_result_subqueries = _extract_sql_subqueries_with_no_results(state)
    attempts = int(state.get("attempts", 0) or 0)

    if attempts <= 0 or not no_result_subqueries:
        return routes

    question = str(state.get("question", "") or "")
    has_schema_overlap_for_question = _has_schema_overlap(question, schema_terms)

    if has_schema_overlap_for_question:
        print(
            "[ROUTER SAFEGUARD] SQL no-result detected but safeguard skipped because "
            "question overlaps with SQL schema terms; preserving SQL refinement path."
        )
        return routes

    print(
        "[ROUTER SAFEGUARD] Detected prior SQL route(s) with no results; "
        f"attempt={attempts}, sub_queries={sorted(no_result_subqueries)}, question_schema_overlap=False"
    )

    updated_routes = []
    swapped_count = 0
    for route in routes:
        if not isinstance(route, dict):
            updated_routes.append(route)
            continue

        sub_query = str(route.get("sub_query", "") or "").strip()
        has_schema_overlap_for_subquery = _has_schema_overlap(sub_query, schema_terms)
        if route.get("route") == "sql" and sub_query in no_result_subqueries and not has_schema_overlap_for_subquery:
            swapped_count += 1
            updated_routes.append(
                {
                    **route,
                    "route": "vector",
                    "tool_name": vector_tool_name,
                    "tool_input": {
                        "query": sub_query,
                        "collection_name": str(state.get("collection_name", "") or "").strip(),
                    },
                    "reason": (
                        "Safeguard switched SQL to vector because prior SQL attempt returned no rows "
                        "during refinement."
                    ),
                    "safeguard_applied": "sql_no_result_to_vector",
                }
            )
            continue

        updated_routes.append(route)

    if swapped_count:
        print(
            "[ROUTER SAFEGUARD] Switched "
            f"{swapped_count} SQL route(s) to vector retrieval to avoid no-result refinement loops."
        )
    else:
        print(
            "[ROUTER SAFEGUARD] No SQL routes were switched because no no-result SQL sub-query "
            "qualified for non-schema-overlap reroute."
        )

    return updated_routes


def reroute_blocked_sql_routes_to_vector(routes, vector_tool_name, collection_name):
    if not isinstance(routes, list):
        return routes

    clean_collection_name = str(collection_name or "").strip()
    updated_routes = []
    rerouted_count = 0

    for route in routes:
        if not isinstance(route, dict):
            updated_routes.append(route)
            continue

        is_sql_route = str(route.get("route", "") or "").strip().lower() == "sql"
        validation_status = str(route.get("validation_status", "") or "")
        should_reroute = (
            is_sql_route
            and (
                validation_status.startswith("blocked_invalid_sql")
                or validation_status.startswith("regeneration_error")
            )
        )

        if not should_reroute:
            updated_routes.append(route)
            continue

        sub_query = str(route.get("sub_query", "") or "").strip()
        rerouted_count += 1
        updated_routes.append(
            {
                **route,
                "route": "vector",
                "tool_name": vector_tool_name,
                "tool_input": {
                    "query": sub_query,
                    "collection_name": clean_collection_name,
                },
                "reason": (
                    "Switched to vector retrieval because generated SQL failed live schema validation."
                ),
                "safeguard_applied": "invalid_sql_to_vector",
            }
        )

    if rerouted_count:
        print(
            "[ROUTER SAFEGUARD] Switched "
            f"{rerouted_count} SQL route(s) to vector due to schema validation failure."
        )

    return updated_routes

import re

from pipeline.prompts import build_sql_generation_prompt, build_sql_repair_prompt
from utilities.llm_output import llm_result_to_text


def extract_sql_from_text(text: str) -> str:
    if not isinstance(text, str):
        return ""

    candidate = text.strip()
    fenced = re.search(r"```(?:sql)?\s*(.*?)```", candidate, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        candidate = fenced.group(1).strip()

    select_match = re.search(r"(?is)\bselect\b.*?;", candidate)
    if select_match:
        return select_match.group(0).strip()

    if candidate.lower().startswith("select"):
        return candidate

    return ""


def generate_sql_with_schema(pipeline, sub_query: str, schema_json: str, previous_sql: str = "") -> str:
    generation_prompt = build_sql_generation_prompt(
        sub_query=sub_query,
        schema_json=schema_json,
        previous_sql=previous_sql,
    )

    generated = pipeline.llm_agent.invoke(generation_prompt)
    return extract_sql_from_text(llm_result_to_text(generated))


def repair_sql_query_with_schema(pipeline, sub_query: str, broken_sql: str, error_message: str) -> str:
    try:
        schema_json = pipeline.sql_dao.get_full_schema_json(indent=2)
    except Exception:
        schema_json = "{}"

    repair_prompt = build_sql_repair_prompt(
        sub_query=sub_query,
        broken_sql=broken_sql,
        error_message=error_message,
        schema_json=schema_json,
    )

    repaired = pipeline.llm_agent.invoke(repair_prompt)
    return extract_sql_from_text(llm_result_to_text(repaired))


def enrich_sql_routes_with_live_schema(pipeline, routes):
    if not isinstance(routes, list):
        return routes

    sql_route_exists = any(route.get("route") == "sql" for route in routes if isinstance(route, dict))
    if not sql_route_exists:
        return routes

    try:
        schema_json = pipeline.sql_dao.get_full_schema_json(indent=2)
    except Exception:
        return routes

    enriched_routes = []
    for route in routes:
        if not isinstance(route, dict) or route.get("route") != "sql":
            enriched_routes.append(route)
            continue

        tool_input = route.get("tool_input", {})
        existing_sql = tool_input.get("query", "") if isinstance(tool_input, dict) else ""
        regenerated_sql = generate_sql_with_schema(
            pipeline,
            sub_query=route.get("sub_query", ""),
            schema_json=schema_json,
            previous_sql=existing_sql,
        )

        if regenerated_sql:
            route = dict(route)
            next_tool_input = dict(tool_input) if isinstance(tool_input, dict) else {}
            next_tool_input["query"] = regenerated_sql
            route["tool_input"] = next_tool_input

        enriched_routes.append(route)

    return enriched_routes

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor

from pipeline.prompts import build_router_prompt
from pipeline.nodes.sql import (
    apply_sql_no_result_safeguard,
    build_schema_terms,
    enrich_sql_routes_with_live_schema,
    reroute_blocked_sql_routes_to_vector,
    validate_and_refine_routes,
)
from pipeline.nodes.vector import (
    build_vector_only_routes,
    inject_collection_into_vector_routes,
    query_has_schema_overlap_parallel,
    resolve_vector_collection_name,
)
from utilities.timer import Timer


def _build_available_tools(pipeline):
    available_tools = []
    for tool in pipeline.dao_tools:
        tool_name = getattr(tool, "name", None) or getattr(tool, "__name__", str(tool))
        tool_description = (getattr(tool, "description", "") or "").strip()
        available_tools.append({"name": tool_name, "description": tool_description})
    return available_tools


def _resolve_tool_names(available_tools):
    sql_tool_name = next((tool["name"] for tool in available_tools if tool["name"] == "select"), "select")
    vector_tool_name = next(
        (tool["name"] for tool in available_tools if tool["name"] not in {"select", "get_full_schema", "get_full_schema_json"}),
        "vector_search",
    )
    return sql_tool_name, vector_tool_name


def _get_cached_schema_context(pipeline):
    cache = getattr(pipeline, "_router_schema_cache", None)

    def _load_schema_context():
        schema = None
        schema_terms = set()
        schema_context_section = ""
        try:
            schema = pipeline.sql_dao.get_full_schema()
            schema_terms = build_schema_terms(schema)
            schema_json = json.dumps(schema, indent=2)
            schema_context_section = f"""
                Live database schema (authoritative):
                {schema_json}
            """
        except Exception as schema_error:
            schema_context_section = f"Schema unavailable at routing time: {schema_error}"

        return schema, schema_terms, schema_context_section

    if cache is not None:
        return cache.get_or_set("schema_context", _load_schema_context)

    return _load_schema_context()


def _retrieve_golden_sql_examples(pipeline, n_examples=3):
    try:
        collection_name = os.getenv("chroma_db_collection_golden_sql", "golden_sql_collection")
        collection = pipeline.vector_db._get_collection_internal(collection_name)
        query_embeddings = pipeline.embedding_function(["SELECT query examples"])
        examples = collection.query(query_embeddings=query_embeddings, n_results=n_examples)
        return examples.get("documents", []) if examples else []
    except Exception:
        return []


def _retrieve_golden_reasoning_examples(pipeline, n_examples=2):
    try:
        collection_name = os.getenv("chroma_db_collection_cot_reasoning", "cot_reasoning_collection")
        collection = pipeline.vector_db._get_collection_internal(collection_name)
        query_embeddings = pipeline.embedding_function(["multi-step reasoning examples"])
        examples = collection.query(query_embeddings=query_embeddings, n_results=n_examples)
        return examples.get("documents", []) if examples else []
    except Exception:
        return []


def _build_few_shot_prompt_section(golden_examples, reasoning_examples):
    few_shot_section = ""

    if golden_examples:
        few_shot_section += "\n\nGolden SQL Examples (Few-Shot Learning):\n"
        few_shot_section += "These are validated example patterns for common query types:\n"
        for i, example in enumerate(golden_examples, 1):
            few_shot_section += f"{i}. {example}\n"

    if reasoning_examples:
        few_shot_section += "\n\nChain-of-Thought Reasoning Examples:\n"
        few_shot_section += "These demonstrate multi-step reasoning for complex queries:\n"
        for i, example in enumerate(reasoning_examples, 1):
            few_shot_section += f"{i}. {example}\n"

    return few_shot_section


def _get_cached_few_shot_prompt_section(pipeline):
    cache = getattr(pipeline, "_router_few_shot_cache", None)

    def _load_few_shot_section():
        golden_examples = _retrieve_golden_sql_examples(pipeline, n_examples=3)
        reasoning_examples = _retrieve_golden_reasoning_examples(pipeline, n_examples=2)
        return _build_few_shot_prompt_section(golden_examples, reasoning_examples)

    if cache is not None:
        return cache.get_or_set("few_shot_section", _load_few_shot_section)

    return _load_few_shot_section()


def _build_schema_overlap_terms(schema):
    schema_terms = set()
    if not isinstance(schema, dict):
        return schema_terms

    tables = schema.get("tables", {})
    for table_name, table_meta in tables.items():
        schema_terms.add(str(table_name).lower())
        for part in re.split(r"[_\W]+", str(table_name).lower()):
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


def _build_fallback_route_for_subquery(sub_query, sql_tool_name, vector_tool_name, collection_name, schema_terms):
    print("Evaluating sub-query for fallback routing:", sub_query)
    query_terms = {token.lower() for token in re.findall(r"[A-Za-z0-9_]+", sub_query) if token}
    has_schema_overlap = any(term in schema_terms for term in query_terms)

    if has_schema_overlap:
        return {
            "sub_query": sub_query,
            "route": "sql",
            "tool_name": sql_tool_name,
            "tool_input": {"query": "SELECT 1;"},
            "reason": "Fallback routing detected overlap with live schema terms.",
        }

    return {
        "sub_query": sub_query,
        "route": "vector",
        "tool_name": vector_tool_name,
        "tool_input": {"query": sub_query, "collection_name": collection_name},
        "reason": "Fallback routing selected semantic retrieval for unstructured query.",
    }


def _build_fallback_routes(query, sql_tool_name, vector_tool_name, schema, collection_name):
    split_parts = [
        part.strip(" .")
        for part in re.split(r"\?|\band\b|;", query, flags=re.IGNORECASE)
        if part and part.strip(" .")
    ]
    sub_queries = split_parts if split_parts else [query]

    schema_terms = _build_schema_overlap_terms(schema)
    fallback_routes = [
        _build_fallback_route_for_subquery(
            sub_query,
            sql_tool_name,
            vector_tool_name,
            collection_name,
            schema_terms,
        )
        for sub_query in sub_queries
    ]

    return {"routes": fallback_routes}


def _normalize_routes(parsed, query):
    if isinstance(parsed, dict) and "routes" in parsed and isinstance(parsed["routes"], list):
        return parsed["routes"]

    if isinstance(parsed, list):
        return parsed

    if isinstance(parsed, dict) and all(key in parsed for key in ("route", "tool_name", "tool_input")):
        return [
            {
                "sub_query": query,
                "route": parsed.get("route"),
                "tool_name": parsed.get("tool_name"),
                "tool_input": parsed.get("tool_input", {}),
                "reason": parsed.get("reason", ""),
            }
        ]

    return None


def _canonicalize_routes(routes):
    normalized_routes = []
    for route in routes:
        if not isinstance(route, dict):
            normalized_routes.append(route)
            continue

        normalized_route = dict(route)
        normalized_route["route"] = str(route.get("route", "") or "").strip().lower()

        tool_input = route.get("tool_input", {})
        normalized_route["tool_input"] = dict(tool_input) if isinstance(tool_input, dict) else {}

        tool_name = route.get("tool_name", "")
        normalized_route["tool_name"] = str(tool_name or "").strip()

        normalized_routes.append(normalized_route)

    return normalized_routes


def _finalize_routes(pipeline, state, routes, schema, schema_terms, vector_tool_name, selected_collection):
    routes = _canonicalize_routes(routes)
    routes = enrich_sql_routes_with_live_schema(pipeline, routes)
    if schema:
        routes = validate_and_refine_routes(pipeline, routes, schema)
    routes = reroute_blocked_sql_routes_to_vector(routes, vector_tool_name, selected_collection)
    routes = apply_sql_no_result_safeguard(state, routes, vector_tool_name, schema_terms)
    routes = inject_collection_into_vector_routes(routes, selected_collection)
    return routes


def _prepare_router_inputs(pipeline, state, query, timer):
    selected_collection = str(state.get("collection_name", "") or "").strip()

    timer.start("preparation")
    with ThreadPoolExecutor(max_workers=int(os.getenv("concurrency_worker_count", "4"))) as executor:
        schema_future = executor.submit(_get_cached_schema_context, pipeline)
        collection_future = None
        if not selected_collection:
            collection_future = executor.submit(resolve_vector_collection_name, pipeline, query)

        schema, schema_terms, schema_context_section = schema_future.result()
        if collection_future is not None:
            selected_collection = collection_future.result()
            state["collection_name"] = selected_collection

    return {
        "schema": schema,
        "schema_terms": schema_terms,
        "schema_context_section": schema_context_section,
        "selected_collection": selected_collection,
        "preparation_ms": timer.elapsed_ms("preparation"),
    }


def _try_apply_vector_fast_path(state, query, attempts, selected_collection, schema_terms, vector_tool_name, prep_duration_ms, timer):
    if not (
        attempts == 0
        and selected_collection
        and schema_terms
        and not query_has_schema_overlap_parallel(query, schema_terms)
    ):
        return None

    print("[ROUTER FAST-PATH] Skipping LLM routing; using vector-only routes.")
    routes = build_vector_only_routes(query, vector_tool_name, selected_collection)["routes"]
    routes = _canonicalize_routes(routes)
    routes = inject_collection_into_vector_routes(routes, selected_collection)
    state["routes"] = routes
    Timer.log(
        "router",
        preparation_ms=prep_duration_ms,
        total_ms=timer.total_ms(),
        routes=len(routes),
        path="fast",
    )
    return state


def _invoke_router_llm(pipeline, query, available_tools, schema_context_section, sql_tool_name, vector_tool_name, timer):
    tool_catalog = "\n".join(
        f"- {tool['name']}: {tool['description'] or 'No description provided.'}" for tool in available_tools
    )
    few_shot_section = _get_cached_few_shot_prompt_section(pipeline)

    prompt = build_router_prompt(
        query=query,
        tool_catalog=tool_catalog,
        few_shot_section=few_shot_section,
        schema_context_section=schema_context_section,
        sql_tool_name=sql_tool_name,
        vector_tool_name=vector_tool_name,
    )

    timer.start("llm")
    response = pipeline.llm_agent.invoke(prompt)
    content = response.content if hasattr(response, "content") else str(response)

    if isinstance(content, list):
        content = "\n".join(
            chunk.get("text", str(chunk)) if isinstance(chunk, dict) else str(chunk) for chunk in content
        )

    return content, timer.elapsed_ms("llm")


def _finalize_and_store_routes(
    pipeline,
    state,
    normalized_routes,
    schema,
    schema_terms,
    vector_tool_name,
    selected_collection,
):
    routes = _finalize_routes(
        pipeline,
        state,
        normalized_routes,
        schema,
        schema_terms,
        vector_tool_name,
        selected_collection,
    )
    state["routes"] = routes
    return routes


def _try_parse_and_finalize_routes(
    pipeline,
    state,
    content,
    query,
    schema,
    schema_terms,
    vector_tool_name,
    selected_collection,
    timer,
):
    parse_attempts = [content]
    start_idx = content.find("{")
    end_idx = content.rfind("}")
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        parse_attempts.append(content[start_idx : end_idx + 1])

    seen_attempts = set()
    for raw_content in parse_attempts:
        if raw_content in seen_attempts:
            continue
        seen_attempts.add(raw_content)

        try:
            normalized_routes = _normalize_routes(json.loads(raw_content), query)
        except json.JSONDecodeError:
            continue

        if normalized_routes is None:
            continue

        timer.start("finalize")
        routes = _finalize_and_store_routes(
            pipeline,
            state,
            normalized_routes,
            schema,
            schema_terms,
            vector_tool_name,
            selected_collection,
        )
        return routes, timer.elapsed_ms("finalize"), raw_content == content

    return None, None, None


def _log_router_completion(path, prep_duration_ms, llm_duration_ms, timer, routes, finalize_duration_ms=None):
    log_fields = {
        "preparation_ms": prep_duration_ms,
        "llm_ms": llm_duration_ms,
        "total_ms": timer.total_ms(),
        "routes": len(routes),
        "path": path,
    }
    if finalize_duration_ms is not None:
        log_fields["finalize_ms"] = finalize_duration_ms
    Timer.log("router", **log_fields)


def router_node(pipeline, state):
    timer = Timer()
    print("Router node invoked. Decomposing query and determining routes...")
    query = str(state.get("effective_question", "") or state.get("question", ""))
    preparation = _prepare_router_inputs(pipeline, state, query, timer)
    schema = preparation["schema"]
    schema_terms = preparation["schema_terms"]
    schema_context_section = preparation["schema_context_section"]
    selected_collection = preparation["selected_collection"]
    prep_duration_ms = preparation["preparation_ms"]
    available_tools = _build_available_tools(pipeline)
    sql_tool_name, vector_tool_name = _resolve_tool_names(available_tools)
    attempts = int(state.get("attempts", 0) or 0)
    fast_path_state = _try_apply_vector_fast_path(
        state,
        query,
        attempts,
        selected_collection,
        schema_terms,
        vector_tool_name,
        prep_duration_ms,
        timer,
    )
    if fast_path_state is not None:
        return fast_path_state

    content, llm_duration_ms = _invoke_router_llm(
        pipeline,
        query,
        available_tools,
        schema_context_section,
        sql_tool_name,
        vector_tool_name,
        timer,
    )
    routes, finalize_duration_ms, used_direct_json = _try_parse_and_finalize_routes(
        pipeline,
        state,
        content,
        query,
        schema,
        schema_terms,
        vector_tool_name,
        selected_collection,
        timer,
    )
    if routes is not None:
        _log_router_completion(
            "llm_json" if used_direct_json else "llm_extracted_json",
            prep_duration_ms,
            llm_duration_ms,
            timer,
            routes,
            finalize_duration_ms=finalize_duration_ms,
        )
        return state

    fallback = _build_fallback_routes(
        query=query,
        sql_tool_name=sql_tool_name,
        vector_tool_name=vector_tool_name,
        schema=schema,
        collection_name=selected_collection,
    )
    routes = _finalize_routes(
        pipeline,
        state,
        fallback["routes"],
        schema,
        schema_terms,
        vector_tool_name,
        selected_collection,
    )

    state["routes"] = routes
    _log_router_completion("fallback", prep_duration_ms, llm_duration_ms, timer, routes)
    print(f"State: {json.dumps(state, default=str, indent=2)}")
    return state

import re
import os
from multiprocessing import get_context


def split_subqueries(query):
    parts = [
        part.strip(" .")
        for part in re.split(r"\?|\band\b|;", str(query or ""), flags=re.IGNORECASE)
        if part and part.strip(" .")
    ]
    return parts if parts else [str(query or "").strip()]


def query_has_schema_overlap(query, schema_terms):
    sub_queries = split_subqueries(query)
    for sub_query in sub_queries:
        query_terms = {token.lower() for token in re.findall(r"[A-Za-z0-9_]+", sub_query) if token}
        if any(term in schema_terms for term in query_terms):
            return True
    return False


def _schema_overlap_worker(payload):
    sub_query, schema_terms = payload
    query_terms = {token.lower() for token in re.findall(r"[A-Za-z0-9_]+", str(sub_query or "")) if token}
    return any(term in schema_terms for term in query_terms)


def query_has_schema_overlap_parallel(query, schema_terms):
    sub_queries = split_subqueries(query)
    if not sub_queries:
        return False

    # Process startup and IPC are expensive; use multiprocessing only when it can amortize overhead.
    if len(sub_queries) < 8 or len(schema_terms) < 2000:
        return query_has_schema_overlap(query, schema_terms)

    try:
        ctx = get_context("spawn")
        configured_workers = os.getenv("router_overlap_worker_count", "4")
        try:
            max_workers = max(1, int(configured_workers))
        except ValueError:
            max_workers = 4
        worker_count = min(max_workers, len(sub_queries))
        with ctx.Pool(processes=worker_count) as pool:
            results = pool.map(_schema_overlap_worker, [(sub_query, schema_terms) for sub_query in sub_queries])
        return any(results)
    except Exception as ex:
        print(f"[ROUTER MP] Multiprocessing overlap check failed, falling back to single-process path: {ex}")
        return query_has_schema_overlap(query, schema_terms)


def build_vector_only_routes(query, vector_tool_name, collection_name):
    return {
        "routes": [
            {
                "sub_query": sub_query,
                "route": "vector",
                "tool_name": vector_tool_name,
                "tool_input": {"query": sub_query, "collection_name": collection_name},
                "reason": "Fast-path routing: no SQL schema overlap detected.",
            }
            for sub_query in split_subqueries(query)
        ]
    }


def resolve_vector_collection_name(pipeline, query: str) -> str:
    try:
        all_collections = pipeline.vector_db.client.list_collections()
    except Exception as ex:
        print(f"[ROUTER] Unable to list vector collections for auto-selection: {ex}")
        return ""

    names = []
    for collection in all_collections:
        if isinstance(collection, str):
            names.append(collection)
        else:
            names.append(getattr(collection, "name", str(collection)))

    reserved_collections = {
        os.getenv("chroma_db_collection_golden_sql", "golden_sql_collection"),
        os.getenv("chroma_db_collection_cot_reasoning", "cot_reasoning_collection"),
    }
    candidate_names = sorted({name for name in names if name and name not in reserved_collections})
    if not candidate_names:
        print("[ROUTER] No candidate vector collections available for auto-selection.")
        return ""

    if len(candidate_names) == 1:
        selected = candidate_names[0]
        print(f"[ROUTER] Auto-selected only available vector collection: {selected}")
        return selected

    query_terms = {token.lower() for token in re.findall(r"[A-Za-z0-9_]+", str(query or "")) if token}
    scored = []
    for name in candidate_names:
        name_terms = {token.lower() for token in re.findall(r"[A-Za-z0-9_]+", name) if token}
        overlap_score = len(query_terms.intersection(name_terms))
        scored.append((overlap_score, name))

    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    best_score, best_name = scored[0]
    if best_score > 0:
        print(
            "[ROUTER] Auto-selected vector collection by query/name overlap: "
            f"collection={best_name}, score={best_score}"
        )
        return best_name

    selected = candidate_names[0]
    print(
        "[ROUTER] Auto-selected vector collection by deterministic fallback "
        f"(no overlap): {selected}"
    )
    return selected


def inject_collection_into_vector_routes(routes, collection_name):
    clean_collection_name = str(collection_name or "").strip()
    has_vector_routes = any(isinstance(route, dict) and route.get("route") == "vector" for route in routes)
    if has_vector_routes and not clean_collection_name:
        raise ValueError("No vector collection could be auto-selected for vector routes.")

    updated_routes = []
    for route in routes:
        if not isinstance(route, dict):
            updated_routes.append(route)
            continue

        if route.get("route") != "vector":
            updated_routes.append(route)
            continue

        tool_input = route.get("tool_input", {})
        next_tool_input = dict(tool_input) if isinstance(tool_input, dict) else {}
        next_tool_input["collection_name"] = clean_collection_name

        updated_route = dict(route)
        updated_route["tool_input"] = next_tool_input
        updated_routes.append(updated_route)

    return updated_routes

import uuid
import os
from typing import Any, Dict, List


GOLDEN_SQL_COLLECTION = os.getenv("chroma_db_collection_golden_sql", "golden_sql_collection")


def extract_sql_feedback_entries(final_state: Dict[str, Any]) -> List[Dict[str, str]]:
    if not isinstance(final_state, dict):
        return []

    user_query = str(final_state.get("question", "") or "").strip()
    routes = final_state.get("routes", []) or []
    answer = final_state.get("answer", {}) or {}
    results = answer.get("results", []) if isinstance(answer, dict) else []

    sql_results_by_subquery = {}
    for result in results:
        if not isinstance(result, dict):
            continue
        if result.get("route") != "sql":
            continue

        sub_query = str(result.get("query", "") or "").strip()
        documents = result.get("documents", [])
        if sub_query and isinstance(documents, list) and documents:
            sql_results_by_subquery[sub_query] = True

    entries: List[Dict[str, str]] = []
    for route in routes:
        if not isinstance(route, dict):
            continue
        if route.get("route") != "sql":
            continue

        sub_query = str(route.get("sub_query", "") or "").strip()
        tool_input = route.get("tool_input", {})
        sql_query = ""
        if isinstance(tool_input, dict):
            sql_query = str(tool_input.get("query", "") or "").strip()

        if not sub_query or not sql_query:
            continue

        # Only enable feedback for SQL routes that produced result documents.
        if sub_query not in sql_results_by_subquery:
            continue

        entries.append(
            {
                "user_query": user_query,
                "sub_query": sub_query,
                "sql_query": sql_query,
            }
        )

    deduped: List[Dict[str, str]] = []
    seen = set()
    for item in entries:
        key = (item["user_query"], item["sub_query"], item["sql_query"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    print(f"Extracted {len(deduped)} unique SQL feedback entries from final state.")
    return deduped


def save_good_sql_feedback(pipeline, entries: List[Dict[str, str]]) -> int:
    if not entries:
        return 0

    collection = pipeline.vector_db._get_collection_internal(GOLDEN_SQL_COLLECTION)

    ids: List[str] = []
    documents: List[str] = []
    metadatas: List[Dict[str, Any]] = []

    for entry in entries:
        document = (
            f"User query: {entry['user_query']}\\n"
            f"Sub-query: {entry['sub_query']}\\n"
            f"SQL: {entry['sql_query']}"
        )
        ids.append(str(uuid.uuid4()))
        documents.append(document)
        metadatas.append(
            {
                "user_query": entry["user_query"],
                "sub_query": entry["sub_query"],
                "sql_query": entry["sql_query"],
                "feedback": "good",
                "source": "ui_feedback",
            }
        )

    embeddings = pipeline.embedding_function(documents)
    print(f"Saving {entries} good SQL feedback entries to collection '{GOLDEN_SQL_COLLECTION}'...")
    collection.add(ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings)
    return len(documents)

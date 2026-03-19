import json

from langchain_classic.schema import Document

from pipeline.nodes.sql import invoke_tool
from pipeline.nodes.vector import validate_vector_route_documents
from utilities.safety import (
    POLICY_BLOCK_MESSAGE,
    answer_results_contain_ssn,
    references_ssn,
)


def _to_documents(output, route):
    base_metadata = {
        "route": route.get("route"),
        "tool_name": route.get("tool_name"),
        "sub_query": route.get("sub_query"),
    }

    if output is None:
        return []

    if isinstance(output, Document):
        merged_metadata = {**base_metadata, **(output.metadata or {})}
        return [Document(page_content=output.page_content, metadata=merged_metadata)]

    if isinstance(output, dict):
        return [
            Document(
                page_content=json.dumps(output, indent=2, default=str),
                metadata=base_metadata,
            )
        ]

    if isinstance(output, list):
        documents = []
        for index, item in enumerate(output):
            item_metadata = {**base_metadata, "result_index": index}

            if isinstance(item, Document):
                merged_metadata = {**item_metadata, **(item.metadata or {})}
                documents.append(Document(page_content=item.page_content, metadata=merged_metadata))
                continue

            documents.append(
                Document(
                    page_content=json.dumps(item, indent=2, default=str) if isinstance(item, (dict, list, tuple)) else str(item),
                    metadata=item_metadata,
                )
            )

        return documents

    return [Document(page_content=str(output), metadata=base_metadata)]


def _serialize_documents(documents):
    return [
        {
            "page_content": document.page_content,
            "metadata": document.metadata,
        }
        for document in documents
    ]


def executor_node(pipeline, state):
    compiled_results = []
    reranked_documents = []
    question = state.get("question", "")
    routes = state.get("routes", [])

    for route in routes:
        validation_status = str(route.get("validation_status", ""))
        if route.get("route") == "sql" and (
            validation_status.startswith("blocked_invalid_sql")
            or validation_status.startswith("regeneration_error")
        ):
            compiled_results.append(
                {
                    "query": route.get("sub_query", question),
                    "route": route.get("route"),
                    "tool_name": route.get("tool_name"),
                    "reason": route.get("reason", ""),
                    "validation_status": validation_status,
                    "documents": [],
                }
            )
            continue

        output = invoke_tool(pipeline, route)
        documents = _to_documents(output, route)
        ranked_documents = pipeline.reranker.rerank(route.get("sub_query", question), documents)
        ranked_documents = validate_vector_route_documents(route, ranked_documents)

        compiled_results.append(
            {
                "query": route.get("sub_query", question),
                "route": route.get("route"),
                "tool_name": route.get("tool_name"),
                "reason": route.get("reason", ""),
                "documents": _serialize_documents(ranked_documents),
            }
        )
        reranked_documents.extend(ranked_documents)

    should_apply_ssn_policy = references_ssn(question) or answer_results_contain_ssn(compiled_results)
    if should_apply_ssn_policy:
        print("[SAFETY] Suppressing response due to SSN policy.")
        state["retrieved_docs"] = []
        state["answer"] = {
            "query": question,
            "results": [],
            "policy_message": POLICY_BLOCK_MESSAGE,
            "policy_blocked": True,
            "policy_reason": "ssn_response_suppressed",
        }
        print(f"Executor node completed. State: {json.dumps(state, default=str, indent=2)}")
        return state

    state["retrieved_docs"] = reranked_documents
    state["answer"] = {
        "query": question,
        "results": compiled_results,
    }
    print(f"Executor node completed. State: {json.dumps(state, default=str, indent=2)}")
    return state

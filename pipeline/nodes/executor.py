import os, json
from concurrent.futures import ThreadPoolExecutor

from langchain_classic.schema import Document

from pipeline.prompts import build_final_answer_prompt, build_vector_synthesis_prompt
from pipeline.nodes.sql import invoke_tool
from pipeline.nodes.vector import validate_vector_route_documents
from utilities.llm_output import llm_result_to_text
from utilities.safety import (
    POLICY_BLOCK_MESSAGE,
    answer_results_contain_ssn,
    references_ssn,
)
from utilities.timer import Timer


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


def _safe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_source_label(metadata):
    if not isinstance(metadata, dict):
        metadata = {}

    source = (
        metadata.get("document")
        or metadata.get("source_document")
        or metadata.get("source_file")
        or metadata.get("source")
        or metadata.get("file_name")
        or metadata.get("filename")
        or "Unknown document"
    )

    page = metadata.get("page")
    if page is None:
        page_index = _safe_int(metadata.get("page_index"))
        if page_index is not None:
            page = page_index + 1

    if page in (None, 0, "0"):
        page = 1

    return str(source), str(page)


def _build_vector_synthesis_context(documents):
    seen = set()
    lines = []
    max_docs = max(1, int(os.getenv("vector_synthesis_doc_limit", "5")))

    for document in documents:
        if not isinstance(document, Document):
            continue

        content = str(document.page_content or "").strip()
        if not content:
            continue

        metadata = document.metadata if isinstance(document.metadata, dict) else {}
        source, page = _extract_source_label(metadata)
        dedupe_key = (source, page, content)
        if dedupe_key in seen:
            continue

        seen.add(dedupe_key)
        compact_content = " ".join(content.split())
        lines.append(f"- Source: {source}, page {page}\n  Content: {compact_content}")

        if len(lines) >= max_docs:
            break

    return "\n".join(lines)


def _build_final_answer_context(compiled_results):
    lines = []
    max_results = max(1, int(os.getenv("final_answer_result_limit", "8")))
    max_docs_per_result = max(1, int(os.getenv("final_answer_docs_per_result", "8")))

    for result_index, result in enumerate(compiled_results[:max_results], start=1):
        if not isinstance(result, dict):
            continue

        route = str(result.get("route", "") or "").strip()
        query = str(result.get("query", "") or "").strip()
        lines.append(f"Result {result_index} | route={route} | query={query}")

        documents = result.get("documents", [])
        if not isinstance(documents, list) or not documents:
            lines.append("- No documents found")
            continue

        for doc_index, document in enumerate(documents[:max_docs_per_result], start=1):
            if not isinstance(document, dict):
                lines.append(f"- Document {doc_index}: {document}")
                continue

            content = str(document.get("page_content", "") or "").strip()
            metadata = document.get("metadata", {}) if isinstance(document.get("metadata", {}), dict) else {}
            compact_content = " ".join(content.split())
            if len(compact_content) > 1200:
                compact_content = compact_content[:1200].rstrip() + "..."
            lines.append(
                f"- Document {doc_index}: content={compact_content} | metadata={json.dumps(metadata, default=str)}"
            )

    return "\n".join(lines)


def _synthesize_general_final_answer(pipeline, question, compiled_results):
    if not compiled_results:
        return ""

    compiled_context = _build_final_answer_context(compiled_results)
    if not compiled_context:
        return ""

    prompt = build_final_answer_prompt(
        question=question,
        compiled_context=compiled_context,
    )

    try:
        result = pipeline.llm_agent.invoke(prompt)
        return llm_result_to_text(result).strip()
    except Exception as ex:
        print(f"[EXECUTOR] Failed to synthesize final answer: {ex}")
        return ""


def _synthesize_final_answer(pipeline, question, vector_documents):
    if not vector_documents:
        return ""

    compiled_context = _build_vector_synthesis_context(vector_documents)
    if not compiled_context:
        return ""

    prompt = build_vector_synthesis_prompt(
        question=question,
        compiled_context=compiled_context,
    )

    try:
        result = pipeline.llm_agent.invoke(prompt)
        return llm_result_to_text(result).strip()
    except Exception as ex:
        print(f"[EXECUTOR] Failed to synthesize final vector answer: {ex}")
        return ""


def _execute_route(pipeline, route, question):
    validation_status = str(route.get("validation_status", ""))
    if route.get("route") == "sql" and (
        validation_status.startswith("blocked_invalid_sql")
        or validation_status.startswith("regeneration_error")
    ):
        return {
            "query": route.get("sub_query", question),
            "route": route.get("route"),
            "tool_name": route.get("tool_name"),
            "reason": route.get("reason", ""),
            "validation_status": validation_status,
            "documents": [],
        }, []

    output = invoke_tool(pipeline, route)
    documents = _to_documents(output, route)
    ranked_documents = pipeline.reranker.rerank(route.get("sub_query", question), documents)
    ranked_documents = validate_vector_route_documents(route, ranked_documents)

    return (
        {
            "query": route.get("sub_query", question),
            "route": route.get("route"),
            "tool_name": route.get("tool_name"),
            "reason": route.get("reason", ""),
            "documents": _serialize_documents(ranked_documents),
        },
        ranked_documents,
    )


def executor_node(pipeline, state):
    timer = Timer()
    compiled_results = []
    reranked_documents = []
    vector_reranked_documents = []
    question = str(state.get("effective_question", "") or state.get("question", ""))
    routes = state.get("routes", [])

    indexed_results = [None] * len(routes)
    max_workers = min(len(routes), max(1, int(os.getenv("concurrency_worker_count", "4")))) if routes else 1

    # Execute independent routes concurrently but block until all complete.
    timer.start("route_execution")
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_by_index = {
            index: executor.submit(_execute_route, pipeline, route, question)
            for index, route in enumerate(routes)
        }

        for index in range(len(routes)):
            compiled_result, ranked_docs = future_by_index[index].result()
            indexed_results[index] = (compiled_result, ranked_docs)
    execution_duration_ms = timer.elapsed_ms("route_execution")

    for result in indexed_results:
        if result is None:
            continue
        compiled_result, ranked_docs = result
        compiled_results.append(compiled_result)
        reranked_documents.extend(ranked_docs)
        if compiled_result.get("route") == "vector":
            vector_reranked_documents.extend(ranked_docs)

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
        Timer.log(
            "executor",
            route_execution_ms=execution_duration_ms,
            total_ms=timer.total_ms(),
            routes=len(routes),
            policy_blocked=True,
        )
        print(f"[EXECUTOR] Completed. routes={len(routes)} policy_blocked=True")
        return state

    state["retrieved_docs"] = reranked_documents
    timer.start("synthesis")
    final_answer = _synthesize_general_final_answer(pipeline, question, compiled_results)
    if not final_answer:
        final_answer = _synthesize_final_answer(pipeline, question, vector_reranked_documents)
    synthesis_duration_ms = timer.elapsed_ms("synthesis")
    state["answer"] = {
        "query": question,
        "results": compiled_results,
        "final_answer": final_answer,
    }
    Timer.log(
        "executor",
        route_execution_ms=execution_duration_ms,
        synthesis_ms=synthesis_duration_ms,
        total_ms=timer.total_ms(),
        routes=len(routes),
    )
    print(f"[EXECUTOR] Completed. routes={len(routes)} final_answer_len={len(final_answer)}")
    return state

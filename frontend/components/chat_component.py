import streamlit as st

from frontend.services.query_feedback_service import extract_sql_feedback_entries
from frontend.services.session_service import append_chat_turn, get_chat_context, get_query_thread_id
from frontend.utils.answer_formatter import extract_answer_text, to_display_text
from pipeline.prompts import build_vector_answer_prompt
from utilities.safety import redact_ssn_values


def _safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_valid_vector_chunk(doc, min_chars: int = 30) -> bool:
    if not isinstance(doc, dict):
        return False
    content = str(doc.get("page_content", "") or "").strip()
    return len(content) >= min_chars


def _extract_source_fields(doc):
    metadata = doc.get("metadata", {}) if isinstance(doc, dict) else {}
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
    page = "Unknown page"
    for key in ("page", "page_number", "page_num", "pageIndex", "page_index"):
        if key in metadata and metadata.get(key) is not None:
            page = metadata.get(key)
            break

    if isinstance(page, int) and "page_index" in metadata and page == metadata.get("page_index"):
        page = page + 1

    if page == 0:
        page = 1

    return str(source), str(page), metadata


def _pick_best_vector_document(docs):
    if not isinstance(docs, list) or not docs:
        return None

    best = None
    best_similarity = None
    best_distance = None

    for doc in docs:
        if not _is_valid_vector_chunk(doc):
            continue

        metadata = doc.get("metadata", {}) if isinstance(doc, dict) else {}
        if not isinstance(metadata, dict):
            metadata = {}

        similarity = _safe_float(metadata.get("similarity_score"))
        distance = _safe_float(metadata.get("distance"))

        if best is None:
            best = doc
            best_similarity = similarity
            best_distance = distance
            continue

        similarity_current = similarity if similarity is not None else -1.0
        similarity_best = best_similarity if best_similarity is not None else -1.0

        if similarity_current > similarity_best:
            best = doc
            best_similarity = similarity
            best_distance = distance
            continue

        if similarity_current == similarity_best:
            distance_current = distance if distance is not None else float("inf")
            distance_best = best_distance if best_distance is not None else float("inf")
            if distance_current < distance_best:
                best = doc
                best_similarity = similarity
                best_distance = distance

    return best


def _summarize_vector_document(pipeline, user_query: str, doc: dict) -> str:
    content = ""
    if isinstance(doc, dict):
        content = str(doc.get("page_content", "") or "")

    source, page, _ = _extract_source_fields(doc)

    if not content.strip():
        return f"I could not find related information.\n\nMore info: {source}, page {page}"

    prompt = build_vector_answer_prompt(
        question=redact_ssn_values(user_query),
        document_text=redact_ssn_values(content),
        source_label=source,
        page_label=page,
    )

    try:
        result = pipeline.llm_agent.invoke(prompt)
        text = to_display_text(result)
        if text:
            return text
    except Exception:
        pass

    sentences = [s.strip() for s in content.replace("\n", " ").split(".") if len(s.strip()) > 20]
    first_sentence = (sentences[0] + ".") if sentences else ""
    if first_sentence:
        return f"{first_sentence}\n\nMore info: {source}, page {page}"
    return f"Information was found but could not be summarized at this time.\n\nMore info: {source}, page {page}"


def build_chat_response_text(pipeline, final_state: dict) -> str:
    if not isinstance(final_state, dict):
        return extract_answer_text(final_state)

    answer = final_state.get("answer", {})
    if not isinstance(answer, dict):
        return extract_answer_text(final_state)

    policy_message = to_display_text(answer.get("policy_message", ""))
    if policy_message:
        return policy_message

    final_answer = to_display_text(answer.get("final_answer", ""))
    if final_answer:
        return final_answer

    results = answer.get("results", [])
    question = str(final_state.get("question", "") or "").strip()
    vector_docs = []

    if isinstance(results, list):
        for item in results:
            if isinstance(item, dict) and item.get("route") == "vector":
                docs = item.get("documents", [])
                if isinstance(docs, list):
                    vector_docs.extend(docs)

    best_doc = _pick_best_vector_document(vector_docs)
    if best_doc is not None:
        return _summarize_vector_document(pipeline, question, best_doc)

    return extract_answer_text(final_state)


def render_chat_component(pipeline) -> None:
    with st.form(key="query_form", clear_on_submit=False):
        query = st.text_area(
            "User query",
            placeholder="Enter a question here...",
            height=140,
            key="user_query_input",
            label_visibility="collapsed",
        )
        _, run_col = st.columns([4, 1.1])
        with run_col:
            run_clicked = st.form_submit_button("Run query", type="primary", use_container_width=True)

    if run_clicked:
        if not query.strip():
            st.warning("Please enter a query before running.")
            return
        with st.spinner("Running pipeline..."):
            final_state = pipeline.run_graph(
                query.strip(),
                conversation_context=get_chat_context(),
                thread_id=get_query_thread_id(),
            )
        st.session_state.last_query_final_state = final_state
        st.session_state.last_query_feedback_entries = extract_sql_feedback_entries(final_state)
        append_chat_turn(query.strip(), build_chat_response_text(pipeline, final_state))
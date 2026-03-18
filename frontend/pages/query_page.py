import json

import streamlit as st

from pipeline.prompts import build_vector_answer_prompt
from frontend.services.query_feedback_service import extract_sql_feedback_entries, save_good_sql_feedback
from frontend.utils.answer_formatter import extract_answer_text


def _parse_page_content(content: str):
    text = str(content or "").strip()
    if not text:
        return ""

    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text


def _render_documents(docs) -> None:
    if not isinstance(docs, list) or not docs:
        st.write("No documents found.")
        return

    table_rows = []
    text_rows = []

    for idx, doc in enumerate(docs, start=1):
        content = doc.get("page_content", "") if isinstance(doc, dict) else str(doc)
        parsed = _parse_page_content(content)

        if isinstance(parsed, dict):
            table_rows.append(parsed)
            continue

        if isinstance(parsed, list) and parsed and all(isinstance(item, dict) for item in parsed):
            table_rows.extend(parsed)
            continue

        if isinstance(parsed, list):
            for item in parsed:
                text_rows.append(f"{idx}. {item}")
            continue

        text_rows.append(f"{idx}. {parsed}")

    if table_rows:
        st.table(table_rows)

    for row in text_rows:
        st.write(row)


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
    page = (
        metadata.get("page")
        or metadata.get("page_number")
        or metadata.get("page_num")
        or metadata.get("pageIndex")
        or "Unknown page"
    )
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
        question=user_query,
        document_text=content,
        source_label=source,
        page_label=page,
    )

    try:
        result = pipeline.llm_agent.invoke(prompt)
        if not isinstance(result, str):
            result = str(result)
        text = result.strip()
        if text:
            return text
    except Exception:
        pass

    # Deterministic fallback if LLM summarization fails.
    shortened = content.strip().replace("\n", " ")
    if len(shortened) > 350:
        shortened = shortened[:347] + "..."
    return f"{shortened}\n\nMore info: {source}, page {page}"


def render_query_page(pipeline) -> None:
    st.header("Run Query")
    st.write("Enter a question and run it through the pipeline.")

    if "last_query_final_state" not in st.session_state:
        st.session_state.last_query_final_state = None
    if "last_query_feedback_entries" not in st.session_state:
        st.session_state.last_query_feedback_entries = []

    query = st.text_area(
        "User query",
        placeholder="Example: List all employees in the Sales department.",
        height=120,
    )

    if st.button("Run Query", type="primary", key="run_query_btn"):
        if not query.strip():
            st.warning("Please enter a query before running.")
            return

        with st.spinner("Running pipeline..."):
            final_state = pipeline.run_graph(query.strip())

        st.session_state.last_query_final_state = final_state
        st.session_state.last_query_feedback_entries = extract_sql_feedback_entries(final_state)

    final_state = st.session_state.last_query_final_state
    feedback_entries = st.session_state.last_query_feedback_entries

    if final_state:
        st.subheader("Pipeline Output")
        selected_collection = final_state.get("collection_name", "") if isinstance(final_state, dict) else ""
        if selected_collection:
            st.caption(f"Selected vector collection: {selected_collection}")

        answer = final_state.get("answer", {}) if isinstance(final_state, dict) else {}
        results = answer.get("results", []) if isinstance(answer, dict) else []
        reflection = final_state.get("reflection", "") if isinstance(final_state, dict) else ""

        vector_results = [
            item for item in results
            if isinstance(item, dict) and item.get("route") == "vector"
        ]
        if vector_results:
            vector_docs = []
            for item in vector_results:
                docs = item.get("documents", []) if isinstance(item, dict) else []
                if isinstance(docs, list):
                    vector_docs.extend(docs)

            best_doc = _pick_best_vector_document(vector_docs)
            if best_doc is not None:
                official_answer = _summarize_vector_document(
                    pipeline,
                    final_state.get("question", "") if isinstance(final_state, dict) else "",
                    best_doc,
                )
                st.subheader("Official Answer")
                st.write(official_answer)

        if results:
            for item in results:
                query_text = item.get("query", "") if isinstance(item, dict) else ""
                st.markdown(f"**Sub-query:** {query_text}")
                docs = item.get("documents", []) if isinstance(item, dict) else []
                if item.get("route") == "vector":
                    best_doc = _pick_best_vector_document(docs)
                    if best_doc is not None:
                        source, page, metadata = _extract_source_fields(best_doc)
                        st.write(f"Top vector source: {source} (page {page})")
                        similarity = _safe_float(metadata.get("similarity_score"))
                        distance = _safe_float(metadata.get("distance"))
                        score_text = []
                        if similarity is not None:
                            score_text.append(f"similarity={similarity:.3f}")
                        if distance is not None:
                            score_text.append(f"distance={distance:.3f}")
                        if score_text:
                            st.caption(" | ".join(score_text))
                    else:
                        st.write("No documents found.")
                else:
                    _render_documents(docs)
                st.divider()
        else:
            st.write(extract_answer_text(final_state))

        if reflection:
            st.markdown("**Reflection**")
            st.write(str(reflection).strip())

        # Keep these buttons hidden until SQL results are available.
        if feedback_entries:
            good_col, bad_col = st.columns(2)
            with good_col:
                if st.button("Good", type="secondary", key="query_feedback_good_btn"):
                    saved_count = save_good_sql_feedback(pipeline, feedback_entries)
                    st.success(f"Saved {saved_count} SQL example(s) to golden_sql.")

            with bad_col:
                if st.button("Bad", type="secondary", key="query_feedback_bad_btn"):
                    st.info("Feedback received. No example was stored.")

        with st.expander("Raw output"):
            st.write(final_state)

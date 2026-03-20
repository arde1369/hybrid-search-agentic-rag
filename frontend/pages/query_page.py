import os
import json

import streamlit as st

from frontend.components.chat_component import build_chat_response_text, render_chat_component
from frontend.components.chat_history_component import render_chat_history_component
from frontend.components.raw_output_component import render_raw_output_component
from frontend.services.query_feedback_service import save_good_sql_feedback
from frontend.services.session_service import get_query_thread_id, reset_query_session


GOLDEN_SQL_COLLECTION = os.getenv("chroma_db_collection_golden_sql", "golden_sql_collection")


def _parse_document_content(content: str):
    text = str(content or "").strip()
    if not text:
        return None

    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None


def _question_requests_table(question: str) -> bool:
    text = str(question or "").strip().lower()
    if not text:
        return False

    table_keywords = (
        "table",
        "tabular",
        "grid",
        "columns",
        "rows",
        "spreadsheet",
    )
    return any(keyword in text for keyword in table_keywords)


def _extract_sql_table_rows(results: list) -> list[dict]:
    table_rows = []
    for item in results:
        if not isinstance(item, dict) or item.get("route") != "sql":
            continue

        documents = item.get("documents", [])
        if not isinstance(documents, list):
            continue

        for document in documents:
            if not isinstance(document, dict):
                continue

            parsed_content = _parse_document_content(document.get("page_content", ""))
            if isinstance(parsed_content, dict):
                table_rows.append(parsed_content)
            elif isinstance(parsed_content, list):
                table_rows.extend(row for row in parsed_content if isinstance(row, dict))

    return table_rows


def _render_official_answer_table(results: list) -> bool:
    table_rows = _extract_sql_table_rows(results)
    if not table_rows:
        return False

    st.subheader("Official Answer")
    st.table(table_rows)
    return True


def _render_official_answer(pipeline, question: str, results: list, policy_message: str) -> None:
    if policy_message:
        st.subheader("Official Answer")
        st.write(policy_message)
        return

    if _question_requests_table(question) and _render_official_answer_table(results):
        return

    final_state = st.session_state.get("last_query_final_state")
    answer = final_state.get("answer", {}) if isinstance(final_state, dict) else {}
    final_answer = str(answer.get("final_answer", "") or "").strip() if isinstance(answer, dict) else ""

    if final_answer:
        st.subheader("Official Answer")
        st.write(final_answer)
        return

    vector_docs = []
    for item in results:
        if isinstance(item, dict) and item.get("route") == "vector":
            docs = item.get("documents", []) if isinstance(item, dict) else []
            if isinstance(docs, list):
                vector_docs.extend(docs)

    if not vector_docs:
        return

    fallback_state = {
        "question": question,
        "answer": {"results": results},
    }
    official_answer = build_chat_response_text(pipeline, fallback_state)
    st.subheader("Official Answer")
    st.write(official_answer)


def _render_reflection(reflection: str) -> None:
    if reflection:
        st.markdown("**Reflection**")
        st.write(str(reflection).strip())


def _render_feedback_buttons(pipeline, feedback_entries: list) -> None:
    if not feedback_entries:
        return
    good_col, bad_col = st.columns(2)
    with good_col:
        if st.button("Good", type="secondary", key="query_feedback_good_btn"):
            saved_count = save_good_sql_feedback(pipeline, feedback_entries)
            st.success(f"Saved {saved_count} SQL example(s) to {GOLDEN_SQL_COLLECTION}.")
    with bad_col:
        if st.button("Bad", type="secondary", key="query_feedback_bad_btn"):
            st.info("Feedback received. No example was stored.")


def render_query_page(pipeline) -> None:
    active_thread_id = get_query_thread_id()

    if "last_query_final_state" not in st.session_state:
        st.session_state.last_query_final_state = None
    if "last_query_feedback_entries" not in st.session_state:
        st.session_state.last_query_feedback_entries = []

    st.markdown("<h1 style='text-align:center; margin-top:0.1rem; margin-bottom:1.1rem;'>Autonomous RAG Assistant</h1>", unsafe_allow_html=True)

    main_col, history_col = st.columns([2.35, 1.15], gap="large")

    with main_col:
        with st.container(border=False):
            top_left, top_right = st.columns([4, 1.1])
            with top_left:
                st.markdown("#### Enter your question.")
            with top_right:
                if st.button("Reset Session", key="reset_query_session_btn", use_container_width=True):
                    reset_query_session()
                    st.rerun()

            if active_thread_id:
                st.caption(f"Session thread: {active_thread_id}")

            render_chat_component(pipeline)

    final_state = st.session_state.last_query_final_state
    feedback_entries = st.session_state.last_query_feedback_entries

    with history_col:
        with st.container(border=False):
            render_chat_history_component(exclude_latest_turn=bool(final_state))

    if not final_state:
        return

    with main_col:
        with st.container(border=False):
            st.subheader("Pipeline Output")
            selected_collection = final_state.get("collection_name", "") if isinstance(final_state, dict) else ""
            if selected_collection:
                st.caption(f"Selected vector collection: {selected_collection}")

            answer = final_state.get("answer", {}) if isinstance(final_state, dict) else {}
            results = answer.get("results", []) if isinstance(answer, dict) else []
            policy_message = str(answer.get("policy_message", "") or "").strip() if isinstance(answer, dict) else ""
            reflection = final_state.get("reflection", "") if isinstance(final_state, dict) else ""
            if isinstance(final_state, dict):
                question = final_state.get("effective_question", "") or final_state.get("question", "")
            else:
                question = ""

            _render_official_answer(pipeline, question, results, policy_message)
            _render_reflection(reflection)
            _render_feedback_buttons(pipeline, feedback_entries)
            render_raw_output_component(final_state)

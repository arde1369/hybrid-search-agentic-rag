import uuid

import streamlit as st


QUERY_THREAD_ID_KEY = "query_thread_id"
LAST_QUERY_STATE_KEY = "last_query_final_state"
LAST_QUERY_FEEDBACK_KEY = "last_query_feedback_entries"


def initialize_query_session() -> str:
    """Ensure a stable query session/thread id exists for the current user session."""
    if QUERY_THREAD_ID_KEY not in st.session_state:
        st.session_state[QUERY_THREAD_ID_KEY] = str(uuid.uuid4().hex)

    if LAST_QUERY_STATE_KEY not in st.session_state:
        st.session_state[LAST_QUERY_STATE_KEY] = None

    if LAST_QUERY_FEEDBACK_KEY not in st.session_state:
        st.session_state[LAST_QUERY_FEEDBACK_KEY] = []

    return str(st.session_state[QUERY_THREAD_ID_KEY])


def get_query_thread_id() -> str:
    return str(st.session_state.get(QUERY_THREAD_ID_KEY, "") or "")


def reset_query_session() -> str:
    """Clear current query context and issue a new conversation thread id."""
    st.session_state[QUERY_THREAD_ID_KEY] = str(uuid.uuid4().hex)
    st.session_state[LAST_QUERY_STATE_KEY] = None
    st.session_state[LAST_QUERY_FEEDBACK_KEY] = []
    return str(st.session_state[QUERY_THREAD_ID_KEY])

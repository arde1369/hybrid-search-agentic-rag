import uuid

import streamlit as st


QUERY_THREAD_ID_KEY = "query_thread_id"
LAST_QUERY_STATE_KEY = "last_query_final_state"
LAST_QUERY_FEEDBACK_KEY = "last_query_feedback_entries"
CHAT_HISTORY_KEY = "chat_history"


def initialize_query_session() -> str:
    """Ensure a stable query session/thread id exists for the current user session."""
    if QUERY_THREAD_ID_KEY not in st.session_state:
        st.session_state[QUERY_THREAD_ID_KEY] = str(uuid.uuid4().hex)

    if LAST_QUERY_STATE_KEY not in st.session_state:
        st.session_state[LAST_QUERY_STATE_KEY] = None

    if LAST_QUERY_FEEDBACK_KEY not in st.session_state:
        st.session_state[LAST_QUERY_FEEDBACK_KEY] = []

    if CHAT_HISTORY_KEY not in st.session_state:
        st.session_state[CHAT_HISTORY_KEY] = []

    return str(st.session_state[QUERY_THREAD_ID_KEY])


def get_query_thread_id() -> str:
    return str(st.session_state.get(QUERY_THREAD_ID_KEY, "") or "")


def get_chat_history() -> list[dict]:
    history = st.session_state.get(CHAT_HISTORY_KEY, [])
    return history if isinstance(history, list) else []


def get_chat_context(max_turns: int = 6) -> str:
    history = get_chat_history()
    if not history:
        return ""

    recent_history = history[-max_turns:]
    lines = []
    for item in recent_history:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "") or "").strip().lower()
        content = str(item.get("content", "") or "").strip()
        if role not in {"user", "assistant"} or not content:
            continue
        speaker = "User" if role == "user" else "Assistant"
        lines.append(f"{speaker}: {content}")

    return "\n".join(lines)


def append_chat_turn(user_message: str, assistant_message: str) -> None:
    history = get_chat_history()
    history.extend(
        [
            {"role": "user", "content": str(user_message or "").strip()},
            {"role": "assistant", "content": str(assistant_message or "").strip()},
        ]
    )
    st.session_state[CHAT_HISTORY_KEY] = history


def reset_query_session() -> str:
    """Clear current query context and issue a new conversation thread id."""
    st.session_state[QUERY_THREAD_ID_KEY] = str(uuid.uuid4().hex)
    st.session_state[LAST_QUERY_STATE_KEY] = None
    st.session_state[LAST_QUERY_FEEDBACK_KEY] = []
    st.session_state[CHAT_HISTORY_KEY] = []
    return str(st.session_state[QUERY_THREAD_ID_KEY])

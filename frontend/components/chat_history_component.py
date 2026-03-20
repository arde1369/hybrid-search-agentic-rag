import streamlit as st

from frontend.services.session_service import get_chat_history


def render_chat_history_component(exclude_latest_turn: bool = False) -> None:
    st.subheader("Chat History")

    history = get_chat_history()
    if exclude_latest_turn and len(history) >= 2:
        history = history[:-2]

    if not history:
        st.caption("No conversation history yet.")
        return

    for item in history:
        if not isinstance(item, dict):
            continue

        role = str(item.get("role", "") or "").strip().lower()
        content = str(item.get("content", "") or "").strip()
        if role not in {"user", "assistant"} or not content:
            continue

        with st.chat_message(role):
            st.write(content)
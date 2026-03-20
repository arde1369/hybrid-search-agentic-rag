import streamlit as st


NAV_OPTIONS = ["Upload File", "Run Query"]


def render_navbar() -> str:
    return st.radio(
        "Navigation",
        options=NAV_OPTIONS,
        horizontal=False,
        label_visibility="visible",
    )

import streamlit as st

from frontend.components.navbar import render_navbar
from frontend.pages.query_page import render_query_page
from frontend.pages.upload_page import render_upload_page
from frontend.services.pipeline_service import get_pipeline
from frontend.services.session_service import initialize_query_session


def _apply_modern_theme() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;700;800&display=swap');

        html, body, [class*="css"] {
            font-family: 'Manrope', sans-serif;
            font-size: 14px;
        }

        .stApp {
            background:
                radial-gradient(circle at 15% 15%, rgba(120, 183, 255, 0.20), transparent 32%),
                radial-gradient(circle at 85% 12%, rgba(255, 175, 90, 0.18), transparent 28%),
                #f4f7fb;
        }

        .block-container {
            padding-top: 1.25rem;
            padding-bottom: 1.5rem;
        }

        h1 {
            font-size: 1.9rem;
        }

        h2 {
            font-size: 1.45rem;
        }

        h3 {
            font-size: 1.15rem;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 20px;
            border: none;
            background: rgba(255, 255, 255, 0.78);
            box-shadow: none;
        }

        .stButton > button {
            border-radius: 12px;
            border: 1px solid rgba(15, 23, 42, 0.15);
            background: linear-gradient(180deg, #ffffff 0%, #eef3fa 100%);
            color: #0f172a;
            font-weight: 700;
            padding: 0.45rem 1rem;
        }

        .stTextArea textarea {
            border-radius: 18px;
            border: 1px solid rgba(30, 41, 59, 0.18);
            background: #ffffff;
        }

        .stRadio > div {
            gap: 0.35rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def run_app() -> None:
    st.set_page_config(page_title="Agentic RAG", page_icon="🔎", layout="wide")
    _apply_modern_theme()
    initialize_query_session()
    pipeline = get_pipeline()

    nav_col, content_col = st.columns([1.1, 5.2], gap="large")

    with nav_col:
        with st.container(border=False):
            nav_option = render_navbar()

    with content_col:
        if nav_option == "Upload File":
            render_upload_page(pipeline)
        else:
            render_query_page(pipeline)

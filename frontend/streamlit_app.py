import streamlit as st

from frontend.components.navbar import render_navbar
from frontend.pages.query_page import render_query_page
from frontend.pages.upload_page import render_upload_page
from frontend.services.pipeline_service import get_pipeline
from frontend.services.session_service import initialize_query_session


def run_app() -> None:
    st.set_page_config(page_title="Agentic RAG", page_icon="🔎", layout="wide")
    st.title("Agentic RAG Assistant")
    initialize_query_session()
    pipeline = get_pipeline()

    nav_option = render_navbar()

    if nav_option == "Upload File":
        render_upload_page(pipeline)
    else:
        render_query_page(pipeline)

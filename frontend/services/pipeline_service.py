import streamlit as st

from pipeline.rag_pipeline import Pipeline


@st.cache_resource
def get_pipeline() -> Pipeline:
    return Pipeline()

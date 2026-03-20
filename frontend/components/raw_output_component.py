import streamlit as st


def render_raw_output_component(final_state: dict) -> None:
    with st.expander("Raw output"):
        raw_results = (
            final_state.get("answer", {}).get("results", [])
            if isinstance(final_state, dict)
            else []
        )
        if not raw_results:
            st.write(final_state)
            return

        for raw_item in raw_results:
            if not isinstance(raw_item, dict):
                continue
            st.markdown(
                f"**Route:** `{raw_item.get('route', '')}` &nbsp;|&nbsp; "
                f"**Sub-query:** {raw_item.get('query', '')}"
            )
            raw_docs = raw_item.get("documents", [])
            if raw_docs:
                for raw_doc in raw_docs:
                    if isinstance(raw_doc, dict):
                        st.write(
                            {
                                "page_content": raw_doc.get("page_content", ""),
                                "metadata": raw_doc.get("metadata", {}),
                            }
                        )
                    else:
                        st.write(raw_doc)
            else:
                st.write("_(no documents)_")
            st.divider()
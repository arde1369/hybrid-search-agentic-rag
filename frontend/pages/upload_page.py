import streamlit as st

from frontend.services.upload_service import (
    cleanup_temp_file,
    ensure_collection,
    infer_expected_extension,
    list_collection_names,
    process_and_store_upload,
    save_uploaded_file,
)


UPLOAD_OPTIONS = [
    "PDF with images",
    "PDF with text ONLY",
    "Structured DOCX",
    "Unstructured DOCX",
]


def render_upload_page(pipeline) -> None:
    st.header("Upload File")
    st.write("Choose a file type, browse to your file, and upload it to the vector store.")

    if "selected_collection_name" not in st.session_state:
        st.session_state.selected_collection_name = ""

    _, refresh_col = st.columns([5, 1])
    with refresh_col:
        if st.button("Refresh collections", key="refresh_collections_btn"):
            st.rerun()

    available_collections = list_collection_names(pipeline)
    collection_options = [*available_collections, "+ Create new collection"]
    preferred_collection = st.session_state.selected_collection_name
    if preferred_collection in collection_options:
        selected_index = collection_options.index(preferred_collection)
    else:
        selected_index = 0 if available_collections else len(available_collections)

    collection_option = st.selectbox(
        "Select collection",
        options=collection_options,
        index=selected_index,
        placeholder="Choose a collection",
    )
    st.session_state.selected_collection_name = collection_option

    selected_collection = collection_option
    if collection_option == "+ Create new collection":
        new_collection_name = st.text_input("New collection name", placeholder="my_collection")
        selected_collection = new_collection_name.strip() if new_collection_name else ""
        if selected_collection:
            try:
                created_name = ensure_collection(pipeline, selected_collection)
                st.session_state.selected_collection_name = created_name
                st.caption(f"Collection ready: {created_name}")
                st.rerun()
            except Exception as ex:
                st.error(f"Could not create collection: {ex}")
                return

    upload_mode = st.radio(
        "Select upload type",
        options=UPLOAD_OPTIONS,
        horizontal=True,
    )

    expected_extension = infer_expected_extension(upload_mode)
    uploaded_file = st.file_uploader(
        "Browse file",
        type=[expected_extension.lstrip(".")],
        accept_multiple_files=False,
    )

    if st.button("Upload file", type="primary", key="upload_file_btn"):
        if not selected_collection:
            st.warning("Please select an existing collection or add a new collection.")
            return

        if uploaded_file is None:
            st.warning("Please browse and select a file before uploading.")
            return

        if not uploaded_file.name.lower().endswith(expected_extension):
            st.error(f"Selected file must be a {expected_extension.upper()} file.")
            return

        temp_file_path = save_uploaded_file(uploaded_file, suffix=expected_extension)

        try:
            with st.spinner("Processing and uploading to vector store..."):
                result = process_and_store_upload(
                    pipeline=pipeline,
                    upload_mode=upload_mode,
                    temp_file_path=temp_file_path,
                    source_file=uploaded_file.name,
                    collection_name=selected_collection,
                )

            st.success(
                "Upload complete. "
                f"Processed {result['processed_count']} item(s) and stored "
                f"{result['stored_count']} item(s) in collection "
                f"'{result['collection_name']}'."
            )
        except Exception as ex:
            st.error(f"Failed to process/upload file: {ex}")
        finally:
            cleanup_temp_file(temp_file_path)

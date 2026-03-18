import os
import tempfile
import uuid
from typing import Any, Dict, List, Optional

from docx_processing.docx_processor import DocxProcessor
from pdf_processing.multi_modal_processor import MultiModalPDFProcessor
from pdf_processing.pdf_processor_text import TextProcessor


def list_collection_names(pipeline) -> List[str]:
    collections = pipeline.vector_db.client.list_collections()
    names: List[str] = []
    for collection in collections:
        if isinstance(collection, str):
            names.append(collection)
        else:
            names.append(getattr(collection, "name", str(collection)))
    return sorted(set(names))


def ensure_collection(pipeline, collection_name: str) -> str:
    clean_name = collection_name.strip()
    if not clean_name:
        raise ValueError("Collection name cannot be empty.")
    pipeline.vector_db.client.get_or_create_collection(name=clean_name)
    return clean_name


def infer_expected_extension(upload_mode: str) -> str:
    if upload_mode in {"PDF with images", "PDF with text ONLY"}:
        return ".pdf"
    return ".docx"


def save_uploaded_file(uploaded_file, suffix: str) -> str:
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
        tmp_file.write(uploaded_file.getvalue())
        return tmp_file.name


def cleanup_temp_file(file_path: str) -> None:
    if file_path and os.path.exists(file_path):
        os.remove(file_path)


def _text_collection_name() -> str:
    return os.getenv("upload_text_collection_name", "uploaded_documents")


def _multimodal_collection_name() -> str:
    return os.getenv("upload_multimodal_collection_name", "uploaded_multimodal_documents")


def _store_text_documents(
    pipeline,
    documents: List[Any],
    source_file: str,
    upload_mode: str,
    collection_name: str,
) -> int:
    texts: List[str] = []
    metadatas: List[Dict[str, Any]] = []

    for idx, doc in enumerate(documents):
        page_content = str(getattr(doc, "page_content", "") or "").strip()
        if not page_content:
            continue

        metadata = dict(getattr(doc, "metadata", {}) or {})
        metadata.update(
            {
                "source_file": source_file,
                "upload_mode": upload_mode,
                "chunk_index": idx,
            }
        )
        texts.append(page_content)
        metadatas.append(metadata)

    if not texts:
        return 0

    embeddings = pipeline.embedding_function(texts)
    ids = [str(uuid.uuid4()) for _ in texts]

    collection = pipeline.vector_db.client.get_or_create_collection(name=collection_name)
    collection.add(ids=ids, documents=texts, metadatas=metadatas, embeddings=embeddings)
    return len(texts)


def _store_multimodal_documents(
    pipeline,
    documents: List[Any],
    embeddings: List[Any],
    source_file: str,
    upload_mode: str,
    collection_name: str,
) -> int:
    if not documents or not embeddings:
        return 0

    texts: List[str] = []
    metadatas: List[Dict[str, Any]] = []
    normalized_embeddings: List[List[float]] = []

    for idx, (doc, embedding) in enumerate(zip(documents, embeddings)):
        page_content = str(getattr(doc, "page_content", "") or "").strip()
        if not page_content:
            continue

        metadata = dict(getattr(doc, "metadata", {}) or {})
        metadata.update(
            {
                "source_file": source_file,
                "upload_mode": upload_mode,
                "chunk_index": idx,
            }
        )

        vector = embedding.tolist() if hasattr(embedding, "tolist") else list(embedding)

        texts.append(page_content)
        metadatas.append(metadata)
        normalized_embeddings.append(vector)

    if not texts:
        return 0

    ids = [str(uuid.uuid4()) for _ in texts]
    collection = pipeline.vector_db.client.get_or_create_collection(name=collection_name)
    collection.add(ids=ids, documents=texts, metadatas=metadatas, embeddings=normalized_embeddings)
    return len(texts)


def process_and_store_upload(
    pipeline,
    upload_mode: str,
    temp_file_path: str,
    source_file: str,
    collection_name: Optional[str] = None,
) -> Dict[str, Any]:
    resolved_collection_name = collection_name or (
        _multimodal_collection_name()
        if upload_mode == "PDF with images"
        else _text_collection_name()
    )
    resolved_collection_name = ensure_collection(pipeline, resolved_collection_name)

    if upload_mode == "PDF with text ONLY":
        processor = TextProcessor()
        chunks = processor._process_pdf(temp_file_path)
        stored_count = _store_text_documents(
            pipeline,
            chunks,
            source_file,
            upload_mode,
            resolved_collection_name,
        )
        return {
            "processed_count": len(chunks),
            "stored_count": stored_count,
            "collection_name": resolved_collection_name,
        }

    if upload_mode == "PDF with images":
        processor = MultiModalPDFProcessor()
        processor._process_pdf(temp_file_path)
        stored_count = _store_multimodal_documents(
            pipeline,
            processor.all_documents,
            processor.all_embeddings,
            source_file,
            upload_mode,
            resolved_collection_name,
        )
        return {
            "processed_count": len(processor.all_documents),
            "stored_count": stored_count,
            "collection_name": resolved_collection_name,
        }

    processor = DocxProcessor()
    if upload_mode == "Structured DOCX":
        documents = processor._load_docx_structured(temp_file_path)
    else:
        documents = processor._load_docx_unstructured(temp_file_path)

    chunks = processor._process_docx(documents)
    stored_count = _store_text_documents(
        pipeline,
        chunks,
        source_file,
        upload_mode,
        resolved_collection_name,
    )
    return {
        "processed_count": len(chunks),
        "stored_count": stored_count,
        "collection_name": resolved_collection_name,
    }

from langchain.tools import tool

from langchain_community.document_loaders import Docx2txtLoader, UnstructuredWordDocumentLoader
from typing import List
from langchain_classic.schema import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
import os

class DocxProcessor:
    def __init__(self):
        """Processor for DOCX files, supporting both structured and unstructured loading, with text splitting capabilities."""
        self.chunk_size = int(os.getenv("chunk_size", 1000))
        self.chunk_overlap = int(os.getenv("chunk_overlap", 100))
        self.text_splitter = RecursiveCharacterTextSplitter(
            separators=[" ", "\n", "\n\n", ""],
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap
        )

    def _load_docx_structured(self, file_path: str):
        """Load a DOCX file using a structured loader."""
        try:
            docx_loader = Docx2txtLoader(file_path)
            return docx_loader.load()
        except Exception as e:
            print(f"Error loading DOCX file: {e}")
            raise e

    def _load_docx_unstructured(self, file_path: str):
        """Load a DOCX file using an unstructured loader."""
        try:
            unstructured_docx_loader = UnstructuredWordDocumentLoader(file_path, mode="elements")
            unstruct_docs = unstructured_docx_loader.load()
            print(f"Loaded {len(unstruct_docs)} document(s)")
            return unstruct_docs
        except Exception as e:
            print(f"Error loading unstructured DOCX file: {e}")
            raise e

    def _process_docx(self, documents: List[Document]):
        """Split text from documents into chunks using the configured text splitter."""
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", " ", ""],
        )
        return text_splitter.split_documents(documents)

    @tool
    def load_docx_structured(self, file_path: str):
        """Load a DOCX file using a structured loader."""
        return self._load_docx_structured(file_path)

    @tool
    def load_docx_unstructured(self, file_path: str):
        """Load a DOCX file using an unstructured loader."""
        return self._load_docx_unstructured(file_path)

    @tool
    def process_docx(self, documents: List[Document]):
        """Split text from documents into chunks using the configured text splitter."""
        return self._process_docx(documents)
    
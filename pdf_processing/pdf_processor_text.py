
import os
from langchain.tools import tool
from langchain_community.document_loaders import PyPDFLoader
from typing import List, Dict, Any
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

class TextProcessor:
    """Advanced TEXT ONLY PDF processing with error handling"""
    def __init__(self):
        self.chunk_size = int(os.getenv("chunk_size", 1000))
        self.chunk_overlap = int(os.getenv("chunk_overlap", 100))
        self.text_splitter = RecursiveCharacterTextSplitter(
            separators=[" "],
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap
        )

    # Apply the cleaning function
    def _clean_text(self, text:str) -> str:
        """ Cleans the passed in text """
        # Remove excessive whitespace
        text = " ".join(text.split())
        
        # Fix ligatures
        text = text.replace("ﬁ", "fi")
        text = text.replace("ﬂ", "fl")
        
        return text

    def _process_pdf(self, pdf_path: str) -> List[Document]:
        """Process PDF by loading and chunking and metadata enhancement."""
        loader = PyPDFLoader(pdf_path)
        pages = loader.load()

        processed_chunks = []
        for page_num, page in enumerate(pages):
            cleaned_text = self._clean_text(page.page_content)
            if len(cleaned_text.strip()) < 50:
                continue

            chunks = self.text_splitter.create_documents(
                texts=[cleaned_text],
                metadatas=[{
                    **page.metadata,
                    "page": page_num + 1,
                    "total_pages": len(pages),
                    "chunk_method": "smart_pdf_processor",
                    "char_count": len(cleaned_text),
                }],
            )
            processed_chunks.extend(chunks)

        return processed_chunks

    @tool
    def process_pdf(self, pdf_path: str) -> List[Document]:
        """Process PDF by loading and chunking and metadata enhancement."""
        return self._process_pdf(pdf_path)

    def get_load_tools(self):
        """Return the tools for loading and processing PDFs."""
        return [self.process_pdf]
    
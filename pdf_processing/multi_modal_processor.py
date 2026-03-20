
import os
from langchain.tools import tool
import fitz  # PyMuPDF
from langchain_core.documents import Document
from pdf_processing.multi_modal_parent import MultiModalParent
from transformers import CLIPProcessor, CLIPModel
from PIL import Image
import torch
import numpy as np
import base64
import io
from langchain_classic.text_splitter import RecursiveCharacterTextSplitter

class MultiModalPDFProcessor(MultiModalParent):
    """Processes PDFs to extract both text and images, creating CLIP embeddings for unified multi-modal retrieval."""
    def __init__(self, clip_model_name="openai/clip-vit-base-patch32"):
        super().__init__()
        self.pdf_path = ""
        self.clip_model_name = clip_model_name
        self.clip_model = CLIPModel.from_pretrained(self.clip_model_name)
        self.clip_processor = CLIPProcessor.from_pretrained(self.clip_model_name)
        # Storage for all documents and their embeddings
        self.all_documents = []
        self.all_embeddings = []
        self.image_data_storage = {}  # To store image data for later retrieval
        self.chunk_size = int(os.getenv("chunk_size", 1000))
        self.chunk_overlap = int(os.getenv("chunk_overlap", 100))
    

    # Embedding functions
    # embedding function for image
    def embed_image(self, image_data):
        """Embed image data using class's CLIP model."""
        if isinstance(image_data, str):
            image = Image.open(image_data).convert("RGB")
        else:
            image = image_data
            inputs = self.clip_processor(images=image, return_tensors="pt")
            with torch.no_grad():
                outputs = self.clip_model.get_image_features(**inputs)
            
            # FIX: Extract the tensor from the 'BaseModelOutputWithPooling' object
            # Usually .pooler_output, or fallback to 'outputs' if it's already a tensor
            image_features = outputs.pooler_output if hasattr(outputs, "pooler_output") else outputs
            
            # Normalize embeddings to unit vector
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            return image_features.squeeze().cpu().numpy()
    
    def _process_pdf(self, pdf_path: str) -> None:
        """
        Process the PDF file, extracting both text and images, and creating embeddings for each.
        """
        self.pdf_path = pdf_path
        # Ensure each processing run starts clean so no prior-file artifacts affect indexing.
        self.all_documents = []
        self.all_embeddings = []
        self.image_data_storage = {}
        doc = fitz.open(pdf_path)

        splitter = RecursiveCharacterTextSplitter(chunk_size=self.chunk_size, chunk_overlap=self.chunk_overlap)

        try:
            for i, page in enumerate(doc):
                text = page.get_text()
                if text.strip():
                    temp_doc = Document(
                        page_content=text,
                        metadata={"page": i + 1, "page_index": i, "type": "text"},
                    )
                    text_chunks = splitter.split_documents([temp_doc])
                    for chunk in text_chunks:
                        embedding = self.embed_text(chunk.page_content)
                        self.all_embeddings.append(embedding)
                        self.all_documents.append(chunk)

                for img_idx, img in enumerate(page.get_images(full=True)):
                    try:
                        xref = img[0]
                        base_image = doc.extract_image(xref)
                        image_bytes = base_image["image"]

                        pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
                        image_id = f"page_{i}_img_{img_idx}"

                        buffered = io.BytesIO()
                        pil_image.save(buffered, format="PNG")
                        img_base64 = base64.b64encode(buffered.getvalue()).decode()
                        self.image_data_storage[image_id] = img_base64

                        embedding = self.embed_image(pil_image)
                        self.all_embeddings.append(embedding)

                        image_doc = Document(
                            page_content=f"[Image: {image_id}]",
                            metadata={"page": i + 1, "page_index": i, "type": "image", "image_id": image_id},
                        )
                        self.all_documents.append(image_doc)
                    except Exception as e:
                        print(f"Error processing image {img_idx} on page {i}: {e}")
                        continue
        finally:
            doc.close()

    @tool
    def process_pdf(self, pdf_path: str) -> None:
        """
        Process the PDF file, extracting both text and images, and creating embeddings for each.
        """
        self._process_pdf(pdf_path)

    @tool
    def get_all_embeddings(self):
        """Return all documents with their corresponding embeddings."""
        embeddings_array = np.array(self.all_embeddings)

        all_embeddings = [(doc.page_content, emb) for doc, emb in zip(self.all_documents, embeddings_array)]
        return all_embeddings

    def get_load_tools(self):
        """Return the tools for loading and processing PDFs."""
        return [self.process_pdf, self.get_all_embeddings]
        
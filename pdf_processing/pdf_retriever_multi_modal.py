from langchain_classic.schema.messages import HumanMessage
from pdf_processing.multi_modal_parent import MultiModalParent
from langchain.tools import tool

class PDFRetrieverMultiModal(MultiModalParent):

    def __init__(self, vector_store, image_data_storage):
        """Multi-modal PDF retriever that uses CLIP embeddings for unified retrieval of text and images."""
        super().__init__()
        self.vector_store = vector_store  # This should be an instance of a vector store that supports similarity search
        self.image_data_storage = image_data_storage  # To store image data for later retrieval

    @tool
    def retrieve_multimodal(self, query, k=5):
        """Unified retrieval using CLIP embeddings for both text and images."""
        # Embed query using CLIP
        query_embedding = self.embed_text(query)

        # Search based on the query embedding
        results = self.vector_store.similarity_search_by_vector(embedding=query_embedding, k=k)

        return results
    
    @tool
    def create_multi_modal_message(self, query, retrieve_docs):
        """Create a human message with both text and images."""
        content = []

        # Add the query
        content.append({
            "type": "text",
            "text": f"Q: {query}\n\nContext:\n"
        })

        # Separate text and image documents
        text_docs = [doc for doc in retrieve_docs if doc.metadata.get("type") == "text"]
        image_docs = [doc for doc in retrieve_docs if doc.metadata.get("type") == "image"]

        # Add text context
        if text_docs:
            text_content = "\n\n".join([
                f"[page {doc.metadata['page']}]: {doc.page_content}"
                for doc in text_docs
            ])
            content.append({
                "type": "text",
                "text": f"Text excerpts:\n{text_content}\n"
            })

        # Add images
        for doc in image_docs:
            image_id = doc.metadata.get("image_id")
            if image_id and image_id in self.image_data_storage:
                content.append({
                    "type": "text",
                    "text": f"\n[Image from page {doc.metadata['page']}]:\n"
                })
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{self.image_data_storage[image_id]}"
                    }
                })

        # Add instructions
        content.append({
            "type": "text",
            "text": "\n\nPlease answer the question based on the provided text and images."
        })

        return HumanMessage(content=content)
    
    @tool
    def get_multi_modal_response(self, query, llm):
        """Get a response from LLM based on the query and retrieved multimodal context and return the content."""
        # Retrieve relevant documents
        context_docs = self.retrieve_multimodal(query, k=5)
        
        # Create multimodal message
        message = self.create_multi_modal_message(query, context_docs)
        
        response = llm.invoke([message])
        
        # Print retrieved context info
        print(f"\nRetrieved {len(context_docs)} documents:")
        for doc in context_docs:
            doc_type = doc.metadata.get("type", "unknown")
            page = doc.metadata.get("page", "?")
            if doc_type == "text":
                preview = doc.page_content[:100] + "..." if len(doc.page_content) > 100 else doc.page_content
                print(f"  - Text from page {page}: {preview}")
            else:
                print(f"  - Image from page {page}")
        print("\n")
        
        return response.content
    
    def get_retrieval_tools(self):
        """Return the tools for loading and processing PDFs."""
        return [self.retrieve_multimodal, self.create_multi_modal_message, self.get_multi_modal_response]
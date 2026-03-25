
import os
import uuid
from langchain.tools import tool
import chromadb
from chromadb.errors import InvalidArgumentError
from dotenv import load_dotenv
from langchain_classic.schema import Document
from pipeline.nodes.vector.answer_validation import distance_to_similarity

load_dotenv()

class ChromaDB:
    def __init__(self, embedding_func):
        # Use HttpClient for Docker/Server connections
        self.host = os.getenv('chroma_db_host')
        self.port = int(os.getenv('chroma_db_port'))
        self.client = chromadb.HttpClient(host=self.host, port=self.port)
        self.embedding_func = embedding_func
        self.default_n_results = self._parse_n_results(os.getenv("chroma_db_n_results", "10"))
        self._multimodal_processor = None
        self.retriever = None

    def _parse_n_results(self, raw_value):
        try:
            parsed = int(raw_value)
            return parsed if parsed > 0 else 10
        except (TypeError, ValueError):
            return 10

    def _resolve_n_results(self, n_results):
        if n_results is None:
            return self.default_n_results
        return self._parse_n_results(n_results)

    def _is_probably_multimodal_collection(self, collection_name: str) -> bool:
        name = str(collection_name or "").strip().lower()
        return "multimodal" in name or "multi_modal" in name

    def _get_multimodal_processor(self):
        if self._multimodal_processor is None:
            from pdf_processing.multi_modal_processor import MultiModalPDFProcessor

            self._multimodal_processor = MultiModalPDFProcessor()
        return self._multimodal_processor

    def _embed_query_text(self, query_text: str, use_multimodal: bool = False):
        if use_multimodal:
            processor = self._get_multimodal_processor()
            embedding = processor.embed_text(query_text)
            return [embedding.tolist() if hasattr(embedding, "tolist") else list(embedding)]
        return self.embedding_func([query_text])

    def _embed_query_texts(self, query_texts, use_multimodal: bool = False):
        payload = [str(item or "") for item in (query_texts or [])]
        if not payload:
            payload = [""]
        if use_multimodal:
            processor = self._get_multimodal_processor()
            embeddings = []
            for query_text in payload:
                embedding = processor.embed_text(query_text)
                embeddings.append(embedding.tolist() if hasattr(embedding, "tolist") else list(embedding))
            return embeddings
        return self.embedding_func(payload)

    def _query_collection_with_fallback(self, collection, query_text: str, n_results: int):
        collection_name = getattr(collection, "name", "")
        if self._is_probably_multimodal_collection(collection_name):
            query_embeddings = self._embed_query_text(query_text, use_multimodal=True)
            return collection.query(query_embeddings=query_embeddings, n_results=n_results)

        try:
            query_embeddings = self._embed_query_text(query_text, use_multimodal=False)
            return collection.query(query_embeddings=query_embeddings, n_results=n_results)
        except InvalidArgumentError as ex:
            error_message = str(ex)
            if "dimension" not in error_message.lower():
                raise
            print(
                "[VECTOR RETRIEVER] Embedding dimension mismatch detected. "
                "Retrying with CLIP text embeddings for multimodal collection."
            )
            query_embeddings = self._embed_query_text(query_text, use_multimodal=True)
            return collection.query(query_embeddings=query_embeddings, n_results=n_results)

    def _get_collection_internal(self, name):
        """Internal method to retrieve or create a collection (not exposed as tool)."""
        return self.client.get_or_create_collection(name=name)

    @tool
    def get_collection(self, name):
        """Retrieves an existing collection or creates it if it doesn't exist."""
        return self._get_collection_internal(name)

    @tool
    def similarity_search(self, collection_name, query_texts, n_results=None):
        """
        Runs a similarity search (semantic select) against the collection
        using explicit query embeddings from the configured embedding function.
        """
        resolved_n_results = self._resolve_n_results(n_results)
        collection = self._get_collection_internal(collection_name)
        query_payload = query_texts if isinstance(query_texts, list) else [query_texts]
        if self._is_probably_multimodal_collection(collection_name):
            query_embeddings = self._embed_query_texts(query_payload, use_multimodal=True)
            return collection.query(query_embeddings=query_embeddings, n_results=resolved_n_results)

        try:
            query_embeddings = self._embed_query_texts(query_payload, use_multimodal=False)
            results = collection.query(query_embeddings=query_embeddings, n_results=resolved_n_results)
        except InvalidArgumentError as ex:
            error_message = str(ex)
            if "dimension" not in error_message.lower():
                raise
            print(
                "[VECTOR RETRIEVER] Embedding dimension mismatch detected. "
                "Retrying with CLIP text embeddings for multimodal collection."
            )
            query_embeddings = self._embed_query_texts(query_payload, use_multimodal=True)
            results = collection.query(query_embeddings=query_embeddings, n_results=resolved_n_results)
        return results
    
    @tool
    def similarity_search_with_scores(self, collection_name, query, n_results=None):
        """
        Similar to similarity_search but also returns similarity scores.
        """
        resolved_n_results = self._resolve_n_results(n_results)
        collection = self._get_collection_internal(collection_name)
        results = self._query_collection_with_fallback(collection, str(query or ""), resolved_n_results)

        distances = results.get("distances", [[]])
        distance_list = distances[0] if distances and isinstance(distances[0], list) else []
        results["similarity_scores"] = [distance_to_similarity(float(distance)) for distance in distance_list]
        return results
    
    @tool
    def add_documents_to_collection(self, collection_name, documents, metadatas=None):
        """
        Adds new documents to the collection using explicit embeddings.
        """
        collection = self._get_collection_internal(collection_name)
        document_payload = documents if isinstance(documents, list) else [documents]
        embeddings = self.embedding_func(document_payload)
        ids = [str(uuid.uuid4()) for _ in document_payload]

        metadata_payload = metadatas
        if metadata_payload is None:
            metadata_payload = [{} for _ in document_payload]

        collection.add(
            ids=ids,
            documents=document_payload,
            embeddings=embeddings,
            metadatas=metadata_payload,
        )
    
    @tool
    def add_embeddings_to_collection(self, collection_name, embeddings, all_documents):
        """
        Adds documents with pre-computed embeddings to the collection.
        This is useful if you want to use a custom embedding function or have already generated embeddings.
        """
        collection = self._get_collection_internal(collection_name)

        doc_payload = []
        metadata_payload = []
        for doc in all_documents:
            page_content = getattr(doc, "page_content", None)
            metadata = getattr(doc, "metadata", None)
            doc_payload.append(str(page_content) if page_content is not None else "")
            metadata_payload.append(metadata if isinstance(metadata, dict) else {})

        ids = [str(uuid.uuid4()) for _ in doc_payload]
        collection.add(
            ids=ids,
            documents=doc_payload,
            embeddings=embeddings,
            metadatas=metadata_payload,
        )

    def as_retriever(self, search_type="similarity", score_threshold=float(os.getenv("vector_similarity_threshold", 0.8)), n_results=None, ):
        """
        Returns a retriever function that can be used in LangChain pipelines.
        """
        resolved_n_results = self._resolve_n_results(n_results)
        if search_type == "similarity_score_threshold":
            self.retriever = self.client.as_retriever(
                search_type=search_type,
                search_kwargs={"k": resolved_n_results,"score_threshold": score_threshold}
            )
        else:
            self.retriever = self.client.as_retriever(search_type=search_type)

        return self.retriever
    
    def as_retriever_tool(self):
        """Returns a vector retrieval tool backed by direct Chroma queries."""

        def _retrieve(query: str, collection_name: str, n_results: int = None):
            """Retrieve relevant documents from a specific Chroma collection using semantic search."""
            selected_collection = (collection_name or "").strip()
            if not selected_collection:
                raise ValueError("collection_name is required for vector retrieval.")

            resolved_n_results = self._resolve_n_results(n_results)

            print(
                f"[VECTOR RETRIEVER] Querying collection='{selected_collection}' "
                f"with n_results={resolved_n_results}"
            )

            collection = self._get_collection_internal(selected_collection)
            response = self._query_collection_with_fallback(collection, str(query or ""), resolved_n_results)

            documents = response.get("documents", [[]])
            metadatas = response.get("metadatas", [[]])
            distances = response.get("distances", [[]])

            doc_list = documents[0] if documents and isinstance(documents[0], list) else []
            metadata_list = metadatas[0] if metadatas and isinstance(metadatas[0], list) else []
            distance_list = distances[0] if distances and isinstance(distances[0], list) else []

            results = []
            for idx, page_content in enumerate(doc_list):
                metadata = metadata_list[idx] if idx < len(metadata_list) and isinstance(metadata_list[idx], dict) else {}
                if idx < len(distance_list):
                    distance = distance_list[idx]
                    similarity_score = distance_to_similarity(float(distance))
                    metadata = {
                        **metadata,
                        "distance": distance,
                        "similarity_score": similarity_score,
                        "score": similarity_score,
                    }
                results.append(Document(page_content=str(page_content), metadata=metadata))

            print(f"[VECTOR RETRIEVER] Retrieved {len(results)} document(s).")
            return results

        return tool("chroma_db_retriever")(_retrieve)
        
    def get_vector_db_tools(self):
        """Return the tools for interacting with the vector database."""
        return [self.similarity_search, self.similarity_search_with_scores, self.add_documents_to_collection, self.add_embeddings_to_collection, self.get_collection, self.as_retriever_tool]
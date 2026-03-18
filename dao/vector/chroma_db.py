
import os
import uuid
from langchain.tools import tool
import chromadb
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
        self.retriever = None

    def _get_collection_internal(self, name):
        """Internal method to retrieve or create a collection (not exposed as tool)."""
        return self.client.get_or_create_collection(name=name)

    @tool
    def get_collection(self, name):
        """Retrieves an existing collection or creates it if it doesn't exist."""
        return self._get_collection_internal(name)

    @tool
    def similarity_search(self, collection_name, query_texts, n_results=5):
        """
        Runs a similarity search (semantic select) against the collection
        using explicit query embeddings from the configured embedding function.
        """
        collection = self._get_collection_internal(collection_name)
        query_payload = query_texts if isinstance(query_texts, list) else [query_texts]
        query_embeddings = self.embedding_func(query_payload)
        results = collection.query(query_embeddings=query_embeddings, n_results=n_results)
        return results
    
    @tool
    def similarity_search_with_scores(self, collection_name, query, n_results=5):
        """
        Similar to similarity_search but also returns similarity scores.
        """
        collection = self._get_collection_internal(collection_name)
        query_embeddings = self.embedding_func([query])
        results = collection.query(query_embeddings=query_embeddings, n_results=n_results)

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

    def as_retriever(self, search_type="similarity", score_threshold=0.5, n_results=5, ):
        """
        Returns a retriever function that can be used in LangChain pipelines.
        """
        if search_type == "similarity_score_threshold":
            self.retriever = self.client.as_retriever(
                search_type=search_type,
                search_kwargs={"k": n_results,"score_threshold": score_threshold}
            )
        else:
            self.retriever = self.client.as_retriever(search_type=search_type)

        return self.retriever
    
    def as_retriever_tool(self):
        """Returns a vector retrieval tool backed by direct Chroma queries."""

        def _retrieve(query: str, collection_name: str, n_results: int = 5):
            """Retrieve relevant documents from a specific Chroma collection using semantic search."""
            selected_collection = (collection_name or "").strip()
            if not selected_collection:
                raise ValueError("collection_name is required for vector retrieval.")
            print(
                f"[VECTOR RETRIEVER] Querying collection='{selected_collection}' "
                f"with n_results={n_results}"
            )

            collection = self._get_collection_internal(selected_collection)
            query_embeddings = self.embedding_func([query])
            response = collection.query(query_embeddings=query_embeddings, n_results=n_results)

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
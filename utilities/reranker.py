import os

import cohere

class Reranker:
    def __init__(self, llm_model=None, model_name=None, api_key=None):
        self.llm_model = llm_model
        self.model_name = model_name or os.getenv("cohere_rerank_model", "rerank-v4.0")
        self.api_key = api_key or os.getenv("COHERE_API_KEY") or os.getenv("cohere_api_key")
        self.client = cohere.ClientV2(api_key=self.api_key) if self.api_key else None

    def rerank(self, query: str, documents: list) -> list:
        if not documents:
            return []

        if self.client is None:
            return documents

        doc_texts = [doc.page_content for doc in documents]

        try:
            response = self.client.rerank(
                model=self.model_name,
                query=query,
                documents=doc_texts,
                top_n=len(doc_texts),
            )
        except Exception:
            return documents

        ranked_indices = []
        for item in response.results:
            index = getattr(item, "index", None)
            if isinstance(index, int) and 0 <= index < len(documents) and index not in ranked_indices:
                ranked_indices.append(index)

        ranked_documents = [documents[index] for index in ranked_indices]

        for index, document in enumerate(documents):
            if index not in ranked_indices:
                ranked_documents.append(document)

        return ranked_documents
import os

from chromadb.utils import embedding_functions
from langchain_ollama import OllamaLLM


def _normalize_model_name(model_name: str, default: str) -> str:
    if not model_name:
        return default
    cleaned = str(model_name).strip().strip('"').strip("'")
    if ":" in cleaned:
        prefix, value = cleaned.split(":", 1)
        if prefix.lower() in {"ollama", "model"}:
            return value
    return cleaned


class OllamaModel:
    def __init__(self):
        self.host = str(os.getenv("ollama_host", "localhost")).strip().strip('"').strip("'")
        self.port = str(os.getenv("ollama_port", "11434")).strip().strip('"').strip("'")

        self.llm_model_name = _normalize_model_name(
            os.getenv("ollama_llm_model_name") or os.getenv("ollama_model_name"),
            default="mistral",
        )
        self.embedding_model_name = _normalize_model_name(
            os.getenv("ollama_embedding_model_name"),
            default="nomic-embed-text",
        )

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def create_llm(self):
        return OllamaLLM(
            model=self.llm_model_name,
            base_url=self.base_url,
        )

    def create_embedding_function(self):
        return embedding_functions.OllamaEmbeddingFunction(
            model_name=self.embedding_model_name,
            url=f"{self.base_url}/api/embeddings",
        )
import os

from chromadb.utils import embedding_functions
from langchain_openai import ChatOpenAI


def _clean_value(value: str, default: str = "") -> str:
    if value is None:
        return default
    cleaned = str(value).strip().strip('"').strip("'")
    return cleaned or default


class OpenAIModel:
    def __init__(self):
        self.api_key = _clean_value(os.getenv("OPENAI_API_KEY"))
        self.base_url = _clean_value(os.getenv("OPENAI_BASE_URL"))

        self.llm_model_name = _clean_value(
            os.getenv("openai_llm_model_name") or os.getenv("openai_model_name"),
            default="gpt-4o-mini",
        )
        self.embedding_model_name = _clean_value(
            os.getenv("openai_embedding_model_name"),
            default="text-embedding-3-small",
        )

    def create_llm(self):
        kwargs = {
            "model": self.llm_model_name,
            "api_key": self.api_key,
        }
        if self.base_url:
            kwargs["base_url"] = self.base_url
        return ChatOpenAI(**kwargs)

    def create_embedding_function(self):
        kwargs = {
            "api_key": self.api_key,
            "model_name": self.embedding_model_name,
        }
        if self.base_url:
            kwargs["api_base"] = self.base_url
        return embedding_functions.OpenAIEmbeddingFunction(**kwargs)
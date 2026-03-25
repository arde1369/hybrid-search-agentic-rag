#!/usr/bin/env python
"""
Utility script to load golden SQL seed data from feedback_pairs.csv into Chroma.
This provides a good starting reference point for the application.

Usage:
    python load_golden_sql_seeds.py
"""

import os
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List

import chromadb
from chromadb.utils import embedding_functions


GOLDEN_SQL_COLLECTION = os.getenv("chroma_db_collection_golden_sql", "golden_sql_collection")


def _normalize_model_name(model_name: str, default: str) -> str:
    """Normalize model name from environment variable."""
    if not model_name:
        return default
    cleaned = str(model_name).strip().strip('"').strip("'")
    if ":" in cleaned:
        prefix, value = cleaned.split(":", 1)
        if prefix.lower() in {"ollama", "model"}:
            return value
    return cleaned


def _clean_value(value: str, default: str = "") -> str:
    """Clean string value from environment variable."""
    if value is None:
        return default
    cleaned = str(value).strip().strip('"').strip("'")
    return cleaned or default


def create_minimal_pipeline():
    """Create a minimal pipeline with only vector DB and embedding function."""
    llm_provider = str(os.getenv("llm_provider", "ollama")).strip().lower()
    
    if llm_provider == "openai":
        # Create OpenAI embedding function directly
        api_key = _clean_value(os.getenv("OPENAI_API_KEY"))
        embedding_model_name = _clean_value(
            os.getenv("openai_embedding_model_name") or os.getenv("openai_model_name"),
            default="text-embedding-3-small",
        )
        base_url = _clean_value(os.getenv("OPENAI_BASE_URL"))
        
        kwargs = {
            "api_key": api_key,
            "model_name": embedding_model_name,
        }
        if base_url:
            kwargs["api_base"] = base_url
        embedding_function = embedding_functions.OpenAIEmbeddingFunction(**kwargs)
    else:
        # Create Ollama embedding function directly
        host = str(os.getenv("ollama_host", "localhost")).strip().strip('"').strip("'")
        port = str(os.getenv("ollama_port", "11434")).strip().strip('"').strip("'")
        embedding_model_name = _normalize_model_name(
            os.getenv("ollama_embedding_model_name"),
            default="nomic-embed-text",
        )
        
        base_url = f"http://{host}:{port}"
        embedding_function = embedding_functions.OllamaEmbeddingFunction(
            model_name=embedding_model_name,
            url=f"{base_url}/api/embeddings",
        )
    
    # Create Chroma client directly (HttpClient for server/Docker, local otherwise)
    chroma_host = os.getenv('chroma_db_host')
    chroma_port = os.getenv('chroma_db_port')
    
    if chroma_host and chroma_port:
        try:
            client = chromadb.HttpClient(host=chroma_host, port=int(chroma_port))
        except (ValueError, TypeError):
            client = chromadb.EphemeralClient()
    else:
        client = chromadb.EphemeralClient()
    
    class MinimalPipeline:
        pass
    
    pipeline = MinimalPipeline()
    pipeline.client = client
    pipeline.embedding_function = embedding_function
    
    return pipeline


def load_golden_sql_seed_data(pipeline, seed_file_path: str) -> int:
    """
    Load golden SQL examples from a seed file into the golden_sql_collection.
    Seed file format: entries separated by '---', each entry has three lines:
      User query: ...
      Sub-query: ...
      SQL: ...
    """
    if not os.path.exists(seed_file_path):
        print(f"Seed file not found: {seed_file_path}")
        return 0

    try:
        with open(seed_file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading seed file {seed_file_path}: {e}")
        return 0

    # Split by '---' to get individual entries
    entry_blocks = content.split("---")
    
    entries: List[Dict[str, str]] = []
    for block in entry_blocks:
        block = block.strip()
        if not block:
            continue
        
        # Parse three-line format
        lines = block.split("\n")
        user_query = ""
        sub_query = ""
        sql_query = ""
        
        for line in lines:
            line = line.strip()
            if line.startswith("User query:"):
                user_query = line.replace("User query:", "", 1).strip()
            elif line.startswith("Sub-query:"):
                sub_query = line.replace("Sub-query:", "", 1).strip()
            elif line.startswith("SQL:"):
                sql_query = line.replace("SQL:", "", 1).strip()
        
        if user_query and sub_query and sql_query:
            entries.append(
                {
                    "user_query": user_query,
                    "sub_query": sub_query,
                    "sql_query": sql_query,
                }
            )
    
    if not entries:
        print(f"No valid entries found in seed file: {seed_file_path}")
        return 0

    # Deduplicate entries
    deduped: List[Dict[str, str]] = []
    seen = set()
    for item in entries:
        key = (item["user_query"], item["sub_query"], item["sql_query"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    print(f"Loaded {len(deduped)} unique golden SQL seed entries from {seed_file_path}")

    # Get or create collection from chromadb client
    collection = pipeline.client.get_or_create_collection(
        name=GOLDEN_SQL_COLLECTION,
        metadata={"hnsw:space": "cosine"}
    )

    ids: List[str] = []
    documents: List[str] = []
    metadatas: List[Dict[str, Any]] = []

    for entry in deduped:
        document = (
            f"User query: {entry['user_query']}\n"
            f"Sub-query: {entry['sub_query']}\n"
            f"SQL: {entry['sql_query']}"
        )
        ids.append(str(uuid.uuid4()))
        documents.append(document)
        metadatas.append(
            {
                "user_query": entry["user_query"],
                "sub_query": entry["sub_query"],
                "sql_query": entry["sql_query"],
                "feedback": "good",
                "source": "seed_data",
            }
        )

    embeddings = pipeline.embedding_function(documents)
    print(f"Adding {len(documents)} seed entries to '{GOLDEN_SQL_COLLECTION}'...")
    collection.add(ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings)
    return len(documents)


def main():
    """Load golden SQL seed data into the vector database."""
    
    # Determine seed file path
    seed_file = Path(__file__).parent / "sample_docs" / "feedback_pairs.csv"
    
    if not seed_file.exists():
        print(f"Error: Seed file not found at {seed_file}")
        return 1
    
    print(f"Loading golden SQL seed data from: {seed_file}")
    print("-" * 60)
    
    try:
        # Create minimal pipeline (no SQL DAO, only vector DB)
        pipeline = create_minimal_pipeline()
        
        # Load seed data
        loaded_count = load_golden_sql_seed_data(pipeline, str(seed_file))
        
        print("-" * 60)
        print(f"Successfully loaded {loaded_count} golden SQL entries into the collection.")
        print("The application now has seed reference examples for SQL generation.")
        return 0
        
    except Exception as e:
        print(f"Error loading seed data: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

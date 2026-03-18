from typing import Any, Dict, List, NotRequired
from langchain_classic.schema import Document

from .base_state import BaseState


class RAGReflectionState(BaseState):
    question: str
    collection_name: NotRequired[str]
    retrieved_docs: NotRequired[List[Document]]
    answer: NotRequired[Dict[str, Any]]
    reflection: NotRequired[str]
    revised: NotRequired[bool]
    attempts: NotRequired[int]
    routes: NotRequired[List[Dict[str, Any]]]
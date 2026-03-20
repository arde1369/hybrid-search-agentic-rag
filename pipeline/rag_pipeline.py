import os
import json

from dao.sql.sql_dao import SQLDAO
from dao.vector.chroma_db import ChromaDB
from langgraph.graph import StateGraph, END, START
from langchain_core.messages import HumanMessage
from models import OllamaModel, OpenAIModel
from pipeline.prompts import build_follow_up_resolution_prompt
from state.rag_reflection_state import RAGReflectionState
from utilities.cache import InMemoryCache
from utilities.reranker import Reranker
from utilities.safety import POLICY_BLOCK_MESSAGE, should_block_ssn_prompt_input
from langgraph.checkpoint.memory import MemorySaver
from pipeline.nodes import (
    executor_node as run_executor_node,
    reflect_node as run_reflect_node,
    router_node as run_router_node,
    should_continue_refining as should_continue_refining_node,
)

class Pipeline:
    def __init__(self):
        self.sql_dao = SQLDAO()
        self.llm_provider = str(os.getenv("llm_provider", "ollama")).strip().lower()

        if self.llm_provider == "openai":
            self.model_provider = OpenAIModel()
        else:
            self.model_provider = OllamaModel()

        self.embedding_function = self.model_provider.create_embedding_function()

        try:
            router_cache_ttl_seconds = max(1, int(os.getenv("router_cache_ttl_seconds", "120")))
        except ValueError:
            router_cache_ttl_seconds = 120

        try:
            router_cache_max_entries = max(1, int(os.getenv("router_cache_max_entries", "1")))
        except ValueError:
            router_cache_max_entries = 1

        try:
            reflection_cache_max_entries = max(1, int(os.getenv("reflection_cache_max_entries", "200")))
        except ValueError:
            reflection_cache_max_entries = 200

        try:
            reflection_cache_ttl_raw = int(os.getenv("reflection_cache_ttl_seconds", "0"))
        except ValueError:
            reflection_cache_ttl_raw = 0
        reflection_cache_ttl_seconds = reflection_cache_ttl_raw if reflection_cache_ttl_raw > 0 else None
        
        self.vector_db = ChromaDB(embedding_func=self.embedding_function)
        self.llm_agent = self.model_provider.create_llm()
        self.reranker = Reranker(self.llm_agent)
        self.dao_tools = [self.vector_db.as_retriever_tool(), *self.sql_dao.get_sql_tools()]
        self._memory = MemorySaver()
        self._graph = None
        self._router_schema_cache = InMemoryCache(
            max_entries=router_cache_max_entries,
            default_ttl_seconds=router_cache_ttl_seconds,
        )
        self._router_few_shot_cache = InMemoryCache(
            max_entries=router_cache_max_entries,
            default_ttl_seconds=router_cache_ttl_seconds,
        )
        self._reflection_cache = InMemoryCache(
            max_entries=reflection_cache_max_entries,
            default_ttl_seconds=reflection_cache_ttl_seconds,
        )

    def router_node(self, state : RAGReflectionState) -> RAGReflectionState:
        return run_router_node(self, state)

    def executor_node(self, state: RAGReflectionState) -> RAGReflectionState:
        return run_executor_node(self, state)

    
    def reflect_node(self, state: RAGReflectionState) -> RAGReflectionState:
        return run_reflect_node(self, state)

    def _should_continue_refining(self, state: RAGReflectionState) -> str:
        return should_continue_refining_node(state)

    def _resolve_effective_question(self, question: str, conversation_context: str = "") -> str:
        question = str(question or "").strip()
        conversation_context = str(conversation_context or "").strip()
        if not question or not conversation_context:
            return question

        prompt = build_follow_up_resolution_prompt(
            question=question,
            conversation_context=conversation_context,
        )

        try:
            result = self.llm_agent.invoke(prompt)
            if not isinstance(result, str):
                result = str(result)
            resolved_question = result.strip()
            return resolved_question or question
        except Exception as ex:
            print(f"[PIPELINE] Failed to resolve follow-up question: {ex}")
            return question

    def build_graph(self):
        """
        Build and compile the LangGraph workflow.
        
        Flow:
        1. START -> router_node (decompose query into routes)
        2. router_node -> executor_node (execute routes and retrieve results)
        3. executor_node -> reflect_node (evaluate answer quality)
        4. reflect_node -> conditional:
           - If answer is complete OR max iterations (2): -> END
           - Else: -> router_node (refine with better reasoning)
        
        REQUIREMENT: Maintains Few-Shot Learning integration throughout the graph.
        """
        if self._graph is not None:
            return self._graph

        print("Building RAG Pipeline graph...")
        workflow = StateGraph(RAGReflectionState)
        
        workflow.add_node("router", self.router_node)
        workflow.add_node("executor", self.executor_node)
        workflow.add_node("reflect", self.reflect_node)
        
        workflow.add_edge(START, "router")
        workflow.add_edge("router", "executor")
        workflow.add_edge("executor", "reflect")
        
        workflow.add_conditional_edges(
            "reflect",
            self._should_continue_refining,
            {
                "end": END,
                "refine": "router"
            }
        )
        
        self._graph = workflow.compile(checkpointer=self._memory)
        return self._graph

    @staticmethod
    def _build_policy_block_state(question: str, reason_code: str) -> RAGReflectionState:
        return {
            "question": question,
            "collection_name": "",
            "retrieved_docs": [],
            "answer": {
                "query": question,
                "results": [],
                "policy_message": POLICY_BLOCK_MESSAGE,
                "policy_blocked": True,
                "policy_reason": reason_code,
            },
            "reflection": "",
            "revised": False,
            "attempts": 0,
            "routes": [],
            "messages": [HumanMessage(content=question)],
        }

    def run_graph(self, question: str, collection_name: str = "", thread_id: str = "", conversation_context: str = ""):
        """
        Execute the compiled LangGraph with an input question.
        
        Args:
            question: The user's input question
            
        Returns:
            Final state containing the answer and reflection history
        """
        question = str(question or "").strip()
        conversation_context = str(conversation_context or "").strip()
        effective_question = self._resolve_effective_question(question, conversation_context)
        print(f"Running RAG Pipeline for question: {question}")
        if effective_question != question:
            print(f"Resolved follow-up question to: {effective_question}")

        if should_block_ssn_prompt_input(question):
            print("[SAFETY] Blocked prompt input due to SSN policy.")
            return self._build_policy_block_state(question, reason_code="ssn_prompt_input_blocked")

        resolved_thread_id = str(thread_id or "default_thread").strip()
        config = {"configurable": {"thread_id": resolved_thread_id}}

        graph = self.build_graph()
        
        initial_state: RAGReflectionState = {
            "question": question,
            "effective_question": effective_question,
            "conversation_context": conversation_context,
            "collection_name": collection_name,
            "thread_id": resolved_thread_id,
            "retrieved_docs": [],
            "answer": {},
            "reflection": "",
            "revised": False,
            "attempts": 0,
            "routes": [],
            "messages": [HumanMessage(content=question)],
        }
        
        final_state = graph.invoke(initial_state, config=config)
        print(f"RAG Pipeline completed for question: {question}")
        print(f"Final state: {json.dumps(final_state, default=str, indent=2)}")
        return final_state
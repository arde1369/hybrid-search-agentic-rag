import os
import json

from dao.sql.sql_dao import SQLDAO
from dao.vector.chroma_db import ChromaDB
from langgraph.graph import StateGraph, END, START
from langchain_ollama import OllamaLLM
from chromadb.utils import embedding_functions
from langchain_core.messages import HumanMessage
from state.rag_reflection_state import RAGReflectionState
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
    @staticmethod
    def _normalize_ollama_model_name(model_name: str, default: str) -> str:
        if not model_name:
            return default
        cleaned = model_name.strip().strip('"').strip("'")
        # Accept values like "ollama:mistral" and pass only "mistral" to Ollama.
        if ":" in cleaned:
            prefix, value = cleaned.split(":", 1)
            if prefix.lower() in {"ollama", "model"}:
                return value
        return cleaned

    def __init__(self):
        self.sql_dao = SQLDAO()

        self.ollama_host = os.getenv('ollama_host')
        self.ollama_port = os.getenv('ollama_port')
        self.ollama_model_name = self._normalize_ollama_model_name(
            os.getenv('ollama_model_name'),
            default='mistral'
        )
        self.ollama_embedding_model_name = self._normalize_ollama_model_name(
            os.getenv('ollama_embedding_model_name'),
            default='nomic-embed-text'
        )

        self.embedding_function = embedding_functions.OllamaEmbeddingFunction(
                model_name=self.ollama_embedding_model_name,
                url=f"http://{self.ollama_host}:{self.ollama_port}/api/embeddings"
            )
        
        self.vector_db = ChromaDB(embedding_func=self.embedding_function)
        self.llm_agent = OllamaLLM(
            model=self.ollama_model_name,
            base_url=f"http://{self.ollama_host}:{self.ollama_port}"
        )
        self.reranker = Reranker(self.llm_agent)
        self.dao_tools = [self.vector_db.as_retriever_tool(), *self.sql_dao.get_sql_tools()]
        self._memory = MemorySaver()
        self._graph = None

    def router_node(self, state : RAGReflectionState) -> RAGReflectionState:
        return run_router_node(self, state)

    def executor_node(self, state: RAGReflectionState) -> RAGReflectionState:
        return run_executor_node(self, state)

    
    def reflect_node(self, state: RAGReflectionState) -> RAGReflectionState:
        return run_reflect_node(self, state)

    def _should_continue_refining(self, state: RAGReflectionState) -> str:
        return should_continue_refining_node(state)

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

    def run_graph(self, question: str, collection_name: str = "", thread_id: str = ""):
        """
        Execute the compiled LangGraph with an input question.
        
        Args:
            question: The user's input question
            
        Returns:
            Final state containing the answer and reflection history
        """
        question = str(question or "").strip()
        print(f"Running RAG Pipeline for question: {question}")

        if should_block_ssn_prompt_input(question):
            print("[SAFETY] Blocked prompt input due to SSN policy.")
            return self._build_policy_block_state(question, reason_code="ssn_prompt_input_blocked")

        resolved_thread_id = str(thread_id or "default_thread").strip()
        config = {"configurable": {"thread_id": resolved_thread_id}}

        graph = self.build_graph()
        
        initial_state: RAGReflectionState = {
            "question": question,
            "collection_name": collection_name,
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
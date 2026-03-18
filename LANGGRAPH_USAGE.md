# LangGraph Workflow Usage Guide

## Overview
The RAG pipeline now uses LangGraph to orchestrate a multi-step workflow with conditional routing for answer refinement.

## Workflow Flow

```
START
  ↓
ROUTER NODE
  • Decomposes user query into atomic sub-queries
  • Uses Few-Shot Learning with golden_sql collection
  • Applies Chain-of-Thought reasoning
  • Creates routes to SQL, Vector, or Schema tools
  ↓
EXECUTOR NODE
  • Executes each route in parallel/sequence
  • Converts outputs to Documents
  • Reranks results using Cohere
  • Compiles results into state.answer
  ↓
REFLECT NODE
  • Evaluates answer quality
  • Increments iteration counter
  • Determines if answer is complete
  ↓
CONDITIONAL LOGIC
  • If answer is complete → END
  • If attempts < 2 → Back to ROUTER (refine)
  • If attempts >= 2 → END (max iterations)
```

## Usage

### Basic Usage

```python
from pipeline.rag_pipeline import Pipeline

# Initialize the pipeline
pipeline = Pipeline()

# Run the graph with a question
question = "How many employees are in the Sales department?"
result = pipeline.run_graph(question)

# Access results
print("Question:", result.question)
print("Answer:", result.answer)
print("Reflection:", result.reflection)
print("Iterations:", result.attempts)
```

### Advanced Usage with Custom Configuration

```python
pipeline = Pipeline()

# Build the graph manually for inspection
graph = pipeline.build_graph()

# View graph structure
print(graph.get_graph().draw_mermaid())

# Run graph on a complex question
question = """
What are the top 3 projects assigned to contract 1 
and what is the company's policy on remote work?
"""
result = pipeline.run_graph(question)

# The graph will:
# 1. Decompose into 2 routes (SQL for projects, Vector for policy)
# 2. Execute both routes
# 3. Rerank and compile results
# 4. Reflect on answer completeness
# 5. If needed, refine with better reasoning
```

## State Management

The workflow uses `RAGReflectionState` which tracks:

```python
class RAGReflectionState:
    question: str                          # Original user question
    routes: List[Dict[str, Any]]          # Decomposed routes from router
    retrieved_docs: List[Document]        # Final reranked documents
    answer: Dict[str, Any]                # Compiled answer with results
    reflection: str                       # LLM's quality evaluation
    revised: bool                         # True if answer needs refinement
    attempts: int                         # Iteration counter (max 2)
```

## Conditional Routing Logic

### `_should_continue_refining()` Method

```python
def _should_continue_refining(self, state: RAGReflectionState) -> str:
    """
    Returns "refine" to loop back to router_node
    Returns "end" to terminate the workflow
    
    Conditions for END:
    - state.revised == False (answer is complete)
    - state.attempts >= 2 (max iterations reached)
    """
```

## Few-Shot Learning Integration

Throughout the workflow, Few-Shot Learning is maintained:

1. **Router Node**: Injects golden SQL examples and CoT reasoning
2. **Executor Node**: Processes routes with Cohere reranker
3. **Reflect Node**: Evaluates answer quality
4. **Loop Back**: Router node uses refined context for better routing

## Example Scenarios

### Scenario 1: Simple Query (Completes in 1 iteration)

```
Question: "List all employees in HR"
  ↓ Router: Simple SQL route
  ↓ Executor: Execute SELECT, get results
  ↓ Reflect: "YES, answer is complete"
  ↓ Conditional: revised=False → END
```

### Scenario 2: Complex Query (Requires 2 iterations)

```
Question: "How many employees are in Sales? What about their locations?"
  ↓ Router: Creates 2 routes (count + geo info)
  ↓ Executor: Execute both routes
  ↓ Reflect: "Partial - missing city breakdown"
  ↓ Conditional: revised=True, attempts=1 → Route back to Router
  ↓ Router: Creates more specific route for location details
  ↓ Executor: Execute enhanced route
  ↓ Reflect: "YES, answer is now complete"
  ↓ Conditional: revised=False → END
```

### Scenario 3: Max Iterations Reached

```
Question: [Complex multi-part question]
  ↓ Router → Executor → Reflect (attempts=1, revised=True)
  ↓ Router → Executor → Reflect (attempts=2, revised=True)
  ↓ Conditional: attempts >= 2 → END (even if revised=True)
```

## Error Handling

The workflow handles errors gracefully:

- **Router Node**: Fallback to keyword-based routing if LLM fails
- **Executor Node**: Catches tool invocation errors, returns empty docs
- **Reflect Node**: Always returns state update even if LLM fails
- **Graph**: Compiles successfully even with partial implementations

## Performance Considerations

1. **Golden SQL Collection**: Cached in-memory after first retrieval
2. **Reranking**: Uses Cohere API (consider rate limits)
3. **Max Iterations**: Hard limit of 2 prevents infinite loops
4. **Document Limit**: Each route processes first N results before reranking

## Monitoring and Debugging

```python
# Check intermediate states
result = pipeline.run_graph(question)

# Analyze routing decisions
for route in result.routes:
    print(f"Sub-query: {route['sub_query']}")
    print(f"Route: {route['route']}")
    print(f"Reason: {route['reason']}")

# Check refinement history
print(f"Reflection iterations: {result.attempts}")
print(f"Final reflection: {result.reflection}")

# Inspect retrieved documents
for doc in result.retrieved_docs:
    print(f"Source: {doc.metadata}")
    print(f"Content: {doc.page_content[:100]}...")
```

## Next Steps

- Implement metrics collection for routing accuracy
- Add caching for frequently asked questions
- Expand golden_sql collection with more patterns
- Integrate with user feedback loop for improvements
- Add visualization of graph execution path

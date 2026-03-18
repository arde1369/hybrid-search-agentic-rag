# Few-Shot Learning Integration Requirement

## Overview
This project implements Few-Shot Learning using a vector database to inject "Golden" SQL examples and Chain-of-Thought (CoT) reasoning to improve logic for complex queries.

## Critical Requirements

### 1. Golden SQL Collection (`golden_sql`)
- **Location**: Vector Database (ChromaDB)
- **Collection Name**: `golden_sql`
- **Purpose**: Store validated example SQL queries for common patterns
- **Retrieval Method**: `Pipeline._retrieve_golden_sql_examples(n_examples=3)`
- **Usage**: Injected into `router_node` prompt to guide SQL generation
- **Requirement**: This collection MUST be maintained and populated with quality examples to ensure Few-Shot Learning effectiveness

### 2. Chain-of-Thought (CoT) Reasoning Collection (`cot_reasoning`)
- **Location**: Vector Database (ChromaDB)
- **Collection Name**: `cot_reasoning`
- **Purpose**: Store multi-step reasoning examples for complex query decomposition
- **Retrieval Method**: `Pipeline._retrieve_golden_reasoning_examples(n_examples=2)`
- **Usage**: Injected into `router_node` prompt to demonstrate reasoning steps
- **Reasoning Steps**:
  1. Identify key entities and relationships in the query
  2. Determine if the query requires structured (SQL) or unstructured (semantic) data
  3. Check if schema context is needed first
  4. Consider if multiple sub-queries are needed
  5. Validate each sub-query can be independently executed

### 3. Integration Points in Code

#### `Pipeline._retrieve_golden_sql_examples()`
```python
def _retrieve_golden_sql_examples(self, n_examples=3):
    """Retrieve golden SQL examples from golden_sql collection"""
```
- **Called by**: `router_node()`
- **Change Impact**: Any modification to query retrieval logic must preserve collection name "golden_sql"

#### `Pipeline._retrieve_golden_reasoning_examples()`
```python
def _retrieve_golden_reasoning_examples(self, n_examples=2):
    """Retrieve reasoning examples from cot_reasoning collection"""
```
- **Called by**: `router_node()`
- **Change Impact**: Any modification to reasoning retrieval must preserve collection name "cot_reasoning"

#### `Pipeline._build_few_shot_prompt_section()`
```python
def _build_few_shot_prompt_section(self, golden_examples, reasoning_examples):
    """Build the few-shot learning section of the routing prompt"""
```
- **Called by**: `router_node()`
- **Change Impact**: This method formats examples for LLM injection; preserve the formatting structure

#### `Pipeline.router_node()`
```python
def router_node(self, state: RAGReflectionState) -> RAGReflectionState:
    """Route queries using Few-Shot Learning and CoT reasoning"""
```
- **Responsibility**: Orchestrate golden example retrieval and injection
- **Chain-of-Thought Integration**: Prompt includes explicit step-by-step reasoning guidance
- **Golden Examples Injection**: Prompt includes formatted golden SQL and reasoning examples
- **Change Impact**: Any router logic modification must maintain the few-shot learning flow

### 4. Data Flow

```
router_node()
    ├── Retrieve golden_sql examples
    ├── Retrieve cot_reasoning examples
    ├── Build few-shot prompt section
    ├── Inject into LLM prompt with CoT guidance
    └── LLM uses examples to improve routing decisions
```

### 5. Vector Database Setup

Before using this feature, ensure your ChromaDB instance has:

```python
# Example: Initialize golden collections
def init_golden_collections():
    vector_db = ChromaDB(embedding_function)
    
    # Golden SQL Examples
    golden_sql_examples = [
        "SELECT * FROM employee WHERE department = 'Sales';",
        "SELECT COUNT(*) FROM projects WHERE contract_id = 1;",
        "SELECT firstname, lastname FROM employee WHERE residency_state = 'California';",
        # Add more validated SQL examples
    ]
    
    vector_db.add_documents_to_collection(
        collection_name="golden_sql",
        documents=golden_sql_examples,
        metadatas=[{"type": "sql_example"} for _ in golden_sql_examples]
    )
    
    # CoT Reasoning Examples
    cot_examples = [
        "Query: Get employees in NY. Step 1: Identify entity (employees, state). Step 2: Determine SQL needed. Step 3: Generate SELECT with WHERE clause.",
        "Query: Get policy info. Step 1: Identify policy topic. Step 2: Determine semantic search needed. Step 3: Query vector database.",
        # Add more reasoning examples
    ]
    
    vector_db.add_documents_to_collection(
        collection_name="cot_reasoning",
        documents=cot_examples,
        metadatas=[{"type": "reasoning_example"} for _ in cot_examples]
    )
```

### 6. Maintenance Checklist

When developing or modifying the codebase:

- [ ] Preserve collection names: `golden_sql` and `cot_reasoning`
- [ ] Maintain the `_retrieve_golden_sql_examples()` method signature
- [ ] Maintain the `_retrieve_golden_reasoning_examples()` method signature
- [ ] Keep CoT reasoning steps in `router_node` prompt
- [ ] Test that examples are properly injected into LLM prompts
- [ ] Monitor LLM routing quality after any vector DB changes
- [ ] Update golden examples as new patterns emerge
- [ ] Document any changes to the few-shot integration

### 7. Troubleshooting

**Issue**: Golden examples not being retrieved
- **Solution**: Check ChromaDB connection and verify collections exist
- **Check**: `vector_db.get_collection("golden_sql")` returns a valid collection

**Issue**: Prompt formatting issues with examples
- **Solution**: Review `_build_few_shot_prompt_section()` output
- **Check**: Ensure no HTML/special character encoding issues

**Issue**: LLM not using examples effectively
- **Solution**: Update golden examples quality or count
- **Check**: If examples are too complex/simple for the model

### 8. Future Enhancements

- Dynamic golden example selection based on query similarity
- Automatic golden example quality scoring
- Integration with retrieval metrics to identify high-quality patterns
- Support for domain-specific collections (e.g., `golden_sql_advanced`, `golden_sql_joins`)
- Caching of frequently used examples for performance optimization

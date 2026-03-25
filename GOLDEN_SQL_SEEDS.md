# Golden SQL Seed Data Loading

## Overview

The `feedback_pairs.csv` file contains a curated set of 88 SQL query examples that serve as training data for the RAG pipeline. These examples are now formatted to match the golden SQL document structure used internally by the application.

## File Format

Each entry in `feedback_pairs.csv` follows this three-line format:

```
User query: [natural language question]
Sub-query: [potentially transformed question]
SQL: [SQL query]
---
```

Entries are separated by `---` on its own line.

## Loading the Seed Data

### Method 1: Run the Seed Loader Script

From the project root, run:

```bash
python load_golden_sql_seeds.py
```

This will:
1. Parse all 88 entries from `feedback_pairs.csv`
2. Deduplicate any identical entries
3. Generate embeddings for each entry using the pipeline's embedding function
4. Insert entries into the `golden_sql_collection` Chroma collection
5. Tag each entry with `source=seed_data` for tracking

### Method 2: Call the Loader Programmatically

In your Python code:

```python
from pipeline.rag_pipeline import create_pipeline
from frontend.services.query_feedback_service import load_golden_sql_seed_data

pipeline = create_pipeline()
loaded_count = load_golden_sql_seed_data(
    pipeline, 
    "sample_docs/feedback_pairs.csv"
)
print(f"Loaded {loaded_count} seed entries")
```

### Method 3: Integrate into Initialization

If you want seed data to load automatically on first run, add this to your initialization logic:

```python
from frontend.services.query_feedback_service import load_golden_sql_seed_data

# In your startup sequence:
seed_file = "sample_docs/feedback_pairs.csv"
if os.path.exists(seed_file):
    load_golden_sql_seed_data(pipeline, seed_file)
```

## Collection Structure

The seed entries are stored in the `golden_sql_collection` (or the collection name specified by the `CHROMA_DB_COLLECTION_GOLDEN_SQL` environment variable) with:

- **Document**: Three-line formatted text (User query, Sub-query, SQL)
- **Metadata**:
  - `user_query`: The original natural language question
  - `sub_query`: The potentially refined question
  - `sql_query`: The generated SQL
  - `feedback`: Always "good" for seed data
  - `source`: "seed_data" (vs "ui_feedback" for user-provided examples)

## Benefits

1. **Few-Shot Learning**: The router uses these examples in prompts for SQL generation
2. **Better SQL Generation**: LLM can see patterns in SQL query structure
3. **Consistent Starting Point**: Every deployment starts with the same reference examples
4. **Trackable Source**: Seed data is marked separately from user feedback for analysis

## Next Steps

- Run the loader script to populate the golden SQL collection
- Verify in your application that SQL generation uses these reference examples
- Add your own domain-specific queries to `feedback_pairs.csv` as needed
- Monitor which seed examples are most useful in your logs

# System Design Document

## 1. Purpose

This document defines the pre-implementation architecture, requirements, and delivery plan for an enterprise question-answering platform that combines structured data retrieval, unstructured knowledge retrieval, and language-model reasoning.

## 2. Product Scope

The product will allow users to:

- Upload enterprise documents into searchable knowledge collections.
- Ask natural-language questions.
- Receive concise, source-aware answers.
- Ask follow-up questions within the same conversational session.

The system will support both:

- Structured retrieval from a relational data source.
- Semantic retrieval from a vector knowledge store.

## 3. Design Objectives

1. Provide accurate answers across both structured and unstructured enterprise domains.
2. Select the best retrieval strategy automatically (structured, semantic, or mixed).
3. Preserve response quality through validation, reranking, and reflection.
4. Enforce safety controls for sensitive identifier handling.
5. Preserve conversational continuity for follow-up questions.
6. Keep deployment cloud-ready and container-compatible.

## 4. Out of Scope

1. Transactional write-back workflows to operational systems.
2. Destructive data operations through user prompts.
3. Full business-process orchestration across external systems.

## 5. High-Level Architecture

### 5.1 Logical Layers

- Experience Layer:
  - Document upload workflow.
  - Query and follow-up interaction workflow.
- Orchestration Layer:
  - Route planning.
  - Multi-step execution.
  - Reflection-driven refinement.
- Retrieval Layer:
  - Relational query execution for structured intents.
  - Vector similarity retrieval for semantic intents.
- Quality Layer:
  - Schema validation.
  - Similarity thresholding.
  - Candidate reranking.
  - Answer summarization and citation formatting.
- Safety Layer:
  - Prompt-level sensitive-input checks.
  - Response-level sensitive-content suppression.
- Data Layer:
  - Relational database.
  - Vector database.

### 5.2 Deployment Components

- Web application service.
- Relational database service.
- Vector database service.
- Model inference service.

### 5.3 Architecture Diagram

```mermaid
flowchart TD
  User --> UI[User Interface]
  UI --> ORCH[Orchestration Engine]

  ORCH --> PLAN[Route Planning]
  PLAN --> EXEC[Execution]
  EXEC --> REFLECT[Reflection]
  REFLECT -->|Refine| PLAN
  REFLECT -->|Complete| ANSWER[Final Answer]

  EXEC --> SQL[(Relational Data Store)]
  EXEC --> VDB[(Vector Data Store)]

  UI --> INGEST[Document Ingestion]
  INGEST --> EMBED[Embedding Generation]
  EMBED --> VDB

  PLAN --> LLM[Language Model]
  REFLECT --> LLM
  ANSWER --> LLM
```

## 6. End-to-End Query Lifecycle

1. User submits a question.
2. System loads session context and conversation thread identity.
3. Planner decomposes question into one or more sub-questions.
4. Each sub-question is assigned a retrieval path.
5. Retrieval executes and returns candidate evidence.
6. Candidate evidence is validated and reranked.
7. Reflection checks completeness and decides whether to refine.
8. Final answer is summarized and returned with source attribution.

## 7. Routing Strategy

### 7.1 Routing Principles

- Prefer structured retrieval when intent maps to known schema entities.
- Prefer semantic retrieval for policy, guideline, and narrative content.
- Use mixed execution when a question spans structured and unstructured domains.

### 7.2 Decomposition Rules

- Split compound questions into atomic sub-questions.
- Keep each sub-question independently answerable.
- Preserve traceability from each sub-question to its evidence.

### 7.3 Fallback Behavior

- If planning output is invalid, apply deterministic fallback routing.
- If structured retrieval is invalid or unsafe, route to semantic retrieval.
- If no reliable route is available, return a bounded safe response.

## 8. Structured Retrieval Design

### 8.1 Validation and Guardrails

- Validate generated queries against live schema metadata.
- Reject unknown tables and unknown columns.
- Apply bounded repair attempts for recoverable issues.
- Reroute to semantic retrieval when structured path remains invalid.

### 8.2 Reliability Controls

- Restrict to non-destructive query intent.
- Record structured route validation outcomes for observability.
- Prevent invalid structured errors from becoming user-visible failures.

## 9. Semantic Retrieval Design

### 9.1 Collection Management

- Segment vector collections by knowledge domain.
- Reserve system collections for planning examples and reasoning aids.
- Exclude reserved collections from user-facing retrieval.

### 9.2 Retrieval Quality

- Normalize distance scores to comparable similarity values.
- Enforce configurable similarity thresholds.
- Reject below-threshold evidence before answer generation.

### 9.3 Multi-Modal Ingestion

- Process PDF documents through a multi-modal path.
- Preserve text and image-derived evidence.
- Store page metadata with human-readable numbering.

## 10. Answer Quality Design

### 10.1 Candidate Ordering

- Apply reranking after retrieval and normalization.
- Keep fallback behavior when reranking service is unavailable.

### 10.2 Final Response Composition

- Select highest-confidence evidence.
- Produce concise summaries, not verbatim chunk dumps.
- Include one citation line with source and page context.

### 10.3 Reflection Loop

- Evaluate completeness after execution.
- Permit bounded refinement iterations.
- Stop when answer is complete or attempt limit is reached.

## 11. Conversation and Session Design

### 11.1 Conversation Memory

- Persist orchestration checkpoints across turns within the same session thread.
- Reuse the same session thread identity for follow-up questions.
- Regenerate session thread identity only on explicit user reset.

### 11.2 Session Controls

- Provide a visible session reset control in the query experience.
- Surface active session identity for troubleshooting continuity.
- Clear session-scoped answer state and feedback state on reset.

## 12. Ingestion and Metadata Design

### 12.1 Supported Inputs

- PDF documents.
- Structured and unstructured word-processing documents.

### 12.2 Ingestion Stages

1. File acceptance and temporary storage.
2. Content extraction and chunking.
3. Metadata enrichment.
4. Embedding generation.
5. Storage of documents, metadata, and vectors.

### 12.3 Metadata Requirements

Minimum metadata should include:

- Source document identifier.
- Page or section reference.
- Chunk index.
- Retrieval scoring fields.

## 13. Safety and Compliance Requirements

### 13.1 Sensitive Identifier Policy

- The system must deny requests for social security numbers.
- The system must deny prompt input containing social security number values.
- The system must return a fixed policy message for denied requests.

### 13.2 False-Positive Reduction

- Response suppression logic should rely on contextual detection, not standalone numeric patterns.
- Metadata scanning should avoid broad dictionary stringification to reduce accidental matches.

## 14. Configuration Requirements

The system should be configurable for:

- Relational service connectivity.
- Vector service connectivity.
- Model selection for generation and embeddings.
- Similarity thresholds.
- Reranking model configuration.
- Parallelism and retry limits.
- Reserved collection names.

## 15. Operational Characteristics

### 15.1 Performance

- Cache expensive planning context where safe.
- Use fast-path routing when schema overlap is clearly absent.
- Limit parallelism to workloads where overhead is justified.

### 15.2 Reliability

- Apply graceful fallback behavior for external model and reranking failures.
- Ensure deterministic behavior under partial dependency failure.
- Minimize user-visible internal errors.

### 15.3 Observability

- Log route decisions and fallback reasons.
- Log validation status and retrieval confidence markers.
- Track session-level continuity indicators for debugging.

## 16. Sequence Diagram

```mermaid
sequenceDiagram
  participant User
  participant UI
  participant Engine
  participant Planner
  participant Executor
  participant SQL
  participant Vector
  participant Model

  User->>UI: Submit question
  UI->>Engine: Send request with session thread identity
  Engine->>Planner: Generate route plan
  Planner->>Model: Reason over intent
  Planner-->>Engine: Route plan

  Engine->>Executor: Execute sub-questions
  alt Structured route
    Executor->>SQL: Execute validated query
  else Semantic route
    Executor->>Vector: Retrieve candidate evidence
  end

  Executor->>Model: Optional reranking and synthesis support
  Executor-->>Engine: Ranked evidence

  Engine->>Model: Reflection check
  Model-->>Engine: Complete or refine

  Engine-->>UI: Final summarized answer + citation
  UI-->>User: Render response
```

## 17. Risks and Mitigations

### 17.1 Retrieval-Route Mismatch

Risk:

- Planner routes to an incorrect retrieval mode.

Mitigations:

- Schema-overlap heuristics.
- Route validation safeguards.
- Deterministic fallback policy.

### 17.2 Follow-Up Context Drift

Risk:

- Follow-up questions lose conversational context.

Mitigations:

- Persistent checkpoint memory keyed by stable session thread identity.
- Explicit reset workflow to bound session lifetime.

### 17.3 Low-Confidence Semantic Responses

Risk:

- Irrelevant chunks produce incorrect answers.

Mitigations:

- Similarity thresholding.
- Reranking.
- Reflection and bounded refinement.

### 17.4 Sensitive Data Leakage

Risk:

- Sensitive identifiers appear in prompt or response.

Mitigations:

- Prompt blocking.
- Response suppression checks.
- Fixed policy response.

## 18. Delivery Plan (Pre-Implementation)

### Phase 1: Core Retrieval Foundation

- Implement relational retrieval with schema validation.
- Implement vector retrieval with similarity scoring.
- Define reserved and user-facing collection strategy.

### Phase 2: Orchestration and Quality Controls

- Implement route planning and decomposition.
- Add reranking and threshold validation.
- Add reflection-driven refinement loop.

### Phase 3: Session and Safety Controls

- Implement conversation checkpointing and session identity control.
- Implement reset behavior and session state management.
- Implement sensitive identifier safeguards.

### Phase 4: UX Hardening and Observability

- Finalize upload and query user workflows.
- Improve source/page citation consistency.
- Add operational logging for routing and fallback analysis.

## 19. Acceptance Criteria

1. Follow-up queries in the same session maintain context continuity.
2. Invalid structured requests do not produce user-visible schema errors.
3. Semantic answers below threshold are suppressed with safe fallback behavior.
4. Final answers are concise and include source citation when evidence exists.
5. Sensitive identifier policy is enforced at prompt and response stages.
6. Reset session action reliably starts a new conversation thread.

def build_final_answer_prompt(question: str, compiled_context: str) -> str:
    return f"""
You are preparing the final user-facing answer from retrieved SQL and vector results.

User question:
{question}

Retrieved results:
{compiled_context}

Instructions:
1. Answer the user's request directly using only the retrieved results above.
2. Preserve requested formatting exactly when possible, including tables, comma-separated lists, counts, or summaries.
3. If the question refers to prior entities like "their" or "those employees", resolve them using the supplied retrieved results and the already-contextualized question.
4. Synthesize the answer directly instead of listing sub-queries unless the user explicitly asked for that.
5. If the results are insufficient, say that briefly and clearly.
6. Do not mention tools, routing, retrieval steps, or internal processing.
7. Do not restate the question.

Return only the final answer text.
"""
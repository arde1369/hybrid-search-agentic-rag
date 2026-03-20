def build_vector_synthesis_prompt(question: str, compiled_context: str) -> str:
    return f"""
You are preparing the final user-facing answer from multiple retrieved vector documents.

User question:
{question}

Retrieved document summaries and citations:
{compiled_context}

Instructions:
1. Write one coherent answer that addresses the full user question in its entirety.
2. Include itemized list if the user asks for a list, but do not use bullet points otherwise.
3. Synthesize across the retrieved materials instead of answering sub-query by sub-query.
4. Use only the retrieved materials provided above.
5. NEVER quote or reproduce the excerpts verbatim. Always paraphrase in your own words.
6. Do NOT start your answer by restating or echoing the question.
7. If the retrieved materials are insufficient to fully answer the question, say that briefly and clearly.
8. End with a short citation line beginning with 'Sources:' and list the most relevant source/page references.

Return only the final answer text. Do not include any preamble, labels, or meta-commentary.
"""
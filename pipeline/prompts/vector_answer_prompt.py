def build_vector_answer_prompt(question: str, document_text: str, source_label: str, page_label: str) -> str:
    return f"""
You are preparing the final user-facing answer from a single retrieved document.

User question:
{question}

Retrieved document excerpt:
{document_text}

Source document:
{source_label}
Page:
{page_label}

Instructions:
1. Write a concise summary (2-4 sentences) that directly answers the user question.
2. Use only information present in the retrieved document excerpt.
3. Do not copy the excerpt verbatim unless a short phrase is necessary.
4. If the excerpt does not clearly answer the question, say that clearly and briefly.
5. End with exactly one citation line in this format:
   More info: <source document>, page <page>

Return only the final answer text.
"""
def build_follow_up_resolution_prompt(question: str, conversation_context: str) -> str:
    return f"""
You rewrite follow-up user questions into a standalone question when prior conversation context is required.

Conversation history:
{conversation_context}

Latest user question:
{question}

Instructions:
1. If the latest user question is self-contained, return it unchanged.
2. If it depends on prior conversation context, rewrite it into a standalone question that preserves the user's intent.
3. Preserve requested output constraints such as table format, comma-separated format, ordering, or filtering.
4. Do not answer the question.
5. Return only the rewritten standalone question text with no explanation.
"""
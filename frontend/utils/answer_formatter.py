import json


def to_display_text(value) -> str:
    if value is None:
        return ""

    if isinstance(value, dict):
        if "content" in value:
            return to_display_text(value.get("content"))
        return str(value).strip()

    content = getattr(value, "content", None)
    if content is not None:
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            return "\n".join(str(item) for item in content).strip()

    return str(value).strip()


def _format_dict_row(data: dict) -> str:
    first = str(data.get("firstname", "")).strip()
    last = str(data.get("lastname", "")).strip()
    email = str(data.get("email", "")).strip()

    if first or last or email:
        full_name = " ".join(part for part in [first, last] if part)
        if full_name and email:
            return f"{full_name} ({email})"
        if full_name:
            return full_name
        return email

    ordered_items = [f"{key}: {value}" for key, value in data.items()]
    return ", ".join(ordered_items)


def _format_doc_content(content: str) -> str:
    text = str(content or "").strip()
    if not text:
        return "(empty)"

    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text

    if isinstance(parsed, dict):
        return _format_dict_row(parsed)

    if isinstance(parsed, list):
        lines = []
        for item in parsed:
            if isinstance(item, dict):
                lines.append(f"- {_format_dict_row(item)}")
            else:
                lines.append(f"- {item}")
        return "\n".join(lines) if lines else "(no items)"

    return str(parsed)


def _clean_reflection(reflection: str) -> str:
    text = to_display_text(reflection)
    if not text:
        return ""
    if text.lower().startswith("reflection:"):
        return text
    return f"Reflection: {text}"


def extract_answer_text(final_state) -> str:
    if final_state is None:
        return "No response returned from the pipeline."

    answer = getattr(final_state, "answer", None)
    reflection = getattr(final_state, "reflection", "")

    if isinstance(final_state, dict):
        answer = final_state.get("answer", answer)
        reflection = final_state.get("reflection", reflection)

    if isinstance(answer, dict):
        policy_message = to_display_text(answer.get("policy_message", ""))
        if policy_message:
            return policy_message

        final_answer = to_display_text(answer.get("final_answer", ""))
        if final_answer:
            return final_answer

        results = answer.get("results", [])
        if results:
            lines = []
            for item in results:
                query = item.get("query", "")
                docs = item.get("documents", [])
                lines.append(f"Sub-query: {query}")
                if docs:
                    lines.append("Documents:")
                    for idx, doc in enumerate(docs, start=1):
                        content = doc.get("page_content", "") if isinstance(doc, dict) else str(doc)
                        formatted = _format_doc_content(content)
                        lines.append(f"{idx}. {formatted}")
                else:
                    lines.append("No documents found.")
                lines.append("")
            if reflection:
                lines.append(_clean_reflection(reflection))
            return "\\n".join(lines).strip()

    return to_display_text(answer if answer is not None else final_state)

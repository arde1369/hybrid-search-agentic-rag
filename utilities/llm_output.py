import os


def _is_openai_provider() -> bool:
    return str(os.getenv("llm_provider", "") or "").strip().lower() == "openai"


def llm_result_to_text(result) -> str:
    if result is None:
        return ""

    if isinstance(result, str):
        return result

    if not _is_openai_provider():
        return str(result)

    if isinstance(result, dict) and "content" in result:
        content_value = result.get("content")
        return llm_result_to_text(content_value)

    content = getattr(result, "content", None)
    if content is not None:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            lines = []
            for item in content:
                if isinstance(item, dict):
                    if "text" in item:
                        lines.append(str(item.get("text", "")))
                    elif "content" in item:
                        lines.append(str(item.get("content", "")))
                    else:
                        lines.append(str(item))
                else:
                    lines.append(str(item))
            return "\n".join(line for line in lines if line).strip()

        return str(content)

    return str(result)
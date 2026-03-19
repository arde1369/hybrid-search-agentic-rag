import re
from typing import Any

POLICY_BLOCK_MESSAGE = "I am unable to provide that information based on company policy"

# Matches common SSN formats such as 123-45-6789, 123 45 6789, or 123456789.
_SSN_VALUE_PATTERN = re.compile(r"\b\d{3}[- ]?\d{2}[- ]?\d{4}\b")
_SSN_KEYWORD_PATTERN = re.compile(r"\b(ssn|social\s+security(?:\s+number)?)\b", re.IGNORECASE)


def contains_ssn_value(text: Any) -> bool:
    return bool(_SSN_VALUE_PATTERN.search(str(text or "")))


def references_ssn(text: Any) -> bool:
    return bool(_SSN_KEYWORD_PATTERN.search(str(text or "")))


def should_block_ssn_prompt_input(text: Any) -> bool:
    candidate = str(text or "")
    return references_ssn(candidate) or contains_ssn_value(candidate)


def redact_ssn_values(text: Any, replacement: str = "[REDACTED_SSN]") -> str:
    return _SSN_VALUE_PATTERN.sub(replacement, str(text or ""))


def _content_contains_ssn(text: Any) -> bool:
    """Return True only when BOTH an SSN keyword and an SSN value appear in the same text.
    Checking for a bare number pattern without context causes false positives on reference
    numbers, phone numbers, page numbers, and other numeric identifiers."""
    candidate = str(text or "")
    return references_ssn(candidate) and contains_ssn_value(candidate)


def answer_results_contain_ssn(results: Any) -> bool:
    if not isinstance(results, list):
        return False

    for item in results:
        if not isinstance(item, dict):
            continue

        if _content_contains_ssn(item.get("query", "")):
            return True

        docs = item.get("documents", [])
        if not isinstance(docs, list):
            continue

        for doc in docs:
            if isinstance(doc, dict):
                if _content_contains_ssn(doc.get("page_content", "")):
                    return True
                # Only check individual string metadata values, never stringify the whole dict,
                # to avoid false positives from page numbers, UUIDs, chunk indexes, etc.
                metadata = doc.get("metadata", {})
                if isinstance(metadata, dict):
                    for v in metadata.values():
                        if isinstance(v, str) and _content_contains_ssn(v):
                            return True
            elif _content_contains_ssn(doc):
                return True

    return False

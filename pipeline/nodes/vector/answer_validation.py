import os

from langchain_classic.schema import Document


NO_INFO_MESSAGE = "I could not find related information"


def _get_similarity_threshold() -> float:
    raw_value = os.getenv("vector_similarity_threshold", "0.5")
    try:
        threshold = float(raw_value)
    except ValueError:
        threshold = 0.5

    if threshold < 0.0:
        return 0.0
    if threshold > 1.0:
        return 1.0
    return threshold


def distance_to_similarity(distance: float) -> float:
    # For cosine distance (0..2 with normalized vectors), map to similarity (1..0).
    # Clamp for robustness when distance is out-of-range.
    similarity = 1.0 - (distance / 2.0)
    if similarity < 0.0:
        return 0.0
    if similarity > 1.0:
        return 1.0
    return similarity


def _extract_similarity_score(document: Document):
    metadata = document.metadata if isinstance(document.metadata, dict) else {}

    # Prefer converting raw distance to normalized similarity when available.
    if "distance" in metadata:
        try:
            return distance_to_similarity(float(metadata["distance"]))
        except (TypeError, ValueError):
            return None

    if "similarity_score" in metadata:
        try:
            similarity = float(metadata["similarity_score"])
            if similarity < 0.0:
                return 0.0
            if similarity > 1.0:
                return 1.0
            return similarity
        except (TypeError, ValueError):
            return None

    return None


def validate_vector_route_documents(route, documents):
    if route.get("route") != "vector":
        return documents

    threshold = _get_similarity_threshold()
    best_score = None

    for document in documents:
        score = _extract_similarity_score(document)
        if score is None:
            continue
        if best_score is None or score > best_score:
            best_score = score

    if best_score is not None and best_score >= threshold:
        return documents

    if not documents:
        print(
            "[VECTOR VALIDATION] No vector documents returned. "
            f"Returning fallback answer. threshold={threshold}"
        )
    else:
        print(
            "[VECTOR VALIDATION] Best similarity score below threshold. "
            f"best_score={best_score}, threshold={threshold}. Returning fallback answer."
        )

    fallback_doc = Document(
        page_content=NO_INFO_MESSAGE,
        metadata={
            "route": "vector",
            "validation": "below_similarity_threshold",
            "best_similarity_score": best_score,
            "similarity_threshold": threshold,
        },
    )
    return [fallback_doc]

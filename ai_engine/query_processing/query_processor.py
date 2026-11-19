"""Conservative query normalization and follow-up resolution."""

import re
from dataclasses import dataclass
from typing import Dict, List, Optional


_CATEGORY_TERMS = {
    "wet waste": ("wet waste", "organic waste", "food waste", "compost"),
    "dry waste": ("dry waste", "recyclable", "paper recycling", "plastic recycling"),
    "sanitary waste": ("sanitary waste", "diaper", "sanitary pad", "hygiene waste"),
    "special-care waste": ("special-care waste", "hazardous waste", "e-waste", "electronic waste", "battery"),
}
_FOLLOW_UP = re.compile(r"\b(it|that|those|them|there|this|these|what about|and then|how about)\b", re.I)


@dataclass(frozen=True)
class ProcessedQuery:
    original_question: str
    retrieval_query: str
    location: Optional[str]
    waste_category: Optional[str]


def process_query(
    question: str,
    *,
    location: Optional[str] = None,
    history: Optional[List[Dict[str, str]]] = None,
) -> ProcessedQuery:
    original = " ".join(question.split())
    if not original:
        raise ValueError("Question must not be blank.")
    category = None
    lowered = original.casefold()
    for canonical, terms in _CATEGORY_TERMS.items():
        if any(term in lowered for term in terms):
            category = canonical
            break

    retrieval_query = original
    previous_question = next(
        (item.get("content", "") for item in reversed(history or []) if item.get("role") == "user"),
        "",
    )
    if previous_question and _FOLLOW_UP.search(original):
        retrieval_query = f"{previous_question} {original}"

    normalized_location = " ".join(location.split()) if location and location.strip() else None
    if category:
        retrieval_query = f"{retrieval_query} {category}"
    if normalized_location:
        retrieval_query = f"{retrieval_query} {normalized_location}"
    return ProcessedQuery(original, retrieval_query, normalized_location, category)

"""Validation for model-generated references to retrieved source chunks."""

import re
from typing import Iterable


_CITATION = re.compile(r"\[(C\d+)\]")


def validate_citations(answer: str, allowed_ids: Iterable[str]) -> bool:
    allowed = set(allowed_ids)
    references = _CITATION.findall(answer)
    if not references or any(reference not in allowed for reference in references):
        return False
    claims = re.split(r"(?<=[.!?])\s+(?!\[C\d+\])|\n+", answer.strip())
    return all(
        not claim.strip() or bool(_CITATION.search(claim))
        for claim in claims
    )

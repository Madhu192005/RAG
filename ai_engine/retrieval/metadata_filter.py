"""Metadata matching and provenance preference for retrieved chunks."""

from datetime import date
from typing import Dict, Optional


_AUTHORITATIVE_NAMES = (
    "cpcb",
    "moefcc",
    "ministry of environment",
    "government of india",
    "tnpcb",
    "tiruchirappalli",
)


def _contains(value: object, expected: Optional[str]) -> bool:
    return expected is None or (
        value is not None and expected.casefold() in str(value).casefold()
    )


def matches_metadata(metadata: Dict[str, object], filters: Optional[Dict[str, object]] = None) -> bool:
    filters = filters or {}
    status = str(metadata.get("status", "unknown")).casefold()
    if status in {"superseded", "inactive"}:
        return False
    requested_location = filters.get("location")
    if requested_location:
        location_fields = " ".join(
            str(metadata.get(key) or "")
            for key in ("jurisdiction", "state", "municipality", "location")
        )
        if str(requested_location).casefold() not in location_fields.casefold():
            return False
    exact_fields = {
        "source_authority": "source_authority",
        "waste_category": "waste_category",
        "jurisdiction": "jurisdiction",
        "state": "state",
        "municipality": "municipality",
        "document_version_id": "document_version_id",
        "status": "status",
    }
    for filter_name, metadata_name in exact_fields.items():
        expected = filters.get(filter_name)
        if expected is not None and not _contains(metadata.get(metadata_name), str(expected)):
            return False

    publication_before = filters.get("publication_before")
    if publication_before:
        published = metadata.get("publication_date")
        if not published:
            return False
        try:
            if date.fromisoformat(str(published)) > date.fromisoformat(str(publication_before)):
                return False
        except ValueError:
            return False

    effective_on = filters.get("effective_on")
    if effective_on:
        effective = metadata.get("effective_date")
        if not effective:
            return False
        try:
            if date.fromisoformat(str(effective)) > date.fromisoformat(str(effective_on)):
                return False
        except ValueError:
            return False
    return True


def provenance_preference(metadata: Dict[str, object], location: Optional[str] = None) -> float:
    authority = str(metadata.get("source_authority") or "").casefold()
    status = str(metadata.get("status", "unknown")).casefold()
    score = 0.15 if status == "current" else 0.0
    if any(name in authority for name in _AUTHORITATIVE_NAMES):
        score += 0.1
    if location:
        local_fields = " ".join(
            str(metadata.get(key) or "")
            for key in ("jurisdiction", "state", "municipality")
        ).casefold()
        if location.casefold() in local_fields:
            score += 0.12
        elif "national" in local_fields or "india" in local_fields:
            score += 0.02
    return score


def has_applicable_local_source(results, location: Optional[str]) -> bool:
    if not location:
        return True
    needle = location.casefold()
    return any(
        needle in " ".join(
            str(result.get("metadata", {}).get(key) or "")
            for key in ("jurisdiction", "state", "municipality")
        ).casefold()
        for result in results
    )

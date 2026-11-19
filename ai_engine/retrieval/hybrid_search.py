"""Reciprocal Rank Fusion for semantic and BM25 candidates."""

from typing import Dict, List, Optional

from ai_engine.retrieval.metadata_filter import provenance_preference


def reciprocal_rank_fusion(
    semantic_results: List[Dict[str, object]],
    keyword_results: List[Dict[str, object]],
    *,
    k: int = 60,
    top_k: int = 12,
    location: Optional[str] = None,
) -> List[Dict[str, object]]:
    if k < 1 or top_k < 1:
        raise ValueError("RRF k and top_k must be positive.")
    merged: Dict[str, Dict[str, object]] = {}
    for source_name, results in (("semantic", semantic_results), ("keyword", keyword_results)):
        for rank, result in enumerate(results, start=1):
            chunk_id = str(result["chunk_id"])
            candidate = merged.setdefault(chunk_id, dict(result))
            candidate[f"{source_name}_rank"] = rank
            candidate["rrf_score"] = float(candidate.get("rrf_score", 0.0)) + 1.0 / (k + rank)
            if source_name == "keyword" and candidate.get("semantic_score") is None:
                candidate["semantic_score"] = result.get("score")

    for candidate in merged.values():
        candidate["hybrid_score"] = float(candidate["rrf_score"]) + provenance_preference(
            candidate["metadata"], location
        )
    return sorted(
        merged.values(),
        key=lambda item: (float(item["hybrid_score"]), float(item.get("rrf_score", 0))),
        reverse=True,
    )[:top_k]

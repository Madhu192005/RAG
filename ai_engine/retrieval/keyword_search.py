"""BM25 lexical retrieval over the chunks persisted alongside the FAISS index."""

import re
from typing import Dict, List, Optional

from ai_engine.ingestion.vector_index import FaissVectorIndex
from ai_engine.retrieval.metadata_filter import matches_metadata


_TOKEN = re.compile(r"\w+", re.UNICODE)
_EXPANSIONS = {
    "wet waste": ("organic", "biodegradable", "food", "compost"),
    "dry waste": ("recyclable", "paper", "plastic", "glass", "metal"),
    "sanitary waste": ("diaper", "hygiene", "sanitary pad", "personal care"),
    "special-care waste": ("hazardous", "e-waste", "electronic", "battery", "chemical"),
    "battery": ("battery disposal", "lithium", "e-waste"),
}


def tokenize(text: str) -> List[str]:
    return _TOKEN.findall(text.casefold())


def expand_query(query: str) -> str:
    lowered = query.casefold()
    additions = [term for keyword, terms in _EXPANSIONS.items() if keyword in lowered for term in terms]
    return " ".join([query] + additions)


class BM25KeywordSearch:
    def __init__(self, index: FaissVectorIndex):
        try:
            from rank_bm25 import BM25Okapi
        except ImportError as exc:
            raise RuntimeError("Keyword retrieval requires rank-bm25; install backend/requirements.txt.") from exc
        self._records = index.all_chunks()
        self._tokenized = [tokenize(str(record.get("text", ""))) for record in self._records]
        self._bm25 = BM25Okapi(self._tokenized) if self._tokenized else None

    def search(
        self,
        query: str,
        *,
        top_k: int = 20,
        filters: Optional[Dict[str, object]] = None,
    ) -> List[Dict[str, object]]:
        if self._bm25 is None:
            return []
        query_tokens = tokenize(expand_query(query))
        scores = self._bm25.get_scores(query_tokens)
        results = []
        for record, score in zip(self._records, scores):
            if score <= 0 or not matches_metadata(record["metadata"], filters):
                continue
            result = dict(record)
            result["keyword_score"] = float(score)
            results.append(result)
        return sorted(results, key=lambda item: item["keyword_score"], reverse=True)[:top_k]

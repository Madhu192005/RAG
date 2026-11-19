"""Step 6-compatible retrieval boundaries; generation is intentionally absent."""

from typing import Dict, List, Optional, Protocol

import numpy as np

from ai_engine.ingestion.embedding_generator import EmbeddingGenerator
from ai_engine.ingestion.vector_index import FaissVectorIndex


class BM25Retriever(Protocol):
    def search(self, query: str, limit: int = 5) -> List[Dict[str, object]]:
        """Search a lexical index."""


class Reranker(Protocol):
    def rerank(self, query: str, results: List[Dict[str, object]]) -> List[Dict[str, object]]:
        """Reorder candidate documents."""


class DocumentRetriever:
    def __init__(self, vector_index: FaissVectorIndex, embeddings: EmbeddingGenerator):
        self.vector_index = vector_index
        self.embeddings = embeddings

    def search(
        self,
        query: str,
        *,
        limit: int = 5,
        filters: Optional[Dict[str, object]] = None,
    ) -> List[Dict[str, object]]:
        if not query.strip():
            raise ValueError("Query cannot be empty.")
        query_vector = self.embeddings.encode([query])[0]
        results = self.vector_index.search(query_vector, limit=max(limit, 1))
        if filters:
            results = [
                result
                for result in results
                if all(result["metadata"].get(key) == value for key, value in filters.items())
            ]
        return results[:limit]


def format_source_citation(result: Dict[str, object]) -> str:
    metadata = result["metadata"]
    title = metadata.get("document_title") or metadata.get("title") or "Untitled source"
    pages = metadata.get("page_start")
    page_end = metadata.get("page_end")
    page_reference = f", pp. {pages}" if pages == page_end else f", pp. {pages}-{page_end}" if pages else ""
    authority = metadata.get("source_authority")
    prefix = f"{authority}: " if authority else ""
    return f"{prefix}{title}{page_reference}"

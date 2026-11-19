"""FAISS-backed semantic retrieval."""

from typing import Dict, List, Optional

from ai_engine.ingestion.embedding_generator import EmbeddingGenerator
from ai_engine.ingestion.vector_index import FaissVectorIndex
from ai_engine.retrieval.metadata_filter import matches_metadata


class SemanticSearch:
    def __init__(self, index: FaissVectorIndex, embeddings: EmbeddingGenerator):
        self.index = index
        self.embeddings = embeddings

    def search(
        self,
        query: str,
        *,
        top_k: int = 20,
        filters: Optional[Dict[str, object]] = None,
    ) -> List[Dict[str, object]]:
        if self.index.count == 0:
            return []
        vector = self.embeddings.encode([query])[0]
        candidates = self.index.search(vector, limit=min(self.index.count, max(top_k * 4, top_k)))
        filtered = [
            item for item in candidates if matches_metadata(item["metadata"], filters)
        ]
        return filtered[:top_k]

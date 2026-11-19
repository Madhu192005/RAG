"""Persistent FAISS cosine-style index plus an explicit chunk metadata map."""

import json
import os
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from ai_engine.ingestion.chunker import DocumentChunk


class VectorIndexError(RuntimeError):
    """Raised when an index is missing, corrupt, or inconsistent."""


class FaissVectorIndex:
    def __init__(self, directory: Path, model_name: str):
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self.index_path = directory / "index.faiss"
        self.metadata_path = directory / "index_metadata.json"
        self.model_name = model_name
        self._index = None
        self._metadata: Dict[str, Dict[str, object]] = {}
        self._faiss = None

    def _load_faiss(self):
        if self._faiss is None:
            try:
                import faiss
            except ImportError as exc:
                raise RuntimeError("FAISS indexing requires faiss-cpu; install backend/requirements.txt.") from exc
            self._faiss = faiss
        return self._faiss

    def _new_index(self, dimension: int):
        faiss = self._load_faiss()
        return faiss.IndexIDMap2(faiss.IndexFlatIP(dimension))

    @property
    def count(self) -> int:
        return int(self._index.ntotal) if self._index is not None else 0

    def all_chunks(self) -> List[Dict[str, object]]:
        """Return persisted chunk records for lexical retrieval."""
        return [
            {
                "chunk_id": item["chunk_id"],
                "text": item["text"],
                "metadata": item["metadata"],
                "vector_id": int(vector_id),
            }
            for vector_id, item in self._metadata.items()
        ]

    def load(self) -> None:
        if not self.index_path.exists() and not self.metadata_path.exists():
            return
        if not self.index_path.exists() or not self.metadata_path.exists():
            raise VectorIndexError("FAISS index and metadata must both exist.")
        faiss = self._load_faiss()
        try:
            with self.metadata_path.open("r", encoding="utf-8") as source:
                payload = json.load(source)
            index = faiss.read_index(str(self.index_path))
        except Exception as exc:
            raise VectorIndexError(f"Unable to load persisted FAISS data: {exc}") from exc
        if payload.get("embedding_model") != self.model_name:
            raise VectorIndexError(
                f"Index uses model {payload.get('embedding_model')!r}, not configured model {self.model_name!r}."
            )
        metadata = payload.get("vectors")
        if not isinstance(metadata, dict):
            raise VectorIndexError("FAISS metadata mapping is malformed.")
        chunk_ids = []
        for item in metadata.values():
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("chunk_id"), str)
                or not isinstance(item.get("text"), str)
                or not isinstance(item.get("metadata"), dict)
            ):
                raise VectorIndexError("FAISS chunk metadata entry is malformed.")
            chunk_ids.append(item["chunk_id"])
        if len(set(chunk_ids)) != len(chunk_ids):
            raise VectorIndexError("FAISS metadata contains duplicate chunk IDs.")
        vector_ids = {str(int(value)) for value in faiss.vector_to_array(index.id_map)}
        if vector_ids != set(metadata) or int(index.ntotal) != len(metadata):
            raise VectorIndexError("FAISS vector IDs do not match the persisted metadata mapping.")
        self._index = index
        self._metadata = metadata

    def add(
        self,
        chunks: List[DocumentChunk],
        embeddings: np.ndarray,
        vector_ids: Optional[List[int]] = None,
    ) -> List[int]:
        vectors = np.asarray(embeddings, dtype=np.float32)
        if vectors.ndim != 2 or vectors.shape[0] != len(chunks):
            raise ValueError("Embedding count must match chunk count.")
        if not chunks:
            return []
        norms = np.linalg.norm(vectors, axis=1)
        if np.any(~np.isfinite(vectors)) or np.any(norms == 0):
            raise ValueError("Embeddings must be finite and non-zero.")
        vectors = vectors / norms[:, None]
        if self._index is None:
            self._index = self._new_index(vectors.shape[1])
        elif self._index.d != vectors.shape[1]:
            raise ValueError("Embedding dimension does not match the existing FAISS index.")

        used_ids = {int(vector_id) for vector_id in self._metadata}
        existing_chunk_ids = {str(item["chunk_id"]) for item in self._metadata.values()}
        requested_chunk_ids = [chunk.chunk_id for chunk in chunks]
        if len(set(requested_chunk_ids)) != len(requested_chunk_ids) or existing_chunk_ids.intersection(requested_chunk_ids):
            raise ValueError("Chunk IDs must be unique within the index.")
        if vector_ids is None:
            start = max(used_ids, default=0) + 1
            ids = np.arange(start, start + len(chunks), dtype=np.int64)
        else:
            if len(vector_ids) != len(chunks):
                raise ValueError("Vector ID count must match chunk count.")
            if (
                len(set(vector_ids)) != len(vector_ids)
                or used_ids.intersection(vector_ids)
                or any(vector_id < 1 for vector_id in vector_ids)
            ):
                raise ValueError("Vector IDs must be positive and unique within the index.")
            ids = np.asarray(vector_ids, dtype=np.int64)
        self._index.add_with_ids(vectors, ids)
        for vector_id, chunk in zip(ids, chunks):
            self._metadata[str(int(vector_id))] = {
                "chunk_id": chunk.chunk_id,
                "text": chunk.text,
                "metadata": chunk.metadata,
                "token_count": chunk.token_count,
            }
        return [int(vector_id) for vector_id in ids]

    def remove(self, vector_ids: List[int]) -> None:
        if not vector_ids or self._index is None:
            return
        ids = np.asarray(vector_ids, dtype=np.int64)
        self._index.remove_ids(ids)
        for vector_id in vector_ids:
            self._metadata.pop(str(vector_id), None)

    def search(self, query_embedding: np.ndarray, limit: int = 5) -> List[Dict[str, object]]:
        if limit < 1:
            raise ValueError("limit must be positive.")
        if self._index is None or self.count == 0:
            return []
        query = np.asarray(query_embedding, dtype=np.float32).reshape(1, -1)
        if query.shape[1] != self._index.d:
            raise ValueError("Query embedding dimension does not match the index.")
        norm = np.linalg.norm(query)
        if not np.isfinite(norm) or norm == 0:
            raise ValueError("Query embedding must be finite and non-zero.")
        scores, ids = self._index.search(query / norm, min(limit, self.count))
        results = []
        for score, vector_id in zip(scores[0], ids[0]):
            if vector_id < 0:
                continue
            result = dict(self._metadata[str(int(vector_id))])
            result["score"] = float(score)
            result["vector_id"] = int(vector_id)
            results.append(result)
        return results

    def save(self) -> None:
        if self._index is None:
            return
        faiss = self._load_faiss()
        index_tmp = None
        metadata_tmp = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.directory, suffix=".faiss", delete=False) as file:
                index_tmp = file.name
            faiss.write_index(self._index, index_tmp)
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.directory, suffix=".json", delete=False
            ) as file:
                metadata_tmp = file.name
                json.dump(
                    {"embedding_model": self.model_name, "vectors": self._metadata},
                    file,
                    ensure_ascii=False,
                    indent=2,
                )
                file.write("\n")
            os.replace(index_tmp, self.index_path)
            index_tmp = None
            os.replace(metadata_tmp, self.metadata_path)
            metadata_tmp = None
        finally:
            for temporary in (index_tmp, metadata_tmp):
                if temporary and os.path.exists(temporary):
                    os.unlink(temporary)

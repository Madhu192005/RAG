"""Multilingual Sentence Transformers embedding adapter."""

from typing import List, Optional

import numpy as np


DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


class EmbeddingGenerator:
    def __init__(self, model_name: str = DEFAULT_MODEL, device: Optional[str] = None):
        self.model_name = model_name
        self.device = device
        self._model = None
        self._package_version = None

    def _load_model(self):
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "Embedding generation requires sentence-transformers; install backend/requirements.txt."
            ) from exc
        try:
            self._model = SentenceTransformer(self.model_name, device=self.device)
        except Exception as exc:
            raise RuntimeError(f"Unable to load embedding model '{self.model_name}': {exc}") from exc
        return self._model

    @property
    def dimension(self) -> int:
        model = self._load_model()
        dimension_getter = getattr(model, "get_embedding_dimension", None)
        if dimension_getter is None:
            dimension_getter = model.get_sentence_embedding_dimension
        return int(dimension_getter())

    @property
    def version(self) -> str:
        self._load_model()
        if self._package_version is None:
            import sentence_transformers

            self._package_version = str(sentence_transformers.__version__)
        return self._package_version

    def encode(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        if not texts:
            return np.empty((0, self.dimension), dtype=np.float32)
        vectors = self._load_model().encode(
            texts,
            batch_size=batch_size,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        result = np.asarray(vectors, dtype=np.float32)
        if result.ndim != 2 or result.shape[0] != len(texts):
            raise ValueError("Embedding model returned an invalid vector shape.")
        return result

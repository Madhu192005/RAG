"""Lazy-loaded Cross-Encoder reranker."""

from typing import Dict, List


class RerankerUnavailable(RuntimeError):
    """Raised when the configured Cross-Encoder cannot be loaded or used."""


class CrossEncoderReranker:
    def __init__(self, model_name: str, device: str = "cpu"):
        self.model_name = model_name
        self.device = device
        self._model = None

    def _load_model(self):
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self.model_name, device=self.device)
        except Exception as exc:
            raise RerankerUnavailable(f"Unable to load Cross-Encoder '{self.model_name}'.") from exc
        return self._model

    def rerank(
        self,
        query: str,
        results: List[Dict[str, object]],
        *,
        top_k: int = 5,
    ) -> List[Dict[str, object]]:
        if not results:
            return []
        try:
            model = self._load_model()
            pairs = [(query, str(item["text"])) for item in results]
            scores = model.predict(pairs, show_progress_bar=False)
        except Exception as exc:
            raise RerankerUnavailable("Cross-Encoder scoring failed.") from exc
        ranked = []
        for result, score in zip(results, scores):
            item = dict(result)
            item["rerank_score"] = float(score)
            ranked.append(item)
        return sorted(ranked, key=lambda item: item["rerank_score"], reverse=True)[:top_k]

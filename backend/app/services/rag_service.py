"""Grounded hybrid retrieval and answer orchestration."""

import logging
from pathlib import Path
from typing import Dict, List, Optional

from ai_engine.generation.citation_validator import validate_citations
from ai_engine.generation.groq_generator import (
    INSUFFICIENT_EVIDENCE_ANSWER,
    GenerationUnavailable,
    GroqAnswerGenerator,
)
from ai_engine.ingestion.embedding_generator import EmbeddingGenerator
from ai_engine.ingestion.vector_index import FaissVectorIndex, VectorIndexError
from ai_engine.query_processing.query_processor import process_query
from ai_engine.retrieval.hybrid_search import reciprocal_rank_fusion
from ai_engine.retrieval.keyword_search import BM25KeywordSearch
from ai_engine.retrieval.metadata_filter import has_applicable_local_source
from ai_engine.retrieval.reranker import CrossEncoderReranker, RerankerUnavailable
from ai_engine.retrieval.semantic_search import SemanticSearch
from app.core.config import settings
from app.schemas.assistant import (
    AssistantChatRequest,
    AssistantChatResponse,
    AssistantSource,
)

logger = logging.getLogger("wastewise_ai.rag")


class RAGServiceUnavailable(RuntimeError):
    """Raised when the configured retrieval or generation service is unavailable."""


class GroundedRAGService:
    def __init__(
        self,
        *,
        index: Optional[FaissVectorIndex] = None,
        embeddings: Optional[EmbeddingGenerator] = None,
        reranker=None,
        generator=None,
    ):
        project_root = Path(__file__).resolve().parents[3]
        index_directory = Path(settings.RAG_INDEX_DIRECTORY) if settings.RAG_INDEX_DIRECTORY else (
            project_root / "vector_store" / "faiss_index"
        )
        self.index = index or FaissVectorIndex(index_directory, settings.RAG_EMBEDDING_MODEL)
        self.embeddings = embeddings
        self.reranker = reranker
        self.generator = generator
        self._loaded = False
        self._keyword_search = None

    def _load_index(self) -> None:
        if self._loaded:
            return
        try:
            self.index.load()
        except VectorIndexError as exc:
            raise RAGServiceUnavailable("The knowledge-base index is invalid or unavailable.") from exc
        self._loaded = True

    def _get_generator(self):
        if self.generator is not None:
            return self.generator
        if not settings.GROQ_API_KEY or not settings.GROQ_MODEL:
            raise GenerationUnavailable(
                "Grounded answer generation is not configured. Set GROQ_API_KEY and GROQ_MODEL."
            )
        self.generator = GroqAnswerGenerator(
            settings.GROQ_API_KEY,
            settings.GROQ_MODEL,
            settings.RAG_GROQ_TIMEOUT_SECONDS,
        )
        return self.generator

    @staticmethod
    def _history_for_retrieval(history: Optional[List[Dict[str, str]]]):
        return history or []

    def _retrieve(
        self,
        retrieval_query: str,
        *,
        filters: Dict[str, object],
        location: Optional[str],
    ):
        self._load_index()
        if self.index.count == 0:
            return [], None
        if self.embeddings is None:
            self.embeddings = EmbeddingGenerator(settings.RAG_EMBEDDING_MODEL)
        semantic = SemanticSearch(self.index, self.embeddings).search(
            retrieval_query,
            top_k=settings.RAG_SEMANTIC_TOP_K,
            filters=filters,
        )
        if self._keyword_search is None:
            self._keyword_search = BM25KeywordSearch(self.index)
        keyword = self._keyword_search.search(
            retrieval_query,
            top_k=settings.RAG_KEYWORD_TOP_K,
            filters=filters,
        )
        fused = reciprocal_rank_fusion(
            semantic,
            keyword,
            k=settings.RAG_RRF_K,
            top_k=settings.RAG_HYBRID_TOP_K,
            location=location,
        )
        return fused, len(semantic) + len(keyword)

    @staticmethod
    def _prepare_evidence(results, max_chars: int):
        evidence = []
        used_chars = 0
        for result in results:
            metadata = result["metadata"]
            if not all(
                metadata.get(key)
                for key in ("document_id", "document_version_id", "document_title")
            ):
                continue
            text = str(result["text"])
            remaining = max_chars - used_chars
            if remaining <= 0:
                break
            excerpt = text[:remaining].strip()
            if not excerpt:
                continue
            citation_id = f"C{len(evidence) + 1}"
            evidence.append(
                {
                    "citation_id": citation_id,
                    "chunk_id": str(result["chunk_id"]),
                    "text": excerpt,
                    "metadata": metadata,
                    "rerank_score": result.get("rerank_score"),
                    "hybrid_score": result.get("hybrid_score"),
                }
            )
            used_chars += len(excerpt)
        return evidence

    @staticmethod
    def _source(item) -> AssistantSource:
        metadata = item["metadata"]
        title = metadata.get("document_title") or metadata.get("title") or "Untitled source"
        page_start = metadata.get("page_start")
        page_end = metadata.get("page_end")
        source_url = metadata.get("source_url") or metadata.get("url")
        if not isinstance(source_url, str) or not source_url.startswith(("https://", "http://")):
            source_url = None
        return AssistantSource(
            title=str(title),
            source_authority=metadata.get("source_authority"),
            url=source_url,
            snippet=item["text"],
            document_id=str(metadata.get("document_id") or "unknown"),
            document_version_id=metadata.get("document_version_id"),
            chunk_id=item["chunk_id"],
            page_number=page_start if page_start == page_end else None,
            page_start=page_start,
            page_end=page_end,
            citation_id=item["citation_id"],
        )

    def answer(
        self,
        request: AssistantChatRequest,
        *,
        history: Optional[List[Dict[str, str]]] = None,
        session_id: Optional[str] = None,
    ) -> AssistantChatResponse:
        processed = process_query(
            request.question,
            location=request.location,
            history=self._history_for_retrieval(history),
        )
        filters = request.metadata_filters.model_dump(exclude_none=True) if request.metadata_filters else {}
        try:
            candidates, candidate_count = self._retrieve(
                processed.retrieval_query,
                filters=filters,
                location=processed.location,
            )
        except RAGServiceUnavailable:
            raise
        except RuntimeError as exc:
            raise RAGServiceUnavailable("Knowledge-base retrieval is temporarily unavailable.") from exc

        if not candidates:
            return self._insufficient_response(request.question, session_id)

        warnings = []
        rerank_score = None
        if self.reranker is None:
            self.reranker = CrossEncoderReranker(settings.RAG_RERANKER_MODEL)
        try:
            ranked = self.reranker.rerank(
                processed.retrieval_query,
                candidates,
                top_k=settings.RAG_FINAL_TOP_K,
            )
        except RerankerUnavailable:
            logger.warning("Cross-Encoder unavailable; using fused retrieval ranking.")
            ranked = candidates[:settings.RAG_FINAL_TOP_K]
            warnings.append("Reranking was unavailable; results use hybrid retrieval ranking.")

        if not ranked:
            return self._insufficient_response(request.question, session_id)
        rerank_score = ranked[0].get("rerank_score")
        if rerank_score is not None and float(rerank_score) < settings.RAG_MIN_RERANK_SCORE:
            return self._insufficient_response(request.question, session_id)

        evidence = self._prepare_evidence(ranked, settings.RAG_CONTEXT_MAX_CHARS)
        if not evidence:
            return self._insufficient_response(
                request.question,
                session_id,
                warning="Retrieved passages did not include complete source provenance.",
            )
        try:
            answer = self._get_generator().generate(processed.retrieval_query, evidence)
        except GenerationUnavailable:
            raise

        source_ids = [item["citation_id"] for item in evidence]
        if not validate_citations(answer, source_ids):
            logger.warning("Discarded assistant response with invalid or uncited claims.")
            return self._insufficient_response(
                request.question,
                session_id,
                warning="The generated response did not pass source-citation validation.",
            )

        if not has_applicable_local_source(ranked, processed.location):
            warnings.append(
                "No source specific to the requested location was found; local rules may differ."
            )
        unknown_status = any(
            str(item["metadata"].get("status", "unknown")).casefold() == "unknown"
            for item in evidence
        )
        if unknown_status:
            warnings.append("Some cited documents have unverified current-status metadata.")

        confidence = "Moderate evidence"
        if (
            rerank_score is not None
            and float(rerank_score) >= settings.RAG_HIGH_RERANK_SCORE
            and not unknown_status
            and has_applicable_local_source(ranked, processed.location)
        ):
            confidence = "High evidence"
        return AssistantChatResponse(
            answer=answer,
            question=request.question,
            confidence=confidence,
            sources=[self._source(item) for item in evidence],
            warnings=warnings,
            warning=warnings[0] if warnings else None,
            status="success",
            retrieval_metadata={
                "semantic_and_keyword_candidates": candidate_count,
                "sources_used": len(evidence),
                "reranked": rerank_score is not None,
            },
            session_id=session_id,
        )

    @staticmethod
    def _insufficient_response(question, session_id, warning=None):
        warnings = [warning] if warning else []
        return AssistantChatResponse(
            answer=INSUFFICIENT_EVIDENCE_ANSWER,
            question=question,
            confidence="Insufficient evidence",
            sources=[],
            warnings=warnings,
            warning=warning,
            status="insufficient_evidence",
            retrieval_metadata={"semantic_and_keyword_candidates": 0, "sources_used": 0},
            session_id=session_id,
        )

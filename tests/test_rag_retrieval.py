from ai_engine.generation.citation_validator import validate_citations
from ai_engine.generation.groq_generator import (
    INSUFFICIENT_EVIDENCE_ANSWER,
    GroqAnswerGenerator,
)
from ai_engine.query_processing.query_processor import process_query
from ai_engine.retrieval.hybrid_search import reciprocal_rank_fusion
from ai_engine.retrieval.metadata_filter import matches_metadata
from app.schemas.assistant import AssistantChatRequest
from app.services.rag_service import GroundedRAGService


def _chunk(chunk_id, *, status="current", authority="CPCB"):
    return {
        "chunk_id": chunk_id,
        "text": f"Evidence for {chunk_id}.",
        "metadata": {
            "document_id": f"doc-{chunk_id}",
            "document_title": "Waste guidance",
            "source_authority": authority,
            "status": status,
        },
    }


def test_query_processor_resolves_followup_and_extracts_category_location():
    query = process_query(
        "What about composting it?",
        location="Chennai",
        history=[{"role": "user", "content": "How should I separate wet waste?"}],
    )
    assert "separate wet waste" in query.retrieval_query
    assert "Chennai" in query.retrieval_query
    assert query.waste_category == "wet waste"


def test_metadata_filter_excludes_superseded_and_honors_requested_version():
    assert not matches_metadata({"status": "superseded"})
    assert matches_metadata(
        {"status": "current", "document_version_id": "version-1"},
        {"document_version_id": "version-1"},
    )
    assert not matches_metadata(
        {"status": "current", "document_version_id": "version-2"},
        {"document_version_id": "version-1"},
    )


def test_reciprocal_rank_fusion_deduplicates_and_prefers_shared_evidence():
    semantic = [_chunk("shared"), _chunk("semantic-only", authority="unknown")]
    lexical = [_chunk("shared"), _chunk("lexical-only")]
    results = reciprocal_rank_fusion(semantic, lexical, k=60, top_k=5)
    assert len(results) == 3
    assert results[0]["chunk_id"] == "shared"
    assert results[0]["semantic_rank"] == 1
    assert results[0]["keyword_rank"] == 1


def test_citation_validator_requires_known_citations_on_each_claim():
    assert validate_citations("Sort organics separately. [C1]", ["C1"])
    assert not validate_citations("Sort organics separately. [C2]", ["C1"])
    assert not validate_citations("Sort organics separately.", ["C1"])
    assert not validate_citations("Sort organics. [C1]\nDo not guess.", ["C1"])


def test_empty_index_returns_fallback_without_loading_generator():
    class EmptyIndex:
        count = 0

        def load(self):
            pass

    class ForbiddenGenerator:
        def generate(self, *_args):
            raise AssertionError("Generation must not run without retrieved evidence.")

    service = GroundedRAGService(index=EmptyIndex(), generator=ForbiddenGenerator())
    response = service.answer(AssistantChatRequest(question="How should I sort batteries?"))

    assert response.answer == INSUFFICIENT_EVIDENCE_ANSWER
    assert response.sources == []
    assert response.status == "insufficient_evidence"


def test_rag_answer_requires_provenance_and_valid_citations():
    class EmptyIndex:
        count = 1

        def load(self):
            pass

    class Reranker:
        def rerank(self, _query, results, **_kwargs):
            return [{**results[0], "rerank_score": 1.0}]

    class Generator:
        def generate(self, _question, evidence):
            assert evidence[0]["citation_id"] == "C1"
            return "Follow the local sorting guidance. [C1]"

    service = GroundedRAGService(
        index=EmptyIndex(),
        reranker=Reranker(),
        generator=Generator(),
    )
    service._retrieve = lambda *_args, **_kwargs: (
        [
            {
                **_chunk("grounded"),
                "metadata": {
                    "document_id": "doc-grounded",
                    "document_version_id": "version-grounded",
                    "document_title": "Local Waste Guidance",
                    "jurisdiction": "Chennai",
                    "status": "current",
                },
                "hybrid_score": 0.1,
            }
        ],
        2,
    )
    response = service.answer(
        AssistantChatRequest(question="How should I sort this?", location="Chennai")
    )

    assert response.status == "success"
    assert response.confidence == "Moderate evidence"
    assert response.sources[0].document_version_id == "version-grounded"
    assert response.sources[0].citation_id == "C1"


def test_rag_discards_answer_without_valid_citations():
    class EmptyIndex:
        count = 1

        def load(self):
            pass

    class Reranker:
        def rerank(self, _query, results, **_kwargs):
            return [{**results[0], "rerank_score": 1.0}]

    class Generator:
        def generate(self, _question, _evidence):
            return "Sort batteries separately."

    service = GroundedRAGService(
        index=EmptyIndex(),
        reranker=Reranker(),
        generator=Generator(),
    )
    service._retrieve = lambda *_args, **_kwargs: (
        [
            {
                **_chunk("uncited"),
                "metadata": {
                    "document_id": "doc-uncited",
                    "document_version_id": "version-uncited",
                    "document_title": "Verified source",
                    "status": "current",
                },
            }
        ],
        1,
    )
    response = service.answer(AssistantChatRequest(question="How do I sort batteries?"))

    assert response.status == "insufficient_evidence"
    assert response.answer == INSUFFICIENT_EVIDENCE_ANSWER
    assert response.sources == []


def test_groq_generator_uses_only_provided_source_context():
    class Completion:
        def create(self, **kwargs):
            assert "[C1] Source passage" in kwargs["messages"][1]["content"]
            return type(
                "Response",
                (),
                {
                    "choices": [
                        type(
                            "Choice",
                            (),
                            {"message": type("Message", (), {"content": "Sort waste. [C1]"})()},
                        )()
                    ]
                },
            )()

    client = type(
        "Client",
        (),
        {"chat": type("Chat", (), {"completions": Completion()})()},
    )()
    generator = GroqAnswerGenerator("test-key", "test-model")
    generator._client = client
    answer = generator.generate(
        "How should I sort waste?",
        [{"citation_id": "C1", "text": "Source passage"}],
    )
    assert answer == "Sort waste. [C1]"

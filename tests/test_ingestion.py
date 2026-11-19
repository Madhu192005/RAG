import json
from pathlib import Path

import numpy as np
import pytest

from ai_engine.ingestion.chunker import chunk_document, DocumentChunk
from ai_engine.ingestion.ingestion_pipeline import ingest_paths, rebuild_vector_index, set_document_status
from ai_engine.ingestion.metadata_manager import DocumentRegistry
from ai_engine.ingestion.pdf_extractor import extract_pdf
from ai_engine.ingestion.embedding_generator import EmbeddingGenerator
from ai_engine.ingestion.retrieval import DocumentRetriever, format_source_citation
from ai_engine.ingestion.text_cleaner import clean_text
from ai_engine.ingestion.vector_index import FaissVectorIndex, VectorIndexError
from ai_engine.utils.file_hash import sha256_file


fitz = pytest.importorskip("fitz")
pytest.importorskip("faiss")


def _write_pdf(path: Path, pages):
    document = fitz.open()
    for text in pages:
        page = document.new_page()
        if text:
            page.insert_text((72, 72), text)
    document.save(path)
    document.close()


def test_extracts_pages_and_marks_empty_pages_for_ocr(tmp_path):
    pdf = tmp_path / "source.pdf"
    _write_pdf(pdf, ["Section 1. Waste\nKeep waste separate.", ""])

    extracted = extract_pdf(pdf)

    assert extracted.title == "source"
    assert len(extracted.pages) == 2
    assert "Keep waste separate" in extracted.pages[0].text
    assert extracted.needs_ocr_pages == [2]
    assert extracted.pages[1].needs_ocr is True


def test_pdf_extraction_rejects_malformed_file(tmp_path):
    broken = tmp_path / "broken.pdf"
    broken.write_bytes(b"not a PDF")
    with pytest.raises(RuntimeError, match="Unable to extract PDF"):
        extract_pdf(broken)


def test_text_cleaning_preserves_section_and_normalizes_whitespace():
    source = "  SECTION 4\r\n\r\n\r\nDo not mix\t batteries. \x00"
    assert clean_text(source) == "SECTION 4\n\nDo not mix batteries."


def test_chunk_size_overlap_and_page_metadata(tmp_path):
    pdf = tmp_path / "chunks.pdf"
    words = [f"word{i}" for i in range(90)]
    body = "Section 1\n" + "\n".join(
        " ".join(words[index:index + 10]) for index in range(0, len(words), 10)
    )
    _write_pdf(pdf, [body])
    extracted = extract_pdf(pdf)
    chunks = chunk_document(
        extracted,
        {"document_id": "doc-1", "document_version_id": "version-1", "title": "Source"},
        target_tokens=30,
        overlap_tokens=5,
    )

    assert len(chunks) > 1
    assert all(chunk.token_count <= 30 for chunk in chunks)
    assert all(chunk.metadata["page_start"] == 1 for chunk in chunks)
    assert all(chunk.metadata["document_version_id"] == "version-1" for chunk in chunks)
    assert chunks[0].metadata["section_heading"] == "Section 1"
    assert set(chunks[0].text.split()) & set(chunks[1].text.split())


def test_chunker_keeps_sentence_boundaries_when_sentences_fit(tmp_path):
    pdf = tmp_path / "sentences.pdf"
    _write_pdf(pdf, ["Section 2\nFirst legal sentence remains intact. Second legal sentence also remains intact."])
    chunks = chunk_document(
        extract_pdf(pdf),
        {"document_id": "doc-sentences"},
        target_tokens=9,
        overlap_tokens=2,
    )

    text = " ".join(chunk.text for chunk in chunks)
    assert "First legal sentence remains intact." in text
    assert "Second legal sentence also remains intact." in text


def test_registry_checksum_duplicate_and_version_history(tmp_path):
    source = tmp_path / "document.pdf"
    source.write_bytes(b"one document version")
    registry = DocumentRegistry(tmp_path / "registry.json")
    metadata = {"document_id": "stable-id", "title": "Verified source", "status": "unknown"}
    checksum = sha256_file(source)

    first = registry.add_version(
        source_path=source, metadata=metadata, page_count=2, chunk_count=3, checksum=checksum
    )
    assert registry.find_checksum(checksum)["version_id"] == first["version"]["version_id"]
    source.write_bytes(b"updated document version")
    second = registry.add_version(source_path=source, metadata=metadata, page_count=3, chunk_count=4)

    assert second["document"]["document_id"] == first["document"]["document_id"]
    assert len(registry.data["documents"][0]["versions"]) == 2
    assert registry.data["documents"][0]["status"] == "unknown"


def test_document_status_can_be_changed_without_reingesting(tmp_path):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"source")
    registry_path = tmp_path / "registry.json"
    registry = DocumentRegistry(registry_path)
    registry.add_version(
        source_path=source,
        metadata={"document_id": "status-test-id", "title": "Source", "status": "unknown"},
        page_count=1,
        chunk_count=0,
    )

    result = set_document_status("status-test-id", "superseded", registry_path=registry_path)

    assert result["status"] == "superseded"
    assert DocumentRegistry(registry_path).data["documents"][0]["status"] == "superseded"


def test_faiss_index_round_trip_and_metadata_mapping(tmp_path):
    index = FaissVectorIndex(tmp_path, "test-model")
    chunks = [
        DocumentChunk("chunk-a", "Wet waste", {"document_id": "one"}, 2),
        DocumentChunk("chunk-b", "Dry waste", {"document_id": "two"}, 2),
    ]
    ids = index.add(chunks, np.asarray([[1, 0], [0, 1]], dtype=np.float32))
    index.save()

    reopened = FaissVectorIndex(tmp_path, "test-model")
    reopened.load()
    results = reopened.search(np.asarray([0.9, 0.1], dtype=np.float32), limit=1)

    assert reopened.count == 2
    assert results[0]["chunk_id"] == "chunk-a"
    assert results[0]["vector_id"] == ids[0]
    assert results[0]["metadata"]["document_id"] == "one"


def test_faiss_rejects_mismatched_metadata(tmp_path):
    index = FaissVectorIndex(tmp_path, "test-model")
    index.add([DocumentChunk("chunk", "text", {}, 1)], np.asarray([[1, 2]], dtype=np.float32))
    index.save()
    metadata_file = tmp_path / "index_metadata.json"
    payload = json.loads(metadata_file.read_text(encoding="utf-8"))
    payload["vectors"] = {}
    metadata_file.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(VectorIndexError, match="do not match"):
        FaissVectorIndex(tmp_path, "test-model").load()


def test_embedding_generator_uses_model_dimension_and_normalizes():
    class Model:
        def get_sentence_embedding_dimension(self):
            return 2

        def encode(self, texts, **_kwargs):
            assert _kwargs["normalize_embeddings"] is True
            return np.asarray([[0.6, 0.8] for _ in texts], dtype=np.float32)

    generator = EmbeddingGenerator("injected-test-model")
    generator._model = Model()
    vectors = generator.encode(["query", "passage"])

    assert generator.dimension == 2
    assert vectors.shape == (2, 2)
    assert np.linalg.norm(vectors[0]) == pytest.approx(1.0)


def test_retrieval_filters_metadata_and_formats_page_citation(tmp_path):
    index = FaissVectorIndex(tmp_path, "test-model")
    chunk = DocumentChunk(
        "chunk-cited",
        "Source passage",
        {
            "source_authority": "Verified authority",
            "document_title": "Verified document",
            "jurisdiction": "national",
            "page_start": 4,
            "page_end": 5,
        },
        2,
    )
    index.add([chunk], np.asarray([[1.0, 0.0]], dtype=np.float32))

    class Embeddings:
        def encode(self, _texts):
            return np.asarray([[1.0, 0.0]], dtype=np.float32)

    retriever = DocumentRetriever(index, Embeddings())
    results = retriever.search("question", filters={"jurisdiction": "national"})

    assert len(results) == 1
    assert format_source_citation(results[0]) == "Verified authority: Verified document, pp. 4-5"
    assert retriever.search("question", filters={"jurisdiction": "other"}) == []


class _FakeEmbeddingGenerator:
    model_name = "test-embedding-model"
    version = "0.0-test"

    def encode(self, texts, batch_size=32):
        return np.asarray([[float(len(text)), 1.0] for text in texts], dtype=np.float32)


def test_pipeline_isolates_failed_pdf_and_skips_duplicate(tmp_path):
    source_dir = tmp_path / "pdfs"
    source_dir.mkdir()
    _write_pdf(source_dir / "good.pdf", ["Waste handling guidance."])
    (source_dir / "bad.pdf").write_bytes(b"malformed")
    options = {
        "registry_path": tmp_path / "metadata" / "registry.json",
        "index_directory": tmp_path / "faiss",
        "raw_directory": tmp_path / "raw",
        "embedding_generator": _FakeEmbeddingGenerator(),
    }

    first = ingest_paths(source_dir, {"source_authority": "unverified test"}, **options)
    second = ingest_paths(source_dir / "good.pdf", {}, **options)

    assert first["success_count"] == 1
    assert first["failed_count"] == 1
    assert second["skipped_duplicate_count"] == 1
    assert list((tmp_path / "raw").glob("*.json"))
    _write_pdf(source_dir / "bad.pdf", ["The corrected source has readable text."])
    recovered = ingest_paths(source_dir, {"source_authority": "unverified test"}, **options)
    assert recovered["success_count"] == 1
    assert recovered["skipped_duplicate_count"] == 1
    rebuilt = rebuild_vector_index(
        registry_path=options["registry_path"],
        raw_directory=options["raw_directory"],
        index_directory=options["index_directory"],
        embedding_generator=options["embedding_generator"],
    )
    assert rebuilt["status"] == "rebuilt"
    assert rebuilt["chunk_count"] > 0
    assert rebuilt["backup_directory"] is not None


def test_retrieval_dataset_contains_questions_without_claiming_accuracy():
    dataset_path = Path(__file__).parents[1] / "ai_engine" / "evaluation" / "retrieval_dataset.json"
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    assert len(dataset) >= 20
    assert all(item.get("expected_source_authority") for item in dataset)

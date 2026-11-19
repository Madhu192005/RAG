"""Persistence adapter for MySQL document, version, job, and chunk records."""

from datetime import datetime
from typing import Dict, List
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.knowledge import DocumentChunk, DocumentVersion, IngestionJob, KnowledgeDocument
from ai_engine.ingestion.chunker import DocumentChunk as IngestedChunk


def has_checksum(db: Session, checksum: str) -> bool:
    return db.query(DocumentVersion.version_id).filter(DocumentVersion.checksum == checksum).first() is not None


def save_document(
    db: Session,
    document: Dict[str, object],
    version: Dict[str, object],
    chunks: List[IngestedChunk],
    vector_ids: List[int],
) -> None:
    document_id = str(document["document_id"])
    row = db.query(KnowledgeDocument).filter_by(document_id=document_id).first()
    if row is None:
        row = KnowledgeDocument(
            document_id=document_id,
            title=str(document["title"]),
            source_authority=document.get("source_authority"),
            source_url=document.get("source_url"),
            jurisdiction=document.get("jurisdiction"),
            document_category=document.get("document_category"),
            status=str(document.get("status", "unknown")),
        )
        db.add(row)
    version_row = DocumentVersion(
        version_id=str(version["version_id"]),
        document_id=document_id,
        checksum=str(version["checksum"]),
        original_filename=str(version["original_filename"]),
        publication_date=version.get("publication_date"),
        effective_date=version.get("effective_date"),
        ingested_at=datetime.fromisoformat(str(version["ingested_at"]).replace("Z", "+00:00")).replace(
            tzinfo=None
        ),
        processing_status=str(version["processing_status"]),
        page_count=int(version["page_count"]),
        chunk_count=int(version["chunk_count"]),
        embedding_model=version.get("embedding_model"),
        embedding_model_version=version.get("embedding_model_version"),
    )
    db.add(version_row)
    for chunk, vector_id in zip(chunks, vector_ids):
        db.add(
            DocumentChunk(
                chunk_id=chunk.chunk_id,
                version_id=str(version["version_id"]),
                faiss_vector_id=vector_id,
                metadata_json=chunk.metadata,
            )
        )
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise


def save_job(db: Session, report: Dict[str, object]) -> None:
    db.add(
        IngestionJob(
            job_id=str(uuid4()),
            started_at=report["started_at"],
            finished_at=report["finished_at"],
            status=report["status"],
            success_count=report["success_count"],
            failed_count=report["failed_count"],
            skipped_duplicate_count=report["skipped_duplicate_count"],
            page_count=report["page_count"],
            chunk_count=report["chunk_count"],
            duration_seconds=float(report["duration_seconds"]),
            error_details=report["errors"],
        )
    )
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

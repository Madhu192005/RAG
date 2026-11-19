"""Database records for source documents and RAG ingestion provenance."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database.connection import Base


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"
    __table_args__ = (
        CheckConstraint(
            "status IN ('unknown', 'current', 'superseded', 'inactive')",
            name="ck_knowledge_documents_status",
        ),
    )

    document_id = Column(String(36), primary_key=True)
    title = Column(String(500), nullable=False)
    source_authority = Column(String(255), nullable=True, index=True)
    source_url = Column(Text, nullable=True)
    jurisdiction = Column(String(255), nullable=True, index=True)
    document_category = Column(String(100), nullable=True, index=True)
    status = Column(String(30), nullable=False, default="unknown", index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    versions = relationship("DocumentVersion", back_populates="document")


class DocumentVersion(Base):
    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint("checksum", name="uq_document_versions_checksum"),
        CheckConstraint(
            "processing_status IN ('processed', 'processed_with_ocr_required', 'failed')",
            name="ck_document_versions_processing_status",
        ),
    )

    version_id = Column(String(36), primary_key=True)
    document_id = Column(
        String(36),
        ForeignKey("knowledge_documents.document_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    checksum = Column(String(64), nullable=False)
    original_filename = Column(String(500), nullable=False)
    publication_date = Column(String(30), nullable=True)
    effective_date = Column(String(30), nullable=True)
    ingested_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    processing_status = Column(String(40), nullable=False, index=True)
    page_count = Column(Integer, nullable=False, default=0)
    chunk_count = Column(Integer, nullable=False, default=0)
    embedding_model = Column(String(255), nullable=True)
    embedding_model_version = Column(String(100), nullable=True)

    document = relationship("KnowledgeDocument", back_populates="versions")
    chunks = relationship("DocumentChunk", back_populates="version")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("faiss_vector_id", name="uq_document_chunks_faiss_vector_id"),
    )

    chunk_id = Column(String(36), primary_key=True)
    version_id = Column(
        String(36),
        ForeignKey("document_versions.version_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    faiss_vector_id = Column(BigInteger, nullable=True)
    metadata_json = Column(JSON, nullable=False)

    version = relationship("DocumentVersion", back_populates="chunks")


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('completed', 'completed_with_errors')",
            name="ck_ingestion_jobs_status",
        ),
    )

    job_id = Column(String(36), primary_key=True)
    started_at = Column(DateTime, nullable=False)
    finished_at = Column(DateTime, nullable=False)
    status = Column(String(30), nullable=False, index=True)
    success_count = Column(Integer, nullable=False, default=0)
    failed_count = Column(Integer, nullable=False, default=0)
    skipped_duplicate_count = Column(Integer, nullable=False, default=0)
    page_count = Column(Integer, nullable=False, default=0)
    chunk_count = Column(Integer, nullable=False, default=0)
    duration_seconds = Column(Float, nullable=False, default=0.0)
    error_details = Column(JSON, nullable=False, default=list)

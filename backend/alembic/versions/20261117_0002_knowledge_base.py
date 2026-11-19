"""Add document ingestion and FAISS chunk references.

Revision ID: 20261117_0002
Revises: 20261117_0001
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261117_0002"
down_revision: Union[str, Sequence[str], None] = "20261117_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "knowledge_documents",
        sa.Column("document_id", sa.String(length=36), primary_key=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("source_authority", sa.String(length=255), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("jurisdiction", sa.String(length=255), nullable=True),
        sa.Column("document_category", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.CheckConstraint(
            "status IN ('unknown', 'current', 'superseded', 'inactive')",
            name="ck_knowledge_documents_status",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_knowledge_documents_source_authority", "knowledge_documents", ["source_authority"])
    op.create_index("ix_knowledge_documents_jurisdiction", "knowledge_documents", ["jurisdiction"])
    op.create_index("ix_knowledge_documents_document_category", "knowledge_documents", ["document_category"])
    op.create_index("ix_knowledge_documents_status", "knowledge_documents", ["status"])
    op.create_table(
        "document_versions",
        sa.Column("version_id", sa.String(length=36), primary_key=True),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("original_filename", sa.String(length=500), nullable=False),
        sa.Column("publication_date", sa.String(length=30), nullable=True),
        sa.Column("effective_date", sa.String(length=30), nullable=True),
        sa.Column("ingested_at", sa.DateTime(), nullable=False),
        sa.Column("processing_status", sa.String(length=40), nullable=False),
        sa.CheckConstraint(
            "processing_status IN ('processed', 'processed_with_ocr_required', 'failed')",
            name="ck_document_versions_processing_status",
        ),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("embedding_model", sa.String(length=255), nullable=True),
        sa.Column("embedding_model_version", sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(
            ["document_id"], ["knowledge_documents.document_id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint("checksum", name="uq_document_versions_checksum"),
    )
    op.create_index("ix_document_versions_document_id", "document_versions", ["document_id"])
    op.create_index("ix_document_versions_processing_status", "document_versions", ["processing_status"])
    op.create_table(
        "document_chunks",
        sa.Column("chunk_id", sa.String(length=36), primary_key=True),
        sa.Column("version_id", sa.String(length=36), nullable=False),
        sa.Column("faiss_vector_id", sa.BigInteger(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["version_id"], ["document_versions.version_id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint("faiss_vector_id", name="uq_document_chunks_faiss_vector_id"),
    )
    op.create_index("ix_document_chunks_version_id", "document_chunks", ["version_id"])
    op.create_table(
        "ingestion_jobs",
        sa.Column("job_id", sa.String(length=36), primary_key=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.CheckConstraint(
            "status IN ('completed', 'completed_with_errors')",
            name="ck_ingestion_jobs_status",
        ),
        sa.Column("success_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("skipped_duplicate_count", sa.Integer(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=False),
        sa.Column("error_details", sa.JSON(), nullable=False),
    )
    op.create_index("ix_ingestion_jobs_status", "ingestion_jobs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_ingestion_jobs_status", table_name="ingestion_jobs")
    op.drop_table("ingestion_jobs")
    op.drop_index("ix_document_chunks_version_id", table_name="document_chunks")
    op.drop_table("document_chunks")
    op.drop_index("ix_document_versions_processing_status", table_name="document_versions")
    op.drop_index("ix_document_versions_document_id", table_name="document_versions")
    op.drop_table("document_versions")
    op.drop_index("ix_knowledge_documents_status", table_name="knowledge_documents")
    op.drop_index("ix_knowledge_documents_document_category", table_name="knowledge_documents")
    op.drop_index("ix_knowledge_documents_jurisdiction", table_name="knowledge_documents")
    op.drop_index("ix_knowledge_documents_source_authority", table_name="knowledge_documents")
    op.drop_table("knowledge_documents")

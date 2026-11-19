"""Explicit, destructive-only-on-empty-disposable PostgreSQL verification.

Run separately with POSTGRES_TEST_DATABASE_URL set to a dedicated *_test database
and POSTGRES_TEST_DATABASE_CONFIRMATION=I_CREATED_A_DISPOSABLE_TEST_DATABASE.
This suite never reads DATABASE_URL as a target fallback.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.dialects.postgresql import JSON as PostgreSQLJSON
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
EXPECTED_TABLES = {
    "roles", "users", "waste_categories", "waste_reports", "recycling_centers",
    "accepted_waste_types", "collection_requests", "collection_records", "notifications",
    "audit_logs", "knowledge_documents", "document_versions", "document_chunks",
    "ingestion_jobs", "assistant_conversations", "assistant_messages", "waste_classifications",
}
CONFIRMATION = "I_CREATED_A_DISPOSABLE_TEST_DATABASE"


def _configured_test_url():
    """Fail closed: this suite never falls back to DATABASE_URL or DB_* settings."""
    raw_url = os.environ.get("POSTGRES_TEST_DATABASE_URL")
    if not raw_url:
        raise pytest.UsageError(
            "POSTGRES_TEST_DATABASE_URL is required for postgres_tests; "
            "the suite will not use DATABASE_URL or MySQL defaults."
        )
    if os.environ.get("POSTGRES_TEST_DATABASE_CONFIRMATION") != CONFIRMATION:
        raise pytest.UsageError(
            "Set POSTGRES_TEST_DATABASE_CONFIRMATION to the documented confirmation "
            "only after selecting an empty disposable non-production test database."
        )
    try:
        url = make_url(raw_url)
    except Exception:
        raise pytest.UsageError("POSTGRES_TEST_DATABASE_URL is not a valid SQLAlchemy URL.") from None

    if url.get_backend_name() != "postgresql":
        raise pytest.UsageError("PostgreSQL integration tests require a PostgreSQL URL.")
    database = (url.database or "").casefold()
    host = (url.host or "").casefold()
    if "test" not in database or "prod" in database or "prod" in host:
        raise pytest.UsageError(
            "Refusing PostgreSQL integration tests: use a dedicated test-named database "
            "on a non-production endpoint."
        )
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg")
    elif url.drivername != "postgresql+psycopg":
        raise pytest.UsageError("Use the postgresql+psycopg SQLAlchemy driver URL.")
    return raw_url, url


# Module-level guard makes an explicit invocation fail before creating an
# engine or touching a database when no isolated target is configured.
TEST_URL_RAW, TEST_URL = _configured_test_url()


def _alembic_config() -> Config:
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    return config


def _assert_empty_or_known_empty_head(engine) -> None:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names(schema="public"))
    if not tables:
        return
    if "alembic_version" not in tables:
        pytest.fail(
            "Refusing migration: the test database already has tables without an Alembic marker. "
            "Choose a new empty disposable test database."
        )
    version = None
    with engine.connect() as connection:
        version = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
    if version != "20261118_0005" or tables != EXPECTED_TABLES | {"alembic_version"}:
        pytest.fail(
            "Refusing migration: existing schema is not the expected empty Step 8 test schema."
        )
    with engine.connect() as connection:
        for table in EXPECTED_TABLES:
            count = connection.execute(text(f'SELECT count(*) FROM public."{table}"')).scalar_one()
            if count:
                pytest.fail(
                    "Refusing migration: test schema contains records. Choose a new disposable database."
                )


def _verify_schema(engine) -> None:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names(schema="public"))
    assert EXPECTED_TABLES.issubset(tables)

    primary_key = inspector.get_pk_constraint("users", schema="public")
    assert primary_key["constrained_columns"] == ["id"]
    with engine.connect() as connection:
        generated_id = connection.execute(
            text(
                "INSERT INTO public.roles (role_name) VALUES (:name) RETURNING id"
            ), {"name": f"generated-{uuid4()}"}
        ).scalar_one()
        connection.execute(text("DELETE FROM public.roles WHERE id=:id"), {"id": generated_id})
        connection.commit()
    assert generated_id > 0

    user_fks = inspector.get_foreign_keys("users", schema="public")
    assert any(fk["referred_table"] == "roles" for fk in user_fks)
    collection_fks = inspector.get_foreign_keys("collection_requests", schema="public")
    assert {fk["referred_table"] for fk in collection_fks} >= {
        "users", "waste_categories", "waste_classifications", "recycling_centers"
    }
    assert inspector.get_indexes("collection_requests", schema="public")
    assert any(
        constraint.get("name") == "uq_center_category_material"
        for constraint in inspector.get_unique_constraints("accepted_waste_types", schema="public")
    )
    assert any(
        constraint.get("name") == "uq_users_email"
        for constraint in inspector.get_unique_constraints("users", schema="public")
    )

    chunk_columns = {
        column["name"]: column for column in inspector.get_columns("document_chunks", schema="public")
    }
    job_columns = {
        column["name"]: column for column in inspector.get_columns("ingestion_jobs", schema="public")
    }
    assert isinstance(chunk_columns["metadata_json"]["type"], PostgreSQLJSON)
    assert isinstance(job_columns["error_details"]["type"], PostgreSQLJSON)
    classification_columns = {
        column["name"]: column
        for column in inspector.get_columns("waste_classifications", schema="public")
    }
    assert classification_columns["confirmed_class"]["nullable"] is True
    assert classification_columns["user_id"]["nullable"] is False


def _verify_model_crud(engine) -> None:
    # Import after DATABASE_URL has been explicitly replaced with the test URL.
    if str(BACKEND) not in sys.path:
        sys.path.insert(0, str(BACKEND))
    from app.models import (  # noqa: PLC0415
        AcceptedWasteType,
        AuditLog,
        AssistantConversation,
        AssistantMessage,
        CollectionRecord,
        CollectionRequest,
        DocumentChunk,
        DocumentVersion,
        IngestionJob,
        KnowledgeDocument,
        Notification,
        RecyclingCenter,
        Role,
        User,
        WasteCategory,
        WasteClassification,
        WasteReport,
    )

    token = uuid4().hex[:10]
    with Session(engine, expire_on_commit=False) as db:
        role = Role(role_name=f"citizen-{token}")
        category = WasteCategory(category_name=f"Dry-{token}")
        db.add_all([role, category])
        db.commit()
        assert role.id and category.id

        user = User(email=f"user-{token}@example.test", hashed_password="not-a-real-login")
        db.add(user)
        db.commit()
        assert user.id
        assert db.scalar(select(User).where(User.email == user.email)).id == user.id

        report = WasteReport(user_id=user.id, category_id=category.id, title="PostgreSQL report")
        center = RecyclingCenter(
            center_name="PostgreSQL center", address="Test Road", city="Test City",
            verification_status="verified",
        )
        db.add_all([report, center])
        db.flush()
        acceptance = AcceptedWasteType(
            center_id=center.id, category_id=category.id, accepted_waste_label="Plastic"
        )
        request = CollectionRequest(
            user_id=user.id, category_id=category.id, full_name="Test User",
            email=user.email, phone="5551234567", category_label=category.category_name,
            recycling_center_id=center.id, quantity=2, quantity_unit="kg",
            pickup_address="1 Test Collection Road", preferred_pickup_date="2035-01-01",
            status="completed",
        )
        db.add_all([acceptance, request])
        db.flush()
        record = CollectionRecord(
            request_id=request.id, collector_id=user.id, collected_quantity=1.75,
            quantity_unit="kg",
        )
        notification = Notification(user_id=user.id, title="Test", message="Persistence check")
        audit = AuditLog(user_id=user.id, action="postgres_test", entity_type="test")
        classification = WasteClassification(
            user_id=user.id, image_path="test/unused.png", predicted_class="Plastic",
            confidence_score=0.9, confidence_label="High", model_version="test-only",
            requires_confirmation=False,
        )
        conversation = AssistantConversation(conversation_id=str(uuid4()), user_id=user.id, title="test")
        db.add_all([record, notification, audit, classification, conversation])
        db.flush()
        message = AssistantMessage(
            conversation_id=conversation.conversation_id, role="assistant", content="test",
            source_metadata=[{"source": "test"}],
        )
        document = KnowledgeDocument(document_id=str(uuid4()), title="test source", status="current")
        db.add_all([message, document])
        db.flush()
        version = DocumentVersion(
            version_id=str(uuid4()), document_id=document.document_id, checksum=uuid4().hex,
            original_filename="test.pdf", processing_status="processed", page_count=1,
            chunk_count=1,
        )
        db.add(version)
        db.flush()
        chunk = DocumentChunk(
            chunk_id=str(uuid4()), version_id=version.version_id, faiss_vector_id=987654321,
            metadata_json={"page": 1},
        )
        job = IngestionJob(
            job_id=str(uuid4()), status="completed", success_count=1, failed_count=0,
            skipped_duplicate_count=0, page_count=1, chunk_count=1, duration_seconds=0.1,
            started_at=report.created_at, finished_at=report.created_at, error_details=[],
        )
        db.add_all([chunk, job])
        db.commit()

        # Verify reads and updates survive a commit on PostgreSQL.
        report.title = "Updated PostgreSQL report"
        center.center_name = "Updated PostgreSQL center"
        db.commit()
        db.expire_all()
        assert db.get(WasteReport, report.id).title == "Updated PostgreSQL report"
        assert db.get(RecyclingCenter, center.id).center_name == "Updated PostgreSQL center"
        assert db.get(CollectionRequest, request.id).collection_records[0].id == record.id
        assert db.get(WasteClassification, classification.id).predicted_class == "Plastic"
        assert db.get(Notification, notification.id).message == "Persistence check"
        assert db.get(AuditLog, audit.id).action == "postgres_test"

        # PostgreSQL must enforce the ORM's email uniqueness and foreign keys.
        with pytest.raises(IntegrityError):
            with db.begin_nested():
                db.add(User(email=user.email, hashed_password="duplicate"))
                db.flush()
        with pytest.raises(IntegrityError):
            with db.begin_nested():
                db.add(WasteReport(category_id=-999, title="invalid foreign key"))
                db.flush()
        db.rollback()

        # A rollback must not persist the transient row.
        transient_email = f"rollback-{token}@example.test"
        with db.begin_nested() as nested:
            db.add(User(email=transient_email, hashed_password="rolled back"))
            db.flush()
            nested.rollback()
        assert db.scalar(select(User).where(User.email == transient_email)) is None

        db.delete(report)
        db.commit()
        assert db.get(WasteReport, report.id) is None


def test_postgres_migration_and_model_compatibility():
    previous_database_url = os.environ.get("DATABASE_URL")
    previous_debug = os.environ.get("DEBUG")
    os.environ["DATABASE_URL"] = TEST_URL_RAW
    os.environ["DEBUG"] = "false"
    engine = create_engine(TEST_URL, pool_pre_ping=True, pool_size=2, max_overflow=0)
    try:
        with engine.connect() as connection:
            identity = connection.execute(
                text("SELECT current_database(), current_user, current_setting('server_version')")
            ).one()
            assert identity[0] == TEST_URL.database

        _assert_empty_or_known_empty_head(engine)
        config = _alembic_config()

        # Fresh empty DBs run the five revisions directly. A previously verified,
        # empty head schema is cycled only after the checks above prove no rows exist.
        existing_tables = set(inspect(engine).get_table_names(schema="public"))
        if existing_tables:
            command.downgrade(config, "base")
        command.upgrade(config, "head")

        with engine.connect() as connection:
            revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        assert revision == "20261118_0005"
        _verify_schema(engine)
        _verify_model_crud(engine)

        # Downgrade/upgrade is limited to the confirmed empty-schema disposable target.
        command.downgrade(config, "base")
        assert not inspect(engine).get_table_names(schema="public")
        command.upgrade(config, "head")
        with engine.connect() as connection:
            revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        assert revision == "20261118_0005"
        assert EXPECTED_TABLES.issubset(set(inspect(engine).get_table_names(schema="public")))
    finally:
        engine.dispose()
        if previous_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_database_url
        if previous_debug is None:
            os.environ.pop("DEBUG", None)
        else:
            os.environ["DEBUG"] = previous_debug

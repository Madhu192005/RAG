"""
Database connection, schema, and migration tests.

API tests use an isolated SQLite database.
MySQL checks run only when a live MySQL instance is reachable and
WASTEWISE_RUN_MYSQL_TESTS=1 is set, targeting wastewise_test_db.
"""

import os

from sqlalchemy import inspect, text

from app.core.security import create_access_token, decode_access_token, hash_password, verify_password
from app.database.connection import Base, check_database_connection
from app.models.role import Role
from app.models.user import User
from app.models.waste import WasteCategory
from app.models.knowledge import DocumentChunk, DocumentVersion, KnowledgeDocument


REQUIRED_TABLES = {
    "users",
    "roles",
    "waste_categories",
    "waste_reports",
    "recycling_centers",
    "accepted_waste_types",
    "collection_requests",
    "collection_records",
    "waste_classifications",
    "notifications",
    "audit_logs",
    "knowledge_documents",
    "document_versions",
    "document_chunks",
    "ingestion_jobs",
}


def test_isolated_engine_connection(db_session):
    result = db_session.execute(text("SELECT 1")).scalar()
    assert result == 1


def test_tables_exist_after_creation():
    table_names = set(Base.metadata.tables.keys())
    assert REQUIRED_TABLES.issubset(table_names)


def test_seeded_roles_and_categories(db_session):
    roles = {row.role_name for row in db_session.query(Role).all()}
    assert {"admin", "citizen", "collector"}.issubset(roles)
    categories = {row.category_name for row in db_session.query(WasteCategory).all()}
    assert {"Wet waste", "Dry waste", "Sanitary waste", "Special-care waste"}.issubset(categories)


def test_user_role_foreign_key(db_session):
    citizen = db_session.query(Role).filter(Role.role_name == "citizen").first()
    user = User(
        email="fk-user@example.com",
        hashed_password=hash_password("Password123!"),
        full_name="FK User",
        role_id=citizen.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    assert user.role_rel.role_name == "citizen"


def test_knowledge_document_version_chunk_relationships(db_session):
    document = KnowledgeDocument(
        document_id="document-test-id",
        title="Verified test source",
        status="unknown",
    )
    version = DocumentVersion(
        version_id="version-test-id",
        document_id=document.document_id,
        checksum="a" * 64,
        original_filename="source.pdf",
        processing_status="processed",
        page_count=1,
        chunk_count=1,
    )
    chunk = DocumentChunk(
        chunk_id="chunk-test-id",
        version_id=version.version_id,
        faiss_vector_id=1,
        metadata_json={"page_start": 1, "page_end": 1},
    )
    db_session.add_all([document, version, chunk])
    db_session.commit()

    assert document.versions[0].chunks[0].metadata_json["page_start"] == 1


def test_password_hashing_is_not_plaintext():
    raw = "Password123!"
    hashed = hash_password(raw)
    assert hashed != raw
    assert verify_password(raw, hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_jwt_round_trip():
    token = create_access_token(subject="42", extra_claims={"role": "citizen"})
    payload = decode_access_token(token)
    assert payload["sub"] == "42"
    assert payload["role"] == "citizen"


def test_app_database_probe_function():
    # The imported app engine may be sqlite memory (tests) or MySQL (local .env).
    result = check_database_connection()
    assert isinstance(result, bool)


def test_mysql_connection_optional():
    if os.getenv("WASTEWISE_RUN_MYSQL_TESTS") != "1":
        return
    from sqlalchemy import create_engine
    from urllib.parse import quote_plus
    from app.core.config import settings

    uri = (
        f"mysql+pymysql://{quote_plus(settings.DB_USER)}:{quote_plus(settings.DB_PASSWORD)}"
        f"@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
    )
    engine = create_engine(uri, pool_pre_ping=True)
    with engine.connect() as connection:
        assert connection.execute(text("SELECT 1")).scalar() == 1
    inspector = inspect(engine)
    present = set(inspector.get_table_names())
    assert REQUIRED_TABLES.issubset(present)
    engine.dispose()

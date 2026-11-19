"""
WasteWise AI – Pytest Configuration & Test Fixtures
----------------------------------------------------
Uses an isolated SQLite in-memory database so tests never touch wastewise_db.
"""

import os
import sys

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-wastewise-ai"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.connection import Base, get_db
from app.main import app
from app.models import *  # noqa: F401,F403
from app.services.seed_service import seed_reference_data

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)


@event.listens_for(engine, "connect")
def _enable_sqlite_fks(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture(autouse=True)
def setup_test_db(monkeypatch):
    """Give every test a fresh isolated schema and reference rows."""
    Base.metadata.create_all(bind=engine)
    # The application lifespan must use the same isolated test database as
    # request dependencies; the default DATABASE_URL engine is a separate DB.
    import app.main as app_main
    monkeypatch.setattr(app_main, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(app_main, "check_database_connection", lambda: True)
    db = TestingSessionLocal()
    seed_reference_data(db)
    db.close()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    """Provides a session bound to the isolated test database."""
    session = TestingSessionLocal()
    yield session
    session.close()


@pytest.fixture
def client(db_session):
    """
    TestClient that overrides the get_db dependency to use the isolated test database.
    """

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(client):
    client.post(
        "/api/auth/register",
        json={
            "email": "citizen.auth@example.com",
            "password": "Password123!",
            "full_name": "Citizen Auth",
        },
    )
    token = client.post(
        "/api/auth/login",
        json={"email": "citizen.auth@example.com", "password": "Password123!"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

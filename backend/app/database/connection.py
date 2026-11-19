"""
WasteWise AI – Database Connection & Session Management
--------------------------------------------------------
SQLAlchemy engine, SessionLocal, declarative Base, and FastAPI dependency.
Configured for MySQL via PyMySQL with connection pooling.
"""

import logging
from typing import Generator

from fastapi import HTTPException, status
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings

logger = logging.getLogger("wastewise_ai.db")

database_uri = settings.sqlalchemy_database_uri
database_url = make_url(database_uri)
database_backend = database_url.get_backend_name()
is_sqlite = database_backend == "sqlite"

connect_args = {"check_same_thread": False} if is_sqlite else {}

engine_kwargs = {
    "connect_args": connect_args,
    "echo": False,
    "pool_pre_ping": True,
}

if is_sqlite and database_url.database in (None, "", ":memory:"):
    # Keep a single in-memory database connection for local/test application use.
    engine_kwargs["poolclass"] = StaticPool
elif database_backend == "postgresql":
    # Use SQLAlchemy's pool only; do not layer a psycopg_pool on top of it.
    # Keep per-process connections bounded when Neon PgBouncer is enabled.
    engine_kwargs.update(
        {
            "pool_size": 5,
            "max_overflow": 5,
            "pool_recycle": 300,
            "pool_timeout": 30,
        }
    )
elif database_backend == "mysql":
    # Preserve the existing MySQL pool settings during the database transition.
    engine_kwargs.update(
        {
            "pool_size": 5,
            "max_overflow": 10,
            "pool_recycle": 3600,
            "pool_timeout": 30,
        }
    )

try:
    engine = create_engine(database_uri, **engine_kwargs)
except Exception as exc:
    # Driver/parser exception strings can include URL details; log only type.
    logger.error("Failed to configure SQLAlchemy engine (%s)", type(exc).__name__)
    raise RuntimeError(
        "Unable to configure the database engine. Check DATABASE_URL or DB_* settings."
    ) from None

if is_sqlite:
    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    bind=engine,
)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a SQLAlchemy session
    and rolls back on database errors without leaking SQL details.
    """
    db = SessionLocal()
    try:
        yield db
    except HTTPException:
        db.rollback()
        raise
    except OperationalError as exc:
        db.rollback()
        logger.error("Database operational error during request processing (%s)", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The database is temporarily unavailable. Please try again later.",
        )
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("Database error during request processing (%s)", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A database error occurred while processing this request.",
        )
    finally:
        db.close()


def check_database_connection() -> bool:
    """Return True if a simple connectivity probe succeeds."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except OperationalError as exc:
        logger.error("Database connectivity probe failed (%s)", type(exc).__name__)
        return False
    except SQLAlchemyError as exc:
        logger.error("Database connectivity probe failed (%s)", type(exc).__name__)
        return False

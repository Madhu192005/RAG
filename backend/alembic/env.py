"""Alembic environment for WasteWise AI."""

from logging.config import fileConfig
import os
import sys

from alembic import context
from sqlalchemy import engine_from_config, pool

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.core.config import settings  # noqa: E402
from app.database.connection import Base  # noqa: E402
from app.models import (  # noqa: E402,F401
    AcceptedWasteType,
    AssistantConversation,
    AssistantMessage,
    AuditLog,
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
    WasteReport,
    WasteClassification,
)

config = context.config
# Do not copy DATABASE_URL into ConfigParser: percent-encoded credentials are
# interpreted as interpolation syntax there. Migration engines below use the
# SQLAlchemy URL directly from settings instead.

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = settings.sqlalchemy_database_uri
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        {"sqlalchemy.url": settings.sqlalchemy_database_uri},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

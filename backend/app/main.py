"""
WasteWise AI – Backend Application Entry Point (Step 4)
--------------------------------------------------------
MySQL persistence via SQLAlchemy. Tables are created through Alembic
migrations rather than dropping/recreating on every startup.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.api import api_router
from app.core.config import settings
from app.database.connection import SessionLocal, check_database_connection
from app.services.seed_service import seed_reference_data

logging.basicConfig(
    level=logging.INFO if settings.DEBUG else logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("wastewise_ai")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing WasteWise AI backend services...")
    if check_database_connection():
        logger.info("Database connectivity verified.")
        db = SessionLocal()
        try:
            seed_reference_data(db)
        except SQLAlchemyError:
            logger.exception(
                "Reference seed skipped because tables are not ready. Run Alembic migrations first."
            )
        finally:
            db.close()
    else:
        logger.error(
            "Database is unreachable. Apply docs/DATABASE_SETUP.md before serving traffic."
        )
    yield
    logger.info("Shutting down WasteWise AI backend...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description=(
        "AI-Powered Waste Classification, Recycling Guidance & Management Platform. "
        "Step 8 recycling center recommendations and collection management, with image classification and grounded RAG."
    ),
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    logger.exception("Unhandled database exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "A database error occurred. Please contact system support.",
            "path": str(request.url.path),
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        "Unhandled exception processing %s %s: %s",
        request.method,
        request.url,
        exc,
        exc_info=True,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An internal server error occurred. Please contact system support.",
            "path": str(request.url.path),
        },
    )


@app.get("/", summary="Root – welcome message", tags=["System"])
def read_root():
    """Return platform metadata and documentation endpoints."""
    return {
        "message": "Welcome to WasteWise AI Backend!",
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "step": "Step 8 – Smart Recycling Centers and Collection Management",
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health",
        "api": settings.API_PREFIX,
    }


@app.get("/health", summary="Health check", tags=["System"])
def health_check():
    """
    Returns backend health status, database connection state, and AI engine status.
    Called by the frontend 'Check Backend Connection' diagnostic button.
    """
    now_utc = datetime.now(timezone.utc).isoformat()
    db_ok = check_database_connection()
    return {
        "status": "healthy" if db_ok else "degraded",
        "service": "WasteWise AI Backend",
        "version": settings.VERSION,
        "timestamp": now_utc,
        "database": "connected" if db_ok else "unavailable",
        "ai_engine": "grounded RAG endpoint available; indexed sources and Groq are checked per request",
    }


app.include_router(api_router, prefix=settings.API_PREFIX)

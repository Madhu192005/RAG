"""
WasteWise AI – Application Configuration Module
------------------------------------------------
Loads environment variables using Pydantic Settings and python-dotenv.
Builds the SQLAlchemy MySQL URL from discrete DB_* variables.
"""

from typing import List, Optional, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url


class Settings(BaseSettings):
    PROJECT_NAME: str = "WasteWise AI"
    VERSION: str = "0.4.0"
    API_PREFIX: str = "/api"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # JWT (preferred names from Step 4)
    JWT_SECRET_KEY: str = "replace_with_secure_secret"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Backward-compatible aliases used by Step 3 .env files
    SECRET_KEY: Optional[str] = None
    ALGORITHM: Optional[str] = None

    # CORS
    CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:3000",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        if isinstance(v, list):
            return v
        return ["http://localhost:5500", "http://127.0.0.1:5500"]

    # MySQL connection parts. DATABASE_URL, when set, takes precedence.
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_NAME: str = "wastewise_db"
    DB_USER: str = "root"
    DB_PASSWORD: str = "your_password"

    # Optional full URL override (used by isolated tests)
    DATABASE_URL: Optional[str] = None

    # RAG and generation configuration
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: Optional[str] = None
    RAG_EMBEDDING_MODEL: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    RAG_RERANKER_MODEL: str = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
    RAG_INDEX_DIRECTORY: Optional[str] = None
    RAG_SEMANTIC_TOP_K: int = Field(default=20, ge=1, le=200)
    RAG_KEYWORD_TOP_K: int = Field(default=20, ge=1, le=200)
    RAG_HYBRID_TOP_K: int = Field(default=12, ge=1, le=100)
    RAG_FINAL_TOP_K: int = Field(default=5, ge=1, le=30)
    RAG_RRF_K: int = Field(default=60, ge=1)
    RAG_CONTEXT_MAX_CHARS: int = Field(default=12000, ge=1000, le=50000)
    RAG_HISTORY_LIMIT: int = Field(default=6, ge=0, le=30)
    RAG_GROQ_TIMEOUT_SECONDS: float = Field(default=30.0, gt=0, le=120)
    RAG_MIN_RERANK_SCORE: float = -1.0
    RAG_HIGH_RERANK_SCORE: float = 2.0

    # Host & Port
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @property
    def jwt_secret(self) -> str:
        return self.SECRET_KEY or self.JWT_SECRET_KEY

    @property
    def jwt_algorithm(self) -> str:
        return self.ALGORITHM or self.JWT_ALGORITHM

    @property
    def sqlalchemy_database_uri(self) -> str:
        if self.DATABASE_URL:
            url = make_url(self.DATABASE_URL)
            if url.get_backend_name() == "sqlite":
                # Preserve SQLite URI syntax such as sqlite:///:memory:.
                return self.DATABASE_URL
            # Neon examples often use the driver-neutral PostgreSQL scheme.
            # Select psycopg 3 explicitly while preserving its SSL query args.
            if url.drivername in {"postgres", "postgresql"}:
                url = url.set(drivername="postgresql+psycopg")
            return url.render_as_string(hide_password=False)

        # URL.create safely quotes usernames/passwords containing @, :, /, %,
        # and other reserved URL characters.
        return URL.create(
            "mysql+pymysql",
            username=self.DB_USER,
            password=self.DB_PASSWORD,
            host=self.DB_HOST,
            port=self.DB_PORT,
            database=self.DB_NAME,
        ).render_as_string(hide_password=False)


settings = Settings()

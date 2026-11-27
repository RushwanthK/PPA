"""Settings for the AI service, read from environment variables or ai_service/.env.

Secrets use ``SecretStr`` so they never appear in logs, tracebacks or ``repr()``.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

SERVICE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=SERVICE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    env: Literal["development", "test", "production"] = Field("development", alias="AI_ENV")
    # Logging: readable text locally, one JSON object per line in production (see logging_setup.py).
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field("INFO", alias="AI_LOG_LEVEL")
    log_format_override: Literal["text", "json"] | None = Field(None, alias="AI_LOG_FORMAT")

    # Postgres with the pgvector extension. Optional so the service can still
    # start (and report "not ready") when the database is missing.
    database_url: SecretStr | None = Field(None, alias="AI_DATABASE_URL")
    db_pool_min: int = Field(1, ge=0, alias="AI_DB_POOL_MIN")
    db_pool_max: int = Field(5, ge=1, alias="AI_DB_POOL_MAX")
    # Upper bound for connecting and for each query, so a hung database
    # cannot hold a request open forever.
    db_timeout_seconds: float = Field(3.0, gt=0, alias="AI_DB_TIMEOUT_SECONDS")

    # ---- LLM providers. Keys are optional so the service and tests run without them.
    groq_api_key: SecretStr | None = Field(None, alias="GROQ_API_KEY")
    groq_model: str = Field("openai/gpt-oss-120b", alias="GROQ_MODEL")
    gemini_api_key: SecretStr | None = Field(None, alias="GEMINI_API_KEY")
    gemini_model: str = Field("gemini-3.5-flash-lite", alias="GEMINI_MODEL")
    gemini_embedding_model: str = Field("gemini-embedding-001", alias="GEMINI_EMBEDDING_MODEL")
    # Must match the vector(768) column in db/migrations/0001_knowledge_base.sql.
    embedding_dimensions: int = Field(768, gt=0, alias="EMBEDDING_DIMENSIONS")
    # The free tier counts each embedded text against a per-minute quota. Stay just under it.
    gemini_embed_texts_per_minute: int = Field(90, ge=1, alias="GEMINI_EMBED_TEXTS_PER_MINUTE")

    # ---- RAG tuning
    knowledge_dir: Path = Field(SERVICE_DIR / "knowledge", alias="RAG_KNOWLEDGE_DIR")
    chunk_max_tokens: int = Field(350, ge=50, alias="RAG_CHUNK_MAX_TOKENS")
    chunk_overlap_tokens: int = Field(60, ge=0, alias="RAG_CHUNK_OVERLAP_TOKENS")
    retrieval_top_k: int = Field(5, ge=1, le=20, alias="RAG_TOP_K")
    # Weight of keyword results in hybrid fusion (vector = 1.0). 0.5 scored best on the
    # evaluation set: MRR 0.97 vs 0.95 at 1.0 (one more question ranked first out of 36).
    keyword_weight: float = Field(0.5, ge=0, le=2, alias="RAG_KEYWORD_WEIGHT")

    # ---- Assistant (step 3)
    # Kill switch: false makes /v1/ask return 503 without calling any provider.
    ai_enabled: bool = Field(True, alias="AI_ENABLED")
    # Flask validates tokens (signature, expiry, logout/revocation) via GET /me.
    flask_api_url: str = Field("http://127.0.0.1:5000", alias="FLASK_API_URL")
    # Browser origins allowed to call the API (comma-separated). The React dev server by
    # default; production adds the Vercel URL (the owner sets it on the host).
    cors_origins: str = Field("http://localhost:3000", alias="AI_CORS_ORIGINS")
    # My-data mode: timeout for each read from Flask's GET endpoints.
    flask_data_timeout_seconds: float = Field(5.0, gt=0, le=30, alias="FLASK_DATA_TIMEOUT_SECONDS")
    auth_cache_seconds: float = Field(30.0, ge=0, le=300, alias="AUTH_CACHE_SECONDS")
    llm_timeout_seconds: float = Field(20.0, gt=0, alias="LLM_TIMEOUT_SECONDS")
    # Output budget per answer. gpt-oss reasoning tokens count against it too.
    answer_max_tokens: int = Field(700, ge=100, le=4000, alias="ANSWER_MAX_TOKENS")
    # How much retrieved text may go into one prompt (estimated tokens).
    context_max_tokens: int = Field(1800, ge=200, le=8000, alias="CONTEXT_MAX_TOKENS")
    # Best vector similarity below this means "not covered": answer without calling an LLM.
    # Calibrated on 2026-11-24: real questions >= 0.623, off-topic <= 0.600.
    min_relevance: float = Field(0.61, ge=0, le=1, alias="RAG_MIN_RELEVANCE")
    question_max_chars: int = Field(500, ge=20, le=4000, alias="QUESTION_MAX_CHARS")
    daily_request_limit: int = Field(50, ge=1, alias="ASSISTANT_DAILY_REQUESTS")
    daily_token_limit: int = Field(60000, ge=1000, alias="ASSISTANT_DAILY_TOKENS")
    requests_per_minute: int = Field(6, ge=1, alias="ASSISTANT_REQUESTS_PER_MINUTE")
    # Testing phase (Nov 26): false switches OFF the two per-user DAILY caps above (usage is
    # still counted and shown). The per-minute limit stays on. Turn back on for production.
    limits_enabled: bool = Field(True, alias="ASSISTANT_LIMITS_ENABLED")
    # Groq free tier for gpt-oss-120b: 200,000 tokens per day for the whole account (Groq's
    # rate-limit table; recorded in AI_AND_RAG.md). With the caps off, the panel's "% left"
    # is measured against this, across all users.
    groq_daily_tokens: int = Field(200000, ge=1000, alias="GROQ_FREE_DAILY_TOKENS")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.cors_origins.split(",") if o.strip()]

    @property
    def log_format(self) -> str:
        return self.log_format_override or ("json" if self.env == "production" else "text")

    @property
    def docs_enabled(self) -> bool:
        # The interactive API docs are a map of the API, so they stay off in production.
        return self.env != "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()

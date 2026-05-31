"""Application configuration loaded from environment variables."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DEV_SECRET = "dev-secret-change-me"
SUPPORTED_RAG_CHUNKING_MODES = {"structured", "hybrid_semantic"}


def env_bool(name, default=False):
    """Return a boolean environment variable value."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name, default):
    """Return an integer environment variable value."""
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


def env_float(name, default):
    """Return a float environment variable value."""
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc


def validate_runtime_config(config):
    """Validate high-risk runtime configuration values."""
    chunking_mode = str(config.get("RAG_CHUNKING_MODE", "hybrid_semantic")).strip().lower()
    chunk_size = config.get("RAG_CHUNK_SIZE", 1400)
    chunk_overlap = config.get("RAG_CHUNK_OVERLAP", 160)
    semantic_breakpoint_threshold = config.get("RAG_SEMANTIC_BREAKPOINT_THRESHOLD", 0.35)
    semantic_min_chars = config.get("RAG_SEMANTIC_MIN_CHUNK_CHARS", 600)
    semantic_target_chars = config.get("RAG_SEMANTIC_TARGET_CHUNK_CHARS", 1200)
    semantic_max_chars = config.get("RAG_SEMANTIC_MAX_CHUNK_CHARS", 1800)
    top_k = config.get("RAG_TOP_K", 4)
    rerank_candidate_limit = config.get("RAG_RERANK_CANDIDATE_LIMIT", 20)
    semantic_only_min_similarity = config.get("RAG_SEMANTIC_ONLY_MIN_SIMILARITY", 0.78)
    if chunk_size < 200:
        raise RuntimeError("RAG_CHUNK_SIZE must be at least 200")
    if chunk_overlap < 0:
        raise RuntimeError("RAG_CHUNK_OVERLAP must not be negative")
    if chunk_overlap >= chunk_size:
        raise RuntimeError("RAG_CHUNK_OVERLAP must be smaller than RAG_CHUNK_SIZE")
    if chunking_mode not in SUPPORTED_RAG_CHUNKING_MODES:
        raise RuntimeError(
            "RAG_CHUNKING_MODE must be one of " f"{sorted(SUPPORTED_RAG_CHUNKING_MODES)}"
        )
    if not 0 <= semantic_breakpoint_threshold <= 1:
        raise RuntimeError("RAG_SEMANTIC_BREAKPOINT_THRESHOLD must be between 0 and 1")
    if semantic_min_chars < 100:
        raise RuntimeError("RAG_SEMANTIC_MIN_CHUNK_CHARS must be at least 100")
    if semantic_target_chars < semantic_min_chars:
        raise RuntimeError(
            "RAG_SEMANTIC_TARGET_CHUNK_CHARS must be greater than or equal to "
            "RAG_SEMANTIC_MIN_CHUNK_CHARS"
        )
    if semantic_max_chars < semantic_target_chars:
        raise RuntimeError(
            "RAG_SEMANTIC_MAX_CHUNK_CHARS must be greater than or equal to "
            "RAG_SEMANTIC_TARGET_CHUNK_CHARS"
        )
    if top_k < 1:
        raise RuntimeError("RAG_TOP_K must be at least 1")
    if rerank_candidate_limit < top_k:
        raise RuntimeError("RAG_RERANK_CANDIDATE_LIMIT must be greater than or equal to RAG_TOP_K")
    if not 0 <= semantic_only_min_similarity <= 1:
        raise RuntimeError("RAG_SEMANTIC_ONLY_MIN_SIMILARITY must be between 0 and 1")
    if config.get("TESTING"):
        return
    if str(config.get("FLASK_ENV", "")).lower() != "production":
        return

    weak_values = {"", DEFAULT_DEV_SECRET, "change-this-secret-in-production"}
    for key in ("SECRET_KEY", "JWT_SECRET_KEY"):
        value = str(config.get(key) or "")
        if value in weak_values or len(value) < 24:
            raise RuntimeError(f"{key} must be set to a strong value in production")


class Config:
    """Application configuration loaded from environment variables."""

    SECRET_KEY = os.getenv(
        "SECRET_KEY",
        os.getenv("JWT_SECRET_KEY", DEFAULT_DEV_SECRET),
    )
    FLASK_ENV = os.getenv("FLASK_ENV", "development")
    AUTO_CREATE_DATABASE = env_bool(
        "AUTO_CREATE_DATABASE",
        default=FLASK_ENV != "production",
    )
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'data' / 'maintenance.db'}",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", DEFAULT_DEV_SECRET)
    AI_PROVIDER = os.getenv("AI_PROVIDER", "openai")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    AI_BASE_URL = os.getenv("AI_BASE_URL", "")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    OPENAI_MODEL_FAST = os.getenv("OPENAI_MODEL_FAST", OPENAI_MODEL)
    OPENAI_MODEL_BALANCED = os.getenv("OPENAI_MODEL_BALANCED", OPENAI_MODEL)
    OPENAI_MODEL_QUALITY = os.getenv("OPENAI_MODEL_QUALITY", "gpt-5-mini")
    AI_TIMEOUT_SECONDS = env_float("AI_TIMEOUT_SECONDS", 10.0)
    AI_MAX_RETRIES = env_int("AI_MAX_RETRIES", 1)
    AI_TASK_PRIORITIZATION_TIMEOUT_SECONDS = env_float(
        "AI_TASK_PRIORITIZATION_TIMEOUT_SECONDS",
        6.0,
    )
    AI_TASK_PRIORITIZATION_MAX_RETRIES = env_int(
        "AI_TASK_PRIORITIZATION_MAX_RETRIES",
        0,
    )
    AI_ENABLE_STREAMING = env_bool("AI_ENABLE_STREAMING", default=True)
    LANGFUSE_ENABLED = env_bool("LANGFUSE_ENABLED", default=False)
    LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")
    LANGFUSE_BASE_URL = os.getenv(
        "LANGFUSE_BASE_URL",
        os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
    )
    LANGFUSE_HOST = LANGFUSE_BASE_URL
    LANGFUSE_TRACING_ENVIRONMENT = os.getenv(
        "LANGFUSE_TRACING_ENVIRONMENT",
        os.getenv("LANGFUSE_ENVIRONMENT", FLASK_ENV),
    )
    LANGFUSE_ENVIRONMENT = LANGFUSE_TRACING_ENVIRONMENT
    LANGFUSE_RELEASE = os.getenv("LANGFUSE_RELEASE", "")
    GITHUB_REPOSITORY = os.getenv("GITHUB_REPOSITORY", "siinanXD/MaintanaceAIsisst")
    GITHUB_SHA = os.getenv("GITHUB_SHA", "")
    GITHUB_REF_NAME = os.getenv("GITHUB_REF_NAME", "")
    RAG_ENABLED = env_bool("RAG_ENABLED", default=True)
    RAG_VECTOR_STORE = os.getenv("RAG_VECTOR_STORE", "pgvector")
    RAG_CHUNKING_MODE = os.getenv("RAG_CHUNKING_MODE", "hybrid_semantic")
    RAG_CHUNK_SIZE = env_int("RAG_CHUNK_SIZE", 1400)
    RAG_CHUNK_OVERLAP = env_int("RAG_CHUNK_OVERLAP", 160)
    RAG_MAX_CHUNKS = env_int("RAG_MAX_CHUNKS", 80)
    RAG_SEMANTIC_BREAKPOINT_THRESHOLD = env_float(
        "RAG_SEMANTIC_BREAKPOINT_THRESHOLD",
        0.35,
    )
    RAG_SEMANTIC_MIN_CHUNK_CHARS = env_int("RAG_SEMANTIC_MIN_CHUNK_CHARS", 600)
    RAG_SEMANTIC_TARGET_CHUNK_CHARS = env_int("RAG_SEMANTIC_TARGET_CHUNK_CHARS", 1200)
    RAG_SEMANTIC_MAX_CHUNK_CHARS = env_int("RAG_SEMANTIC_MAX_CHUNK_CHARS", 1800)
    RAG_TOP_K = env_int("RAG_TOP_K", 4)
    RAG_RERANK_CANDIDATE_LIMIT = env_int("RAG_RERANK_CANDIDATE_LIMIT", 20)
    RAG_SCAN_LIMIT = env_int("RAG_SCAN_LIMIT", 300)
    RAG_MIN_SCORE = env_int("RAG_MIN_SCORE", 1)
    RAG_SCORE_DEBUG = env_bool("RAG_SCORE_DEBUG", default=False)
    RAG_SCORE_SEMANTIC_WEIGHT = env_float("RAG_SCORE_SEMANTIC_WEIGHT", 70.0)
    RAG_SCORE_LEXICAL_WEIGHT = env_float("RAG_SCORE_LEXICAL_WEIGHT", 60.0)
    RAG_SCORE_QUALITY_WEIGHT = env_float("RAG_SCORE_QUALITY_WEIGHT", 30.0)
    RAG_SCORE_RECENCY_WEIGHT = env_float("RAG_SCORE_RECENCY_WEIGHT", 15.0)
    RAG_SCORE_MACHINE_WEIGHT = env_float("RAG_SCORE_MACHINE_WEIGHT", 50.0)
    RAG_SCORE_FEEDBACK_WEIGHT = env_float("RAG_SCORE_FEEDBACK_WEIGHT", 20.0)
    RAG_SCORE_USAGE_WEIGHT = env_float("RAG_SCORE_USAGE_WEIGHT", 15.0)
    RAG_SCORE_SOURCE_PRIORITY_WEIGHT = env_float(
        "RAG_SCORE_SOURCE_PRIORITY_WEIGHT",
        15.0,
    )
    RAG_RECENCY_WINDOW_DAYS = env_int("RAG_RECENCY_WINDOW_DAYS", 90)
    RAG_AGING_OUTDATED_MULTIPLIER = env_float("RAG_AGING_OUTDATED_MULTIPLIER", 0.55)
    RAG_AGING_STALE_MULTIPLIER = env_float("RAG_AGING_STALE_MULTIPLIER", 0.65)
    RAG_AGING_OLD_MULTIPLIER = env_float("RAG_AGING_OLD_MULTIPLIER", 0.78)
    RAG_FEEDBACK_SCAN_LIMIT = env_int("RAG_FEEDBACK_SCAN_LIMIT", 300)
    RAG_SEMANTIC_ONLY_MIN_SIMILARITY = env_float(
        "RAG_SEMANTIC_ONLY_MIN_SIMILARITY",
        0.78,
    )
    KNOWLEDGE_GAP_DEDUP_HOURS = env_int("KNOWLEDGE_GAP_DEDUP_HOURS", 24)
    KNOWLEDGE_GAP_LOW_CONFIDENCE_SCORE = env_int("KNOWLEDGE_GAP_LOW_CONFIDENCE_SCORE", 35)
    KNOWLEDGE_AGING_STALE_DAYS = env_int("KNOWLEDGE_AGING_STALE_DAYS", 180)
    KNOWLEDGE_AGING_UNCONFIRMED_DAYS = env_int("KNOWLEDGE_AGING_UNCONFIRMED_DAYS", 60)
    KNOWLEDGE_AGING_STABLE_CONFIRMATIONS = env_int(
        "KNOWLEDGE_AGING_STABLE_CONFIRMATIONS",
        3,
    )
    KNOWLEDGE_AGING_STABLE_HELPFUL_FEEDBACK = env_int(
        "KNOWLEDGE_AGING_STABLE_HELPFUL_FEEDBACK",
        3,
    )
    AI_SESSION_CONTEXT_MESSAGES = env_int("AI_SESSION_CONTEXT_MESSAGES", 4)
    AI_SESSION_CONTEXT_TTL_MINUTES = env_int("AI_SESSION_CONTEXT_TTL_MINUTES", 120)
    AI_SESSION_CONTEXT_MAX_CHARS = env_int("AI_SESSION_CONTEXT_MAX_CHARS", 1400)
    RETRIEVAL_TELEMETRY_WINDOW_DAYS = env_int("RETRIEVAL_TELEMETRY_WINDOW_DAYS", 30)
    RETRIEVAL_TELEMETRY_LIMIT = env_int("RETRIEVAL_TELEMETRY_LIMIT", 10)
    RETRIEVAL_TELEMETRY_LOW_CONFIDENCE_SCORE = env_int(
        "RETRIEVAL_TELEMETRY_LOW_CONFIDENCE_SCORE",
        35,
    )
    RETRIEVAL_TELEMETRY_LOW_SOURCE_SCORE = env_float(
        "RETRIEVAL_TELEMETRY_LOW_SOURCE_SCORE",
        20.0,
    )
    EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "hashing")
    OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    RAG_HASH_EMBEDDING_DIMENSIONS = env_int("RAG_HASH_EMBEDDING_DIMENSIONS", 384)
    CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", str(BASE_DIR / "data" / "chroma"))
    CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "maintenance_knowledge")
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", str(BASE_DIR / "data" / "uploads"))
    DOCUMENTS_FOLDER = os.getenv("DOCUMENTS_FOLDER", str(BASE_DIR / "documents"))
    MANUALS_FOLDER = os.getenv("MANUALS_FOLDER", str(BASE_DIR / "manuals"))
    KNOWLEDGE_FOLDER = os.getenv("KNOWLEDGE_FOLDER", str(BASE_DIR / "knowledge"))
    BACKUP_FOLDER = os.getenv("BACKUP_FOLDER", str(BASE_DIR / "backups"))
    LOG_DIR = os.getenv("LOG_DIR", str(BASE_DIR / "logs"))
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    SLOW_REQUEST_THRESHOLD_MS = env_int("SLOW_REQUEST_THRESHOLD_MS", 500)
    MAIL_ENABLED = env_bool("MAIL_ENABLED", default=False)
    MAIL_HOST = os.getenv("MAIL_HOST", "")
    MAIL_PORT = env_int("MAIL_PORT", 587)
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
    MAIL_FROM = os.getenv("MAIL_FROM", "")
    MAIL_USE_TLS = env_bool("MAIL_USE_TLS", default=True)
    MAIL_DRY_RUN = env_bool("MAIL_DRY_RUN", default=True)
    DAILY_BRIEFING_TIME = os.getenv("DAILY_BRIEFING_TIME", "07:00")
    TASK_REMINDER_LOOKBACK_HOURS = env_int("TASK_REMINDER_LOOKBACK_HOURS", 24)
    AI_ALERT_LOOKBACK_MINUTES = env_int("AI_ALERT_LOOKBACK_MINUTES", 60)
    WORKER_RAG_REINDEX_ENABLED = env_bool("WORKER_RAG_REINDEX_ENABLED", default=False)
    WORKER_POLL_SECONDS = env_int("WORKER_POLL_SECONDS", 60)
    WORKER_JOB_LEASE_SECONDS = env_int("WORKER_JOB_LEASE_SECONDS", 900)
    WORKER_RUN_ONCE = env_bool("WORKER_RUN_ONCE", default=False)
    OPERATIONS_HASH_SECRET = os.getenv("OPERATIONS_HASH_SECRET", SECRET_KEY)
    OPERATIONS_EVENT_RETENTION_MONTHS = env_int("OPERATIONS_EVENT_RETENTION_MONTHS", 24)

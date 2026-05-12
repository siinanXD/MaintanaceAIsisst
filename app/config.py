"""Application configuration loaded from environment variables."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DEV_SECRET = "dev-secret-change-me"


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
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", DEFAULT_DEV_SECRET)
    AI_PROVIDER = os.getenv("AI_PROVIDER", "openai")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    OPENAI_MODEL_FAST = os.getenv("OPENAI_MODEL_FAST", OPENAI_MODEL)
    OPENAI_MODEL_BALANCED = os.getenv("OPENAI_MODEL_BALANCED", OPENAI_MODEL)
    OPENAI_MODEL_QUALITY = os.getenv("OPENAI_MODEL_QUALITY", "gpt-5-mini")
    AI_TIMEOUT_SECONDS = env_float("AI_TIMEOUT_SECONDS", 10.0)
    AI_MAX_RETRIES = env_int("AI_MAX_RETRIES", 1)
    AI_ENABLE_STREAMING = env_bool("AI_ENABLE_STREAMING", default=True)
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", str(BASE_DIR / "data" / "uploads"))
    DOCUMENTS_FOLDER = os.getenv("DOCUMENTS_FOLDER", str(BASE_DIR / "documents"))
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

import hashlib
import logging
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import g, request


LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"
DEFAULT_MAX_BYTES = 5 * 1024 * 1024
DEFAULT_BACKUP_COUNT = 5


def configure_logging(app):
    """Configure application logging and request monitoring."""
    log_dir = Path(app.config.get("LOG_DIR", "logs"))
    log_dir.mkdir(parents=True, exist_ok=True)

    level_name = str(app.config.get("LOG_LEVEL", "INFO")).upper()
    level = getattr(logging, level_name, logging.INFO)
    formatter = logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT)

    app_handler = RotatingFileHandler(
        log_dir / "app.log",
        maxBytes=DEFAULT_MAX_BYTES,
        backupCount=DEFAULT_BACKUP_COUNT,
        encoding="utf-8",
    )
    app_handler.setLevel(level)
    app_handler.setFormatter(formatter)

    error_handler = RotatingFileHandler(
        log_dir / "error.log",
        maxBytes=DEFAULT_MAX_BYTES,
        backupCount=DEFAULT_BACKUP_COUNT,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(level)
    stream_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    _replace_app_handlers(root_logger, [app_handler, error_handler, stream_handler])

    app.logger.setLevel(level)
    app.logger.propagate = True
    register_request_logging(app)


def _replace_app_handlers(logger, handlers):
    """Replace previously configured maintenance handlers without duplicates."""
    old_maintenance_handlers = [
        handler
        for handler in logger.handlers
        if getattr(handler, "_maintenance_handler", False)
    ]
    existing_handlers = [
        handler
        for handler in logger.handlers
        if not getattr(handler, "_maintenance_handler", False)
    ]
    for handler in old_maintenance_handlers:
        handler.close()
    for handler in handlers:
        handler._maintenance_handler = True
    logger.handlers = existing_handlers + handlers


def register_request_logging(app):
    """Register request timing logs for non-static requests."""

    @app.before_request
    def start_request_timer():
        """Store the request start time for duration logging."""
        g.request_started_at = time.perf_counter()

    @app.after_request
    def log_request(response):
        """Log request metadata and slow requests without sensitive payloads."""
        if request.endpoint == "static":
            return response

        duration_ms = request_duration_ms()
        endpoint = request.endpoint or request.path
        logging.getLogger("app.request").info(
            "request method=%s endpoint=%s status=%s duration_ms=%.2f",
            request.method,
            endpoint,
            response.status_code,
            duration_ms,
        )

        threshold_ms = float(app.config.get("SLOW_REQUEST_THRESHOLD_MS", 500))
        if duration_ms > threshold_ms:
            logging.getLogger("app.performance").warning(
                "slow_request method=%s endpoint=%s status=%s duration_ms=%.2f",
                request.method,
                endpoint,
                response.status_code,
                duration_ms,
            )
        return response


def request_duration_ms():
    """Return the current request duration in milliseconds."""
    started_at = getattr(g, "request_started_at", None)
    if started_at is None:
        return 0.0
    return (time.perf_counter() - started_at) * 1000


def safe_identifier(value):
    """Return a non-reversible short hash for a user-provided identifier."""
    normalized = str(value or "").strip().lower()
    if not normalized:
        return "missing"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]

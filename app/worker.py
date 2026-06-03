"""Background worker entry point for maintenance automation jobs."""

import logging
import signal
import time
from pathlib import Path

from app import create_app
from app.services.background_job_service import process_next_background_job

logger = logging.getLogger(__name__)
SHOULD_STOP = False


def request_shutdown(_signum, _frame):
    """Request a graceful worker shutdown from a process signal."""
    global SHOULD_STOP
    SHOULD_STOP = True


def worker_enabled(app):
    """Return whether the background worker loop should process jobs."""
    return bool(app.config.get("WORKER_RAG_REINDEX_ENABLED", False))


def poll_seconds(app):
    """Return the configured worker polling interval in seconds."""
    return max(5, int(app.config.get("WORKER_POLL_SECONDS", 60)))


def heartbeat_path(app):
    """Return the configured worker heartbeat file path."""
    configured = str(app.config.get("WORKER_HEARTBEAT_PATH") or "").strip()
    return Path(configured or "/app/data/worker_heartbeat")


def write_worker_heartbeat(app):
    """Persist a lightweight heartbeat timestamp for container health checks."""
    path = heartbeat_path(app)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(int(time.time())), encoding="utf-8")


def process_once(app):
    """Process one worker cycle and return a compact job summary."""
    if not worker_enabled(app):
        write_worker_heartbeat(app)
        return {"enabled": False, "processed": False, "reason": "worker_disabled"}
    with app.app_context():
        result = process_next_background_job()
    write_worker_heartbeat(app)
    logger.info(
        "worker_cycle processed=%s reason=%s",
        result.get("processed"),
        result.get("reason", ""),
    )
    return {"enabled": True, **result}


def run_worker():
    """Run the long-lived background worker loop."""
    app = create_app()
    interval = poll_seconds(app)
    logger.info(
        "worker_started background_jobs_enabled=%s poll_seconds=%s",
        worker_enabled(app),
        interval,
    )
    if app.config.get("WORKER_RUN_ONCE", False):
        process_once(app)
        return
    while not SHOULD_STOP:
        process_once(app)
        time.sleep(interval)
    logger.info("worker_stopped")


def main():
    """Register signal handlers and run the worker."""
    signal.signal(signal.SIGTERM, request_shutdown)
    signal.signal(signal.SIGINT, request_shutdown)
    run_worker()


if __name__ == "__main__":
    main()

"""Tests for the background worker foundation."""

from app.models import BackgroundJob
from app.services.background_job_service import enqueue_rag_reindex_job
from app.worker import poll_seconds, process_once, worker_enabled


def test_worker_disabled_returns_empty_summary(app):
    """Verify disabled worker cycles do not process RAG jobs."""
    with app.app_context():
        app.config["WORKER_RAG_REINDEX_ENABLED"] = False
        result = process_once(app)

    assert result == {"enabled": False, "processed": False, "reason": "worker_disabled"}


def test_worker_enabled_processes_queued_rag_reindex_job(app, make_user, make_task):
    """Verify enabled worker cycles process queued RAG jobs."""
    user = make_user(
        username="worker_rag_user",
        role="master_admin",
        department_name=None,
    )
    make_task(
        "Worker RAG Task",
        creator_username=user["username"],
        department_name="Instandhaltung",
        description="Worker indexiert pending RAG Quellen.",
    )

    with app.app_context():
        enqueue_rag_reindex_job(mode="stale", user=None)
        app.config["WORKER_RAG_REINDEX_ENABLED"] = True
        result = process_once(app)
        job = BackgroundJob.query.one()

    assert result["enabled"] is True
    assert result["processed"] is True
    assert job.status == "done"
    assert job.result()["indexed"] >= 1


def test_worker_configuration_helpers(app):
    """Verify worker config helpers normalize values conservatively."""
    app.config["WORKER_RAG_REINDEX_ENABLED"] = True
    app.config["WORKER_POLL_SECONDS"] = 1

    assert worker_enabled(app) is True
    assert poll_seconds(app) == 5

"""Tests for background job queue APIs and services."""

from datetime import timedelta

from app.domain_models.common import utc_now
from app.extensions import db
from app.models import BackgroundJob, KnowledgeChunk, KnowledgeDocument


def test_admin_can_queue_and_list_rag_reindex_jobs(client, make_user, auth_headers):
    """Verify admins can queue and inspect RAG reindex background jobs."""
    admin = make_user(
        username="job_admin",
        role="master_admin",
        department_name=None,
    )

    queue_response = client.post(
        "/api/v1/admin/ai/knowledge/reindex/jobs",
        headers=auth_headers(admin["username"]),
        json={"mode": "stale"},
    )
    list_response = client.get(
        "/api/v1/admin/jobs?job_type=rag_reindex",
        headers=auth_headers(admin["username"]),
    )

    queued_job = queue_response.get_json()["data"]
    jobs = list_response.get_json()["data"]["items"]
    assert queue_response.status_code == 202
    assert queued_job["job_type"] == "rag_reindex"
    assert queued_job["status"] == "queued"
    assert queued_job["payload"]["mode"] == "stale"
    assert list_response.status_code == 200
    assert jobs[0]["id"] == queued_job["id"]


def test_rag_reindex_job_validates_mode(app, client, make_user, auth_headers):
    """Verify invalid RAG job modes are rejected."""
    admin = make_user(
        username="job_bad_mode_admin",
        role="master_admin",
        department_name=None,
    )

    response = client.post(
        "/api/v1/admin/ai/knowledge/reindex/jobs",
        headers=auth_headers(admin["username"]),
        json={"mode": "invalid"},
    )

    assert response.status_code == 400
    with app.app_context():
        assert BackgroundJob.query.count() == 0


def test_admin_can_queue_knowledge_aging_job(client, make_user, auth_headers):
    """Verify admins can queue knowledge aging background jobs."""
    admin = make_user(
        username="job_aging_admin",
        role="master_admin",
        department_name=None,
    )

    queue_response = client.post(
        "/api/v1/admin/ai/knowledge/aging/jobs",
        headers=auth_headers(admin["username"]),
        json={"dry_run": True, "limit": 5},
    )

    queued_job = queue_response.get_json()["data"]
    assert queue_response.status_code == 202
    assert queued_job["job_type"] == "knowledge_aging"
    assert queued_job["payload"]["dry_run"] is True
    assert queued_job["payload"]["limit"] == 5


def test_worker_marks_failed_rag_document_job(app, make_user):
    """Verify missing document jobs end in failed state after max attempts."""
    from app.services.background_job_service import enqueue_rag_reindex_job, process_background_job

    make_user(
        username="job_failed_admin",
        role="master_admin",
        department_name=None,
    )
    with app.app_context():
        job = enqueue_rag_reindex_job(document_id=99999, user=None)
        job.max_attempts = 1
        process_background_job(job)
        job = db.session.get(BackgroundJob, job.id)

    assert job.status == "failed"
    assert "Knowledge document not found" in job.error_message


def test_worker_processes_knowledge_aging_job(app):
    """Verify knowledge aging jobs mark old reviewed documents as outdated."""
    from app.services.background_job_service import (
        enqueue_knowledge_aging_job,
        process_background_job,
    )

    with app.app_context():
        app.config["KNOWLEDGE_AGING_STALE_DAYS"] = 30
        old_timestamp = utc_now() - timedelta(days=120)
        document = KnowledgeDocument(
            source_type="upload",
            title="Job Aging AG900",
            original_filename="job-aging.txt",
            relative_path="uploads/job-aging.txt",
            content_type="text/plain",
            department="Produktion",
            status="indexed",
            quality_status="admin_approved",
            last_confirmed_at=old_timestamp,
            confirmation_count=1,
            is_public=True,
            chunk_count=1,
            created_at=old_timestamp,
            updated_at=old_timestamp,
        )
        db.session.add(document)
        db.session.flush()
        db.session.add(
            KnowledgeChunk(
                document_id=document.id,
                chunk_index=0,
                text="AG900 Hydraulik Servo Ablauf pruefen.",
                token_text="ag900 hydraulik servo ablauf pruefen",
                created_at=old_timestamp,
            )
        )
        db.session.commit()

        job = enqueue_knowledge_aging_job(user=None)
        result = process_background_job(job)
        job = db.session.get(BackgroundJob, job.id)
        refreshed = db.session.get(KnowledgeDocument, document.id)

    assert result["processed"] is True
    assert job.status == "done"
    assert job.result()["documents"] == 1
    assert refreshed.quality_status == "outdated"


def test_worker_claims_each_job_once(app):
    """Verify queued jobs are claimed once and marked running atomically."""
    from app.services.background_job_service import (
        claim_next_queued_job,
        enqueue_rag_reindex_job,
    )

    with app.app_context():
        queued = enqueue_rag_reindex_job(mode="stale", user=None)
        first_claim = claim_next_queued_job()
        second_claim = claim_next_queued_job()

    assert first_claim.id == queued.id
    assert first_claim.status == "running"
    assert first_claim.attempts == 1
    assert second_claim is None


def test_expired_running_job_is_released_for_retry(app):
    """Verify an expired worker lease makes a running job claimable again."""
    from app.services.background_job_service import (
        claim_next_queued_job,
        enqueue_rag_reindex_job,
        requeue_expired_jobs,
    )

    with app.app_context():
        app.config["WORKER_JOB_LEASE_SECONDS"] = 60
        job = enqueue_rag_reindex_job(mode="stale", user=None)
        job.status = "running"
        job.attempts = 1
        job.locked_at = utc_now() - timedelta(minutes=10)
        db.session.commit()

        released = requeue_expired_jobs()
        claimed = claim_next_queued_job()

    assert released == 1
    assert claimed.id == job.id
    assert claimed.status == "running"
    assert claimed.attempts == 2


def test_duplicate_reindex_jobs_reuse_active_job(app):
    """Verify duplicate queued RAG jobs are not inserted twice."""
    from app.services.background_job_service import enqueue_rag_reindex_job

    with app.app_context():
        first_job = enqueue_rag_reindex_job(mode="stale", user=None)
        second_job = enqueue_rag_reindex_job(mode="stale", user=None)
        job_count = BackgroundJob.query.count()

    assert second_job.id == first_job.id
    assert job_count == 1

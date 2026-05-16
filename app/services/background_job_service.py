"""Background job queue services for asynchronous maintenance workflows."""

import json
import logging
from datetime import timedelta

from flask import current_app, has_app_context
from sqlalchemy.exc import SQLAlchemyError

from app.domain_models.common import utc_now
from app.extensions import db
from app.models import BackgroundJob, KnowledgeDocument
from app.services.knowledge_service import (
    reindex_all_knowledge,
    reindex_knowledge_document,
    reindex_stale_knowledge,
)

logger = logging.getLogger(__name__)

JOB_RAG_REINDEX = "rag_reindex"
QUEUED = "queued"
RUNNING = "running"
DONE = "done"
FAILED = "failed"
RETRYING_STATUSES = (QUEUED,)
ACTIVE_STATUSES = (RUNNING,)
DEFAULT_JOB_LEASE_SECONDS = 900


def enqueue_rag_reindex_job(mode="stale", document_id=None, user=None):
    """Queue a RAG reindex job and return the persisted job."""
    normalized_mode = validate_reindex_mode(mode, document_id)
    payload = {"mode": normalized_mode}
    if document_id is not None:
        payload["document_id"] = int(document_id)
    existing = existing_active_reindex_job(payload)
    if existing:
        logger.info(
            "background_job_deduplicated id=%s type=%s payload=%s",
            existing.id,
            existing.job_type,
            payload,
        )
        return existing
    job = BackgroundJob(
        job_type=JOB_RAG_REINDEX,
        status=QUEUED,
        payload_json=json.dumps(payload, sort_keys=True),
        result_json="{}",
        error_message="",
        created_by=getattr(user, "id", None),
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.session.add(job)
    db.session.commit()
    logger.info("background_job_queued id=%s type=%s payload=%s", job.id, job.job_type, payload)
    return job


def existing_active_reindex_job(payload):
    """Return an already queued or running RAG reindex job for the payload."""
    payload_json = json.dumps(payload, sort_keys=True)
    return (
        BackgroundJob.query.filter(
            BackgroundJob.job_type == JOB_RAG_REINDEX,
            BackgroundJob.status.in_((QUEUED, RUNNING)),
            BackgroundJob.payload_json == payload_json,
        )
        .order_by(BackgroundJob.created_at.asc(), BackgroundJob.id.asc())
        .first()
    )


def validate_reindex_mode(mode, document_id=None):
    """Return a normalized RAG reindex mode or raise ValueError."""
    if document_id is not None:
        return "document"
    normalized = str(mode or "stale").strip().lower()
    if normalized not in {"all", "stale"}:
        raise ValueError("mode must be 'all' or 'stale'")
    return normalized


def list_background_jobs(args):
    """Return a filtered background job query for admin views."""
    query = BackgroundJob.query
    job_type = str(args.get("job_type") or "").strip()
    status = str(args.get("status") or "").strip()
    if job_type:
        query = query.filter(BackgroundJob.job_type == job_type)
    if status:
        query = query.filter(BackgroundJob.status == status)
    return query.order_by(BackgroundJob.created_at.desc(), BackgroundJob.id.desc())


def process_next_background_job():
    """Process the next queued job and return a worker summary."""
    recovered = requeue_expired_jobs()
    job = claim_next_queued_job()
    if not job:
        return {
            "processed": False,
            "reason": "no_queued_jobs",
            "recovered": recovered,
        }
    return process_background_job(job)


def next_queued_job():
    """Return the oldest queued background job, if one exists."""
    return (
        BackgroundJob.query.filter(BackgroundJob.status.in_(RETRYING_STATUSES))
        .order_by(BackgroundJob.created_at.asc(), BackgroundJob.id.asc())
        .first()
    )


def claim_next_queued_job():
    """Atomically claim the oldest queued job for this worker process."""
    now = utc_now()
    query = BackgroundJob.query.filter(BackgroundJob.status.in_(RETRYING_STATUSES))
    if _supports_skip_locked():
        query = query.with_for_update(skip_locked=True)
    job = query.order_by(BackgroundJob.created_at.asc(), BackgroundJob.id.asc()).first()
    if not job:
        return None

    job.status = RUNNING
    job.attempts += 1
    job.locked_at = now
    job.started_at = now
    job.error_message = ""
    job.updated_at = now
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        logger.exception("background_job_claim_failed")
        return None
    logger.info("background_job_claimed id=%s type=%s", job.id, job.job_type)
    return job


def requeue_expired_jobs():
    """Move running jobs with an expired lease back into the queue."""
    cutoff = utc_now() - timedelta(seconds=job_lease_seconds())
    jobs = (
        BackgroundJob.query.filter(
            BackgroundJob.status.in_(ACTIVE_STATUSES),
            BackgroundJob.locked_at.isnot(None),
            BackgroundJob.locked_at < cutoff,
        )
        .order_by(BackgroundJob.locked_at.asc(), BackgroundJob.id.asc())
        .all()
    )
    if not jobs:
        return 0

    now = utc_now()
    for job in jobs:
        job.status = QUEUED if job.attempts < job.max_attempts else FAILED
        job.locked_at = None
        job.started_at = None if job.status == QUEUED else job.started_at
        job.finished_at = now if job.status == FAILED else None
        job.error_message = "Job lease expired and was released for retry."
        job.updated_at = now
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        logger.exception("background_job_requeue_expired_failed")
        return 0
    logger.warning("background_jobs_requeued count=%s", len(jobs))
    return len(jobs)


def job_lease_seconds():
    """Return the worker job lease duration in seconds."""
    if not has_app_context():
        return DEFAULT_JOB_LEASE_SECONDS
    try:
        value = int(
            current_app.config.get(
                "WORKER_JOB_LEASE_SECONDS",
                DEFAULT_JOB_LEASE_SECONDS,
            )
        )
    except (TypeError, ValueError):
        return DEFAULT_JOB_LEASE_SECONDS
    return max(60, value)


def _supports_skip_locked():
    """Return whether the active database dialect supports skip-locked claims."""
    return db.engine.dialect.name == "postgresql"


def process_background_job(job):
    """Run one background job and persist its final state."""
    if job.status != RUNNING or not job.locked_at:
        job.status = RUNNING
        job.attempts += 1
        job.locked_at = utc_now()
        job.started_at = job.locked_at
        job.error_message = ""
        job.updated_at = utc_now()
        db.session.commit()
    try:
        result = execute_job(job)
    except Exception as exc:
        logger.exception("background_job_failed id=%s type=%s", job.id, job.job_type)
        mark_job_failed(job, exc)
        return {"processed": True, "job": job.to_dict()}

    job.status = DONE
    job.result_json = json.dumps(result)
    job.locked_at = None
    job.finished_at = utc_now()
    job.updated_at = utc_now()
    db.session.commit()
    logger.info("background_job_done id=%s type=%s", job.id, job.job_type)
    return {"processed": True, "job": job.to_dict()}


def execute_job(job):
    """Execute a supported background job and return its result payload."""
    if job.job_type == JOB_RAG_REINDEX:
        return execute_rag_reindex_job(job.payload())
    raise ValueError(f"Unsupported background job type: {job.job_type}")


def execute_rag_reindex_job(payload):
    """Execute a RAG reindex job from a stored payload."""
    mode = validate_reindex_mode(payload.get("mode"), payload.get("document_id"))
    if mode == "document":
        document = db.session.get(KnowledgeDocument, int(payload["document_id"]))
        if not document:
            raise ValueError("Knowledge document not found")
        return reindex_knowledge_document(document)
    if mode == "all":
        return reindex_all_knowledge()
    return reindex_stale_knowledge()


def mark_job_failed(job, exc):
    """Persist a failed job state with retry awareness."""
    job.error_message = str(exc)[:1000]
    job.status = QUEUED if job.attempts < job.max_attempts else FAILED
    job.locked_at = None
    if job.status == FAILED:
        job.finished_at = utc_now()
    else:
        job.started_at = None
        job.finished_at = None
    job.updated_at = utc_now()
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        logger.exception("background_job_failure_persist_failed id=%s", job.id)

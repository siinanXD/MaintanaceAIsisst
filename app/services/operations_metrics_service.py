"""Operations metrics for production readiness and admin diagnostics."""

import time
from datetime import UTC, timedelta

from flask import current_app
from sqlalchemy import func, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.logging import request_metrics_snapshot
from app.domain_models.common import utc_now
from app.extensions import db
from app.models import AIAuditEvent, BackgroundJob
from app.services.knowledge_service import knowledge_index_status


def operations_metrics():
    """Return compact runtime metrics for database, queue, AI, RAG and requests."""
    return {
        "database": database_latency_metrics(),
        "background_jobs": background_job_metrics(),
        "ai": ai_metrics(),
        "rag": rag_metrics(),
        "requests": {
            "slow_endpoints": request_metrics_snapshot(limit=10),
        },
        "generated_at": utc_now().isoformat(),
    }


def database_latency_metrics():
    """Return database readiness and SELECT latency in milliseconds."""
    started_at = time.perf_counter()
    try:
        with db.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        return {
            "ok": False,
            "dialect": db.engine.url.get_backend_name(),
            "latency_ms": None,
            "error": exc.__class__.__name__,
        }
    return {
        "ok": True,
        "dialect": db.engine.url.get_backend_name(),
        "latency_ms": round((time.perf_counter() - started_at) * 1000, 2),
    }


def background_job_metrics():
    """Return queue depth, oldest queued age and recent job duration metrics."""
    status_counts = {
        status: count
        for status, count in db.session.query(BackgroundJob.status, func.count(BackgroundJob.id))
        .group_by(BackgroundJob.status)
        .all()
    }
    type_counts = {
        job_type: count
        for job_type, count in db.session.query(
            BackgroundJob.job_type,
            func.count(BackgroundJob.id),
        )
        .group_by(BackgroundJob.job_type)
        .all()
    }
    oldest_queued = (
        BackgroundJob.query.filter(BackgroundJob.status == "queued")
        .order_by(BackgroundJob.created_at.asc(), BackgroundJob.id.asc())
        .first()
    )
    recent_jobs = (
        BackgroundJob.query.filter(BackgroundJob.finished_at.isnot(None))
        .order_by(BackgroundJob.finished_at.desc(), BackgroundJob.id.desc())
        .limit(100)
        .all()
    )
    durations = [
        _duration_seconds(job.started_at, job.finished_at)
        for job in recent_jobs
        if job.started_at and job.finished_at
    ]
    return {
        "status_counts": status_counts,
        "type_counts": type_counts,
        "queue_length": status_counts.get("queued", 0),
        "running": status_counts.get("running", 0),
        "failed": status_counts.get("failed", 0),
        "oldest_queued_age_seconds": _age_seconds(oldest_queued.created_at) if oldest_queued else 0,
        "recent_avg_duration_seconds": round(sum(durations) / len(durations), 2)
        if durations
        else 0,
        "recent_max_duration_seconds": round(max(durations), 2) if durations else 0,
        "lease_seconds": int(current_app.config.get("WORKER_JOB_LEASE_SECONDS", 900)),
    }


def ai_metrics(days=7):
    """Return AI latency, token and cost metrics for a recent time window."""
    since = utc_now() - timedelta(days=max(1, int(days or 7)))
    query = AIAuditEvent.query.filter(AIAuditEvent.created_at >= since)
    count = query.count()
    aggregates = query.with_entities(
        func.coalesce(func.avg(AIAuditEvent.latency_ms), 0),
        func.coalesce(func.sum(AIAuditEvent.total_tokens), 0),
        func.coalesce(func.sum(AIAuditEvent.estimated_cost_usd), 0.0),
    ).one()
    fallback_count = query.filter(AIAuditEvent.fallback_used.is_(True)).count()
    return {
        "window_days": days,
        "events": count,
        "avg_latency_ms": round(float(aggregates[0] or 0), 2),
        "total_tokens": int(aggregates[1] or 0),
        "estimated_cost_usd": round(float(aggregates[2] or 0.0), 6),
        "fallback_count": fallback_count,
    }


def rag_metrics():
    """Return RAG index scale and stale-source diagnostics."""
    status = knowledge_index_status()
    documents = status.get("documents", 0) or 0
    stale = status.get("stale", 0) or 0
    vector_status = status.get("vector_store", {}) or {}
    return {
        "documents": documents,
        "indexed": status.get("indexed", 0),
        "stale": stale,
        "pending": status.get("pending", 0),
        "chunks": status.get("chunks", 0),
        "stale_ratio": round(stale / documents, 4) if documents else 0,
        "vector_store": status.get("diagnostics", {}).get("vector_store", "local"),
        "vector_sync": {
            "store": vector_status.get("store"),
            "reindex_recommended": bool(vector_status.get("reindex_recommended")),
            "missing_chunk_count": vector_status.get("missing_chunk_count", 0),
            "chunk_mismatch_count": vector_status.get("chunk_mismatch_count", 0),
            "vector_sync_failure_count": vector_status.get(
                "vector_sync_failure_count",
                0,
            ),
        },
        "source_counts": status.get("source_counts", {}),
    }


def _age_seconds(value):
    """Return the age of a datetime in seconds."""
    now = _naive_utc(utc_now())
    return round((now - _naive_utc(value)).total_seconds(), 2)


def _duration_seconds(started_at, finished_at):
    """Return a duration in seconds for datetimes from any supported dialect."""
    return (_naive_utc(finished_at) - _naive_utc(started_at)).total_seconds()


def _naive_utc(value):
    """Return a timezone-naive UTC datetime for arithmetic across DB dialects."""
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)

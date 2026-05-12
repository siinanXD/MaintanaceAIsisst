"""Global security audit helpers for administrative changes."""

import json
from datetime import datetime

from flask import has_request_context, request
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import AuditLogEntry

SENSITIVE_KEYS = {
    "access_token",
    "api_key",
    "authorization",
    "jwt_secret_key",
    "openai_api_key",
    "password",
    "password_hash",
    "secret",
    "secret_key",
    "token",
}


def create_audit_log(
    actor,
    action,
    resource_type,
    resource_id="",
    before=None,
    after=None,
    commit=False,
):
    """Persist one security-relevant audit log entry."""
    entry = AuditLogEntry(
        actor_id=getattr(actor, "id", None),
        action=str(action or "unknown")[:80],
        resource_type=str(resource_type or "unknown")[:80],
        resource_id=str(resource_id or "")[:120],
        before_json=_json_dump(redact_sensitive(before or {})),
        after_json=_json_dump(redact_sensitive(after or {})),
        ip_address=_request_ip(),
        user_agent=_request_user_agent(),
    )
    db.session.add(entry)
    try:
        db.session.flush()
        if commit:
            db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise
    return entry


def audit_log_query(filters):
    """Return audit entries filtered by request query parameters."""
    query = AuditLogEntry.query
    q = str(filters.get("q") or "").strip()
    if q:
        needle = f"%{q}%"
        query = query.filter(
            db.or_(
                AuditLogEntry.action.ilike(needle),
                AuditLogEntry.resource_type.ilike(needle),
                AuditLogEntry.resource_id.ilike(needle),
                AuditLogEntry.user_agent.ilike(needle),
            )
        )
    actor_id = str(filters.get("actor_id") or "").strip()
    if actor_id:
        query = query.filter(AuditLogEntry.actor_id == int(actor_id))
    action = str(filters.get("action") or "").strip()
    if action:
        query = query.filter(AuditLogEntry.action == action)
    resource_type = str(filters.get("resource_type") or "").strip()
    if resource_type:
        query = query.filter(AuditLogEntry.resource_type == resource_type)
    date_from = str(filters.get("date_from") or "").strip()
    if date_from:
        query = query.filter(AuditLogEntry.created_at >= _parse_datetime(date_from))
    date_to = str(filters.get("date_to") or "").strip()
    if date_to:
        query = query.filter(AuditLogEntry.created_at <= _parse_datetime(date_to))
    return query.order_by(AuditLogEntry.created_at.desc(), AuditLogEntry.id.desc())


def redact_sensitive(value):
    """Return a copy of value with known sensitive fields redacted."""
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            normalized = str(key).lower()
            if normalized in SENSITIVE_KEYS or any(part in normalized for part in SENSITIVE_KEYS):
                result[key] = "[redacted]"
            else:
                result[key] = redact_sensitive(item)
        return result
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    return value


def _json_dump(value):
    """Serialize audit data to compact JSON text."""
    return json.dumps(value or {}, ensure_ascii=True, sort_keys=True, default=str)


def _parse_datetime(value):
    """Parse an ISO date or date-time value for audit filters."""
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("date_from and date_to must be ISO date-time values") from exc


def _request_ip():
    """Return the current request IP address if a request is active."""
    if not has_request_context():
        return ""
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()[:80]
    return (request.remote_addr or "")[:80]


def _request_user_agent():
    """Return the current request user-agent if a request is active."""
    if not has_request_context():
        return ""
    return str(request.user_agent or "")[:300]

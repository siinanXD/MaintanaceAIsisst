"""Quality-status workflow for AI knowledge documents."""

import logging

from sqlalchemy.exc import SQLAlchemyError

from app.domain_models.common import Role, utc_now
from app.extensions import db

logger = logging.getLogger(__name__)

KNOWLEDGE_QUALITY_STATUSES = {
    "draft",
    "ai_suggested",
    "technician_confirmed",
    "admin_approved",
    "outdated",
    "rejected",
}
AI_SUGGESTED_SOURCE_TYPES = {"generated_document"}
TECHNICIAN_STATUSES = {"technician_confirmed", "outdated"}


def default_quality_status_for_source(source_type):
    """Return the initial quality status for a knowledge source type."""
    if str(source_type or "").strip() in AI_SUGGESTED_SOURCE_TYPES:
        return "ai_suggested"
    return "draft"


def change_knowledge_quality_status(document, requested_status, user):
    """Persist a validated quality-status transition for a knowledge document."""
    try:
        next_status = normalize_quality_status(requested_status)
        validate_quality_status_permission(document, next_status, user)
        previous_status = document.quality_status or default_quality_status_for_source(
            document.source_type
        )
        document.quality_status = next_status
        document.updated_at = utc_now()
        db.session.commit()
        logger.info(
            "knowledge_quality_status_changed document_id=%s from=%s to=%s user_id=%s",
            document.id,
            previous_status,
            next_status,
            getattr(user, "id", None),
        )
        return document.to_dict(), None, 200
    except ValueError as exc:
        db.session.rollback()
        return None, {"error": str(exc)}, 400
    except PermissionError as exc:
        db.session.rollback()
        return None, {"error": str(exc)}, 403
    except SQLAlchemyError:
        db.session.rollback()
        logger.exception(
            "knowledge_quality_status_update_failed document_id=%s user_id=%s",
            getattr(document, "id", None),
            getattr(user, "id", None),
        )
        return None, {"error": "Database error while updating knowledge quality status"}, 500


def normalize_quality_status(value):
    """Return a normalized supported quality status or raise ValueError."""
    status = str(value or "").strip().lower()
    if status not in KNOWLEDGE_QUALITY_STATUSES:
        valid = ", ".join(sorted(KNOWLEDGE_QUALITY_STATUSES))
        raise ValueError(f"quality_status must be one of: {valid}")
    return status


def validate_quality_status_permission(document, requested_status, user):
    """Raise PermissionError when a user cannot assign the requested status."""
    if not user:
        raise PermissionError("Forbidden")
    if requested_status == "admin_approved" and user.role != Role.MASTER_ADMIN:
        raise PermissionError("Only master admins may approve knowledge entries")
    if user.role == Role.MASTER_ADMIN:
        return
    if user.role == Role.INSTANDHALTUNG and requested_status in TECHNICIAN_STATUSES:
        if _same_department_or_unscoped(document, user):
            return
        raise PermissionError("Technicians may only update knowledge for their department")
    raise PermissionError("Forbidden")


def mark_quality_outdated_if_reviewed(document):
    """Mark previously reviewed knowledge as outdated after source content changes."""
    if not document:
        return
    if document.quality_status in {"technician_confirmed", "admin_approved"}:
        document.quality_status = "outdated"


def _same_department_or_unscoped(document, user):
    """Return whether a document is unscoped or belongs to the user's department."""
    document_department = str(getattr(document, "department", "") or "").strip().lower()
    if not document_department:
        return True
    user_department = ""
    if getattr(user, "department", None):
        user_department = str(user.department.name or "").strip().lower()
    return document_department == user_department

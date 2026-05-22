"""Services for manually maintained assistant training entries."""

import re

from sqlalchemy.exc import SQLAlchemyError

from app.domain_models.common import utc_now
from app.extensions import db
from app.models import AssistantTrainingEntry
from app.services.knowledge_service import (
    delete_source_knowledge_document,
    mark_training_entry_knowledge_stale,
)
from app.services.maintenance_tag_service import suggest_tags_for_knowledge_payload
from app.services.missing_information_service import missing_information_for_knowledge_entry
from app.services.payload_parsing_service import parse_bool

MAX_TITLE_LENGTH = 220
MAX_QUESTION_LENGTH = 1000
MAX_ANSWER_LENGTH = 6000
MAX_KEYWORDS_LENGTH = 1000
MAX_CATEGORY_LENGTH = 80
MAX_DEPARTMENT_LENGTH = 120
DEFAULT_CATEGORY = "wartung"
DEFAULT_PRIORITY = 50


def list_training_entries(args):
    """Return filtered assistant training entries for admin views."""
    query = AssistantTrainingEntry.query
    q = str(args.get("q") or "").strip()
    category = str(args.get("category") or "").strip()
    department = str(args.get("department") or "").strip()
    active = str(args.get("active") or "").strip().lower()
    if q:
        pattern = f"%{q}%"
        query = query.filter(
            (AssistantTrainingEntry.title.ilike(pattern))
            | (AssistantTrainingEntry.question.ilike(pattern))
            | (AssistantTrainingEntry.answer.ilike(pattern))
            | (AssistantTrainingEntry.keywords.ilike(pattern))
        )
    if category:
        query = query.filter(AssistantTrainingEntry.category == category)
    if department:
        query = query.filter(AssistantTrainingEntry.department == department)
    if active in {"true", "1", "yes", "on"}:
        query = query.filter(AssistantTrainingEntry.is_active.is_(True))
    elif active in {"false", "0", "no", "off"}:
        query = query.filter(AssistantTrainingEntry.is_active.is_(False))
    return query.order_by(
        AssistantTrainingEntry.priority.desc(),
        AssistantTrainingEntry.updated_at.desc(),
        AssistantTrainingEntry.id.desc(),
    )


def create_training_entry(data, user):
    """Create a manual assistant training entry and register it for indexing."""
    try:
        payload = normalize_training_payload(data, partial=False)
        entry = AssistantTrainingEntry(created_by=user.id, **payload)
        db.session.add(entry)
        db.session.flush()
        mark_training_entry_knowledge_stale(entry)
        db.session.commit()
        result = entry.to_dict()
        result["missing_information"] = missing_information_for_knowledge_entry(result, user)
        result["tag_suggestions"] = suggest_tags_for_knowledge_payload(result)
        return result, None, 201
    except ValueError as exc:
        db.session.rollback()
        return (
            None,
            {
                "error": str(exc),
                "missing_information": missing_information_for_knowledge_entry(data, user),
            },
            400,
        )
    except SQLAlchemyError:
        db.session.rollback()
        return None, {"error": "Database error while saving training entry"}, 500


def update_training_entry(entry, data):
    """Update a manual assistant training entry and mark its index stale."""
    try:
        payload = normalize_training_payload(data, partial=True)
        if not payload:
            raise ValueError("at least one field is required")
        for field_name, value in payload.items():
            setattr(entry, field_name, value)
        entry.updated_at = utc_now()
        mark_training_entry_knowledge_stale(entry)
        db.session.commit()
        result = entry.to_dict()
        result["missing_information"] = missing_information_for_knowledge_entry(result)
        result["tag_suggestions"] = suggest_tags_for_knowledge_payload(result)
        return result, None, 200
    except ValueError as exc:
        db.session.rollback()
        payload = entry.to_dict()
        payload.update(data if isinstance(data, dict) else {})
        return (
            None,
            {
                "error": str(exc),
                "missing_information": missing_information_for_knowledge_entry(payload),
            },
            400,
        )
    except SQLAlchemyError:
        db.session.rollback()
        return None, {"error": "Database error while updating training entry"}, 500


def delete_training_entry(entry):
    """Delete a manual assistant training entry and its knowledge document."""
    try:
        entry_id = entry.id
        delete_source_knowledge_document("manual_training", entry.id)
        db.session.delete(entry)
        db.session.commit()
        return {"id": entry_id}, None, 200
    except SQLAlchemyError:
        db.session.rollback()
        return None, {"error": "Database error while deleting training entry"}, 500


def normalize_training_payload(data, partial=False):
    """Validate and normalize an assistant training payload."""
    if not isinstance(data, dict):
        raise ValueError("JSON body must be an object")
    payload = {}
    text_fields = {
        "title": MAX_TITLE_LENGTH,
        "question": MAX_QUESTION_LENGTH,
        "answer": MAX_ANSWER_LENGTH,
        "category": MAX_CATEGORY_LENGTH,
        "department": MAX_DEPARTMENT_LENGTH,
    }
    required_fields = {"title", "question", "answer"} if not partial else set()
    for field_name, max_length in text_fields.items():
        if field_name not in data:
            if field_name == "category" and not partial:
                payload[field_name] = DEFAULT_CATEGORY
            elif field_name == "department" and not partial:
                payload[field_name] = ""
            continue
        payload[field_name] = normalize_text_field(
            data.get(field_name),
            field_name,
            max_length,
            required=field_name in required_fields,
        )
    for required_field in required_fields:
        if not payload.get(required_field):
            raise ValueError(f"{required_field} is required")
    if "keywords" in data or not partial:
        payload["keywords"] = normalize_keywords(data.get("keywords", ""))
    if "is_active" in data or not partial:
        payload["is_active"] = parse_bool(data.get("is_active"), default=True)
    if "priority" in data or not partial:
        payload["priority"] = parse_priority(data.get("priority", DEFAULT_PRIORITY))
    if not payload.get("category") and not partial:
        payload["category"] = DEFAULT_CATEGORY
    return payload


def normalize_text_field(value, field_name, max_length, required=False):
    """Return a stripped text field or raise a validation error."""
    text = str(value or "").strip()
    if required and not text:
        raise ValueError(f"{field_name} is required")
    if len(text) > max_length:
        raise ValueError(f"{field_name} must be at most {max_length} characters")
    return text


def normalize_keywords(value):
    """Return a normalized comma-separated keyword string."""
    if isinstance(value, list | tuple | set):
        raw_items = [str(item or "") for item in value]
    else:
        raw_items = re.split(r"[,;\n]+", str(value or ""))
    keywords = []
    seen = set()
    for item in raw_items:
        keyword = " ".join(item.strip().split())
        key = keyword.lower()
        if not keyword or key in seen:
            continue
        seen.add(key)
        keywords.append(keyword)
    text = ", ".join(keywords)
    if len(text) > MAX_KEYWORDS_LENGTH:
        raise ValueError(f"keywords must be at most {MAX_KEYWORDS_LENGTH} characters")
    return text


def parse_priority(value):
    """Parse a bounded training priority."""
    try:
        priority = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("priority must be an integer between 0 and 100") from exc
    if priority < 0 or priority > 100:
        raise ValueError("priority must be an integer between 0 and 100")
    return priority

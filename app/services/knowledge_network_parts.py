"""Build read-only maintenance knowledge network data for admin explainability."""

# ruff: noqa: F401

from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import (
    ErrorEntry,
    GeneratedDocument,
    InventoryMaterial,
    KnowledgeDocument,
    KnowledgeGap,
    Machine,
    MachineManual,
    MaintenancePlan,
    Task,
)
from app.services.knowledge_service import can_user_read_knowledge_document, source_url
from app.services.recurring_issue_service import analyze_recurring_issues
from app.services.technical_entity_service import extract_technical_entities

DEFAULT_DAYS = 30
DEFAULT_LIMIT = 120
DEFAULT_EDGE_LIMIT = 240
MAX_DAYS = 365
MAX_LIMIT = 200
MAX_EDGE_LIMIT = 400
MAX_DOCUMENT_SCAN = 300
MAX_GAP_SCAN = 50
MAX_ENTITY_VALUES = 8
MAX_RECURRING_ISSUES = 12

QUALITY_WEIGHTS = {
    "admin_approved": 4.0,
    "technician_confirmed": 3.0,
    "ai_suggested": 2.0,
    "draft": 1.0,
    "outdated": 0.5,
    "low_quality": 0.35,
    "duplicate": 0.3,
    "rejected": 0.25,
}

TYPE_ORDER = {
    "machine": 1,
    "error": 2,
    "solution": 3,
    "document": 4,
    "task": 5,
    "inventory_part": 6,
    "recurring_issue": 7,
    "knowledge_gap": 8,
    "component": 9,
    "sensor": 10,
}

FOCUS_TYPES = {
    "machine",
    "error",
    "task",
    "document",
    "inventory_part",
    "knowledge_gap",
    "recurring_issue",
}

DIRECT_EDGE_WEIGHT = 8.0
ENTITY_EDGE_WEIGHT = 2.5
QUALITY_EDGE_FACTOR = 0.4


def _network_filters(args):
    """Return validated network query filters from request args."""
    return {
        "q": _clean_filter(args.get("q")),
        "source_type": _clean_filter(args.get("source_type")),
        "quality_status": _clean_filter(args.get("quality_status")),
        "focus": _clean_filter(args.get("focus")),
        "focus_type": _focus_type(args.get("focus_type")),
        "days": _parse_bounded_int(args.get("days"), DEFAULT_DAYS, 1, MAX_DAYS, "days"),
        "limit": _parse_bounded_int(args.get("limit"), DEFAULT_LIMIT, 1, MAX_LIMIT, "limit"),
        "edge_limit": _parse_bounded_int(
            args.get("edge_limit"),
            DEFAULT_EDGE_LIMIT,
            1,
            MAX_EDGE_LIMIT,
            "edge_limit",
        ),
    }


def _parse_bounded_int(value, default, minimum, maximum, field_name):
    """Parse and validate a bounded integer query value."""
    if value in (None, ""):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an integer") from exc
    if parsed < minimum or parsed > maximum:
        raise ValueError(f"{field_name} must be between {minimum} and {maximum}")
    return parsed


def _clean_filter(value):
    """Return a trimmed query-filter value."""
    return " ".join(str(value or "").strip().split())


def _focus_type(value):
    """Return a validated optional focus node type."""
    cleaned = _clean_filter(value)
    if not cleaned:
        return ""
    if cleaned not in FOCUS_TYPES:
        raise ValueError("focus_type is not supported")
    return cleaned


def _quality_weight(quality_status):
    """Return the ranking weight for a knowledge quality status."""
    return QUALITY_WEIGHTS.get(str(quality_status or "").strip(), 1.0)


def _safe_title(value, max_length=140):
    """Return a single-line prompt-safe label."""
    cleaned = " ".join(str(value or "").strip().split())
    if len(cleaned) <= max_length:
        return cleaned
    return f"{cleaned[: max_length - 3].rstrip()}..."


def _group_label(node_type):
    """Return a human-readable group label for one network node type."""
    labels = {
        "machine": "Maschinen",
        "error": "Fehler",
        "solution": "Loesungen",
        "document": "Dokumente",
        "task": "Tasks",
        "inventory_part": "Inventarteile",
        "recurring_issue": "Wiederkehrende Probleme",
        "knowledge_gap": "Knowledge-Gaps",
        "component": "Komponenten",
        "sensor": "Sensorik",
    }
    return labels.get(node_type, node_type)


def _enum_value(value):
    """Return a stable string for enum-like values."""
    return getattr(value, "value", value)


def _slug(value):
    """Return a stable lowercase id fragment."""
    slug = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")
    return slug or "unknown"


def _name_key(value):
    """Return a normalized comparison key for names and labels."""
    return " ".join(str(value or "").strip().lower().split())


def _code_key(value):
    """Return a normalized comparison key for error codes."""
    return "".join(character for character in str(value or "").upper() if character.isalnum())


def _edge_id(source, target, edge_type):
    """Return a compact stable edge id."""
    return _slug(f"{source}-{target}-{edge_type}")


def _merge_unique(existing, additions):
    """Return a stable list with unique values preserving order."""
    values = list(existing or [])
    for item in additions or []:
        if item and item not in values:
            values.append(item)
    return values


def _dedupe_relations(relations):
    """Return unique relation tuples while preserving their first explanation."""
    seen = set()
    unique_relations = []
    for target_node_id, edge_label, signals in relations:
        key = (target_node_id, edge_label)
        if key in seen:
            continue
        seen.add(key)
        unique_relations.append((target_node_id, edge_label, signals))
    return unique_relations


def _iso_or_none(value):
    """Return an ISO timestamp or None."""
    return value.isoformat() if value else None


__all__ = [name for name in globals() if not name.startswith("__")]

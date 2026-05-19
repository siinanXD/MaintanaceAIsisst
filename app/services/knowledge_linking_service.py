"""Entity-based linking between existing knowledge sources."""

from __future__ import annotations

from collections import Counter

from sqlalchemy.orm import joinedload

from app.models import KnowledgeDocument
from app.services.knowledge_service import can_user_read_knowledge_document, source_url

LINK_ENTITY_KEYS = ("machines", "error_codes", "components", "sensors", "inventory_parts")
MAX_LINK_SCAN = 250


def knowledge_links_for_document(document_id, user=None, limit=8):
    """Return related knowledge documents based on source and entity overlap."""
    document = (
        KnowledgeDocument.query.options(joinedload(KnowledgeDocument.chunks))
        .filter(KnowledgeDocument.id == document_id)
        .first()
    )
    if not document:
        return {"document_id": document_id, "links": [], "explainability": _explainability()}
    if user and not can_user_read_knowledge_document(user, document):
        return {"document_id": document_id, "links": [], "explainability": _explainability()}

    base_entities = _document_entities(document)
    candidates = (
        KnowledgeDocument.query.options(joinedload(KnowledgeDocument.chunks))
        .filter(KnowledgeDocument.id != document.id)
        .filter(KnowledgeDocument.status == "indexed")
        .order_by(KnowledgeDocument.updated_at.desc(), KnowledgeDocument.id.desc())
        .limit(MAX_LINK_SCAN)
        .all()
    )
    links = []
    for candidate in candidates:
        if user and not can_user_read_knowledge_document(user, candidate):
            continue
        score, reasons = _link_score(document, candidate, base_entities)
        if score <= 0:
            continue
        links.append(_link_payload(candidate, score, reasons))
    links.sort(key=lambda item: (item["score"], item["id"]), reverse=True)
    return {
        "document_id": document.id,
        "links": links[: _limit(limit)],
        "explainability": _explainability(),
    }


def linked_knowledge_for_sources(sources, user=None, limit=6):
    """Return related knowledge documents for retrieved knowledge sources."""
    document_ids = []
    for source in sources or []:
        if not isinstance(source, dict) or source.get("type") != "knowledge":
            continue
        document_id = source.get("id")
        if document_id in (None, "") or document_id in document_ids:
            continue
        document_ids.append(document_id)
    links = []
    for document_id in document_ids[:5]:
        result = knowledge_links_for_document(document_id, user=user, limit=limit)
        for link in result["links"]:
            if link["id"] not in {item["id"] for item in links}:
                links.append(link)
    links.sort(key=lambda item: (item["score"], item["id"]), reverse=True)
    return {
        "links": links[: _limit(limit)],
        "source_document_ids": document_ids,
        "explainability": _explainability(),
    }


def _document_entities(document):
    """Return normalized entity values for a knowledge document."""
    values = {key: Counter() for key in LINK_ENTITY_KEYS}
    for chunk in document.chunks:
        entities = chunk.entities()
        for key in LINK_ENTITY_KEYS:
            for value in entities.get(key, []):
                normalized = _normalized(value)
                if normalized:
                    values[key][normalized] += 1
    return values


def _link_score(left, right, left_entities):
    """Return an explainable link score for two knowledge documents."""
    reasons = []
    score = 0
    if (
        left.source_type == right.source_type
        and left.source_id
        and left.source_id == right.source_id
    ):
        score += 8
        reasons.append("same_structured_source")
    if left.source_type == right.source_type and left.source_type:
        score += 1
        reasons.append("same_source_type")
    right_entities = _document_entities(right)
    for key in LINK_ENTITY_KEYS:
        overlap = set(left_entities[key]) & set(right_entities[key])
        if not overlap:
            continue
        score += min(6, len(overlap) * 2)
        reasons.append(f"shared_{key}:{len(overlap)}")
    if right.quality_status in {"admin_approved", "technician_confirmed"}:
        score += 2
        reasons.append("confirmed_quality")
    return score, reasons


def _link_payload(document, score, reasons):
    """Return a prompt-safe knowledge link payload."""
    return {
        "type": "knowledge",
        "id": document.id,
        "title": document.title,
        "source_type": document.source_type,
        "source_id": document.source_id,
        "quality_status": document.quality_status,
        "url": source_url(document),
        "score": int(score),
        "reasons": reasons[:6],
    }


def _explainability():
    """Return static link explainability metadata."""
    return {
        "method": "source_relation_and_chunk_entity_overlap",
        "entity_keys": list(LINK_ENTITY_KEYS),
        "permission_aware": True,
        "persistence": "runtime_only",
    }


def _normalized(value):
    """Return normalized entity text for matching."""
    return " ".join(str(value or "").strip().lower().split())


def _limit(value):
    """Return a bounded link limit."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = 8
    return min(max(parsed, 1), 25)

"""Consolidated read model for the automated knowledge lifecycle."""

from collections import Counter

from app.models import AIFeedback, KnowledgeDocument, KnowledgeGap
from app.services.knowledge_quality_service import KNOWLEDGE_QUALITY_STATUSES

INDEXED_STATUS = "indexed"
APPROVED_QUALITY_STATUS = "admin_approved"
DRAFT_QUALITY_STATUSES = {"draft", "ai_suggested"}
PROBLEM_INDEX_STATUSES = {"error", "no_text", "pending", "stale"}

LIFECYCLE_STEP_DEFINITIONS = (
    {
        "key": "source_capture",
        "label": "Quelle entsteht",
        "status": "available",
        "services": [
            "knowledge_service",
            "document_knowledge_processing_service",
        ],
        "notes": (
            "Tasks, Fehler, Dokumente, Maschinen, Handovers und Trainings "
            "koennen als KnowledgeDocument registriert werden."
        ),
    },
    {
        "key": "draft_creation",
        "label": "Knowledge-Draft",
        "status": "available",
        "services": [
            "knowledge_service",
            "assistant_training_service",
            "document_knowledge_processing_service",
        ],
        "notes": "Neue KnowledgeDocument-Zeilen starten mit draft oder ai_suggested.",
    },
    {
        "key": "similarity_detection",
        "label": "Aehnliche Eintraege",
        "status": "partial",
        "services": ["error_service", "recurring_issue_service", "vector_store_service"],
        "notes": (
            "Fehleraehnlichkeit und RAG-Suche existieren; ein generischer "
            "Knowledge-Draft-Similarity-Endpunkt ist noch nicht zentralisiert."
        ),
    },
    {
        "key": "missing_information",
        "label": "Rueckfragen",
        "status": "available",
        "services": ["missing_information_service"],
        "notes": "Fehler- und manuelle Knowledge-Eingaben erhalten strukturierte Rueckfragen.",
    },
    {
        "key": "technician_review",
        "label": "Techniker bestaetigt",
        "status": "available",
        "services": ["knowledge_quality_service"],
        "notes": "Techniker duerfen abteilungsbezogen technician_confirmed oder outdated setzen.",
    },
    {
        "key": "admin_approval",
        "label": "Admin gibt frei",
        "status": "available",
        "services": ["knowledge_quality_service"],
        "notes": "Nur Master Admins duerfen admin_approved setzen.",
    },
    {
        "key": "rag_usage",
        "label": "RAG nutzt Wissen",
        "status": "partial",
        "services": ["knowledge_service", "retrieval_service", "vector_store_service"],
        "notes": (
            "RAG nutzt indexierte und sichtbare Quellen; Quality-Gating wird "
            "aktuell nur ausgewertet, nicht erzwungen."
        ),
    },
    {
        "key": "feedback",
        "label": "Feedback verbessert Qualitaet",
        "status": "available",
        "services": ["ai_feedback_service", "ai_audit_service"],
        "notes": (
            "AI-Antwortfeedback wird mit Frage, Antwort, Quellen und "
            "Review-Status gespeichert."
        ),
    },
    {
        "key": "knowledge_gaps",
        "label": "Wissensluecken",
        "status": "available",
        "services": ["knowledge_gap_service"],
        "notes": (
            "Unbeantwortete oder niedrig-konfidente AI-Fragen erzeugen "
            "deduplizierte KnowledgeGap-Eintraege."
        ),
    },
)


def knowledge_lifecycle_steps():
    """Return stable descriptors for the supported knowledge lifecycle steps."""
    return [dict(step) for step in LIFECYCLE_STEP_DEFINITIONS]


def knowledge_lifecycle_overview(documents=None):
    """Return admin-facing lifecycle counters built from existing services and models."""
    document_items = _document_items(documents)
    status_counts = _counter_for_field(document_items, "status")
    quality_status_counts = _quality_status_counts(document_items)
    indexed_documents = [
        document for document in document_items if document.status == INDEXED_STATUS
    ]
    approved_indexed = [
        document
        for document in indexed_documents
        if document.quality_status == APPROVED_QUALITY_STATUS
    ]
    non_approved_indexed = len(indexed_documents) - len(approved_indexed)
    problem_count = sum(
        1 for document in document_items if document.status in PROBLEM_INDEX_STATUSES
    )
    return {
        "documents": len(document_items),
        "indexed_documents": len(indexed_documents),
        "drafts": _draft_count(quality_status_counts),
        "technician_confirmed": quality_status_counts.get("technician_confirmed", 0),
        "admin_approved": quality_status_counts.get(APPROVED_QUALITY_STATUS, 0),
        "outdated": quality_status_counts.get("outdated", 0),
        "rejected": quality_status_counts.get("rejected", 0),
        "problem_documents": problem_count,
        "feedback_open": _open_feedback_count(),
        "knowledge_gaps_open": _open_gap_count(),
        "status_counts": status_counts,
        "quality_status_counts": quality_status_counts,
        "review_queue": _review_queue(quality_status_counts),
        "rag_quality_gate": {
            "enabled": False,
            "approved_indexed_documents": len(approved_indexed),
            "non_approved_indexed_documents": non_approved_indexed,
            "reason": (
                "RAG verwendet aktuell indexierte und sichtbare Knowledge-Dokumente; "
                "admin_approved wird ausgewertet, aber nicht als Abrufbedingung erzwungen."
            ),
        },
        "steps": knowledge_lifecycle_steps(),
        "next_actions": _next_actions(
            quality_status_counts,
            problem_count,
            non_approved_indexed,
        ),
    }


def knowledge_lifecycle_document_state(document):
    """Return the lifecycle state for one knowledge document."""
    if not isinstance(document, KnowledgeDocument):
        raise ValueError("document must be a KnowledgeDocument")
    return {
        "id": document.id,
        "source_type": document.source_type,
        "source_id": document.source_id,
        "status": document.status,
        "quality_status": document.quality_status,
        "indexed": document.status == INDEXED_STATUS and (document.chunk_count or 0) > 0,
        "ready_for_admin_approval": document.quality_status == "technician_confirmed",
        "approved_for_quality": document.quality_status == APPROVED_QUALITY_STATUS,
        "needs_indexing": document.status in {"pending", "stale"},
        "needs_attention": document.status in PROBLEM_INDEX_STATUSES
        or document.quality_status in DRAFT_QUALITY_STATUSES | {"outdated"},
        "next_action": _document_next_action(document),
    }


def _document_items(documents):
    """Return a list of knowledge documents, querying when no list is provided."""
    if documents is None:
        return KnowledgeDocument.query.order_by(KnowledgeDocument.id.asc()).all()
    return list(documents)


def _counter_for_field(documents, field_name):
    """Return a plain counter for a document attribute."""
    return dict(Counter(str(getattr(document, field_name) or "") for document in documents))


def _quality_status_counts(documents):
    """Return quality-status counts with known statuses always present."""
    counts = Counter(str(document.quality_status or "draft") for document in documents)
    for status in KNOWLEDGE_QUALITY_STATUSES:
        counts.setdefault(status, 0)
    return dict(sorted(counts.items()))


def _draft_count(quality_status_counts):
    """Return how many documents still need first editorial review."""
    return sum(quality_status_counts.get(status, 0) for status in DRAFT_QUALITY_STATUSES)


def _review_queue(quality_status_counts):
    """Return counts for the editorial review handoff."""
    return {
        "needs_technician_review": _draft_count(quality_status_counts),
        "needs_admin_approval": quality_status_counts.get("technician_confirmed", 0),
        "needs_refresh": quality_status_counts.get("outdated", 0),
        "rejected": quality_status_counts.get("rejected", 0),
    }


def _open_feedback_count():
    """Return the count of AI feedback items waiting for review."""
    return AIFeedback.query.filter(AIFeedback.review_status == "open").count()


def _open_gap_count():
    """Return the count of open knowledge gaps."""
    return KnowledgeGap.query.filter(KnowledgeGap.status == "open").count()


def _next_actions(quality_status_counts, problem_count, non_approved_indexed):
    """Return compact admin actions derived from the lifecycle counters."""
    actions = []
    if problem_count:
        actions.append("Indexprobleme in Knowledge-Dokumenten pruefen.")
    if _draft_count(quality_status_counts):
        actions.append("Drafts durch Techniker reviewen lassen.")
    if quality_status_counts.get("technician_confirmed", 0):
        actions.append("Technikerbestaetigte Eintraege als Admin freigeben oder ablehnen.")
    if quality_status_counts.get("outdated", 0):
        actions.append("Veraltete Eintraege aktualisieren und neu indexieren.")
    if non_approved_indexed:
        actions.append("RAG-Qualitaetsgate fachlich entscheiden, bevor es erzwungen wird.")
    if not actions:
        actions.append("Lifecycle ist aktuell ohne offene Review- oder Indexsignale.")
    return actions


def _document_next_action(document):
    """Return the recommended next lifecycle action for one knowledge document."""
    if document.status in {"pending", "stale"}:
        return "reindex"
    if document.status in {"error", "no_text"}:
        return "fix_source"
    if document.quality_status in DRAFT_QUALITY_STATUSES:
        return "technician_review"
    if document.quality_status == "technician_confirmed":
        return "admin_approval"
    if document.quality_status == "outdated":
        return "refresh"
    if document.quality_status == "rejected":
        return "revise_or_archive"
    return "none"

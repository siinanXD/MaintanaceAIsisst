"""Document Review Service helpers."""

# ruff: noqa: F401, F821

import logging
import re
from datetime import UTC, datetime
from html import escape
from html.parser import HTMLParser
from pathlib import Path

from flask import current_app
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import (
    DocumentApprovalEvent,
    DocumentVersion,
    GeneratedDocument,
    Machine,
    MachineManual,
    MachineManualVersion,
    Role,
)
from app.services.ai_service import AIServiceError, get_ai_provider

ALLOWED_CHECK_EXTENSIONS = {".html", ".htm", ".txt"}
ALLOWED_MANUAL_EXTENSIONS = {".pdf", ".txt", ".html", ".htm"}
DOCUMENT_STATUSES = {"draft", "in_review", "approved", "rejected"}

REVIEW_REQUIRED_FIELDS = (
    "Maschine",
    "Ursache",
    "Durchgefuehrte Massnahme",
    "Ergebnis",
    "Notizen",
)

REPORT_FIELD_ALIASES = {
    "anlage": "Maschine",
    "maschine": "Maschine",
    "fehler": "Fehler",
    "fehlercode": "Fehlercode",
    "fehler-code": "Fehlercode",
    "task titel": "Task-Titel",
    "task-titel": "Task-Titel",
    "titel": "Task-Titel",
    "beschreibung": "Beschreibung",
    "ursache": "Ursache",
    "moegliche ursache": "Ursache",
    "mögliche ursache": "Ursache",
    "moegliche ursachen": "Ursache",
    "mögliche ursachen": "Ursache",
    "durchgefuehrte massnahme": "Durchgefuehrte Massnahme",
    "durchgeführte maßnahme": "Durchgefuehrte Massnahme",
    "massnahme": "Durchgefuehrte Massnahme",
    "maßnahme": "Durchgefuehrte Massnahme",
    "vorgeschlagene massnahme": "Durchgefuehrte Massnahme",
    "vorgeschlagene maßnahme": "Durchgefuehrte Massnahme",
    "loesung": "Durchgefuehrte Massnahme",
    "lösung": "Durchgefuehrte Massnahme",
    "ergebnis": "Ergebnis",
    "notizen": "Notizen",
    "hinweise": "Notizen",
}


logger = logging.getLogger(__name__)


def submit_document_review(document, user, comment=""):
    """Move a document into review status and record an approval event."""
    return change_document_status(document, user, "in_review", "submit_review", comment)


def approve_document(document, user, comment=""):
    """Approve a document and store approval metadata."""
    document.approved_by = user.id
    document.approved_at = datetime.now(UTC)
    document.approval_comment = str(comment or "").strip()[:2000]
    document.rejected_by = None
    document.rejected_at = None
    document.rejection_comment = ""
    return change_document_status(document, user, "approved", "approve", comment)


def reject_document(document, user, comment=""):
    """Reject a document and store rejection metadata."""
    document.rejected_by = user.id
    document.rejected_at = datetime.now(UTC)
    document.rejection_comment = str(comment or "").strip()[:2000]
    return change_document_status(document, user, "rejected", "reject", comment)


def change_document_status(document, user, status, action, comment=""):
    """Persist a document status transition with an event."""
    if status not in DOCUMENT_STATUSES:
        raise ValueError("Invalid document status")
    document.status = status
    db.session.add(
        DocumentApprovalEvent(
            document=document,
            action=action,
            comment=str(comment or "").strip()[:2000],
            user_id=user.id,
        )
    )
    db.session.commit()
    return document


def summarize_generated_document(document):
    """Create or update a stored summary for a generated document."""
    path = document_path(document)
    if not path.exists():
        return None, {"error": "Document file not found"}, 404
    text = html_to_text(path.read_text(encoding="utf-8"))
    summary, status = summarize_text(text, {"document_id": document.id, "title": document.title})
    document.summary = summary
    document.summary_status = status
    db.session.commit()
    _process_generated_document_knowledge(document)
    return document.to_dict(), None, 200


def review_document_quality(document):
    """Return a non-persisted quality review for a generated document."""
    path = document_path(document)
    if not path.exists():
        return None, {"error": "Document file not found"}, 404

    html_text = path.read_text(encoding="utf-8")
    provider = get_ai_provider()
    if provider.name == "mock":
        review = local_document_review(document, html_text)
        review["diagnostics"] = {"status": "local_answer", "provider": provider.name}
        return review, None, 200

    try:
        provider_review = provider.review_document(html_text, document.to_dict())
    except AIServiceError:
        logger.warning(
            "ai_fallback workflow=document_review document_id=%s",
            document.id,
        )
        review = local_document_review(document, html_text)
        review["diagnostics"] = {"status": "fallback_used", "provider": provider.name}
        return review, None, 200

    review = normalize_document_review(provider_review, document)
    review["diagnostics"] = {
        "status": "openai_used",
        "provider": provider.name,
        **getattr(provider, "last_call_metadata", {}),
    }
    return review, None, 200


def review_uploaded_document(file_storage):
    """Return a non-persisted quality review for an uploaded document."""
    if not file_storage or not file_storage.filename:
        return None, {"error": "file is required"}, 400

    filename = Path(file_storage.filename).name
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_CHECK_EXTENSIONS:
        return (
            None,
            {
                "error": "file type not supported; use html, htm or txt",
            },
            400,
        )

    try:
        raw_content = file_storage.read()
    except OSError:
        logger.exception("document_upload_read_failed filename=%s", filename)
        return None, {"error": "Document upload could not be read"}, 400

    if not raw_content:
        return None, {"error": "file must not be empty"}, 400

    try:
        html_text = raw_content.decode("utf-8")
    except UnicodeDecodeError:
        logger.warning("document_upload_decode_failed filename=%s", filename)
        return None, {"error": "file must be UTF-8 text"}, 400

    metadata = {
        "title": filename,
        "document_type": "uploaded_document",
        "source": "upload",
    }
    provider = get_ai_provider()
    if provider.name == "mock":
        review = local_uploaded_document_review(metadata, html_text)
        review["diagnostics"] = {"status": "local_answer", "provider": provider.name}
        return review, None, 200

    try:
        provider_review = provider.review_document(html_text, metadata)
    except AIServiceError:
        logger.warning(
            "ai_fallback workflow=document_upload_review filename=%s",
            filename,
        )
        review = local_uploaded_document_review(metadata, html_text)
        review["diagnostics"] = {"status": "fallback_used", "provider": provider.name}
        return review, None, 200

    review = normalize_uploaded_document_review(provider_review, metadata)
    review["diagnostics"] = {
        "status": "openai_used",
        "provider": provider.name,
        **getattr(provider, "last_call_metadata", {}),
    }
    return review, None, 200


def local_document_review(document, html_text):
    """Return a deterministic quality review for a maintenance report."""
    fields = parse_report_fields(html_text)
    findings = []
    recommendations = []

    for field_name in REVIEW_REQUIRED_FIELDS:
        value = fields.get(field_name, "")
        finding = review_field(field_name, value)
        if not finding:
            continue
        findings.append(finding)
        recommendations.append(recommendation_for_field(field_name))

    quality_score = score_from_findings(findings)
    return {
        "document": document.to_dict(),
        "quality_score": quality_score,
        "status": status_from_score(quality_score),
        "extracted_fields": fields,
        "findings": findings,
        "recommendations": recommendations,
    }


def local_uploaded_document_review(metadata, html_text):
    """Return a deterministic quality review for uploaded report text."""
    fields = parse_report_fields(html_text)
    if not fields:
        fields = fields_from_plain_text(html_text)

    findings = []
    recommendations = []
    for field_name in REVIEW_REQUIRED_FIELDS:
        finding = review_field(field_name, fields.get(field_name, ""))
        if not finding:
            continue
        findings.append(finding)
        recommendations.append(recommendation_for_field(field_name))

    quality_score = score_from_findings(findings)
    return {
        "document": metadata,
        "quality_score": quality_score,
        "status": status_from_score(quality_score),
        "extracted_fields": fields,
        "findings": findings,
        "recommendations": recommendations,
    }


def normalize_document_review(provider_review, document):
    """Normalize a provider review to the public response shape."""
    provider_review = provider_review or {}
    score = clamp_score(provider_review.get("quality_score"))
    return {
        "document": document.to_dict(),
        "quality_score": score,
        "status": valid_review_status(provider_review.get("status"), score),
        "extracted_fields": normalize_extracted_fields(
            provider_review.get("extracted_fields"),
        ),
        "findings": normalize_findings(provider_review.get("findings")),
        "recommendations": normalize_recommendations(
            provider_review.get("recommendations"),
        ),
    }


def normalize_uploaded_document_review(provider_review, metadata):
    """Normalize a provider review for uploaded documents."""
    provider_review = provider_review or {}
    score = clamp_score(provider_review.get("quality_score"))
    return {
        "document": metadata,
        "quality_score": score,
        "status": valid_review_status(provider_review.get("status"), score),
        "extracted_fields": normalize_extracted_fields(
            provider_review.get("extracted_fields"),
        ),
        "findings": normalize_findings(provider_review.get("findings")),
        "recommendations": normalize_recommendations(
            provider_review.get("recommendations"),
        ),
    }


def parse_report_fields(html_text):
    """Extract report table fields from generated HTML."""
    parser = ReportTableParser()
    parser.feed(html_text)
    return normalize_report_fields(parser.rows)


def fields_from_plain_text(text):
    """Extract known document fields from line-oriented plain text."""
    fields = {}
    for line in str(text or "").splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        normalized_key = canonical_report_field(key)
        if normalized_key:
            fields[normalized_key] = value.strip()
    return fields


def normalize_report_fields(fields):
    """Return report fields with supported labels normalized."""
    normalized_fields = {}
    for key, value in fields.items():
        normalized_key = canonical_report_field(key)
        if normalized_key:
            normalized_fields[normalized_key] = value
    return normalized_fields


def canonical_report_field(value):
    """Return the canonical report field name for a user-facing label."""
    key = " ".join(str(value or "").strip().lower().split())
    return REPORT_FIELD_ALIASES.get(key)


def review_field(field_name, value):
    """Return a finding when a required report field is weak or missing."""
    cleaned = " ".join(str(value or "").strip().split())
    if not cleaned or cleaned == "-":
        return {
            "field": field_name,
            "severity": "critical",
            "message": f"{field_name} fehlt im Wartungsbericht.",
        }
    if len(cleaned) < 4:
        return {
            "field": field_name,
            "severity": "warning",
            "message": f"{field_name} ist sehr knapp dokumentiert.",
        }
    return None


def recommendation_for_field(field_name):
    """Return a practical recommendation for one weak report field."""
    recommendations = {
        "Maschine": "Maschine oder Anlage eindeutig im Bericht erfassen.",
        "Ursache": "Ursache oder wahrscheinliche Fehlerquelle dokumentieren.",
        "Durchgefuehrte Massnahme": "Ausgefuehrte Arbeiten konkret beschreiben.",
        "Ergebnis": "Pruefergebnis oder Restproblem festhalten.",
        "Notizen": "Relevante Zusatzhinweise oder Folgeaufgaben ergaenzen.",
    }
    return recommendations[field_name]


def score_from_findings(findings):
    """Return a quality score from review findings."""
    score = 100
    for finding in findings:
        if finding["severity"] == "critical":
            score -= 20
        elif finding["severity"] == "warning":
            score -= 10
    return max(0, min(100, score))


def status_from_score(score):
    """Return a public review status for a quality score."""
    if score >= 85:
        return "good"
    if score >= 60:
        return "needs_review"
    return "incomplete"


def clamp_score(value):
    """Return a provider score clamped to the public 0-100 range."""
    try:
        score = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(100, score))


def valid_review_status(value, score):
    """Return a supported review status or derive one from score."""
    if value in {"good", "needs_review", "incomplete"}:
        return value
    return status_from_score(score)


def normalize_findings(findings):
    """Return sanitized provider findings."""
    if not isinstance(findings, list):
        return []
    normalized = []
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        severity = finding.get("severity")
        if severity not in {"info", "warning", "critical"}:
            severity = "warning"
        normalized.append(
            {
                "field": str(finding.get("field") or "Allgemein").strip()[:80],
                "severity": severity,
                "message": str(finding.get("message") or "").strip()[:500],
            }
        )
    return normalized


def normalize_extracted_fields(fields):
    """Return sanitized extracted document fields."""
    if not isinstance(fields, dict):
        return {}
    return {
        str(key or "").strip()[:80]: str(value or "").strip()[:500]
        for key, value in fields.items()
        if str(key or "").strip()
    }


def normalize_recommendations(recommendations):
    """Return sanitized provider recommendations."""
    if not isinstance(recommendations, list):
        return []
    return [
        str(recommendation or "").strip()[:500]
        for recommendation in recommendations
        if str(recommendation or "").strip()
    ][:10]


__all__ = [
    "submit_document_review",
    "approve_document",
    "reject_document",
    "change_document_status",
    "summarize_generated_document",
    "review_document_quality",
    "review_uploaded_document",
    "local_document_review",
    "local_uploaded_document_review",
    "normalize_document_review",
    "normalize_uploaded_document_review",
    "parse_report_fields",
    "fields_from_plain_text",
    "normalize_report_fields",
    "canonical_report_field",
    "review_field",
    "recommendation_for_field",
    "score_from_findings",
    "status_from_score",
    "clamp_score",
    "valid_review_status",
    "normalize_findings",
    "normalize_extracted_fields",
    "normalize_recommendations",
]

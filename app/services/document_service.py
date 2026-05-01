import logging
from datetime import datetime
from html import escape
from html.parser import HTMLParser
from pathlib import Path

from flask import current_app

from app.extensions import db
from app.models import GeneratedDocument, Role
from app.services.ai_service import AIServiceError, get_ai_provider


ALLOWED_CHECK_EXTENSIONS = {".html", ".htm", ".txt"}

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


def visible_documents_query(user):
    """Return a query for documents visible to the user."""
    query = GeneratedDocument.query
    if not user:
        return query.filter(False)
    if user.role != Role.MASTER_ADMIN and user.department:
        query = query.filter(GeneratedDocument.department == user.department.name)
    return query


def document_path(document):
    """Return the absolute safe path for a generated document."""
    base_path = Path(current_app.config["DOCUMENTS_FOLDER"]).resolve()
    full_path = (base_path / document.relative_path).resolve()
    if base_path not in full_path.parents and full_path != base_path:
        raise ValueError("Document path escapes document storage")
    return full_path


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
    review["diagnostics"] = {"status": "openai_used", "provider": provider.name}
    return review, None, 200


def review_uploaded_document(file_storage):
    """Return a non-persisted quality review for an uploaded document."""
    if not file_storage or not file_storage.filename:
        return None, {"error": "file is required"}, 400

    filename = Path(file_storage.filename).name
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_CHECK_EXTENSIONS:
        return None, {
            "error": "file type not supported; use html, htm or txt",
        }, 400

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
    review["diagnostics"] = {"status": "openai_used", "provider": provider.name}
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


class ReportTableParser(HTMLParser):
    """Parse simple generated maintenance report tables."""

    def __init__(self):
        """Initialize the parser state."""
        super().__init__()
        self.rows = {}
        self._current_row = []
        self._active_cell = None
        self._cell_parts = []

    def handle_starttag(self, tag, attrs):
        """Track table row and cell starts."""
        if tag == "tr":
            self._current_row = []
        if tag in {"th", "td"}:
            self._active_cell = tag
            self._cell_parts = []

    def handle_data(self, data):
        """Collect text for the active table cell."""
        if self._active_cell:
            self._cell_parts.append(data)

    def handle_endtag(self, tag):
        """Store completed cells and rows."""
        if tag in {"th", "td"} and self._active_cell == tag:
            self._current_row.append(" ".join("".join(self._cell_parts).split()))
            self._active_cell = None
            self._cell_parts = []
        if tag == "tr" and len(self._current_row) >= 2:
            self.rows[self._current_row[0]] = self._current_row[1]


def generate_maintenance_report(task, user, payload=None):
    """Generate and persist an HTML maintenance report for a completed task."""
    payload = payload or {}
    created_at = datetime.utcnow()
    relative_dir = Path(
        str(created_at.year),
        f"{created_at.month:02d}",
        f"task_{task.id}",
    )
    relative_path = relative_dir / "maintenance_report.html"
    base_path = Path(current_app.config["DOCUMENTS_FOLDER"]).resolve()
    report_path = (base_path / relative_path).resolve()
    if base_path not in report_path.parents:
        raise ValueError("Report path escapes document storage")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        _render_report_html(task, user, payload, created_at),
        encoding="utf-8",
    )

    document = GeneratedDocument(
        task=task,
        document_type="maintenance_report",
        title=f"Wartungsbericht Task {task.id}",
        relative_path=str(relative_path).replace("\\", "/"),
        department=task.department.name if task.department else "",
        machine=payload.get("machine", ""),
        created_by=user.id,
        created_at=created_at,
    )
    db.session.add(document)
    db.session.commit()
    return document


def _render_report_html(task, user, payload, created_at):
    """Render escaped HTML for a maintenance report."""
    rows = [
        ("Datum", created_at.strftime("%Y-%m-%d %H:%M")),
        ("Bearbeiter", user.username),
        ("Bereich", task.department.name if task.department else ""),
        ("Maschine", payload.get("machine", "")),
        ("Task-Titel", task.title),
        ("Beschreibung", task.description),
        ("Ursache", payload.get("cause", "")),
        ("Durchgefuehrte Massnahme", payload.get("action", "")),
        ("Ergebnis", payload.get("result", "")),
        ("Status", task.status.value),
        ("Notizen", payload.get("notes", "")),
    ]
    table_rows = "\n".join(
        f"<tr><th>{escape(label)}</th><td>{escape(str(value or '-'))}</td></tr>"
        for label, value in rows
    )
    return f"""<!doctype html>
<html lang="de">
  <head>
    <meta charset="utf-8">
    <title>Wartungsbericht Task {task.id}</title>
    <style>
      body {{ font-family: Arial, sans-serif; margin: 32px; color: #1f2937; }}
      h1 {{ margin-bottom: 4px; }}
      table {{ border-collapse: collapse; width: 100%; margin-top: 24px; }}
      th, td {{ border: 1px solid #d1d5db; padding: 10px; text-align: left; }}
      th {{ width: 240px; background: #f3f4f6; }}
    </style>
  </head>
  <body>
    <h1>Wartungsbericht</h1>
    <p>Automatisch generierter Bericht aus dem Maintenance Assistant.</p>
    <table>{table_rows}</table>
  </body>
</html>
"""

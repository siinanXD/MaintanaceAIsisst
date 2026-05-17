"""Document generation, parsing, and review services."""

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


def _resolve_machine_id(name):
    """Return Machine.id for an exact case-insensitive name match, or None."""
    if not name:
        return None
    machine = Machine.query.filter(Machine.name.ilike(name)).first()
    return machine.id if machine else None


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
    return safe_storage_path(current_app.config["DOCUMENTS_FOLDER"], document.relative_path)


def manual_path(manual_or_version):
    """Return the absolute safe path for a stored machine manual file."""
    return safe_storage_path(current_app.config["MANUALS_FOLDER"], manual_or_version.relative_path)


def safe_storage_path(base_folder, relative_path):
    """Return a resolved path and reject traversal outside a configured folder."""
    base_path = Path(base_folder).resolve()
    full_path = (base_path / relative_path).resolve()
    if base_path not in full_path.parents and full_path != base_path:
        raise ValueError("Path escapes document storage")
    return full_path


def visible_manuals_query(user):
    """Return a query for machine manuals visible to the user."""
    query = MachineManual.query
    if not user:
        return query.filter(False)
    if user.role != Role.MASTER_ADMIN and user.department:
        query = query.filter(MachineManual.department == user.department.name)
    return query


def ensure_document_version(document):
    """Create a current document version for legacy documents if needed."""
    if document.current_version_id:
        return document.current_version
    path = document_path(document)
    version = DocumentVersion(
        document=document,
        version_number=1,
        relative_path=document.relative_path,
        original_filename=Path(document.relative_path).name,
        content_type="text/html",
        file_size=path.stat().st_size if path.exists() else 0,
        created_by=document.created_by,
        created_at=document.created_at,
    )
    db.session.add(version)
    db.session.flush()
    document.current_version_id = version.id
    db.session.commit()
    return version


def document_versions(document):
    """Return version records for a generated document, creating v1 if missing."""
    ensure_document_version(document)
    return (
        DocumentVersion.query.filter_by(document_id=document.id)
        .order_by(DocumentVersion.version_number.desc())
        .all()
    )


def render_document_pdf(document):
    """Render a generated HTML report as a simple server-side PDF byte stream."""
    path = document_path(document)
    if not path.exists():
        return None, {"error": "Document file not found"}, 404
    html_text = path.read_text(encoding="utf-8")
    title = document.title or f"Wartungsbericht {document.id}"
    pdf_bytes = plain_text_to_pdf(title, html_to_text(html_text))
    return pdf_bytes, None, 200


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


def upload_machine_manual(file_storage, user, machine_id=None, department=""):
    """Persist an uploaded machine manual and create its first version."""
    validation_error = validate_manual_upload(file_storage, machine_id)
    if validation_error:
        return None, validation_error, 400

    machine = db.session.get(Machine, int(machine_id)) if machine_id else None
    filename = secure_filename(Path(file_storage.filename).name)
    raw_content = file_storage.read()
    if not raw_content:
        return None, {"error": "file must not be empty"}, 400

    department_name = (department or "").strip()
    if not department_name and user.department:
        department_name = user.department.name
    if not department_name and machine:
        department_name = ""

    manual = MachineManual(
        machine=machine,
        department=department_name,
        title=Path(filename).stem or filename,
        original_filename=filename,
        relative_path="pending",
        content_type=file_storage.mimetype or "",
        file_size=len(raw_content),
        created_by=user.id,
    )
    db.session.add(manual)
    db.session.flush()

    relative_path = f"manual_{manual.id}/v1/{filename}"
    full_path = safe_storage_path(current_app.config["MANUALS_FOLDER"], relative_path)
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_bytes(raw_content)

    extracted_text, extraction_status = extract_manual_text(filename, raw_content)
    version = MachineManualVersion(
        manual=manual,
        version_number=1,
        relative_path=relative_path,
        original_filename=filename,
        content_type=file_storage.mimetype or "",
        file_size=len(raw_content),
        extracted_text=extracted_text,
        extraction_status=extraction_status,
        created_by=user.id,
    )
    manual.relative_path = relative_path
    db.session.add(version)
    db.session.flush()
    manual.current_version_id = version.id
    db.session.commit()
    _process_machine_manual_knowledge(manual, user)
    return manual.to_dict(), None, 201


def validate_manual_upload(file_storage, machine_id=None):
    """Return an error payload when a manual upload is invalid."""
    if not file_storage or not file_storage.filename:
        return {"error": "file is required"}
    extension = Path(file_storage.filename).suffix.lower()
    if extension not in ALLOWED_MANUAL_EXTENSIONS:
        return {"error": "file type not supported; use pdf, txt, html or htm"}
    if machine_id not in (None, ""):
        try:
            parsed_machine_id = int(machine_id)
        except (TypeError, ValueError):
            return {"error": "machine_id must be a valid machine id"}
        if not db.session.get(Machine, parsed_machine_id):
            return {"error": "machine_id does not reference an existing machine"}
    return None


def analyze_machine_manual(manual):
    """Analyze a machine manual using extracted text and local structured fallback."""
    version = manual.current_version
    if not version or not version.extracted_text.strip():
        manual.analysis_status = "no_text"
        manual.analysis = "Keine Textschicht gefunden. OCR ist nicht integriert."
        db.session.commit()
        return manual.to_dict(), None, 200
    analysis = local_manual_analysis(version.extracted_text, manual)
    manual.analysis = analysis
    manual.analysis_status = "local_answer"
    db.session.commit()
    _process_machine_manual_knowledge(manual)
    return manual.to_dict(), None, 200


def summarize_machine_manual(manual):
    """Create or update a stored machine manual summary."""
    version = manual.current_version
    if not version or not version.extracted_text.strip():
        manual.summary_status = "no_text"
        manual.summary = "Keine Textschicht gefunden. OCR ist nicht integriert."
        db.session.commit()
        return manual.to_dict(), None, 200
    summary, status = summarize_text(
        version.extracted_text,
        {"manual_id": manual.id, "title": manual.title},
    )
    manual.summary = summary
    manual.summary_status = status
    db.session.commit()
    _process_machine_manual_knowledge(manual)
    return manual.to_dict(), None, 200


def delete_machine_manual(manual):
    """Delete a manual record and its stored file if present."""
    _delete_machine_manual_knowledge(manual)
    try:
        path = manual_path(manual)
    except ValueError:
        path = None
    if path and path.exists():
        try:
            path.unlink()
        except OSError as exc:
            logger.warning("manual_file_delete_failed manual_id=%s error=%s", manual.id, exc)
    db.session.delete(manual)
    db.session.commit()


def _process_generated_document_knowledge(document, user=None):
    """Best-effort sync of a generated document into the knowledge index."""
    try:
        from app.services.document_knowledge_processing_service import (
            process_generated_document_for_knowledge,
        )

        _result, error, _status = process_generated_document_for_knowledge(document, user=user)
    except Exception:
        logger.exception(
            "generated_document_knowledge_processing_failed document_id=%s",
            getattr(document, "id", None),
        )
        return
    if error:
        logger.warning(
            "generated_document_knowledge_processing_error document_id=%s error=%s",
            getattr(document, "id", None),
            error,
        )


def _process_machine_manual_knowledge(manual, user=None):
    """Best-effort sync of a machine manual into the knowledge index."""
    try:
        from app.services.document_knowledge_processing_service import (
            process_machine_manual_for_knowledge,
        )

        _result, error, _status = process_machine_manual_for_knowledge(manual, user=user)
    except Exception:
        logger.exception(
            "machine_manual_knowledge_processing_failed manual_id=%s",
            getattr(manual, "id", None),
        )
        return
    if error:
        logger.warning(
            "machine_manual_knowledge_processing_error manual_id=%s error=%s",
            getattr(manual, "id", None),
            error,
        )


def _delete_machine_manual_knowledge(manual):
    """Best-effort deletion of knowledge chunks linked to a machine manual."""
    try:
        from app.services.knowledge_service import delete_source_knowledge_document

        delete_source_knowledge_document("machine_manual", manual.id)
    except Exception:
        logger.exception(
            "machine_manual_knowledge_delete_failed manual_id=%s",
            getattr(manual, "id", None),
        )


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


def html_to_text(html_text):
    """Return readable plain text extracted from HTML."""
    parser = PlainTextParser()
    parser.feed(str(html_text or ""))
    text = "\n".join(part.strip() for part in parser.parts if part.strip())
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def extract_manual_text(filename, raw_content):
    """Extract text from supported manual upload bytes."""
    extension = Path(filename).suffix.lower()
    if extension == ".txt":
        return decode_text(raw_content), "text_extracted"
    if extension in {".html", ".htm"}:
        return html_to_text(decode_text(raw_content)), "text_extracted"
    if extension == ".pdf":
        return extract_pdf_text(raw_content)
    return "", "unsupported"


def decode_text(raw_content):
    """Decode uploaded text bytes as UTF-8 or Latin-1 fallback."""
    try:
        return raw_content.decode("utf-8")
    except UnicodeDecodeError:
        return raw_content.decode("latin-1", errors="ignore")


def extract_pdf_text(raw_content):
    """Extract embedded text from a PDF, returning a clear no-OCR status if needed."""
    try:
        from pypdf import PdfReader

        reader = PdfReader(BytesReader(raw_content))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        cleaned = "\n".join(line.strip() for line in text.splitlines() if line.strip())
        if cleaned:
            return cleaned, "text_extracted"
    except (ImportError, OSError, ValueError):
        logger.info("pypdf_unavailable_or_failed")

    fallback_text = extract_literal_pdf_strings(raw_content)
    if fallback_text:
        return fallback_text, "text_extracted"
    return "", "no_text_layer"


def extract_literal_pdf_strings(raw_content):
    """Extract simple literal strings from text-based PDFs without OCR."""
    decoded = raw_content.decode("latin-1", errors="ignore")
    matches = re.findall(r"\(([^()]*)\)", decoded)
    cleaned = [
        item.replace(r"\(", "(").replace(r"\)", ")").replace(r"\\", "\\").strip()
        for item in matches
    ]
    return "\n".join(item for item in cleaned if item)


def summarize_text(text, metadata=None):
    """Summarize long document text with OpenAI when available and local fallback otherwise."""
    cleaned = " ".join(str(text or "").split())
    if not cleaned:
        return "Keine Textinhalte fuer eine Zusammenfassung gefunden.", "no_text"
    provider = get_ai_provider()
    if provider.name != "mock":
        try:
            prompt = (
                "Fasse dieses Wartungsdokument auf Deutsch zusammen. "
                "Nenne Kernaussagen, Risiken und naechste Schritte."
            )
            summary = provider.answer_question(prompt, cleaned[:12000], workflow="document_summary")
            return str(summary).strip()[:4000], "openai_used"
        except AIServiceError:
            logger.warning("ai_fallback workflow=document_summary metadata=%s", metadata or {})
    return local_summary(cleaned), "local_answer"


def local_summary(text):
    """Return a deterministic extractive summary for document text."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    selected = [sentence.strip() for sentence in sentences if sentence.strip()][:5]
    if not selected:
        selected = [text[:800]]
    return "\n".join(f"- {sentence[:500]}" for sentence in selected)


def local_manual_analysis(text, manual):
    """Return structured local analysis for a machine manual."""
    lowered = text.lower()
    intervals = matching_lines(text, ("taeglich", "täglich", "woechentlich", "monat", "stunden"))
    safety = matching_lines(text, ("warnung", "gefahr", "sicherheit", "schutz", "not-aus"))
    parts = matching_lines(text, ("ersatzteil", "lager", "sensor", "ventil", "filter"))
    errors = matching_lines(text, ("fehler", "error", "alarm", "stoerung", "störung", "code"))
    risks = []
    if not safety:
        risks.append("Keine expliziten Sicherheitshinweise in der Textschicht gefunden.")
    if "ocr" in lowered:
        risks.append("Dokument koennte OCR- oder Scan-Anteile enthalten.")
    lines = [
        f"Maschinenbezug: {manual.machine.name if manual.machine else 'nicht zugeordnet'}",
        "Wartungsintervalle: " + format_matches(intervals),
        "Sicherheitshinweise: " + format_matches(safety),
        "Ersatzteile: " + format_matches(parts),
        "Fehlercodes/Stoerungen: " + format_matches(errors),
        "Offene Risiken: " + (" | ".join(risks) if risks else "Keine lokalen Risiken erkannt."),
    ]
    return "\n".join(lines)


def matching_lines(text, needles):
    """Return relevant text lines containing one of the provided keywords."""
    results = []
    for line in str(text or "").splitlines():
        cleaned = " ".join(line.split())
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if any(needle in lowered for needle in needles):
            results.append(cleaned[:240])
    return results[:5]


def format_matches(items):
    """Return a compact display string for analysis matches."""
    return " | ".join(items) if items else "Keine Treffer"


def plain_text_to_pdf(title, text):
    """Return a minimal valid PDF containing plain text lines."""
    lines = [title, ""] + wrap_pdf_lines(text)
    content_lines = ["BT", "/F1 11 Tf", "50 790 Td", "14 TL"]
    first = True
    for line in lines[:52]:
        if not first:
            content_lines.append("T*")
        content_lines.append(f"({escape_pdf_text(line)}) Tj")
        first = False
    content_lines.append("ET")
    stream = "\n".join(content_lines).encode("latin-1", errors="replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        (
            b"<< /Length "
            + str(len(stream)).encode("ascii")
            + b" >>\nstream\n"
            + stream
            + b"\nendstream"
        ),
    ]
    return build_pdf(objects)


def wrap_pdf_lines(text):
    """Wrap text into PDF-friendly short lines."""
    words = " ".join(str(text or "").split()).split()
    lines = []
    current = []
    for word in words:
        if sum(len(item) + 1 for item in current) + len(word) > 88:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return lines or ["Keine Textinhalte gefunden."]


def escape_pdf_text(value):
    """Escape text for a literal PDF string."""
    return str(value or "").replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_pdf(objects):
    """Build a minimal single-file PDF from encoded PDF objects."""
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode("ascii"))
        output.extend(obj)
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(output)


class BytesReader:
    """Small file-like adapter for optional pypdf without importing io globally."""

    def __init__(self, content):
        """Store PDF bytes for pypdf."""
        from io import BytesIO

        self._buffer = BytesIO(content)

    def __getattr__(self, name):
        """Delegate file-like operations to the underlying BytesIO."""
        return getattr(self._buffer, name)


class PlainTextParser(HTMLParser):
    """Collect visible text from simple HTML content."""

    def __init__(self):
        """Initialize plain-text parser state."""
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        """Collect visible text data."""
        text = " ".join(str(data or "").split())
        if text:
            self.parts.append(text)


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
    created_at = datetime.now(UTC)
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

    machine_name = payload.get("machine", "")
    document = GeneratedDocument(
        task=task,
        document_type="maintenance_report",
        title=f"Wartungsbericht Task {task.id}",
        relative_path=str(relative_path).replace("\\", "/"),
        department=task.department.name if task.department else "",
        machine=machine_name,
        machine_id=_resolve_machine_id(machine_name),
        created_by=user.id,
        created_at=created_at,
    )
    db.session.add(document)
    db.session.flush()
    version = DocumentVersion(
        document=document,
        version_number=1,
        relative_path=document.relative_path,
        original_filename="maintenance_report.html",
        content_type="text/html",
        file_size=report_path.stat().st_size,
        created_by=user.id,
        created_at=created_at,
    )
    db.session.add(version)
    db.session.flush()
    document.current_version_id = version.id
    db.session.commit()
    _process_generated_document_knowledge(document, user)
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

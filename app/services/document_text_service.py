"""Document Text Service helpers."""

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


__all__ = [
    "html_to_text",
    "extract_manual_text",
    "decode_text",
    "extract_pdf_text",
    "extract_literal_pdf_strings",
    "summarize_text",
    "local_summary",
    "local_manual_analysis",
    "matching_lines",
    "format_matches",
    "BytesReader",
    "PlainTextParser",
    "ReportTableParser",
]

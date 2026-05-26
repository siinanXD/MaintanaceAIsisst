"""Document Report Service helpers."""

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


__all__ = [
    "plain_text_to_pdf",
    "wrap_pdf_lines",
    "escape_pdf_text",
    "build_pdf",
    "generate_maintenance_report",
    "_render_report_html",
]

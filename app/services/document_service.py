from datetime import datetime
from html import escape
from pathlib import Path

from flask import current_app

from app.extensions import db
from app.models import GeneratedDocument, Role


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

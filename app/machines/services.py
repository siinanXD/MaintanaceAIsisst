from sqlalchemy import or_

from app.errors.services import visible_errors_query
from app.inventory.services import forecast_inventory_risks
from app.models import ErrorEntry, GeneratedDocument, Machine, Task, TaskStatus
from app.security import has_dashboard_permission
from app.services.ai_service import AIServiceError, get_ai_provider
from app.services.document_service import visible_documents_query
from app.tasks.services import visible_tasks_query


def build_machine_history(machine, user):
    """Build a read-only maintenance history for one machine."""
    task_items = _task_timeline(machine, user)
    error_items = _error_timeline(machine, user)
    document_items = _document_timeline(machine, user)
    timeline = sorted(
        task_items + error_items + document_items,
        key=lambda item: item["date"] or "",
        reverse=True,
    )
    source_counts = {
        "tasks": len(task_items),
        "errors": len(error_items),
        "documents": len(document_items),
        "total": len(timeline),
    }
    return {
        "machine": machine.to_dict(),
        "summary": _machine_summary(machine, timeline, source_counts),
        "source_counts": source_counts,
        "timeline": timeline,
    }


def answer_machine_assistant(machine, user, data):
    """Answer a machine-specific question from visible maintenance context."""
    question = str(data.get("question") or "").strip()
    if not question:
        return None, {"error": "question is required"}, 400
    if len(question) > 1000:
        return None, {"error": "question must not exceed 1000 characters"}, 400

    history = build_machine_history(machine, user)
    forecast = _machine_forecast_context(machine, user)
    provider = get_ai_provider()
    context = _assistant_context(machine, history, forecast)

    if provider.name == "mock":
        return {
            "answer": _local_machine_answer(machine, history, forecast),
            "diagnostics": {"status": "local_answer", "provider": provider.name},
            "context": {
                "source_counts": history["source_counts"],
                "forecast_items": len(forecast),
            },
        }, None, 200

    try:
        answer = provider.answer_question(question, context)
    except AIServiceError:
        return {
            "answer": _local_machine_answer(machine, history, forecast),
            "diagnostics": {"status": "fallback_used", "provider": provider.name},
            "context": {
                "source_counts": history["source_counts"],
                "forecast_items": len(forecast),
            },
        }, None, 200

    return {
        "answer": answer,
        "diagnostics": {"status": "openai_used", "provider": provider.name},
        "context": {
            "source_counts": history["source_counts"],
            "forecast_items": len(forecast),
        },
    }, None, 200


def _task_timeline(machine, user):
    """Return visible task timeline items for a machine."""
    if not has_dashboard_permission(user, "tasks", "view"):
        return []
    needle = f"%{machine.name}%"
    tasks = (
        visible_tasks_query(user)
        .filter(or_(Task.title.ilike(needle), Task.description.ilike(needle)))
        .order_by(Task.updated_at.desc())
        .limit(20)
        .all()
    )
    return [
        {
            "type": "task",
            "date": task.updated_at.isoformat(),
            "title": task.title,
            "status": task.status.value,
            "summary": task.description,
            "url": f"/api/tasks/{task.id}",
        }
        for task in tasks
    ]


def _error_timeline(machine, user):
    """Return visible error timeline items for a machine."""
    if not has_dashboard_permission(user, "errors", "view"):
        return []
    errors = (
        visible_errors_query(user)
        .filter(ErrorEntry.machine.ilike(f"%{machine.name}%"))
        .order_by(ErrorEntry.created_at.desc())
        .limit(20)
        .all()
    )
    return [
        {
            "type": "error",
            "date": entry.created_at.isoformat(),
            "title": f"{entry.error_code} - {entry.title}",
            "status": entry.error_code,
            "summary": entry.solution or entry.description,
            "url": f"/api/errors/{entry.id}",
        }
        for entry in errors
    ]


def _document_timeline(machine, user):
    """Return visible document timeline items for a machine."""
    if not has_dashboard_permission(user, "documents", "view"):
        return []
    documents = (
        visible_documents_query(user)
        .filter(GeneratedDocument.machine.ilike(f"%{machine.name}%"))
        .order_by(GeneratedDocument.created_at.desc())
        .limit(20)
        .all()
    )
    return [
        {
            "type": "document",
            "date": document.created_at.isoformat(),
            "title": document.title,
            "status": document.document_type,
            "summary": f"{document.department} {document.machine}".strip(),
            "url": document.to_dict()["download_url"],
        }
        for document in documents
    ]


def _machine_summary(machine, timeline, source_counts):
    """Return an AI or local summary for the machine history."""
    provider = get_ai_provider()
    if provider.name == "mock":
        return {
            "text": _local_machine_summary(machine, timeline, source_counts),
            "diagnostics": {"status": "local_answer", "provider": provider.name},
        }

    context = _summary_context(machine, timeline, source_counts)
    try:
        answer = provider.answer_question(
            (
                "Fasse diese Maschinenhistorie auf Deutsch in maximal "
                "3 kurzen Saetzen zusammen."
            ),
            context,
        )
    except AIServiceError:
        return {
            "text": _local_machine_summary(machine, timeline, source_counts),
            "diagnostics": {"status": "fallback_used", "provider": provider.name},
        }

    return {
        "text": answer,
        "diagnostics": {"status": "openai_used", "provider": provider.name},
    }


def _local_machine_summary(machine, timeline, source_counts):
    """Return a deterministic local machine history summary."""
    open_tasks = [
        item
        for item in timeline
        if item["type"] == "task" and item["status"] != TaskStatus.DONE.value
    ]
    latest_error = next((item for item in timeline if item["type"] == "error"), None)
    latest_document = next(
        (item for item in timeline if item["type"] == "document"),
        None,
    )
    parts = [
        (
            f"{machine.name} hat {source_counts['tasks']} Tasks, "
            f"{source_counts['errors']} Fehler und "
            f"{source_counts['documents']} Dokumente in der Historie."
        ),
        f"Offene Tasks: {len(open_tasks)}.",
    ]
    if latest_error:
        parts.append(f"Letzter Fehler: {latest_error['title']}.")
    if latest_document:
        parts.append(f"Letztes Dokument: {latest_document['title']}.")
    return " ".join(parts)


def _summary_context(machine, timeline, source_counts):
    """Return compact context text for an AI machine summary."""
    rows = [
        f"Maschine: {machine.name}",
        f"Tasks: {source_counts['tasks']}",
        f"Fehler: {source_counts['errors']}",
        f"Dokumente: {source_counts['documents']}",
    ]
    for item in timeline[:10]:
        rows.append(
            " | ".join(
                [
                    f"Typ: {item['type']}",
                    f"Datum: {item['date']}",
                    f"Titel: {item['title']}",
                    f"Status: {item['status']}",
                    f"Zusammenfassung: {item['summary']}",
                ]
            )
        )
    return "\n".join(rows)


def _machine_forecast_context(machine, user):
    """Return inventory forecast items related to a machine when permitted."""
    if not (
        has_dashboard_permission(user, "inventory", "view")
        and has_dashboard_permission(user, "tasks", "view")
    ):
        return []
    forecast, error, _status = forecast_inventory_risks(
        {"status": "open", "limit": 20, "low_stock_threshold": 5},
        user,
    )
    if error:
        return []
    return [
        item
        for item in forecast.get("items", [])
        if item.get("machine", {}).get("id") == machine.id
    ]


def _assistant_context(machine, history, forecast):
    """Return compact context text for machine assistant answers."""
    rows = [
        f"Maschine: {machine.name}",
        f"Historie: {history['source_counts']}",
        f"Zusammenfassung: {history['summary']['text']}",
    ]
    for item in history["timeline"][:15]:
        rows.append(
            " | ".join(
                [
                    f"Typ: {item['type']}",
                    f"Datum: {item['date']}",
                    f"Titel: {item['title']}",
                    f"Status: {item['status']}",
                    f"Details: {item['summary']}",
                ]
            )
        )
    for item in forecast[:10]:
        rows.append(
            " | ".join(
                [
                    "Typ: lager",
                    f"Material: {item['material']['name']}",
                    f"Risiko: {item['risk_level']}",
                    f"Empfehlung: {item['recommended_action']}",
                ]
            )
        )
    return "\n".join(rows)


def _local_machine_answer(machine, history, forecast):
    """Return a deterministic machine assistant answer."""
    counts = history["source_counts"]
    lines = [
        f"{machine.name}: {counts['tasks']} Tasks, {counts['errors']} Fehler, "
        f"{counts['documents']} Dokumente sichtbar."
    ]
    open_task = next(
        (
            item
            for item in history["timeline"]
            if item["type"] == "task" and item["status"] != TaskStatus.DONE.value
        ),
        None,
    )
    if open_task:
        lines.append(f"Naechster Task: {open_task['title']} ({open_task['status']}).")
    if forecast:
        lines.append(
            f"Lagerhinweis: {forecast[0]['material']['name']} "
            f"ist {forecast[0]['risk_level']}."
        )
    if counts["total"] == 0:
        lines.append("Keine Historie gefunden; Maschine und Taskdaten pruefen.")
    return " ".join(lines)

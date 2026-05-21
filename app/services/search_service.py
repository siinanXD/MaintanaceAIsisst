"""Cross-domain search service helpers."""

from urllib.parse import quote_plus

from sqlalchemy import or_

from app.models import ErrorEntry, GeneratedDocument, Task
from app.security import has_dashboard_permission
from app.services.document_service import visible_documents_query
from app.services.error_service import visible_errors_query
from app.services.task_service import visible_tasks_query


def search_knowledge(query_text, user):
    """Search visible maintenance knowledge across tasks, errors and documents."""
    results = []
    if has_dashboard_permission(user, "tasks", "view"):
        results.extend(_search_tasks(query_text, user))
    if has_dashboard_permission(user, "errors", "view"):
        results.extend(_search_errors(query_text, user))
    if has_dashboard_permission(user, "documents", "view"):
        results.extend(_search_documents(query_text, user))
    return {"query": query_text, "results": results[:30]}


def _enum_value(value):
    """Return a stable JSON value for enum-like fields."""
    return getattr(value, "value", value)


def _ui_search_url(path, query_text):
    """Build a UI deeplink that opens a page with its local search prefilled."""
    return f"{path}?search={quote_plus(query_text or '')}"


def _compact_summary(*parts):
    """Join non-empty summary parts into a concise preview string."""
    return " · ".join(str(part).strip() for part in parts if str(part or "").strip())


def _search_tasks(query_text, user):
    """Search visible tasks."""
    needle = f"%{query_text}%"
    tasks = (
        visible_tasks_query(user)
        .filter(or_(Task.title.ilike(needle), Task.description.ilike(needle)))
        .order_by(Task.updated_at.desc())
        .limit(10)
        .all()
    )
    return [
        {
            "type": "task",
            "entity_id": task.id,
            "title": task.title,
            "summary": task.description,
            "status": _enum_value(task.status),
            "badge": _enum_value(task.priority),
            "url": f"/api/tasks/{task.id}",
            "ui_url": _ui_search_url("/tasks", task.title or query_text),
        }
        for task in tasks
    ]


def _search_errors(query_text, user):
    """Search visible error catalog entries."""
    needle = f"%{query_text}%"
    entries = (
        visible_errors_query(user)
        .filter(
            or_(
                ErrorEntry.machine.ilike(needle),
                ErrorEntry.error_code.ilike(needle),
                ErrorEntry.title.ilike(needle),
                ErrorEntry.solution.ilike(needle),
            )
        )
        .limit(10)
        .all()
    )
    return [
        {
            "type": "error",
            "entity_id": entry.id,
            "title": f"{entry.error_code} - {entry.title}",
            "summary": entry.solution or entry.description,
            "status": entry.error_code,
            "badge": entry.machine,
            "url": f"/api/errors/{entry.id}",
            "ui_url": _ui_search_url("/errors", entry.error_code or entry.title or query_text),
        }
        for entry in entries
    ]


def _search_documents(query_text, user):
    """Search visible document metadata."""
    needle = f"%{query_text}%"
    documents = (
        visible_documents_query(user)
        .filter(
            or_(
                GeneratedDocument.title.ilike(needle),
                GeneratedDocument.department.ilike(needle),
                GeneratedDocument.machine.ilike(needle),
            )
        )
        .order_by(GeneratedDocument.created_at.desc())
        .limit(10)
        .all()
    )
    return [
        {
            "type": "document",
            "entity_id": document.id,
            "title": document.title,
            "summary": _compact_summary(document.department, document.machine),
            "status": document.status,
            "badge": document.machine or document.department,
            "url": document.to_dict()["download_url"],
            "ui_url": _ui_search_url("/documents", document.title or query_text),
        }
        for document in documents
    ]

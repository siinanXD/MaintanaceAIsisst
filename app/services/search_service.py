from sqlalchemy import or_

from app.services.error_service import visible_errors_query
from app.models import ErrorEntry, GeneratedDocument, Task
from app.security import has_dashboard_permission
from app.services.document_service import visible_documents_query
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
            "title": task.title,
            "summary": task.description,
            "url": f"/api/tasks/{task.id}",
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
            "title": f"{entry.error_code} - {entry.title}",
            "summary": entry.solution or entry.description,
            "url": f"/api/errors/{entry.id}",
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
            "title": document.title,
            "summary": f"{document.department} {document.machine}".strip(),
            "url": document.to_dict()["download_url"],
        }
        for document in documents
    ]

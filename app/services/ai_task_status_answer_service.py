"""Structured AI answers for maintenance task status questions."""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta

from app.models import Task, TaskStatus
from app.security import has_dashboard_permission
from app.services.ai_prompting import permission_denied_answer
from app.services.task_service import visible_tasks_query

TASK_TERMS = ("task", "tasks", "aufgabe", "aufgaben")
COUNT_TERMS = ("wie viele", "wieviele", "anzahl", "count")
LIST_TERMS = ("welche", "zeige", "liste", "auflisten", "anzeigen")
YESTERDAY_TERMS = ("gestern",)
STATUS_TERMS = (
    (TaskStatus.IN_PROGRESS, ("in bearbeitung", "in arbeit")),
    (TaskStatus.DONE, ("beendet", "geschlossen", "erledigt", "abgeschlossen")),
    (TaskStatus.OPEN, ("offen",)),
)
STATUS_LABELS = {
    TaskStatus.OPEN: "offen",
    TaskStatus.IN_PROGRESS: "in Bearbeitung",
    TaskStatus.DONE: "beendet",
}
MAX_LIST_ITEMS = 20
MAX_ANSWER_ITEMS = 10


def answer_task_status_question(message, user, conversation_context=None):
    """Return a structured task-status answer or None for unrelated messages."""
    text = _lookup_text(message)
    status = _requested_status(text)
    if not status:
        return None

    has_task_reference = _has_task_reference(text)
    has_task_followup = _has_task_followup(text, conversation_context)
    if not has_task_reference and not has_task_followup:
        return None

    if not _is_task_status_question(text, status):
        return None

    if not has_dashboard_permission(user, "tasks", "view"):
        return {
            "type": "permission_denied",
            "answer": permission_denied_answer("Tasks", "tasks"),
            "data": [],
            "sources": [],
        }

    query = _status_query(user, status, text)
    count = query.count()
    items = _matching_tasks(query, status, text)
    timeframe = _timeframe_label(status, text)
    return {
        "type": "tasks_status",
        "answer": _format_answer(status, count, items, timeframe, _is_count_question(text)),
        "data": {
            "status": status.value,
            "status_label": STATUS_LABELS[status],
            "count": count,
            "timeframe": timeframe,
            "items": [task.to_dict() for task in items],
        },
        "sources": [],
    }


def _status_query(user, status, text):
    """Return the visible task query filtered by status and supported dates."""
    query = visible_tasks_query(user).filter(Task.status == status)
    if status == TaskStatus.DONE and _mentions_yesterday(text):
        start_at, end_at = _yesterday_bounds()
        query = query.filter(Task.completed_at >= start_at, Task.completed_at <= end_at)
    return query


def _matching_tasks(query, status, text):
    """Return a bounded list of matching tasks for display and diagnostics."""
    if status == TaskStatus.DONE and _mentions_yesterday(text):
        query = query.order_by(Task.completed_at.desc(), Task.id.desc())
    else:
        query = query.order_by(Task.due_date.asc(), Task.id.desc())
    return query.limit(MAX_LIST_ITEMS).all()


def _format_answer(status, count, tasks, timeframe, count_question):
    """Return a concise German answer grounded in structured task data."""
    status_label = STATUS_LABELS[status]
    lines = [
        "## Task-Status",
        f"- **Status:** {status_label}",
        f"- **Zeitraum:** {timeframe}",
        f"- **Anzahl:** {count}",
        "- **Quelle:** Strukturierte Task-Daten",
    ]
    if count == 0:
        lines.append("")
        lines.append("Keine passenden sichtbaren Tasks gefunden.")
        return "\n".join(lines)
    if count_question:
        return "\n".join(lines)

    lines.append("")
    lines.append("Sichtbare Treffer:")
    for task in tasks[:MAX_ANSWER_ITEMS]:
        completed = (
            f", abgeschlossen: {task.completed_at:%Y-%m-%d %H:%M}"
            if task.completed_at
            else ""
        )
        lines.append(f"- #{task.id} {task.title} ({task.status.value}{completed})")
    if count > MAX_ANSWER_ITEMS:
        lines.append(f"- ... {count - MAX_ANSWER_ITEMS} weitere passende Tasks")
    return "\n".join(lines)


def _is_task_status_question(text, status):
    """Return whether the normalized text asks for a task status result."""
    if _is_count_question(text):
        return True
    if _is_list_question(text) and _starts_with_task_list_request(text):
        return True
    return status == TaskStatus.DONE and _mentions_yesterday(text)


def _starts_with_task_list_request(text):
    """Return whether a list question asks for tasks themselves."""
    prefixes = (
        "welche task",
        "welche aufgabe",
        "zeige task",
        "zeige aufgabe",
        "liste task",
        "liste aufgabe",
    )
    return any(text.startswith(prefix) for prefix in prefixes)


def _requested_status(text):
    """Return the requested task status, if the wording is supported."""
    for status, terms in STATUS_TERMS:
        if any(term in text for term in terms):
            return status
    return None


def _has_task_reference(text):
    """Return whether the message explicitly references tasks."""
    return any(term in text for term in TASK_TERMS)


def _has_task_followup(text, conversation_context):
    """Return whether the message is an allowed task-related follow-up."""
    if _has_task_reference(text) or not _is_count_question(text):
        return False
    recent_scopes = getattr(conversation_context, "recent_scopes", ()) or ()
    return "tasks" in set(recent_scopes)


def _is_count_question(text):
    """Return whether the message asks for a count."""
    return any(term in text for term in COUNT_TERMS)


def _is_list_question(text):
    """Return whether the message asks for matching task rows."""
    return any(term in text for term in LIST_TERMS)


def _mentions_yesterday(text):
    """Return whether the message asks for yesterday."""
    return any(term in text for term in YESTERDAY_TERMS)


def _timeframe_label(status, text):
    """Return the human-readable timeframe label for the answer."""
    if status == TaskStatus.DONE and _mentions_yesterday(text):
        yesterday = date.today() - timedelta(days=1)
        return f"gestern ({yesterday.isoformat()})"
    return "alle sichtbaren Tasks"


def _yesterday_bounds():
    """Return local yesterday bounds for completed_at filtering."""
    yesterday = date.today() - timedelta(days=1)
    return datetime.combine(yesterday, time.min), datetime.combine(yesterday, time.max)


def _lookup_text(value):
    """Return lowercase lookup text normalized for German variants."""
    text = " ".join(str(value or "").lower().split())
    replacements = {
        "\u00e4": "ae",
        "\u00f6": "oe",
        "\u00fc": "ue",
        "\u00df": "ss",
        "\u00c3\u00a4": "ae",
        "\u00c3\u00b6": "oe",
        "\u00c3\u00bc": "ue",
        "\u00c3\u009f": "ss",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    text = re.sub(r"[^\w\s-]+", " ", text)
    return " ".join(text.split())

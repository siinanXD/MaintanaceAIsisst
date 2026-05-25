"""Build permission-aware incident timelines from existing maintenance data."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta

from app.models import ErrorEntry, Machine, ShiftHandover, Task, TaskStatus
from app.security import has_dashboard_permission
from app.services.error_service import visible_errors_query
from app.services.task_service import visible_tasks_query

DEFAULT_TIMELINE_DAYS = 30
DEFAULT_TIMELINE_LIMIT = 60
MAX_TIMELINE_LIMIT = 200


def incident_timeline(user, args=None):
    """Return a bounded incident timeline for visible maintenance data."""
    args = args or {}
    days = _bounded_int(args.get("days"), DEFAULT_TIMELINE_DAYS, 1, 365)
    limit = _bounded_int(args.get("limit"), DEFAULT_TIMELINE_LIMIT, 1, MAX_TIMELINE_LIMIT)
    machine_id = _optional_int(args.get("machine_id"))
    since = datetime.now(UTC) - timedelta(days=days)
    events = []
    events.extend(_error_events(user, since, machine_id))
    events.extend(_task_events(user, since, machine_id))
    events.extend(_handover_events(user, since, machine_id))
    events.sort(key=lambda item: item["occurred_at"], reverse=True)
    limited_events = events[:limit]
    sequences = _recurring_sequences(list(reversed(events)))
    return {
        "items": [_serialize_event(item) for item in limited_events],
        "sequences": sequences[:10],
        "stats": _stats(events, sequences, days),
        "filters": {"days": days, "limit": limit, "machine_id": machine_id},
        "explainability": {
            "method": "visible_errors_tasks_shift_handovers_ordered_by_time",
            "permission_aware": True,
            "sequence_window_hours": 48,
        },
    }


def timeline_context_for_query(message, user, query_understanding=None, limit=6):
    """Return compact timeline context when a query asks for history or trends."""
    query_type = ""
    if query_understanding is not None:
        query_type = getattr(query_understanding, "query_type", "")
    if query_type != "trend_history_question" and not _looks_temporal(message):
        return {"context": "", "sources": [], "summary": {}}
    timeline = incident_timeline(user, {"days": 30, "limit": limit})
    if not timeline["items"]:
        return {"context": "", "sources": [], "summary": timeline["stats"]}
    lines = ["Incident Timeline Kontext:"]
    for item in timeline["items"][:limit]:
        lines.append(
            f"- {item['occurred_at']}: {item['type']} {item['title']} "
            f"({item.get('machine') or 'ohne Maschine'})"
        )
    if timeline["sequences"]:
        lines.append("Wiederkehrende Sequenzen:")
        for sequence in timeline["sequences"][:3]:
            lines.append(
                f"- {sequence['machine']}: {' -> '.join(sequence['pattern'])} "
                f"({sequence['count']}x)"
            )
    sources = [
        {
            "type": item["type"],
            "id": item["id"],
            "title": item["title"],
            "module": item["module"],
            "url": item["url"],
            "reason": "Timeline-Kontext",
            "score": 35,
        }
        for item in timeline["items"][:limit]
    ]
    return {"context": "\n".join(lines), "sources": sources, "summary": timeline["stats"]}


def daily_briefing_timeline_section(user):
    """Return a minimal daily briefing section for incident timelines."""
    timeline = incident_timeline(user, {"days": 7, "limit": 20})
    sequences = timeline.get("sequences") or []
    if not sequences:
        return None
    items = [
        {
            "title": sequence["machine"],
            "severity": "high" if sequence["count"] >= 2 else "medium",
            "summary": " -> ".join(sequence["pattern"]),
            "url": "/errors",
            "occurrence_count": sequence["count"],
        }
        for sequence in sequences[:3]
    ]
    return {
        "type": "incident_timeline",
        "title": "Incident Timeline",
        "count": len(items),
        "items": items,
        "diagnostics": timeline.get("explainability", {}),
    }


def _error_events(user, since, machine_id):
    """Return visible error events for the timeline."""
    if not has_dashboard_permission(user, "errors", "view"):
        return []
    query = visible_errors_query(user).filter(ErrorEntry.created_at >= since)
    if machine_id:
        query = query.filter(ErrorEntry.machine_id == machine_id)
    events = []
    for entry in query.order_by(ErrorEntry.created_at.desc()).limit(300).all():
        events.append(
            {
                "type": "error",
                "id": entry.id,
                "module": "errors",
                "title": f"{entry.error_code} - {entry.title}",
                "machine": entry.machine_rel.name if entry.machine_rel else entry.machine,
                "machine_id": entry.machine_id,
                "occurred_at": _aware(entry.created_at),
                "url": "/errors",
                "severity": entry.severity,
                "signature": entry.error_code or entry.title,
            }
        )
    return events


def _task_events(user, since, machine_id):
    """Return visible task events that can enrich the incident timeline."""
    if not has_dashboard_permission(user, "tasks", "view"):
        return []
    machine = Machine.query.get(machine_id) if machine_id else None
    query = visible_tasks_query(user).filter(Task.created_at >= since)
    events = []
    for task in query.order_by(Task.created_at.desc()).limit(300).all():
        if machine and _name_key(machine.name) not in _name_key(f"{task.title} {task.description}"):
            continue
        events.append(
            {
                "type": "task",
                "id": task.id,
                "module": "tasks",
                "title": task.title,
                "machine": machine.name if machine else _machine_hint(task.title, task.description),
                "machine_id": machine_id,
                "occurred_at": _aware(task.created_at),
                "url": "/tasks",
                "severity": _task_severity(task),
                "signature": task.status.value,
            }
        )
    return events


def _handover_events(user, since, machine_id):
    """Return visible shift-handover events with machine notes."""
    if not has_dashboard_permission(user, "shiftplans", "view"):
        return []
    machine = Machine.query.get(machine_id) if machine_id else None
    query = ShiftHandover.query.filter(ShiftHandover.created_at >= since)
    if not user.is_admin and user.department:
        query = query.filter(ShiftHandover.department == user.department.name)
    events = []
    for handover in query.order_by(ShiftHandover.created_at.desc()).limit(150).all():
        machine_text = handover.machine_notes or handover.content
        if machine and _name_key(machine.name) not in _name_key(machine_text):
            continue
        events.append(
            {
                "type": "shift_handover",
                "id": handover.id,
                "module": "shiftplans",
                "title": f"Schichtuebergabe {handover.shift_type}",
                "machine": machine.name if machine else _machine_hint(machine_text),
                "machine_id": machine_id,
                "occurred_at": _aware(handover.created_at),
                "url": "/handover",
                "severity": "info",
                "signature": "handover",
            }
        )
    return events


def _recurring_sequences(events):
    """Return recurring event sequences by machine within a 48-hour window."""
    by_machine = defaultdict(list)
    for event in events:
        machine = event.get("machine") or "Unbekannte Maschine"
        by_machine[machine].append(event)
    counter = Counter()
    for machine, machine_events in by_machine.items():
        for left, right in zip(machine_events, machine_events[1:], strict=False):
            delta = right["occurred_at"] - left["occurred_at"]
            if delta.total_seconds() < 0 or delta.total_seconds() > 48 * 3600:
                continue
            pattern = (_pattern_label(left), _pattern_label(right))
            counter[(machine, pattern)] += 1
    return [
        {
            "machine": machine,
            "pattern": list(pattern),
            "count": count,
        }
        for (machine, pattern), count in counter.most_common()
        if count >= 1
    ]


def _stats(events, sequences, days):
    """Return compact timeline statistics."""
    return {
        "event_count": len(events),
        "sequence_count": len(sequences),
        "window_days": days,
        "by_type": dict(Counter(event["type"] for event in events)),
        "by_machine": dict(Counter(event.get("machine") or "" for event in events).most_common(8)),
    }


def _serialize_event(event):
    """Return a JSON-safe timeline event."""
    payload = dict(event)
    payload["occurred_at"] = event["occurred_at"].isoformat()
    return payload


def _pattern_label(event):
    """Return a compact sequence pattern label."""
    if event["type"] == "error":
        return event.get("signature") or "Fehler"
    return event["type"]


def _task_severity(task):
    """Return a severity label for a task event."""
    if task.status == TaskStatus.OPEN and task.priority.value == "urgent":
        return "high"
    if task.status == TaskStatus.IN_PROGRESS:
        return "medium"
    return "info"


def _machine_hint(*values):
    """Return a simple machine-like label from text values."""
    text = " ".join(str(value or "") for value in values)
    lowered = text.lower()
    for marker in ("maschine", "anlage", "linie", "presse", "roboter"):
        index = lowered.find(marker)
        if index >= 0:
            return " ".join(text[index : index + 80].split())[:80]
    return ""


def _looks_temporal(message):
    """Return whether a message asks for temporal context."""
    text = _name_key(message)
    return any(
        keyword in text
        for keyword in ("historie", "verlauf", "trend", "wiederkehrend", "danach", "vorher")
    )


def _bounded_int(value, default, minimum, maximum):
    """Return a bounded integer value."""
    try:
        parsed = int(value if value not in (None, "") else default)
    except (TypeError, ValueError):
        parsed = default
    return min(max(parsed, minimum), maximum)


def _optional_int(value):
    """Return an optional integer value."""
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _aware(value):
    """Return a timezone-aware UTC datetime."""
    if value.tzinfo:
        return value.astimezone(UTC)
    return value.replace(tzinfo=UTC)


def _name_key(value):
    """Return normalized text for matching."""
    return " ".join(str(value or "").strip().lower().split())

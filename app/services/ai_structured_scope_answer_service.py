"""Generic structured follow-up answers for the AI assistant."""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta

from app.models import Department, ErrorEntry, Priority, Task, TaskStatus
from app.security import has_dashboard_permission
from app.services.ai_prompting import permission_denied_answer
from app.services.ai_question_normalizer import (
    detect_department,
    detect_severity,
    detect_status,
    detect_time_range,
    is_structured_follow_up,
    mentions_my_area,
    normalize_text,
)
from app.services.ai_structured_source_service import (
    incident_source_cards,
    incident_source_cards_from_payloads,
    module_count_source_card,
    task_source_cards,
)
from app.services.error_service import visible_errors_query
from app.services.task_service import visible_tasks_query

COUNT_TERMS = ("wie viele", "wieviele", "anzahl", "count")
LIST_TERMS = ("welche", "zeige", "zeig", "liste", "auflisten", "anzeigen")
TASK_ENTITY_TERMS = ("task", "tasks", "aufgabe", "aufgaben")
INCIDENT_ENTITY_TERMS = ("stoerung", "stoerungen", "fehler", "incident", "incidents")
SUPPORTED_ENTITIES = {"tasks", "incidents"}
MAX_ITEMS = 20
ANSWER_ITEMS = 10


def answer_structured_scope_question(message, user, conversation_context=None):
    """Return a permission-aware structured answer for explicit or follow-up scopes."""
    text = normalize_text(message)
    inherited_context = dict(getattr(conversation_context, "structured_scope", {}) or {})
    follow_up = is_structured_follow_up(text)
    explicit_entity = _entity_type_from_text(text)
    entity_type = explicit_entity or (inherited_context.get("entity_type") if follow_up else "")
    if entity_type not in SUPPORTED_ENTITIES:
        return None
    if not explicit_entity and not follow_up:
        return None
    if explicit_entity and not _has_structured_signal(text, explicit_entity):
        return None
    if _should_defer_task_status_answer(text, explicit_entity, follow_up):
        return None

    filters = _merged_filters(inherited_context if follow_up else {}, text, entity_type)
    if entity_type == "tasks":
        return _answer_tasks(message, user, filters)
    if entity_type == "incidents":
        return _answer_incidents(message, user, filters)
    return None


def _answer_tasks(message, user, filters):
    """Return a structured task answer for the requested filters."""
    if not has_dashboard_permission(user, "tasks", "view"):
        return _permission_denied("Tasks", "tasks")

    query = _filtered_task_query(user, filters)
    count = query.count()
    tasks = _ordered_tasks(query, filters).limit(MAX_ITEMS).all()
    count_question = _is_count_question(message)
    sources = _task_sources(tasks, count, user)
    return {
        "type": "structured_scope",
        "answer": _format_answer("Tasks", count, tasks, filters, count_question),
        "data": {
            "entity_type": "tasks",
            "count": count,
            "filters": _public_filters(filters),
            "items": [task.to_dict() for task in tasks],
        },
        "sources": sources,
        "scope": "tasks",
        "structured_context": _structured_context("tasks", filters),
    }


def _answer_incidents(message, user, filters):
    """Return a structured incident answer for the requested filters."""
    if not has_dashboard_permission(user, "errors", "view"):
        return _permission_denied("Fehlerkatalog", "errors")
    if _mentions_incident_machine_aggregation(normalize_text(message)):
        return _answer_incident_machine_aggregation(user, filters)

    query = _filtered_incident_query(user, filters)
    count = query.count()
    incidents = _ordered_incidents(query, filters).limit(MAX_ITEMS).all()
    count_question = _is_count_question(message)
    sources = _incident_sources(incidents, count, user)
    return {
        "type": "structured_scope",
        "answer": _format_answer("Stoerungen", count, incidents, filters, count_question),
        "data": {
            "entity_type": "incidents",
            "count": count,
            "filters": _public_filters(filters),
            "items": [incident.to_dict() for incident in incidents],
        },
        "sources": sources,
        "scope": "errors",
        "structured_context": _structured_context("incidents", filters),
    }


def _answer_incident_machine_aggregation(user, filters):
    """Return the machine with the most visible incident records."""
    query = _filtered_incident_query(user, filters)
    incidents = query.order_by(ErrorEntry.created_at.desc(), ErrorEntry.id.desc()).all()
    groups = _incident_machine_groups(incidents)
    top_group = groups[0] if groups else None
    sources = incident_source_cards_from_payloads(top_group["examples"] if top_group else [])
    if not sources:
        aggregate_source = module_count_source_card("errors", len(incidents), user)
        sources = [aggregate_source] if aggregate_source else []
    return {
        "type": "structured_scope",
        "answer": _format_machine_aggregation_answer(top_group, groups, filters),
        "data": {
            "entity_type": "incidents",
            "count": len(incidents),
            "filters": _public_filters(filters),
            "aggregation": {
                "group_by": "machine",
                "top": top_group,
                "groups": groups[:ANSWER_ITEMS],
            },
            "items": top_group["examples"] if top_group else [],
        },
        "sources": sources,
        "scope": "errors",
        "structured_context": _structured_context("incidents", filters),
    }


def _task_sources(tasks, count, user):
    """Return row or aggregate source cards for a structured task answer."""
    sources = task_source_cards(tasks)
    if sources:
        return sources
    aggregate_source = module_count_source_card("tasks", count, user)
    return [aggregate_source] if aggregate_source else []


def _incident_sources(incidents, count, user):
    """Return row or aggregate source cards for a structured incident answer."""
    sources = incident_source_cards(incidents)
    if sources:
        return sources
    aggregate_source = module_count_source_card("errors", count, user)
    return [aggregate_source] if aggregate_source else []


def _filtered_task_query(user, filters):
    """Return visible tasks filtered by inherited structured context."""
    query = visible_tasks_query(user)
    status = filters.get("status")
    if status:
        query = query.filter(Task.status == _task_status(status))
    if filters.get("department"):
        query = query.filter(Task.department.has(Department.name == filters["department"]))
    if filters.get("priority") == "urgent":
        query = query.filter(Task.priority == Priority.URGENT)
    if filters.get("machine"):
        pattern = f"%{filters['machine']}%"
        query = query.filter(db_or(Task.title.ilike(pattern), Task.description.ilike(pattern)))
    if filters.get("time_range") == "yesterday":
        start_at, end_at = _yesterday_bounds()
        if status == "done":
            query = query.filter(Task.completed_at >= start_at, Task.completed_at <= end_at)
        else:
            query = query.filter(Task.created_at >= start_at, Task.created_at <= end_at)
    return query


def _filtered_incident_query(user, filters):
    """Return visible incidents filtered by inherited structured context."""
    query = visible_errors_query(user)
    status = filters.get("status")
    if status:
        query = query.filter(ErrorEntry.status == _incident_status(status))
    if filters.get("department"):
        query = query.filter(ErrorEntry.department.has(Department.name == filters["department"]))
    if filters.get("severity") == "critical":
        query = query.filter(ErrorEntry.severity == "critical")
    if filters.get("machine"):
        pattern = f"%{filters['machine']}%"
        query = query.filter(ErrorEntry.machine.ilike(pattern))
    if filters.get("time_range") in {"today", "yesterday"}:
        start_at, end_at = _yesterday_bounds()
        if filters.get("time_range") == "today":
            start_at, end_at = _today_bounds()
        if status == "done":
            query = query.filter(ErrorEntry.closed_at >= start_at, ErrorEntry.closed_at <= end_at)
        else:
            query = query.filter(ErrorEntry.created_at >= start_at, ErrorEntry.created_at <= end_at)
    return query


def _ordered_tasks(query, filters):
    """Return task query ordered for stable structured answers."""
    if filters.get("status") == "done":
        return query.order_by(Task.completed_at.desc(), Task.id.desc())
    return query.order_by(Task.priority.asc(), Task.due_date.asc(), Task.id.desc())


def _ordered_incidents(query, filters):
    """Return incident query ordered for stable structured answers."""
    if filters.get("status") == "done":
        return query.order_by(ErrorEntry.closed_at.desc(), ErrorEntry.id.desc())
    return query.order_by(ErrorEntry.created_at.desc(), ErrorEntry.id.desc())


def _format_answer(label, count, items, filters, count_question):
    """Return a compact German answer for structured data."""
    lines = [
        f"## {label}",
        f"- **Anzahl:** {count}",
        f"- **Filter:** {_filter_summary(filters)}",
        "- **Quelle:** Strukturierte Daten",
    ]
    if count == 0:
        lines.append("")
        lines.append("Keine passenden sichtbaren Eintraege gefunden.")
        return "\n".join(lines)
    if count_question:
        return "\n".join(lines)

    lines.append("")
    lines.append("Sichtbare Treffer:")
    for item in items[:ANSWER_ITEMS]:
        lines.append(_item_line(item))
    if count > ANSWER_ITEMS:
        lines.append(f"- ... {count - ANSWER_ITEMS} weitere passende Eintraege")
    return "\n".join(lines)


def _item_line(item):
    """Return one answer line for a task or incident."""
    department_name = item.department.name if item.department else "ohne Bereich"
    if isinstance(item, Task):
        return f"- #{item.id} {item.title} ({item.status.value}, {department_name})"
    return f"- #{item.id} {item.title} ({item.status}, {item.severity}, {department_name})"


def _incident_machine_groups(incidents):
    """Return visible incident groups keyed by machine identity."""
    groups = {}
    for incident in incidents:
        machine_name = incident.machine or "Unbekannte Maschine"
        key = (incident.machine_id or "", machine_name)
        group = groups.setdefault(
            key,
            {
                "machine_id": incident.machine_id,
                "machine": machine_name,
                "count": 0,
                "examples": [],
            },
        )
        group["count"] += 1
        if len(group["examples"]) < 5:
            group["examples"].append(incident.to_dict())
    return sorted(groups.values(), key=lambda item: (-item["count"], item["machine"]))


def _format_machine_aggregation_answer(top_group, groups, filters):
    """Return a compact German incident aggregation answer."""
    lines = [
        "## Stoerungen nach Maschine",
        f"- **Filter:** {_filter_summary(filters)}",
        "- **Quelle:** Strukturierte Fehlerdaten",
    ]
    if not top_group:
        lines.append("- **Status:** Keine passenden sichtbaren Stoerungen gefunden.")
        return "\n".join(lines)
    lines.extend(
        [
            f"- **Top-Maschine:** {top_group['machine']}",
            f"- **Anzahl:** {top_group['count']}",
            "",
            "Sichtbare Beispiele:",
        ]
    )
    for incident in top_group["examples"][:ANSWER_ITEMS]:
        lines.append(
            f"- #{incident['id']} {incident['error_code']} - {incident['title']} "
            f"({incident['status']}, {incident['severity']})"
        )
    if len(groups) > 1:
        lines.append("")
        lines.append("Weitere Maschinen:")
        for group in groups[1:ANSWER_ITEMS]:
            lines.append(f"- {group['machine']}: {group['count']}")
    return "\n".join(lines)


def _filter_summary(filters):
    """Return human-readable filter labels."""
    labels = []
    for key in ("department", "status", "time_range", "machine", "priority", "severity"):
        value = filters.get(key)
        if value:
            labels.append(f"{key}={value}")
    return ", ".join(labels) if labels else "keine Zusatzfilter"


def _merged_filters(base_context, text, entity_type):
    """Merge previous structured context with filters from the current message."""
    filters = {
        key: value
        for key, value in (base_context or {}).items()
        if key in {"department", "status", "time_range", "machine"} and value
    }
    previous_status = filters.get("status")
    status = detect_status(text)
    time_range = detect_time_range(text)
    if status:
        filters["status"] = status
        if _should_drop_inherited_time_range(
            entity_type,
            previous_status,
            status,
            time_range,
        ):
            filters.pop("time_range", None)
    if time_range:
        filters["time_range"] = time_range
    department = detect_department(text)
    if department:
        filters["department"] = department
    machine = "" if _mentions_incident_machine_aggregation(text) else _machine_from_text(text)
    if machine:
        filters["machine"] = machine
    if entity_type == "tasks" and _mentions_urgent(text):
        filters["priority"] = "urgent"
    severity = detect_severity(text)
    if entity_type == "incidents" and severity:
        filters["severity"] = severity
    return filters


def _should_drop_inherited_time_range(entity_type, previous_status, status, time_range):
    """Return whether a status-changing task follow-up should avoid stale time filters."""
    return (
        entity_type == "tasks"
        and bool(previous_status)
        and bool(status)
        and previous_status != status
        and not time_range
    )


def _structured_context(entity_type, filters):
    """Return the persisted structured memory payload."""
    context = {"entity_type": entity_type}
    for key in ("department", "status", "time_range", "machine"):
        if filters.get(key):
            context[key] = filters[key]
    return context


def _public_filters(filters):
    """Return safe structured filters for the API payload."""
    return dict(filters)


def _permission_denied(label, scope):
    """Return a permission denied result for a structured scope."""
    return {
        "type": "permission_denied",
        "answer": permission_denied_answer(label, scope),
        "data": [],
        "sources": [],
        "scope": scope,
    }


def _has_structured_signal(text, entity_type):
    """Return whether explicit entity wording asks for structured filtering."""
    common_signal = bool(detect_status(text)) or bool(detect_department(text))
    if entity_type == "tasks":
        return common_signal or _mentions_urgent(text)
    if entity_type == "incidents":
        return (
            common_signal
            or _is_count_question(text)
            or any(term in text for term in LIST_TERMS)
            or bool(detect_time_range(text))
            or bool(detect_severity(text))
            or mentions_my_area(text)
            or _mentions_incident_machine_aggregation(text)
        )
    return common_signal


def _mentions_incident_machine_aggregation(text):
    """Return whether the message asks for incident counts grouped by machine."""
    return any(term in text for term in INCIDENT_ENTITY_TERMS) and any(
        term in text
        for term in (
            "meisten",
            "haeufigsten",
            "meiste",
            "top maschine",
            "top-maschine",
            "am meisten",
        )
    )


def _should_defer_task_status_answer(text, explicit_entity, follow_up):
    """Return whether the existing task-status answer should handle the question."""
    if explicit_entity != "tasks" or follow_up:
        return False
    if not detect_status(text):
        return False
    return not any(
        (
            detect_department(text),
            _mentions_urgent(text),
            _machine_from_text(text),
        )
    )


def _entity_type_from_text(text):
    """Return the explicit structured entity type, if any."""
    if _mentions_incident_machine_aggregation(text):
        return "incidents"
    if text.startswith(("welche maschine", "welche anlage")):
        return ""
    if any(term in text for term in TASK_ENTITY_TERMS):
        return "tasks"
    if any(term in text for term in INCIDENT_ENTITY_TERMS):
        return "incidents"
    return ""


def _machine_from_text(text):
    """Return a machine phrase mentioned in the message."""
    match = re.search(
        r"\b(?:maschine|anlage|presse|linie|station|roboter|ofen)\s+[a-z0-9-]+\b",
        text,
    )
    return " ".join(match.group(0).split()) if match else ""


def _mentions_urgent(text):
    """Return whether the message asks for urgent task priority."""
    return any(term in text for term in ("dringend", "dringende", "urgent"))


def _is_count_question(message):
    """Return whether the message asks for a count."""
    text = normalize_text(message)
    return any(term in text for term in COUNT_TERMS)


def _task_status(status):
    """Return a TaskStatus for a normalized structured status."""
    mapping = {
        "open": TaskStatus.OPEN,
        "in_progress": TaskStatus.IN_PROGRESS,
        "done": TaskStatus.DONE,
    }
    return mapping.get(status, TaskStatus.OPEN)


def _incident_status(status):
    """Return an incident status for a normalized structured status."""
    return "closed" if status == "done" else status


def _yesterday_bounds():
    """Return local yesterday bounds for date filtering."""
    yesterday = date.today() - timedelta(days=1)
    return datetime.combine(yesterday, time.min), datetime.combine(yesterday, time.max)


def _today_bounds():
    """Return local today bounds for date filtering."""
    today = date.today()
    return datetime.combine(today, time.min), datetime.combine(today, time.max)


def db_or(*conditions):
    """Return SQLAlchemy OR expression without importing db at module load call sites."""
    from app.extensions import db

    return db.or_(*conditions)

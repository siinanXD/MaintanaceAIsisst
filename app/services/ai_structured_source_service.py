"""Safe source-card builders for structured AI answer rows."""

from datetime import UTC, datetime

from app.security import employee_access_level

SOURCE_CARD_LIMIT = 5

_MODULE_COUNT_SOURCES = {
    "admin_users": {
        "label": "Admin Users",
        "module": "admin_users",
        "url": "/admin/users",
    },
    "documents": {
        "label": "Dokumente",
        "module": "documents",
        "url": "/documents",
    },
    "employees": {
        "label": "Mitarbeiter",
        "module": "employees",
        "url": "/employees",
    },
    "errors": {
        "label": "Fehlerkatalog",
        "module": "errors",
        "url": "/errors",
    },
    "inventory": {
        "label": "Lager",
        "module": "inventory",
        "url": "/inventory",
    },
    "machines": {
        "label": "Maschinen",
        "module": "machines",
        "url": "/machines",
    },
    "shiftplans": {
        "label": "Schichtplanung",
        "module": "shiftplans",
        "url": "/shiftplans",
    },
    "tasks": {
        "label": "Tasks",
        "module": "tasks",
        "url": "/tasks",
    },
}


def task_source_cards(tasks, limit=SOURCE_CARD_LIMIT):
    """Return compact source cards for already-visible structured task rows."""
    return [_task_source_card(task) for task in list(tasks or [])[:limit]]


def incident_source_cards(incidents, limit=SOURCE_CARD_LIMIT):
    """Return compact source cards for already-visible structured incident rows."""
    return [_incident_source_card(incident) for incident in list(incidents or [])[:limit]]


def incident_source_cards_from_payloads(incidents, limit=SOURCE_CARD_LIMIT):
    """Return compact source cards from already-visible incident payloads."""
    return [
        _incident_source_card_from_payload(incident)
        for incident in list(incidents or [])[:limit]
    ]


def machine_source_cards(machines, limit=SOURCE_CARD_LIMIT):
    """Return compact source cards for already-visible machine rows."""
    return [_machine_source_card(machine) for machine in list(machines or [])[:limit]]


def machine_source_card(machine):
    """Return one compact source card for an already-visible machine row."""
    return _machine_source_card(machine) if machine else None


def module_count_source_card(scope, count, user):
    """Return one compact aggregate source card for a visible module count."""
    if not count:
        return None

    config = _MODULE_COUNT_SOURCES.get(scope)
    if not config:
        return None

    source = {
        "type": "aggregate",
        "id": None,
        "title": f"{config['label']} Anzahl",
        "module": config["module"],
        "url": config["url"],
        "source_type": "module_count",
        "source_id": None,
        "source_record_id": None,
        "source_kind": "structured_aggregate",
        "role_visibility": _module_count_role_visibility(scope, user),
        "created_at": datetime.now(UTC).isoformat(),
        "count": count,
    }
    if scope == "employees":
        source["employee_access_level"] = employee_access_level(user)
    return source


def _task_source_card(task):
    """Return one prompt-safe task source card."""
    department = _department_name(task)
    return {
        "type": "task",
        "id": task.id,
        "title": task.title,
        "module": "tasks",
        "url": "/tasks",
        "source_type": "task",
        "source_id": task.id,
        "source_record_id": task.id,
        "source_kind": "structured",
        "department": department,
        "role_visibility": _role_visibility(department),
        "created_at": _isoformat(task.created_at),
        "status": task.status.value if task.status else "",
        "priority": task.priority.value if task.priority else "",
        "due_date": task.due_date.isoformat() if task.due_date else "",
    }


def _incident_source_card(incident):
    """Return one prompt-safe incident source card."""
    department = _department_name(incident)
    return {
        "type": "error",
        "id": incident.id,
        "title": _incident_source_title(incident.error_code, incident.title),
        "module": "errors",
        "url": "/errors",
        "source_type": "error",
        "source_id": incident.id,
        "source_record_id": incident.id,
        "source_kind": "structured",
        "department": department,
        "machine": incident.machine,
        "machine_id": incident.machine_id,
        "role_visibility": _role_visibility(department),
        "created_at": _isoformat(incident.created_at),
        "status": incident.status,
        "severity": incident.severity,
        "error_code": incident.error_code,
    }


def _incident_source_card_from_payload(incident):
    """Return one prompt-safe incident source card from a public payload."""
    department = _payload_department_name(incident)
    incident_id = incident.get("id")
    return {
        "type": "error",
        "id": incident_id,
        "title": _incident_source_title(incident.get("error_code"), incident.get("title")),
        "module": "errors",
        "url": "/errors",
        "source_type": "error",
        "source_id": incident_id,
        "source_record_id": incident_id,
        "source_kind": "structured",
        "department": department,
        "machine": incident.get("machine") or "",
        "machine_id": incident.get("machine_id"),
        "role_visibility": _role_visibility(department),
        "created_at": incident.get("created_at") or "",
        "status": incident.get("status") or "",
        "severity": incident.get("severity") or "",
        "error_code": incident.get("error_code") or "",
    }


def _machine_source_card(machine):
    """Return one prompt-safe machine source card."""
    return {
        "type": "machine",
        "id": machine.id,
        "title": machine.name,
        "module": "machines",
        "url": "/machines",
        "source_type": "machine",
        "source_id": machine.id,
        "source_record_id": machine.id,
        "source_kind": "structured",
        "machine_id": machine.id,
        "machine": machine.name,
        "role_visibility": "public",
        "created_at": _isoformat(machine.created_at),
        "status": machine.status,
        "criticality": machine.criticality,
        "produced_item": machine.produced_item,
        "site_id": machine.site_id,
        "last_downtime_at": _isoformat(machine.last_downtime_at),
    }


def _incident_source_title(error_code, title):
    """Return the compact incident source title."""
    safe_title = str(title or "").strip()
    safe_code = str(error_code or "").strip()
    return f"{safe_code} - {safe_title}" if safe_code else safe_title


def _department_name(record):
    """Return a bounded department name from a structured row."""
    department = getattr(record, "department", None)
    if isinstance(department, str):
        return department[:120]
    return str(getattr(department, "name", "") or "")[:120]


def _payload_department_name(payload):
    """Return a bounded department name from a structured row payload."""
    department = payload.get("department") if isinstance(payload, dict) else None
    if isinstance(department, dict):
        return str(department.get("name") or "")[:120]
    return str(department or "")[:120]


def _role_visibility(department):
    """Return a compact role visibility label for structured source cards."""
    return f"department:{department}" if department else "public"


def _module_count_role_visibility(scope, user):
    """Return a compact role visibility label for module count source cards."""
    if scope == "admin_users":
        return "admin_only"

    department = getattr(getattr(user, "department", None), "name", "")
    return _role_visibility(str(department or "")[:120])


def _isoformat(value):
    """Return an ISO timestamp when available."""
    return value.isoformat() if value else ""

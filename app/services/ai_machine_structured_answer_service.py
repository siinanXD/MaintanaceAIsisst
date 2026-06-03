"""Structured AI answers for machine incident and downtime questions."""

from __future__ import annotations

import re

from sqlalchemy import and_, or_

from app.models import ErrorEntry, Machine
from app.security import has_dashboard_permission
from app.services.ai_prompting import permission_denied_answer
from app.services.ai_question_normalizer import normalize_text
from app.services.ai_structured_source_service import (
    incident_source_cards,
    machine_source_card,
)
from app.services.error_service import visible_errors_query
from app.services.visibility_query_service import visible_machines_query

INCIDENT_TERMS = ("stoerung", "stoerungen", "fehler")
DOWNTIME_TERMS = ("ausfallzeit", "downtime")
MAX_GROUPS = 10
MAX_ITEMS = 20
MAX_ANSWER_ITEMS = 10


def answer_machine_structured_question(message, user, conversation_context=None):
    """Return a structured machine answer for supported machine questions."""
    text = normalize_text(message)
    if not _is_supported_machine_question(text):
        return None
    if not _can_read_machine_incidents(user):
        return _permission_denied()
    if _is_downtime_question(text):
        return _answer_machine_downtime(user)

    machine = _resolve_visible_machine(message, user)
    if not machine:
        return None
    return _answer_machine_incidents(machine, user)


def _answer_machine_downtime(user):
    """Return the visible machine group with the highest downtime sum."""
    incidents = _visible_downtime_incidents(user)
    groups = _downtime_groups(incidents, user)
    top_group = groups[0] if groups else None
    supporting_incidents = top_group["examples"] if top_group else []
    machine = top_group.get("machine_record") if top_group else None
    sources = _machine_and_incident_sources(machine, supporting_incidents)
    return {
        "type": "machine_downtime",
        "answer": _format_downtime_answer(top_group, groups),
        "data": {
            "entity_type": "machines",
            "metric": "downtime_minutes",
            "count": len(incidents),
            "aggregation": {
                "group_by": "machine",
                "top": _public_downtime_group(top_group),
                "groups": [_public_downtime_group(group) for group in groups[:MAX_GROUPS]],
            },
            "items": [incident.to_dict() for incident in supporting_incidents],
        },
        "sources": sources,
        "scope": "machines",
        "structured_context": {"entity_type": "machines"},
    }


def _answer_machine_incidents(machine, user):
    """Return visible incidents for one resolved visible machine."""
    incidents = _incidents_for_machine(machine, user)
    return {
        "type": "machine_incidents",
        "answer": _format_machine_incidents_answer(machine, incidents),
        "data": {
            "entity_type": "incidents",
            "machine": {
                "id": machine.id,
                "name": machine.name,
            },
            "count": len(incidents),
            "items": [incident.to_dict() for incident in incidents],
        },
        "sources": _machine_and_incident_sources(machine, incidents),
        "scope": "machines",
        "structured_context": {
            "entity_type": "incidents",
            "machine": machine.name,
        },
    }


def _visible_downtime_incidents(user):
    """Return visible incident rows with tracked downtime."""
    return (
        visible_errors_query(user)
        .filter(ErrorEntry.downtime_minutes > 0)
        .order_by(ErrorEntry.created_at.desc(), ErrorEntry.id.desc())
        .limit(200)
        .all()
    )


def _incidents_for_machine(machine, user):
    """Return bounded visible incidents for the resolved visible machine."""
    return (
        visible_errors_query(user)
        .filter(
            or_(
                ErrorEntry.machine_id == machine.id,
                and_(
                    ErrorEntry.machine_id.is_(None),
                    ErrorEntry.machine.ilike(machine.name),
                ),
            )
        )
        .order_by(ErrorEntry.created_at.desc(), ErrorEntry.id.desc())
        .limit(MAX_ITEMS)
        .all()
    )


def _downtime_groups(incidents, user):
    """Return visible incident groups keyed by machine id or machine text."""
    visible_machines = _visible_machine_lookup(user)
    groups = {}
    for incident in incidents:
        machine = visible_machines.get(incident.machine_id)
        machine_name = machine.name if machine else incident.machine or "Unbekannte Maschine"
        key = ("id", incident.machine_id) if incident.machine_id else ("name", machine_name.lower())
        group = groups.setdefault(
            key,
            {
                "machine_id": incident.machine_id,
                "machine": machine_name,
                "machine_record": machine,
                "total_downtime_minutes": 0,
                "incident_count": 0,
                "examples": [],
            },
        )
        group["total_downtime_minutes"] += int(incident.downtime_minutes or 0)
        group["incident_count"] += 1
        if len(group["examples"]) < MAX_ANSWER_ITEMS:
            group["examples"].append(incident)
    return sorted(
        groups.values(),
        key=lambda item: (
            -item["total_downtime_minutes"],
            -item["incident_count"],
            item["machine"],
        ),
    )


def _visible_machine_lookup(user):
    """Return visible machines keyed by id."""
    return {
        machine.id: machine
        for machine in visible_machines_query(user).order_by(Machine.name.asc()).all()
    }


def _resolve_visible_machine(message, user):
    """Resolve one machine by matching visible Machine.name in the question."""
    text = normalize_text(message)
    machines = visible_machines_query(user).order_by(Machine.name.asc()).all()
    for machine in sorted(machines, key=lambda item: len(item.name or ""), reverse=True):
        name = normalize_text(machine.name)
        if name and re.search(rf"(?<!\w){re.escape(name)}(?!\w)", text):
            return machine
    return None


def _machine_and_incident_sources(machine, incidents):
    """Return one machine source plus capped visible incident sources."""
    sources = []
    machine_source = machine_source_card(machine)
    if machine_source:
        sources.append(machine_source)
    sources.extend(incident_source_cards(incidents))
    return sources


def _public_downtime_group(group):
    """Return a prompt-safe downtime group payload."""
    if not group:
        return None
    return {
        "machine_id": group["machine_id"],
        "machine": group["machine"],
        "total_downtime_minutes": group["total_downtime_minutes"],
        "incident_count": group["incident_count"],
        "examples": [incident.to_dict() for incident in group["examples"]],
    }


def _format_downtime_answer(top_group, groups):
    """Return a compact German downtime aggregation answer."""
    lines = [
        "## Maschinenausfallzeit",
        "- **Quelle:** Strukturierte Fehlerdaten",
    ]
    if not top_group:
        lines.append("- **Status:** Keine sichtbaren Stoerungen mit Ausfallzeit gefunden.")
        return "\n".join(lines)
    lines.extend(
        [
            f"- **Top-Maschine:** {top_group['machine']}",
            f"- **Ausfallzeit:** {top_group['total_downtime_minutes']} Minuten",
            f"- **Sichtbare Stoerungen:** {top_group['incident_count']}",
            "",
            "Sichtbare Beispiele:",
        ]
    )
    for incident in top_group["examples"][:MAX_ANSWER_ITEMS]:
        lines.append(
            f"- #{incident.id} {incident.error_code} - {incident.title} "
            f"({incident.downtime_minutes} Min.)"
        )
    if len(groups) > 1:
        lines.append("")
        lines.append("Weitere Maschinen:")
        for group in groups[1:MAX_GROUPS]:
            lines.append(f"- {group['machine']}: {group['total_downtime_minutes']} Min.")
    return "\n".join(lines)


def _format_machine_incidents_answer(machine, incidents):
    """Return a compact German incident list for one machine."""
    lines = [
        f"## Stoerungen an {machine.name}",
        f"- **Anzahl:** {len(incidents)}",
        "- **Quelle:** Strukturierte Fehlerdaten",
    ]
    if not incidents:
        lines.append("")
        lines.append("Keine sichtbaren Stoerungen fuer diese Maschine gefunden.")
        return "\n".join(lines)
    lines.append("")
    lines.append("Sichtbare Treffer:")
    for incident in incidents[:MAX_ANSWER_ITEMS]:
        lines.append(
            f"- #{incident.id} {incident.error_code} - {incident.title} "
            f"({incident.status}, {incident.severity})"
        )
    if len(incidents) > MAX_ANSWER_ITEMS:
        lines.append(f"- ... {len(incidents) - MAX_ANSWER_ITEMS} weitere passende Stoerungen")
    return "\n".join(lines)


def _is_supported_machine_question(text):
    """Return whether the message matches this narrow machine structured slice."""
    return _is_downtime_question(text) or _is_machine_incident_list_question(text)


def _is_downtime_question(text):
    """Return whether the message asks for machine downtime aggregation."""
    return any(term in text for term in DOWNTIME_TERMS) and any(
        term in text for term in ("maschine", "anlage")
    )


def _is_machine_incident_list_question(text):
    """Return whether the message asks for incidents or errors at one machine."""
    if _mentions_incident_machine_aggregation(text):
        return False
    has_incident_term = any(term in text for term in INCIDENT_TERMS)
    has_machine_term = any(term in text for term in ("maschine", "anlage", "presse", "linie"))
    return has_incident_term and has_machine_term


def _mentions_incident_machine_aggregation(text):
    """Return whether the message asks for incidents grouped by machine."""
    return any(term in text for term in INCIDENT_TERMS) and any(
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


def _can_read_machine_incidents(user):
    """Return whether the user can read machine and error structured data."""
    return has_dashboard_permission(user, "machines", "view") and has_dashboard_permission(
        user,
        "errors",
        "view",
    )


def _permission_denied():
    """Return a permission-denied structured machine answer."""
    return {
        "type": "permission_denied",
        "answer": permission_denied_answer("Maschinen und Fehlerkatalog"),
        "data": [],
        "sources": [],
        "scope": "machines",
    }

"""Structured AI answers for shift-plan metadata questions."""

from __future__ import annotations

from datetime import date, timedelta

from app.models import ShiftPlan, ShiftPlanCoverageSlot, ShiftPlanEntry
from app.security import employee_access_level, has_dashboard_permission
from app.services.ai_prompting import permission_denied_answer
from app.services.ai_question_normalizer import normalize_text
from app.services.ai_structured_source_service import (
    shiftplan_coverage_source_cards,
    shiftplan_entry_source_cards,
)
from app.services.visibility_query_service import visible_shiftplans_query

MAX_ITEMS = 30
MAX_ANSWER_ITEMS = 10
SHIFT_ALIASES = {
    "frueh": "Frueh",
    "fruehschicht": "Frueh",
    "spaet": "Spaet",
    "spaetschicht": "Spaet",
    "nacht": "Nacht",
    "nachtschicht": "Nacht",
}


def answer_shiftplan_structured_question(message, user):
    """Return a structured shift-plan answer for supported German questions."""
    text = normalize_text(message)
    if not _is_shiftplan_question(text):
        return None
    if not has_dashboard_permission(user, "shiftplans", "view"):
        return _permission_denied()
    if _is_understaffed_next_week_question(text):
        return _answer_understaffed_next_week(user)
    if _is_tomorrow_planned_question(text):
        return _answer_entries_for_date(user, _tomorrow(), "morgen")
    if _is_shift_count_question(text):
        shift = _requested_shift(text)
        if shift:
            return _answer_shift_count(user, shift)
    if _is_shift_employee_question(text):
        shift = _requested_shift(text)
        if shift:
            return _answer_entries_for_date(user, _tomorrow(), "morgen", shift=shift)
    if _is_tomorrow_shift_question(text):
        return _answer_entries_for_date(user, _tomorrow(), "morgen")
    return None


def _permission_denied():
    """Return a permission-denied shift-plan answer."""
    return {
        "type": "permission_denied",
        "answer": permission_denied_answer("Schichtplanung", "shiftplans"),
        "data": [],
        "sources": [],
        "scope": "shiftplans",
        "structured_context": {"entity_type": "shiftplans"},
    }


def _answer_entries_for_date(user, work_date, label, shift=""):
    """Return visible shift entries for one date and optional shift."""
    entries = _visible_entries(user)
    entries = [entry for entry in entries if entry.work_date == work_date]
    if shift:
        entries = [entry for entry in entries if entry.shift == shift]
    entries = entries[:MAX_ITEMS]
    title = f"Eingeplant {label}" if not shift else f"{shift}schicht {label}"
    return {
        "type": "shiftplan_entries",
        "answer": _format_entry_answer(title, entries, user),
        "data": {
            "entity_type": "shiftplans",
            "query": "entries",
            "date": work_date.isoformat(),
            "shift": shift,
            "count": len(entries),
            "items": [_entry_payload(entry, user) for entry in entries],
        },
        "sources": shiftplan_entry_source_cards(entries, user),
        "scope": "shiftplans",
        "structured_context": {"entity_type": "shiftplans"},
    }


def _answer_shift_count(user, shift):
    """Return the visible employee count for one shift."""
    entries = [entry for entry in _visible_entries(user) if entry.shift == shift][:MAX_ITEMS]
    employee_ids = {entry.employee_id for entry in entries}
    return {
        "type": "shiftplan_shift_count",
        "answer": (
            "## Schichtplanung\n"
            f"- **Schicht:** {shift}\n"
            f"- **Sichtbar eingeplante Mitarbeiter:** {len(employee_ids)}\n"
            "- **Quelle:** Strukturierte Schichtplandaten"
        ),
        "data": {
            "entity_type": "shiftplans",
            "query": "shift_count",
            "shift": shift,
            "count": len(employee_ids),
            "items": [_entry_payload(entry, user) for entry in entries],
        },
        "sources": shiftplan_entry_source_cards(entries, user),
        "scope": "shiftplans",
        "structured_context": {"entity_type": "shiftplans"},
    }


def _answer_understaffed_next_week(user):
    """Return visible undercoverage slots for the next calendar week."""
    start_date = _next_week_start()
    end_date = start_date + timedelta(days=6)
    slots = [
        slot
        for slot in _visible_coverage_slots(user)
        if start_date <= slot.work_date <= end_date and slot.missing > 0
    ][:MAX_ITEMS]
    return {
        "type": "shiftplan_understaffed",
        "answer": _format_coverage_answer("Unterbesetzte Schichten naechste Woche", slots),
        "data": {
            "entity_type": "shiftplans",
            "query": "understaffed",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "count": len(slots),
            "items": [_coverage_payload(slot) for slot in slots],
        },
        "sources": shiftplan_coverage_source_cards(slots),
        "scope": "shiftplans",
        "structured_context": {"entity_type": "shiftplans"},
    }


def _visible_entries(user):
    """Return entries belonging to visible shift plans."""
    plan_ids = _visible_plan_ids(user)
    if not plan_ids:
        return []
    return (
        ShiftPlanEntry.query.filter(ShiftPlanEntry.plan_id.in_(plan_ids))
        .order_by(
            ShiftPlanEntry.work_date.asc(),
            ShiftPlanEntry.shift.asc(),
            ShiftPlanEntry.id.asc(),
        )
        .limit(MAX_ITEMS)
        .all()
    )


def _visible_coverage_slots(user):
    """Return coverage slots belonging to visible shift plans."""
    plan_ids = _visible_plan_ids(user)
    if not plan_ids:
        return []
    return (
        ShiftPlanCoverageSlot.query.filter(ShiftPlanCoverageSlot.plan_id.in_(plan_ids))
        .order_by(
            ShiftPlanCoverageSlot.work_date.asc(),
            ShiftPlanCoverageSlot.shift.asc(),
            ShiftPlanCoverageSlot.id.asc(),
        )
        .limit(MAX_ITEMS)
        .all()
    )


def _visible_plan_ids(user):
    """Return ids of shift plans visible to a user."""
    return [
        plan.id
        for plan in visible_shiftplans_query(user)
        .order_by(ShiftPlan.start_date.desc(), ShiftPlan.id.desc())
        .limit(MAX_ITEMS)
        .all()
    ]


def _entry_payload(entry, user):
    """Return safe shift-plan entry data for structured answers."""
    employee = entry.employee
    machine = entry.machine
    access_level = employee_access_level(user)
    return {
        "id": entry.id,
        "plan_id": entry.plan_id,
        "department": entry.plan.department if entry.plan else "",
        "employee": employee.to_dict("basic") if employee and access_level != "none" else None,
        "employee_access_level": access_level,
        "machine": machine.to_dict() if machine else None,
        "work_date": entry.work_date.isoformat(),
        "shift": entry.shift,
        "start_time": entry.start_time,
        "end_time": entry.end_time,
    }


def _coverage_payload(slot):
    """Return safe undercoverage data for structured answers."""
    machine = slot.machine
    return {
        "id": slot.id,
        "plan_id": slot.plan_id,
        "department": slot.plan.department if slot.plan else "",
        "machine_id": slot.machine_id,
        "machine_name": machine.name if machine else "",
        "work_date": slot.work_date.isoformat(),
        "shift": slot.shift,
        "required": slot.required,
        "assigned": slot.assigned,
        "missing": slot.missing,
    }


def _format_entry_answer(title, entries, user):
    """Return a compact German shift entry answer."""
    access_level = employee_access_level(user)
    lines = [
        f"## {title}",
        f"- **Eintraege:** {len(entries)}",
        "- **Quelle:** Strukturierte Schichtplandaten",
    ]
    if not entries:
        lines.append("")
        lines.append("Keine sichtbaren Schichtplaneintraege fuer diese Anfrage gefunden.")
        return "\n".join(lines)
    lines.append("")
    lines.append("Sichtbare Einplanung:")
    for entry in entries[:MAX_ANSWER_ITEMS]:
        employee_name = _visible_entry_employee_name(entry, access_level)
        lines.append(
            f"- {entry.work_date.isoformat()} {entry.shift}: "
            f"{employee_name} ({entry.start_time}-{entry.end_time})"
        )
    if len(entries) > MAX_ANSWER_ITEMS:
        lines.append(f"- ... {len(entries) - MAX_ANSWER_ITEMS} weitere Eintraege")
    return "\n".join(lines)


def _visible_entry_employee_name(entry, access_level):
    """Return the employee display name allowed for a shift-plan answer."""
    if access_level == "none":
        return "Mitarbeiter nicht sichtbar"
    return entry.employee.name if entry.employee else "Unbekannt"


def _format_coverage_answer(title, slots):
    """Return a compact German undercoverage answer."""
    lines = [
        f"## {title}",
        f"- **Unterbesetzte Slots:** {len(slots)}",
        "- **Quelle:** Strukturierte Schichtplandaten",
    ]
    if not slots:
        lines.append("")
        lines.append("Keine sichtbare Unterbesetzung fuer diesen Zeitraum gefunden.")
        return "\n".join(lines)
    lines.append("")
    lines.append("Sichtbare Unterbesetzung:")
    for slot in slots[:MAX_ANSWER_ITEMS]:
        machine = slot.machine.name if slot.machine else "ohne Maschine"
        lines.append(
            f"- {slot.work_date.isoformat()} {slot.shift}: "
            f"{machine}, fehlen {slot.missing}"
        )
    if len(slots) > MAX_ANSWER_ITEMS:
        lines.append(f"- ... {len(slots) - MAX_ANSWER_ITEMS} weitere Slots")
    return "\n".join(lines)


def _requested_shift(text):
    """Return the requested canonical shift name."""
    for alias, shift in SHIFT_ALIASES.items():
        if alias in text:
            return shift
    return ""


def _tomorrow():
    """Return tomorrow's date."""
    return date.today() + timedelta(days=1)


def _next_week_start():
    """Return the next calendar week's Monday."""
    today = date.today()
    return today + timedelta(days=7 - today.weekday())


def _is_shiftplan_question(text):
    """Return whether the text is a supported shift-plan question."""
    return any(term in text for term in ("schicht", "schichtplan", "eingeplant"))


def _is_tomorrow_shift_question(text):
    """Return whether the text asks which shift is tomorrow."""
    return "morgen" in text and "schicht" in text and "wer" not in text


def _is_shift_employee_question(text):
    """Return whether the text asks who works in a named shift tomorrow."""
    return "wer" in text and "morgen" in text and _requested_shift(text)


def _is_understaffed_next_week_question(text):
    """Return whether the text asks for next week's undercoverage."""
    return "naechste woche" in text and any(
        term in text for term in ("unterbesetzt", "unterdeckung")
    )


def _is_shift_count_question(text):
    """Return whether the text asks for a shift employee count."""
    return any(term in text for term in ("wie viele", "wieviele", "anzahl")) and _requested_shift(
        text
    )


def _is_tomorrow_planned_question(text):
    """Return whether the text asks who is planned tomorrow."""
    return "wer" in text and "morgen" in text and "eingeplant" in text

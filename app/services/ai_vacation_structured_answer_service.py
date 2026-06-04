"""Structured AI answers for vacation and absence questions."""

from __future__ import annotations

from datetime import date, timedelta

from app.models import VacationRequest
from app.services.ai_question_normalizer import detect_department, normalize_text
from app.services.ai_structured_constants import MAX_ANSWER_ITEMS, MAX_LIST_ITEMS
from app.services.ai_structured_context_helpers import (
    build_structured_context,
    inherited_structured_scope,
    is_list_follow_up,
)
from app.services.ai_structured_source_service import vacation_source_cards
from app.vacations.services import visible_vacation_query

STATUS_LABELS = {
    "approved": "genehmigt",
    "cancelled": "storniert",
    "pending": "offen",
    "rejected": "abgelehnt",
}


def answer_vacation_structured_question(message, user, conversation_context=None):
    """Return a structured vacation answer for supported German questions."""
    text = normalize_text(message)
    if not _is_vacation_question(text) and not _is_vacation_follow_up(text, conversation_context):
        return None
    follow_up_result = _answer_vacation_follow_up(message, user, conversation_context)
    if follow_up_result:
        return follow_up_result
    if _is_pending_count_question(text):
        return _answer_pending_count(user)
    if _is_own_latest_status_question(text):
        return _answer_own_latest_status(user)
    if _is_own_pending_question(text):
        return _answer_own_pending(user)
    if _is_tomorrow_absence_question(text):
        return _answer_absences(user, *_tomorrow_bounds(), "morgen")
    if _is_next_week_absence_question(text):
        return _answer_absences(user, *_next_week_bounds(), "naechste Woche")
    return None


def _answer_vacation_follow_up(message, user, conversation_context):
    """Return a structured vacation follow-up answer."""
    text = normalize_text(message)
    if not _is_vacation_follow_up(text, conversation_context):
        return None

    inherited = inherited_structured_scope(conversation_context)
    query = str(inherited.get("query") or "").strip()
    if query == "pending_count":
        return _answer_pending_list(user)
    if query == "approved_absences":
        time_range = str(inherited.get("time_range") or "").strip()
        if time_range == "tomorrow":
            return _answer_absences(
                user,
                *_tomorrow_bounds(),
                "morgen",
                department=detect_department(message),
            )
        if time_range == "next_week":
            return _answer_absences(
                user,
                *_next_week_bounds(),
                "naechste Woche",
                department=detect_department(message),
            )
    return None


def _answer_pending_list(user):
    """Return visible pending vacation requests after a pending-count follow-up."""
    vacations = (
        visible_vacation_query(user)
        .filter(VacationRequest.status == "pending")
        .order_by(VacationRequest.created_at.desc(), VacationRequest.start_date.desc())
        .limit(MAX_LIST_ITEMS)
        .all()
    )
    return {
        "type": "vacation_pending_list",
        "answer": _format_pending_count_answer(len(vacations), vacations),
        "data": {
            "entity_type": "vacations",
            "query": "pending_count",
            "count": len(vacations),
            "items": [_vacation_payload(vacation) for vacation in vacations],
        },
        "sources": vacation_source_cards(vacations),
        "scope": "employees",
        "structured_context": build_structured_context(
            "vacations",
            query="pending_count",
            status="pending",
        ),
    }


def _answer_own_pending(user):
    """Return the current user's own pending vacation requests."""
    if not getattr(user, "employee_id", None):
        return _no_result("vacation_own_pending", "Keine eigene Mitarbeiterzuordnung gefunden.")

    vacations = (
        visible_vacation_query(user)
        .filter(
            VacationRequest.employee_id == user.employee_id,
            VacationRequest.status == "pending",
        )
        .order_by(VacationRequest.created_at.desc(), VacationRequest.start_date.desc())
        .limit(MAX_LIST_ITEMS)
        .all()
    )
    return {
        "type": "vacation_own_pending",
        "answer": _format_own_pending_answer(vacations),
        "data": {
            "entity_type": "vacations",
            "query": "own_pending",
            "count": len(vacations),
            "items": [_vacation_payload(vacation) for vacation in vacations],
        },
        "sources": vacation_source_cards(
            vacations,
            role_visibility=f"employee:{user.employee_id}",
        ),
        "scope": "employees",
        "structured_context": build_structured_context("vacations", query="own_pending"),
    }


def _answer_own_latest_status(user):
    """Return the latest visible vacation request status for the current user."""
    if not getattr(user, "employee_id", None):
        return _no_result("vacation_own_status", "Keine eigene Mitarbeiterzuordnung gefunden.")

    vacation = (
        visible_vacation_query(user)
        .filter(VacationRequest.employee_id == user.employee_id)
        .order_by(VacationRequest.created_at.desc(), VacationRequest.start_date.desc())
        .first()
    )
    vacations = [vacation] if vacation else []
    return {
        "type": "vacation_own_status",
        "answer": _format_own_status_answer(vacation),
        "data": {
            "entity_type": "vacations",
            "query": "own_latest_status",
            "count": len(vacations),
            "items": [_vacation_payload(item) for item in vacations],
        },
        "sources": vacation_source_cards(
            vacations,
            role_visibility=f"employee:{user.employee_id}",
        ),
        "scope": "employees",
        "structured_context": build_structured_context("vacations", query="own_latest_status"),
    }


def _answer_absences(user, start_date, end_date, label, department=""):
    """Return approved visible vacation absences overlapping the given period."""
    vacations = (
        _overlapping_vacation_query(user, start_date, end_date)
        .order_by(VacationRequest.start_date.asc(), VacationRequest.id.asc())
        .limit(MAX_LIST_ITEMS)
        .all()
    )
    if department:
        vacations = [
            vacation
            for vacation in vacations
            if vacation.employee
            and normalize_text(vacation.employee.department) == normalize_text(department)
        ]
    time_range = "tomorrow" if label == "morgen" else "next_week" if "woche" in label else ""
    return {
        "type": "vacation_absences",
        "answer": _format_absence_answer(vacations, label),
        "data": {
            "entity_type": "vacations",
            "query": "approved_absences",
            "period": {
                "label": label,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "count": len(vacations),
            "items": [_vacation_payload(vacation) for vacation in vacations],
        },
        "sources": vacation_source_cards(vacations),
        "scope": "employees",
        "structured_context": build_structured_context(
            "vacations",
            query="approved_absences",
            time_range=time_range,
            department=department,
            status="approved",
        ),
    }


def _answer_pending_count(user):
    """Return a count of visible pending vacation requests."""
    query = visible_vacation_query(user).filter(VacationRequest.status == "pending")
    count = query.count()
    examples = (
        query.order_by(VacationRequest.created_at.desc(), VacationRequest.start_date.desc())
        .limit(MAX_ANSWER_ITEMS)
        .all()
    )
    return {
        "type": "vacation_pending_count",
        "answer": _format_pending_count_answer(count, examples),
        "data": {
            "entity_type": "vacations",
            "query": "pending_count",
            "count": count,
            "items": [_vacation_payload(vacation) for vacation in examples],
        },
        "sources": vacation_source_cards(examples),
        "scope": "employees",
        "structured_context": build_structured_context(
            "vacations",
            query="pending_count",
            status="pending",
        ),
    }


def _overlapping_vacation_query(user, start_date, end_date):
    """Return visible approved vacations overlapping the inclusive date range."""
    return visible_vacation_query(user).filter(
        VacationRequest.status == "approved",
        VacationRequest.start_date <= end_date,
        VacationRequest.end_date >= start_date,
    )


def _vacation_payload(vacation):
    """Return compact prompt-safe vacation data for AI responses."""
    employee = vacation.employee
    return {
        "id": vacation.id,
        "employee_id": vacation.employee_id,
        "employee_name": employee.name if employee else "",
        "department": employee.department if employee else "",
        "start_date": vacation.start_date.isoformat(),
        "end_date": vacation.end_date.isoformat(),
        "days_used": vacation.days_used,
        "status": vacation.status,
        "status_label": STATUS_LABELS.get(vacation.status, vacation.status),
        "shift_type": vacation.shift_type,
        "created_at": vacation.created_at.isoformat() if vacation.created_at else "",
    }


def _format_own_pending_answer(vacations):
    """Return a compact German answer for own pending vacation requests."""
    lines = [
        "## Urlaub",
        f"- **Offene Antraege:** {len(vacations)}",
        "- **Quelle:** Strukturierte Urlaubsdaten",
    ]
    if not vacations:
        lines.append("")
        lines.append("Du hast keinen sichtbaren offenen Urlaubsantrag.")
        return "\n".join(lines)
    lines.append("")
    lines.append("Offene Antraege:")
    for vacation in vacations[:MAX_ANSWER_ITEMS]:
        lines.append(_vacation_line(vacation))
    return "\n".join(lines)


def _format_own_status_answer(vacation):
    """Return a compact German answer for the latest own vacation status."""
    lines = ["## Urlaubsantrag", "- **Quelle:** Strukturierte Urlaubsdaten"]
    if not vacation:
        lines.append("- **Status:** Kein sichtbarer Urlaubsantrag gefunden.")
        return "\n".join(lines)
    lines.extend(
        [
            f"- **Status:** {STATUS_LABELS.get(vacation.status, vacation.status)}",
            (
                f"- **Zeitraum:** {vacation.start_date.isoformat()} "
                f"bis {vacation.end_date.isoformat()}"
            ),
            f"- **Arbeitstage:** {vacation.days_used}",
        ]
    )
    return "\n".join(lines)


def _format_absence_answer(vacations, label):
    """Return a compact German answer for visible approved absences."""
    lines = [
        "## Abwesenheiten",
        f"- **Zeitraum:** {label}",
        f"- **Genehmigte Urlaube:** {len(vacations)}",
        "- **Quelle:** Strukturierte Urlaubsdaten",
    ]
    if not vacations:
        lines.append("")
        lines.append("Keine sichtbaren genehmigten Urlaube fuer diesen Zeitraum gefunden.")
        return "\n".join(lines)
    lines.append("")
    lines.append("Sichtbare Abwesenheiten:")
    for vacation in vacations[:MAX_ANSWER_ITEMS]:
        lines.append(_vacation_line(vacation))
    if len(vacations) > MAX_ANSWER_ITEMS:
        lines.append(f"- ... {len(vacations) - MAX_ANSWER_ITEMS} weitere sichtbare Urlaube")
    return "\n".join(lines)


def _format_pending_count_answer(count, examples):
    """Return a compact German answer for visible pending vacation count."""
    lines = [
        "## Offene Urlaubsantraege",
        f"- **Anzahl:** {count}",
        "- **Quelle:** Strukturierte Urlaubsdaten",
    ]
    if examples:
        lines.append("")
        lines.append("Sichtbare Beispiele:")
        for vacation in examples[:MAX_ANSWER_ITEMS]:
            lines.append(_vacation_line(vacation))
    return "\n".join(lines)


def _vacation_line(vacation):
    """Return one compact safe vacation answer line."""
    employee = vacation.employee
    name = employee.name if employee else "Unbekannt"
    department = employee.department if employee else "ohne Bereich"
    return (
        f"- #{vacation.id} {name} ({department}): "
        f"{vacation.start_date.isoformat()} bis {vacation.end_date.isoformat()}, "
        f"{STATUS_LABELS.get(vacation.status, vacation.status)}"
    )


def _no_result(response_type, message):
    """Return a safe no-result vacation response."""
    return {
        "type": response_type,
        "answer": "## Urlaub\n- **Quelle:** Strukturierte Urlaubsdaten\n\n" + message,
        "data": {
            "entity_type": "vacations",
            "count": 0,
            "items": [],
        },
        "sources": [],
        "scope": "employees",
        "structured_context": build_structured_context("vacations"),
    }


def _tomorrow_bounds():
    """Return tomorrow as an inclusive date range."""
    tomorrow = date.today() + timedelta(days=1)
    return tomorrow, tomorrow


def _next_week_bounds():
    """Return the next calendar week as an inclusive date range."""
    today = date.today()
    next_monday = today + timedelta(days=7 - today.weekday())
    return next_monday, next_monday + timedelta(days=6)


def _is_vacation_question(text):
    """Return whether the message uses clear German vacation wording."""
    return (
        "urlaub" in text
        or "urlaubsantrag" in text
        or "urlaubsantraeg" in text
        or "abwesenheit" in text
        or "abwesend" in text
        or _is_tomorrow_missing_question(text)
    )


def _is_own_pending_question(text):
    """Return whether the user asks for their own pending vacation."""
    return _mentions_self(text) and "urlaub" in text and _mentions_pending(text)


def _is_own_latest_status_question(text):
    """Return whether the user asks for the latest own vacation request status."""
    return _mentions_self(text) and "status" in text and "urlaubsantrag" in text


def _is_tomorrow_absence_question(text):
    """Return whether the user asks who is on vacation or absent tomorrow."""
    return "morgen" in text and (
        "wer hat" in text and "urlaub" in text or _is_tomorrow_missing_question(text)
    )


def _is_next_week_absence_question(text):
    """Return whether the user asks who is on vacation next week."""
    return "naechste woche" in text and "wer hat" in text and "urlaub" in text


def _is_pending_count_question(text):
    """Return whether the user asks for a visible pending vacation request count."""
    has_count = any(term in text for term in ("wie viele", "wieviele", "anzahl", "count"))
    has_request = "urlaubsantrag" in text or "urlaubsantraeg" in text
    return has_count and has_request and _mentions_pending(text)


def _is_tomorrow_missing_question(text):
    """Return whether the user asks who is missing tomorrow."""
    return text.startswith("wer fehlt morgen") or text.startswith("wer ist morgen abwesend")


def _mentions_self(text):
    """Return whether the message is explicitly about the current user."""
    return any(term in text for term in ("ich", "mein", "meinen", "meine"))


def _mentions_pending(text):
    """Return whether the message asks for pending or open requests."""
    return any(term in text for term in ("offen", "offene", "ausstehend", "pending"))


def _is_vacation_follow_up(text, conversation_context):
    """Return whether a follow-up should stay on structured vacation data."""
    if not is_list_follow_up(text, conversation_context):
        return False
    inherited = inherited_structured_scope(conversation_context)
    return inherited.get("entity_type") == "vacations"

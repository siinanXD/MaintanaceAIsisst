"""Core structured AI answers for employee visibility and availability."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.models import Employee, VacationRequest
from app.permissions import can_read_employee_context
from app.security import employee_access_level
from app.services.ai_question_normalizer import (
    detect_department,
    is_structured_follow_up,
    normalize_text,
)
from app.services.ai_structured_constants import MAX_ANSWER_ITEMS, MAX_LIST_ITEMS
from app.services.ai_structured_context_helpers import (
    build_structured_context,
    mentions_employee_documents,
    structured_permission_denied,
)
from app.services.ai_structured_source_service import (
    employee_count_source_card,
    employee_source_cards,
)
from app.services.visibility_query_service import visible_employees_query
from app.vacations.services import visible_vacation_query

LIST_TERMS = ("welche", "zeige", "zeig", "liste", "auflisten", "anzeigen")
KNOWN_DEPARTMENTS = {
    "instandhaltung": "Instandhaltung",
    "verwaltung": "Verwaltung",
    "produktion": "Produktion",
    "it": "IT",
    "personalabteilung": "Personalabteilung",
}


def try_employee_core_structured_answer(
    message: str,
    user: Any,
    conversation_context: Any | None = None,
) -> dict[str, Any] | None:
    """Return a structured core employee answer when the question matches."""
    text = normalize_text(message)
    if _is_employee_total_follow_up_list(text, conversation_context):
        if not can_read_employee_context(user):
            return _permission_denied()
        return _answer_employee_total_list(user)
    if _is_employee_department_follow_up_list(text, conversation_context):
        if not can_read_employee_context(user):
            return _permission_denied()
        department = _inherited_employee_department(conversation_context)
        if department:
            return _answer_department_list(user, department)
    if not _is_employee_question(text):
        return None
    if not _is_supported_employee_question(text):
        return None
    if not can_read_employee_context(user):
        return _permission_denied()
    if _is_team_lead_question(text):
        return _answer_team_lead_unavailable(message, user)
    if _is_available_today_question(text):
        return _answer_available_on(user, date.today(), "heute")
    if _is_missing_tomorrow_question(text):
        tomorrow = date.today() + timedelta(days=1)
        return _answer_absent_on(user, tomorrow, "morgen")
    if _is_department_count_question(text):
        department = _requested_department(message, user)
        if department:
            return _answer_department_count(user, department)
    if _is_department_list_question(text):
        department = _requested_department(message, user)
        if department:
            return _answer_department_list(user, department)
    return None


def _permission_denied() -> dict[str, Any]:
    """Return a permission-denied employee answer."""
    return structured_permission_denied(
        dashboard_label="Mitarbeiter",
        scope="employees",
        entity_type="employees",
    )


def _answer_department_count(user, department):
    """Return the visible employee count for one department."""
    count = _employees_in_department(user, department).count()
    answer = (
        "## Mitarbeiter\n"
        f"- **Bereich:** {department}\n"
        f"- **Sichtbare Mitarbeiter:** {count}\n"
        "- **Quelle:** Strukturierte Mitarbeiterdaten"
    )
    source = employee_count_source_card(count, user, department=department)
    return {
        "type": "employee_department_count",
        "answer": answer,
        "data": {
            "entity_type": "employees",
            "query": "department_count",
            "department": department,
            "count": count,
        },
        "sources": [source] if source else [],
        "scope": "employees",
        "structured_context": build_structured_context(
            "employees",
            department=department,
            query="department_count",
        ),
    }


def _answer_employee_total_list(user):
    """Return all visible employees for a generic count follow-up."""
    employees = (
        visible_employees_query(user)
        .order_by(Employee.name.asc(), Employee.id.asc())
        .limit(MAX_LIST_ITEMS)
        .all()
    )
    answer = _format_employee_list_answer(
        "Mitarbeiter",
        "alle sichtbaren Mitarbeiter",
        employees,
        "Sichtbare Mitarbeiter",
    )
    return {
        "type": "employee_list",
        "answer": answer,
        "data": {
            "entity_type": "employees",
            "query": "total_list",
            "count": len(employees),
            "items": [_employee_payload(employee, user) for employee in employees],
        },
        "sources": employee_source_cards(employees, user),
        "scope": "employees",
        "structured_context": build_structured_context("employees", query="total_list"),
    }


def _answer_department_list(user, department):
    """Return visible employees for one department."""
    employees = (
        _employees_in_department(user, department)
        .order_by(Employee.name.asc(), Employee.id.asc())
        .limit(MAX_LIST_ITEMS)
        .all()
    )
    answer = _format_employee_list_answer(
        "Mitarbeiter",
        department,
        employees,
        "Sichtbare Mitarbeiter",
    )
    return {
        "type": "employee_department_list",
        "answer": answer,
        "data": {
            "entity_type": "employees",
            "query": "department_list",
            "department": department,
            "count": len(employees),
            "items": [_employee_payload(employee, user) for employee in employees],
        },
        "sources": employee_source_cards(employees, user),
        "scope": "employees",
        "structured_context": _employee_department_structured_context(department),
    }


def _answer_available_on(user, target_date, label):
    """Return visible employees without visible approved vacation on one date."""
    employees = (
        visible_employees_query(user)
        .order_by(Employee.name.asc(), Employee.id.asc())
        .limit(MAX_LIST_ITEMS)
        .all()
    )
    absent_ids = _approved_absent_employee_ids(user, target_date)
    available = [employee for employee in employees if employee.id not in absent_ids]
    answer = _format_employee_list_answer(
        "Verfuegbare Mitarbeiter",
        label,
        available,
        "Sichtbar verfuegbar",
        source="Strukturierte Mitarbeiterdaten und sichtbare genehmigte Urlaube",
    )
    return {
        "type": "employee_available",
        "answer": answer,
        "data": {
            "entity_type": "employees",
            "query": "available",
            "date": target_date.isoformat(),
            "count": len(available),
            "items": [
                {**_employee_payload(employee, user), "availability_status": "available"}
                for employee in available
            ],
        },
        "sources": employee_source_cards(available, user),
        "scope": "employees",
        "structured_context": {"entity_type": "employees"},
    }


def _answer_absent_on(user, target_date, label):
    """Return visible employees with approved vacation on one date."""
    vacations = (
        visible_vacation_query(user)
        .filter(
            VacationRequest.status == "approved",
            VacationRequest.start_date <= target_date,
            VacationRequest.end_date >= target_date,
        )
        .order_by(VacationRequest.start_date.asc(), VacationRequest.id.asc())
        .limit(MAX_LIST_ITEMS)
        .all()
    )
    visible_employee_ids = _visible_employee_ids(user)
    employees = [
        vacation.employee
        for vacation in vacations
        if vacation.employee and vacation.employee_id in visible_employee_ids
    ]
    answer = _format_employee_list_answer(
        "Abwesende Mitarbeiter",
        label,
        employees,
        "Genehmigt abwesend",
        source="Sichtbare genehmigte Urlaube",
    )
    return {
        "type": "employee_absences",
        "answer": answer,
        "data": {
            "entity_type": "employees",
            "query": "approved_absences",
            "date": target_date.isoformat(),
            "count": len(employees),
            "items": [
                {
                    **_employee_payload(employee, user),
                    "availability_status": "absent",
                    "absence_source": "approved_vacation",
                }
                for employee in employees
            ],
        },
        "sources": employee_source_cards(employees, user),
        "scope": "employees",
        "structured_context": {"entity_type": "employees"},
    }


def _answer_team_lead_unavailable(message, user):
    """Return a grounded no-data answer for unsupported team lead questions."""
    department = _requested_department(message, user)
    department_line = f"- **Bereich:** {department}\n" if department else ""
    answer = (
        "## Teamleiter\n"
        f"{department_line}"
        "- **Status:** Kein strukturiertes Teamleiter-Feld vorhanden\n"
        "- **Quelle:** Strukturierte Mitarbeiterdaten"
    )
    return {
        "type": "employee_team_lead_unavailable",
        "answer": answer,
        "data": {
            "entity_type": "employees",
            "query": "team_lead",
            "department": department,
            "count": 0,
            "items": [],
            "reason": "team_lead_field_missing",
        },
        "sources": [],
        "scope": "employees",
        "structured_context": {"entity_type": "employees"},
    }


def _employees_in_department(user, department):
    """Return visible employees filtered to one department."""
    return visible_employees_query(user).filter(Employee.department.ilike(department))


def _approved_absent_employee_ids(user, target_date):
    """Return employee ids with visible approved vacation on a date."""
    vacations = visible_vacation_query(user).filter(
        VacationRequest.status == "approved",
        VacationRequest.start_date <= target_date,
        VacationRequest.end_date >= target_date,
    )
    return {vacation.employee_id for vacation in vacations.all()}


def _visible_employee_ids(user):
    """Return ids of employees visible to the current user."""
    rows = visible_employees_query(user).with_entities(Employee.id)
    return {employee_id for (employee_id,) in rows}


def _employee_payload(employee, user):
    """Return compact safe employee data for structured answers."""
    return _employee_payload_for_access_level(employee, employee_access_level(user))


def _employee_payload_for_access_level(employee, access_level):
    """Return compact employee data allowed by the user's employee access level."""
    payload = {
        "id": employee.id,
        "personnel_number": employee.personnel_number,
        "name": employee.name,
        "department": employee.department,
        "team": employee.team,
    }
    if access_level != "shift":
        return payload
    payload.update(
        {
            "shift_model": employee.shift_model,
            "last_shift": employee.last_shift,
            "current_shift": employee.current_shift,
            "next_shift": employee.next_shift,
            "qualifications": employee.qualifications,
            "favorite_machine": employee.favorite_machine,
            "machine_qualifications": [
                _machine_qualification_payload(qualification)
                for qualification in employee.machine_qualifications
            ],
        }
    )
    return payload


def _machine_qualification_payload(qualification):
    """Return safe machine qualification data for shift-level employee answers."""
    machine = qualification.machine
    return {
        "id": qualification.id,
        "machine_id": qualification.machine_id,
        "machine": machine.to_dict() if machine else None,
        "level": qualification.level,
        "valid_until": (
            qualification.valid_until.isoformat() if qualification.valid_until else None
        ),
    }


def _format_employee_list_answer(
    title,
    label,
    employees,
    count_label,
    source=None,
    total_count=None,
):
    """Return a compact German employee list answer."""
    visible_total = total_count if total_count is not None else len(employees)
    lines = [
        f"## {title}",
        f"- **Filter:** {label}",
        f"- **{count_label}:** {visible_total}",
        f"- **Quelle:** {source or 'Strukturierte Mitarbeiterdaten'}",
    ]
    if total_count is not None and total_count > len(employees):
        lines.append(
            f"- **Hinweis:** {len(employees)} von {total_count} sichtbaren Mitarbeitern angezeigt"
        )
    if not employees:
        lines.append("")
        lines.append("Keine sichtbaren Mitarbeiter fuer diese Anfrage gefunden.")
        return "\n".join(lines)
    lines.append("")
    lines.append("Sichtbare Mitarbeiter:")
    for employee in employees[:MAX_ANSWER_ITEMS]:
        team = f", Team {employee.team}" if employee.team is not None else ""
        lines.append(f"- {employee.name} ({employee.department}{team})")
    if len(employees) > MAX_ANSWER_ITEMS:
        lines.append(f"- ... {len(employees) - MAX_ANSWER_ITEMS} weitere sichtbare Mitarbeiter")
    return "\n".join(lines)


def _requested_department(message, user):
    """Return the department requested by a question."""
    detected = detect_department(message)
    if detected:
        return detected
    text = normalize_text(message)
    for normalized_name, label in KNOWN_DEPARTMENTS.items():
        if normalized_name in text:
            return label
    for department in _visible_department_names(user):
        if normalize_text(department) in text:
            return department
    return ""


def _visible_department_names(user):
    """Return distinct department names from visible employee rows."""
    rows = (
        visible_employees_query(user)
        .with_entities(Employee.department)
        .distinct()
        .order_by(Employee.department.asc())
        .all()
    )
    return [department for (department,) in rows if department]


def _is_employee_question(text):
    """Return whether the text is a supported employee structured question."""
    return any(term in text for term in ("mitarbeiter", "personal", "teamleiter", "wer arbeitet"))


def _is_supported_employee_question(text):
    """Return whether the employee service supports the specific question."""
    return any(
        (
            _is_team_lead_question(text),
            _is_available_today_question(text),
            _is_missing_tomorrow_question(text),
            _is_department_count_question(text),
            _is_department_list_question(text),
        )
    )


def _is_department_count_question(text):
    """Return whether the text asks for employee count in a department."""
    if "schicht" in text:
        return False
    return any(term in text for term in ("wie viele", "wieviele", "anzahl")) and any(
        term in text for term in ("hat die", "hat der", "in der", "im bereich")
    )


def _is_department_list_question(text):
    """Return whether the text asks who works in a department."""
    return any(term in text for term in ("wer arbeitet", "welche mitarbeiter")) and any(
        term in text for term in ("in der", "im bereich", "bei der")
    )


def _is_team_lead_question(text):
    """Return whether the text asks for a team lead."""
    return "teamleiter" in text or "teamleiterin" in text


def _is_available_today_question(text):
    """Return whether the text asks for employees available today."""
    return "heute" in text and any(term in text for term in ("verfuegbar", "verfuegbaren"))


def _is_missing_tomorrow_question(text):
    """Return whether the text asks for employees absent tomorrow."""
    return "morgen" in text and any(term in text for term in ("fehlen", "fehlt", "abwesend"))


def _employee_department_structured_context(department):
    """Return structured memory for employee department answers."""
    return build_structured_context("employees", department=department)


def _inherited_employee_scope(conversation_context):
    """Return inherited employee structured scope payload."""
    if not conversation_context:
        return {}
    structured_scope = dict(getattr(conversation_context, "structured_scope", {}) or {})
    if structured_scope.get("entity_type") != "employees":
        return {}
    return structured_scope


def _inherited_employee_department(conversation_context):
    """Return the department filter from recent employee structured context."""
    return str(_inherited_employee_scope(conversation_context).get("department") or "").strip()


def _is_employee_total_follow_up_list(text, conversation_context):
    """Return whether a follow-up should list all visible employees."""
    if _is_employee_document_follow_up(text, conversation_context):
        return False
    if not is_structured_follow_up(text):
        return False
    if not any(term in text for term in LIST_TERMS):
        return False
    inherited = _inherited_employee_scope(conversation_context)
    if not inherited:
        return False
    if inherited.get("department"):
        return False
    query = str(inherited.get("query") or "").strip()
    return not query


def _is_employee_department_follow_up_list(text, conversation_context):
    """Return whether a follow-up should list employees for one department."""
    if _is_employee_document_follow_up(text, conversation_context):
        return False
    if not is_structured_follow_up(text):
        return False
    if not any(term in text for term in LIST_TERMS):
        return False
    return bool(_inherited_employee_department(conversation_context))


def _is_employee_document_follow_up(text, conversation_context):
    """Return whether a follow-up should stay on employees-with-documents."""
    if not is_structured_follow_up(text):
        return False
    if not mentions_employee_documents(text):
        return False
    return _has_employee_document_context(conversation_context)


def _has_employee_document_context(conversation_context):
    """Return whether recent chat context points to employee document questions."""
    if not conversation_context:
        return False
    structured_scope = dict(getattr(conversation_context, "structured_scope", {}) or {})
    if structured_scope.get("entity_type") == "employees":
        return True
    recent_scopes = set(getattr(conversation_context, "recent_scopes", ()) or ())
    return "employees" in recent_scopes

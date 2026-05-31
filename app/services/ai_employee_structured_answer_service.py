"""Structured AI answers for employee visibility and availability questions."""

from __future__ import annotations

from datetime import date, timedelta

from app.ai.intent import can_read_employee_context
from app.models import Employee, VacationRequest
from app.services.ai_prompting import permission_denied_answer
from app.services.ai_question_normalizer import detect_department, normalize_text
from app.services.ai_structured_source_service import (
    employee_count_source_card,
    employee_source_cards,
)
from app.services.visibility_query_service import visible_employees_query
from app.vacations.services import visible_vacation_query

MAX_ITEMS = 20
MAX_ANSWER_ITEMS = 10
KNOWN_DEPARTMENTS = {
    "instandhaltung": "Instandhaltung",
    "verwaltung": "Verwaltung",
    "produktion": "Produktion",
    "it": "IT",
    "personalabteilung": "Personalabteilung",
}


def answer_employee_structured_question(message, user):
    """Return a structured employee answer for supported German questions."""
    text = normalize_text(message)
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


def _permission_denied():
    """Return a permission-denied employee answer."""
    return {
        "type": "permission_denied",
        "answer": permission_denied_answer("Mitarbeiter", "employees"),
        "data": [],
        "sources": [],
        "scope": "employees",
        "structured_context": {"entity_type": "employees"},
    }


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
        "structured_context": {"entity_type": "employees"},
    }


def _answer_department_list(user, department):
    """Return visible employees for one department."""
    employees = (
        _employees_in_department(user, department)
        .order_by(Employee.name.asc(), Employee.id.asc())
        .limit(MAX_ITEMS)
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
            "items": [_employee_payload(employee) for employee in employees],
        },
        "sources": employee_source_cards(employees, user),
        "scope": "employees",
        "structured_context": {"entity_type": "employees"},
    }


def _answer_available_on(user, target_date, label):
    """Return visible employees without visible approved vacation on one date."""
    employees = (
        visible_employees_query(user)
        .order_by(Employee.name.asc(), Employee.id.asc())
        .limit(MAX_ITEMS)
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
                {**_employee_payload(employee), "availability_status": "available"}
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
        .limit(MAX_ITEMS)
        .all()
    )
    employees = [vacation.employee for vacation in vacations if vacation.employee]
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
                    **_employee_payload(employee),
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


def _employee_payload(employee):
    """Return compact safe employee data for structured answers."""
    return {
        "id": employee.id,
        "personnel_number": employee.personnel_number,
        "name": employee.name,
        "department": employee.department,
        "team": employee.team,
    }


def _format_employee_list_answer(title, label, employees, count_label, source=None):
    """Return a compact German employee list answer."""
    lines = [
        f"## {title}",
        f"- **Filter:** {label}",
        f"- **{count_label}:** {len(employees)}",
        f"- **Quelle:** {source or 'Strukturierte Mitarbeiterdaten'}",
    ]
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
    return any(
        term in text
        for term in ("mitarbeiter", "personal", "teamleiter", "wer arbeitet")
    )


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

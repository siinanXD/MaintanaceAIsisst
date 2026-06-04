"""Structured AI answers for employee document metadata questions."""

from __future__ import annotations

from typing import Any

from app.models import Employee, EmployeeDocument
from app.permissions import can_read_employee_context
from app.services.ai_employee_core_service import (
    _employee_payload,
    _format_employee_list_answer,
    _inherited_employee_scope,
    _permission_denied,
)
from app.services.ai_question_normalizer import (
    detect_department,
    is_structured_follow_up,
    normalize_text,
)
from app.services.ai_structured_constants import MAX_ANSWER_ITEMS, MAX_LIST_ITEMS
from app.services.ai_structured_context_helpers import (
    build_structured_context,
    is_bare_list_refinement,
)
from app.services.ai_structured_source_service import (
    SOURCE_CARD_LIMIT,
    employee_count_source_card,
    employee_document_source_cards,
    employee_source_cards,
)
from app.services.visibility_query_service import visible_employees_query

COUNT_TERMS = ("wie viele", "wieviele", "anzahl", "count")
LIST_TERMS = ("welche", "zeige", "zeig", "liste", "auflisten", "anzeigen")
DOCUMENT_TERMS = ("dokument", "dokumente", "unterlage", "unterlagen", "datei", "dateien")


def try_employee_document_structured_answer(
    message: str,
    user: Any,
    conversation_context: Any | None = None,
) -> dict[str, Any] | None:
    """Return a structured employee-document answer when the question matches."""
    text = normalize_text(message)
    scoped_employee = _document_scope_employee(conversation_context, message, user)
    if _is_employee_name_document_refinement(text, conversation_context, message, user):
        if not can_read_employee_context(user):
            return _permission_denied()
        return _answer_employee_stored_document_list(
            user,
            department=_document_scope_department(conversation_context, message),
            employee=scoped_employee or _requested_employee(message, user),
        )
    if _is_employee_stored_documents_follow_up_list(text, conversation_context):
        if not can_read_employee_context(user):
            return _permission_denied()
        return _answer_employee_stored_document_list(
            user,
            department=_document_scope_department(conversation_context, message),
            employee=scoped_employee,
        )
    if _is_employee_document_question(text, conversation_context, message=message, user=user):
        if not can_read_employee_context(user):
            return _permission_denied()
        department = _document_scope_department(conversation_context, message)
        if _is_employee_stored_document_count_question(text, conversation_context):
            return _answer_employee_stored_document_count(
                user,
                department=department,
                employee=scoped_employee,
            )
        if _asks_which_stored_documents_for_employees(text) or scoped_employee:
            return _answer_employee_stored_document_list(
                user,
                department=department,
                employee=scoped_employee,
            )
        if _is_employee_document_count_question(text, conversation_context):
            return _answer_employee_document_count(user, department=department)
        if _is_employee_document_list_question(
            text, conversation_context
        ) or _is_employee_with_documents_follow_up_list(text, conversation_context):
            return _answer_employee_document_list(user, department=department)
        return _answer_employee_document_list(user, department=department)
    if _is_employee_with_documents_follow_up_list(text, conversation_context):
        if not can_read_employee_context(user):
            return _permission_denied()
        return _answer_employee_document_list(
            user,
            department=_document_scope_department(conversation_context, message),
        )
    return None


def visible_employees_with_documents_query(user):
    """Return visible employees that have at least one employee document row."""
    return (
        visible_employees_query(user)
        .join(EmployeeDocument, EmployeeDocument.employee_id == Employee.id)
        .distinct()
    )


def _answer_employee_document_count(user, department=None):
    """Return the count of visible employees with at least one stored document."""
    count = _employees_with_documents_query(user, department).count()
    label = (
        f"Mitarbeiter mit Dokumenten in {department}"
        if department
        else "Mitarbeiter mit Dokumenten"
    )
    answer = (
        f"## {label}\n"
        f"- **Anzahl:** {count}\n"
        "- **Filter:** mindestens ein hinterlegtes Mitarbeiterdokument\n"
        "- **Quelle:** Strukturierte Mitarbeiterdaten"
    )
    source = employee_count_source_card(count, user, department=department or None)
    structured_context = build_structured_context(
        "employees",
        query="with_documents",
        department=department,
    )
    return {
        "type": "employee_document_count",
        "answer": answer,
        "data": {
            "entity_type": "employees",
            "query": "document_count",
            "department": department or None,
            "count": count,
        },
        "sources": [source] if source else [],
        "scope": "employees",
        "structured_context": structured_context,
    }


def _answer_employee_stored_document_count(user, department=None, employee=None):
    """Return the count of visible stored employee document files."""
    count = _visible_employee_documents_query(user, department, employee=employee).count()
    if employee:
        label = f"hinterlegte Dokumente fuer {employee.name}"
    elif department:
        label = f"hinterlegte Mitarbeiterdokumente in {department}"
    else:
        label = "hinterlegte Mitarbeiterdokumente"
    answer = (
        f"## {label}\n"
        f"- **Anzahl:** {count}\n"
        "- **Filter:** sichtbare Mitarbeiterdokument-Dateien\n"
        "- **Quelle:** Strukturierte Mitarbeiterdaten"
    )
    structured_context = _employee_document_structured_context(
        query="stored_document_count",
        department=department,
        employee=employee,
    )
    sources = (
        employee_document_source_cards(
            _visible_employee_documents_query(user, department, employee=employee)
            .order_by(EmployeeDocument.uploaded_at.desc())
            .limit(SOURCE_CARD_LIMIT)
            .all()
        )
        if count
        else []
    )
    return {
        "type": "employee_stored_document_count",
        "answer": answer,
        "data": {
            "entity_type": "employees",
            "query": "stored_document_count",
            "department": department or None,
            "employee_id": employee.id if employee else None,
            "employee_name": employee.name if employee else None,
            "count": count,
        },
        "sources": sources,
        "scope": "employees",
        "structured_context": structured_context,
    }


def _answer_employee_stored_document_list(user, department=None, employee=None):
    """Return visible employee document files with employee metadata."""
    query = _visible_employee_documents_query(user, department, employee=employee).order_by(
        Employee.name.asc(),
        EmployeeDocument.uploaded_at.desc(),
    )
    total_count, documents, truncated = _paginated_rows(query)
    if employee:
        label = f"hinterlegte Dokumente fuer {employee.name}"
    elif department:
        label = f"hinterlegte Mitarbeiterdokumente in {department}"
    else:
        label = "hinterlegte Mitarbeiterdokumente"
    answer = _format_employee_stored_document_answer(label, documents, total_count=total_count)
    structured_context = _employee_document_structured_context(
        query="stored_document_list",
        department=department,
        employee=employee,
    )
    return {
        "type": "employee_stored_document_list",
        "answer": answer,
        "data": {
            "entity_type": "employees",
            "query": "stored_document_list",
            "department": department or None,
            "employee_id": employee.id if employee else None,
            "employee_name": employee.name if employee else None,
            "count": total_count,
            "returned_count": len(documents),
            "truncated": truncated,
            "items": [_employee_document_payload(document, user) for document in documents],
        },
        "sources": employee_document_source_cards(documents),
        "scope": "employees",
        "structured_context": structured_context,
    }


def _answer_employee_document_list(user, department=None):
    """Return visible employees that have at least one stored document."""
    query = _employees_with_documents_query(user, department).order_by(
        Employee.name.asc(),
        Employee.id.asc(),
    )
    total_count, employees, truncated = _paginated_rows(query)
    label = (
        f"mindestens ein hinterlegtes Mitarbeiterdokument in {department}"
        if department
        else "mindestens ein hinterlegtes Mitarbeiterdokument"
    )
    answer = _format_employee_list_answer(
        "Mitarbeiter mit Dokumenten",
        label,
        employees,
        "Sichtbare Mitarbeiter",
        source="Strukturierte Mitarbeiterdaten",
        total_count=total_count,
    )
    structured_context = build_structured_context(
        "employees",
        query="with_documents",
        department=department,
    )
    return {
        "type": "employee_document_list",
        "answer": answer,
        "data": {
            "entity_type": "employees",
            "query": "document_list",
            "department": department or None,
            "count": total_count,
            "returned_count": len(employees),
            "truncated": truncated,
            "items": [_employee_payload(employee, user) for employee in employees],
        },
        "sources": employee_source_cards(employees, user),
        "scope": "employees",
        "structured_context": structured_context,
    }


def _employees_with_documents_query(user, department=None):
    """Return visible employees with documents, optionally filtered by department."""
    query = visible_employees_with_documents_query(user)
    if department:
        query = query.filter(Employee.department.ilike(department))
    return query


def _visible_employee_documents_query(user, department=None, employee=None):
    """Return employee document rows visible through employee dashboard access."""
    query = EmployeeDocument.query.join(Employee, EmployeeDocument.employee_id == Employee.id)
    query = query.filter(
        EmployeeDocument.employee_id.in_(visible_employees_query(user).with_entities(Employee.id))
    )
    if department:
        query = query.filter(Employee.department.ilike(department))
    if employee is not None:
        query = query.filter(EmployeeDocument.employee_id == employee.id)
    return query


def _employee_document_payload(document, user):
    """Return compact employee document metadata for structured answers."""
    employee = document.employee
    payload = document.to_dict()
    if employee:
        payload["employee_name"] = employee.name
        payload["employee_department"] = employee.department
        payload["employee"] = _employee_payload(employee, user)
    return payload


def _paginated_rows(query):
    """Return total count, a limited row list, and whether more rows exist."""
    total_count = query.count()
    rows = query.limit(MAX_LIST_ITEMS).all()
    return total_count, rows, total_count > len(rows)


def _format_employee_stored_document_answer(label, documents, total_count=None):
    """Return a compact German answer listing stored employee document files."""
    visible_total = total_count if total_count is not None else len(documents)
    lines = [
        "## Hinterlegte Mitarbeiterdokumente",
        f"- **Filter:** {label}",
        f"- **Anzahl:** {visible_total}",
        "- **Quelle:** Strukturierte Mitarbeiterdaten",
    ]
    if total_count is not None and total_count > len(documents):
        lines.append(
            f"- **Hinweis:** {len(documents)} von {total_count} " "sichtbaren Dokumenten angezeigt"
        )
    if not documents:
        lines.append("")
        lines.append("Keine sichtbaren Mitarbeiterdokumente fuer diese Anfrage gefunden.")
        return "\n".join(lines)
    lines.append("")
    lines.append("Sichtbare Dokumente:")
    for document in documents[:MAX_ANSWER_ITEMS]:
        employee = document.employee
        employee_label = employee.name if employee else f"Mitarbeiter #{document.employee_id}"
        uploaded = (
            document.uploaded_at.strftime("%d.%m.%Y")
            if getattr(document, "uploaded_at", None)
            else ""
        )
        uploaded_label = f", {uploaded}" if uploaded else ""
        lines.append(f"- {document.original_filename} ({employee_label}{uploaded_label})")
    if len(documents) > MAX_ANSWER_ITEMS:
        lines.append(f"- ... {len(documents) - MAX_ANSWER_ITEMS} weitere sichtbare Dokumente")
    return "\n".join(lines)


def _mentions_employee_documents(text):
    """Return whether the text asks about employee-attached documents."""
    return any(term in text for term in DOCUMENT_TERMS)


def _is_employee_document_question(text, conversation_context, message=None, user=None):
    """Return whether the message targets employees with stored documents."""
    if _mentions_employee_documents(text):
        if any(term in text for term in ("mitarbeiter", "personal", "employee")):
            return True
        if any(
            phrase in text
            for phrase in (
                "dokumente hat",
                "unterlagen hat",
                "dateien hat",
                "dokumente von",
                "unterlagen von",
                "dateien von",
            )
        ):
            return True
        if message and user and _requested_employee(message, user):
            return True
    return _is_employee_document_follow_up(text, conversation_context)


def _is_employee_document_count_question(text, conversation_context):
    """Return whether the text asks for a count of employees with documents."""
    if _is_employee_stored_document_count_question(text, conversation_context):
        return False
    if not _mentions_employee_documents(text):
        return False
    if any(term in text for term in COUNT_TERMS):
        return True
    return _is_employee_document_follow_up(text, conversation_context) and any(
        term in text for term in COUNT_TERMS
    )


def _is_employee_document_list_question(text, conversation_context):
    """Return whether the text asks which employees have stored documents."""
    if _asks_which_stored_documents_for_employees(text):
        return False
    if _is_employee_with_documents_follow_up_list(text, conversation_context):
        return True
    if not _mentions_employee_documents(text):
        return False
    if _is_employee_first_document_question(text):
        if any(term in text for term in LIST_TERMS):
            return True
    if _is_employee_document_follow_up(text, conversation_context):
        return True
    return any(
        phrase in text
        for phrase in (
            "haben dokumente",
            "haben unterlagen",
            "mit dokumenten",
            "mit unterlagen",
        )
    )


def _is_employee_with_documents_follow_up_list(text, conversation_context):
    """Return whether a follow-up should list employees with stored documents."""
    if _mentions_employee_documents(text):
        return False
    if _is_employee_stored_documents_follow_up_list(text, conversation_context):
        return False
    if not (is_structured_follow_up(text) or is_bare_list_refinement(text)):
        return False
    if not is_bare_list_refinement(text) and not any(term in text for term in LIST_TERMS):
        return False
    inherited = _inherited_employee_scope(conversation_context)
    query = str(inherited.get("query") or "").strip()
    last_response_type = str(getattr(conversation_context, "last_response_type", "") or "")
    if last_response_type == "employee_document_list":
        return False
    if query in {"with_documents", "document_count", "document_list"}:
        return True
    return last_response_type == "employee_document_count"


def _is_employee_stored_documents_follow_up_list(text, conversation_context):
    """Return whether a follow-up should list stored employee document files."""
    if not (is_structured_follow_up(text) or is_bare_list_refinement(text)):
        return False
    last_response_type = str(getattr(conversation_context, "last_response_type", "") or "")
    if last_response_type == "employee_document_list":
        return is_bare_list_refinement(text) or _asks_which_stored_documents_for_employees(text)
    if last_response_type in {"employee_stored_document_list", "employee_stored_document_count"}:
        return is_bare_list_refinement(text)
    return False


def _is_employee_first_document_question(text):
    """Return whether the question focuses on employees rather than document files."""
    return any(
        phrase in text
        for phrase in (
            "welche mitarbeiter",
            "welcher mitarbeiter",
            "mitarbeiter mit dokument",
            "mitarbeiter mit unterlage",
            "mitarbeiter mit datei",
            "mitarbeiter haben dokument",
            "mitarbeiter haben unterlage",
        )
    )


def _is_employee_stored_document_count_question(text, conversation_context):
    """Return whether the text asks for a count of stored employee document files."""
    if not _mentions_employee_documents(text):
        return False
    if not any(term in text for term in COUNT_TERMS):
        return False
    if _is_employee_first_document_question(text):
        return False
    file_count_phrases = (
        "mitarbeiterdokumente",
        "mitarbeiter dokumente",
        "hinterlegte dokumente",
        "hinterlegten dokumenten",
        "dokumente hinterlegt",
        "dateien hinterlegt",
        "unterlagen hinterlegt",
        "wie viele dokumente",
        "wie viele dateien",
        "wie viele unterlagen",
        "anzahl dokumente",
        "anzahl dateien",
    )
    return any(phrase in text for phrase in file_count_phrases)


def _asks_which_stored_documents_for_employees(text):
    """Return whether the text asks which files were stored for employees."""
    if not _mentions_employee_documents(text):
        return False
    if _is_employee_first_document_question(text):
        return False
    document_file_phrases = (
        "welche dokumente",
        "welche unterlagen",
        "welche dateien",
        "dokumente wurden",
        "unterlagen wurden",
        "dateien wurden",
        "dokumente hat",
        "unterlagen hat",
        "dateien hat",
        "dokumente von",
        "unterlagen von",
        "dateien von",
        "bei mitarbeiter",
        "fur mitarbeiter",
        "von mitarbeiter",
        "fuer mitarbeiter",
    )
    return any(phrase in text for phrase in document_file_phrases)


def _requested_employee(message, user):
    """Return a visible employee mentioned by name in the question."""
    text = normalize_text(message)
    matches = []
    for employee in visible_employees_query(user).order_by(Employee.name.desc()).all():
        normalized_name = normalize_text(employee.name)
        if normalized_name and normalized_name in text:
            matches.append(employee)
    if not matches:
        return None
    return max(matches, key=lambda item: len(normalize_text(item.name)))


def _is_employee_name_document_refinement(text, conversation_context, message, user):
    """Return whether a follow-up narrows employee documents to one named employee."""
    employee = _requested_employee(message, user)
    if not employee:
        return False
    if not _has_employee_document_context(conversation_context):
        return False
    last_response_type = str(getattr(conversation_context, "last_response_type", "") or "")
    if last_response_type not in {
        "employee_stored_document_list",
        "employee_stored_document_count",
        "employee_document_list",
        "employee_document_count",
    }:
        inherited = _inherited_employee_scope(conversation_context)
        if str(inherited.get("query") or "") not in {
            "stored_document_list",
            "stored_document_count",
            "document_list",
            "with_documents",
        }:
            return False
    refinement_terms = ("nur ", "bei ", "von ", "fur ", "fuer ")
    if any(term in text for term in refinement_terms):
        return True
    return len(text.split()) <= 4


def _document_scope_employee(conversation_context, message, user):
    """Return an employee filter from the question or inherited structured context."""
    employee = _requested_employee(message, user)
    if employee:
        return employee
    inherited = _inherited_employee_scope(conversation_context)
    employee_id = inherited.get("employee_id")
    if employee_id in (None, ""):
        return None
    return visible_employees_query(user).filter(Employee.id == int(employee_id)).first()


def _employee_document_structured_context(query, department=None, employee=None):
    """Return structured memory for employee document file answers."""
    fields = {"query": query, "department": department}
    if employee is not None:
        fields["employee_id"] = employee.id
        fields["employee_name"] = employee.name
    return build_structured_context("employees", **fields)


def _document_scope_department(conversation_context, message=None):
    """Return a department filter inherited from recent employee document context."""
    inherited = _inherited_employee_scope(conversation_context)
    department = str(inherited.get("department") or "").strip()
    query = str(inherited.get("query") or "").strip()
    last_response_type = str(getattr(conversation_context, "last_response_type", "") or "")
    if department and query in {"department_count", "department_list"}:
        return department
    if department and last_response_type == "employee_department_count":
        return department
    if message:
        detected = detect_department(message)
        if detected:
            return detected
    return ""


def _is_employee_document_follow_up(text, conversation_context):
    """Return whether a follow-up should stay on employees-with-documents."""
    if not is_structured_follow_up(text):
        return False
    if not _mentions_employee_documents(text):
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

"""AI orchestration services for permission-aware workflows."""
# ruff: noqa: F401, F821

import logging
from datetime import date

from app.models import (
    Employee,
    ErrorEntry,
    GeneratedDocument,
    InventoryMaterial,
    Machine,
    ShiftPlan,
    Task,
    User,
)
from app.security import employee_access_level, has_dashboard_permission
from app.services.ai_prompting import (
    permission_denied_answer,
    permission_denied_context,
)
from app.services.ai_structured_source_service import module_count_source_card
from app.services.document_service import visible_documents_query
from app.services.error_service import visible_errors_query
from app.services.task_service import visible_tasks_query
from app.services.visibility_query_service import (
    visible_employees_query,
    visible_inventory_materials_query,
    visible_machines_query,
    visible_shiftplans_query,
)

LAST_OPENAI_ERROR = None
OPENAI_PROVIDER = "OpenAI"
logger = logging.getLogger(__name__)

DASHBOARD_SCOPE_LABELS = {
    "tasks": "Tasks",
    "errors": "Fehlerkatalog",
    "employees": "Mitarbeiter",
    "machines": "Maschinen",
    "inventory": "Lager",
    "documents": "Dokumente",
    "shiftplans": "Schichtplanung",
    "admin_users": "Admin Users",
}

SCOPE_KEYWORDS = {
    "tasks": ["task", "tasks", "aufgabe", "aufgaben", "todo"],
    "errors": [
        "fehler",
        "stoerung",
        "störung",
        "error",
        "fehlercode",
        "ursache",
    ],
    "employees": [
        "mitarbeiter",
        "personal",
        "personaldaten",
        "gehalt",
        "gehaltsklasse",
        "adresse",
        "geburtsdatum",
        "qualifikation",
    ],
    "machines": ["maschine", "maschinen", "anlage", "anlagen", "machine"],
    "inventory": ["lager", "bestand", "material", "ersatzteil", "inventory"],
    "documents": ["dokument", "dokumente", "bericht", "berichte", "report"],
    "shiftplans": ["schichtplan", "schichtplanung", "dienstplan", "schicht"],
    "admin_users": ["user", "users", "nutzer", "benutzer", "accounts"],
}

COUNT_WORDS = [
    "wie viele",
    "wie vile",
    "wieviele",
    "wievile",
    "anzahl",
    "count",
    "many",
]

GENERAL_KNOWLEDGE_PREFIXES = (
    "was ist",
    "was bedeutet",
    "wie funktioniert",
    "warum",
    "wer ist",
    "erklaere",
    "erkläre",
    "what is",
    "how does",
    "why",
)

APP_DATA_INTENT_PHRASES = (
    "bei uns",
    "im system",
    "in der app",
    "in unserer datenbank",
    "meine",
    "mein",
    "unsere",
    "unser",
    "sichtbar",
    "vorhanden",
    "angelegt",
    "offen",
    "heute",
    "morgen",
    "anstehend",
    "zeige",
    "liste",
    "auflisten",
    "anzeigen",
    "gibt es",
    "erstellen",
    "anlegen",
    "loeschen",
    "löschen",
    "aendern",
    "ändern",
)


def format_tasks_today(user):
    """Return a formatted answer and structured data for today's visible tasks."""
    if not has_dashboard_permission(user, "tasks", "view"):
        return permission_denied_answer("Tasks"), []

    tasks = (
        visible_tasks_query(user)
        .filter(Task.due_date == date.today())
        .order_by(Task.priority.asc(), Task.id.desc())
        .all()
    )
    if not tasks:
        return (
            "## Heutige Tasks\n"
            "- **Status:** Keine Tasks fuer heute\n"
            "- **Bereich:** Keine offenen Eintraege sichtbar"
        ), []

    lines = ["## Heutige Tasks"]
    for task in tasks:
        lines.append(
            f"- **{task.title}:** {task.priority.value}, {task.status.value}, "
            f"{task.department.name}"
        )
    return "\n".join(lines), [task.to_dict() for task in tasks]


def build_error_context(entries):
    """Build a text context block from matching error catalog entries."""
    if not entries:
        return ""
    blocks = []
    for entry in entries:
        blocks.append(
            "\n".join(
                [
                    f"Maschine: {entry.machine}",
                    f"Fehlercode: {entry.error_code}",
                    f"Titel: {entry.title}",
                    f"Beschreibung: {entry.description}",
                    f"Mögliche Ursachen: {entry.possible_causes}",
                    f"Lösung: {entry.solution}",
                    f"Bereich: {entry.department.name}",
                ]
            )
        )
    return "\n\n".join(blocks)


def build_task_context(user):
    """Build a text context block from the user's visible tasks."""
    if not has_dashboard_permission(user, "tasks", "view"):
        return permission_denied_context("Tasks", "tasks")

    tasks = visible_tasks_query(user).order_by(Task.due_date.asc(), Task.id.desc()).limit(20).all()
    if not tasks:
        return "Keine sichtbaren Tasks vorhanden."
    lines = []
    for task in tasks:
        lines.append(
            " | ".join(
                [
                    f"Titel: {task.title}",
                    f"Status: {task.status.value}",
                    f"Prioritaet: {task.priority.value}",
                    f"Faellig: {task.due_date.isoformat()}",
                    f"Bereich: {task.department.name}",
                    f"Beschreibung: {task.description}",
                ]
            )
        )
    return "\n".join(lines)


def build_catalog_context(user, preferred_entries):
    """Build a combined error catalog context for the AI assistant."""
    if not has_dashboard_permission(user, "errors", "view"):
        return permission_denied_context("Fehlerkatalog", "errors")

    entries = list(preferred_entries)
    seen = {entry.id for entry in entries}
    query = visible_errors_query(user)
    for entry in query.order_by(ErrorEntry.created_at.desc()).limit(20).all():
        if entry.id not in seen:
            entries.append(entry)
            seen.add(entry.id)
    return build_error_context(entries) or "Keine sichtbaren Fehlerkatalogeintraege vorhanden."


def build_employee_context(user):
    """Build a filtered employee context for the AI assistant."""
    if not can_read_employee_context(user):
        return permission_denied_context("Mitarbeiter", "employees"), []

    access_level = employee_access_level(user)
    employees = visible_employees_query(user).order_by(Employee.name.asc()).limit(30).all()
    if not employees:
        return "Keine sichtbaren Mitarbeiterdaten vorhanden.", []

    lines = []
    for employee in employees:
        data = employee.to_dict(access_level)
        parts = [
            f"Personalnummer: {data.get('personnel_number')}",
            f"Name: {data.get('name')}",
            f"Abteilung: {data.get('department')}",
            f"Team: {data.get('team')}",
        ]
        if access_level in ("shift", "confidential"):
            parts.extend(
                [
                    f"Schichtmodell: {data.get('shift_model')}",
                    f"Aktuelle Schicht: {data.get('current_shift')}",
                    f"Qualifikationen: {data.get('qualifications')}",
                    f"Favoritenmaschine: {data.get('favorite_machine')}",
                ]
            )
        if access_level == "confidential":
            parts.extend(
                [
                    f"Geburtsdatum: {data.get('birth_date')}",
                    f"Wohnort: {data.get('postal_code')} {data.get('city')}",
                    f"Strasse: {data.get('street')}",
                    f"Gehaltsklasse: {data.get('salary_group')}",
                ]
            )
        lines.append(" | ".join(parts))
    return "\n".join(lines), [employee.to_dict(access_level) for employee in employees]


def build_machine_context(user):
    """Build a compact machine context for the AI assistant."""
    if not has_dashboard_permission(user, "machines", "view"):
        return permission_denied_context("Maschinen", "machines"), []

    machines = visible_machines_query(user).order_by(Machine.name.asc()).limit(30).all()
    if not machines:
        return "Keine sichtbaren Maschinen vorhanden.", []

    lines = []
    for machine in machines:
        lines.append(
            " | ".join(
                [
                    f"Maschine: {machine.name}",
                    f"Produkt: {machine.produced_item}",
                    f"Personalbedarf: {machine.required_employees}",
                ]
            )
        )
    return "\n".join(lines), [machine.to_dict() for machine in machines]


def build_inventory_context(user):
    """Build a compact inventory context for the AI assistant."""
    if not has_dashboard_permission(user, "inventory", "view"):
        return permission_denied_context("Lager", "inventory"), []

    materials = (
        visible_inventory_materials_query(user)
        .order_by(
            InventoryMaterial.quantity.asc(),
            InventoryMaterial.name.asc(),
        )
        .limit(30)
        .all()
    )
    if not materials:
        return "Keine sichtbaren Lagerdaten vorhanden.", []

    lines = []
    for material in materials:
        machine_name = material.machine.name if material.machine else "nicht zugeordnet"
        lines.append(
            " | ".join(
                [
                    f"Material: {material.name}",
                    f"Bestand: {material.quantity}",
                    f"Maschine: {machine_name}",
                    f"Hersteller: {material.manufacturer}",
                ]
            )
        )
    return "\n".join(lines), [material.to_dict() for material in materials]


def build_document_context(user):
    """Build a compact generated-document context for the AI assistant."""
    if not has_dashboard_permission(user, "documents", "view"):
        return permission_denied_context("Dokumente", "documents"), []

    documents = (
        visible_documents_query(user).order_by(GeneratedDocument.created_at.desc()).limit(20).all()
    )
    if not documents:
        return "Keine sichtbaren Dokumente vorhanden.", []

    lines = []
    for document in documents:
        lines.append(
            " | ".join(
                [
                    f"Titel: {document.title}",
                    f"Typ: {document.document_type}",
                    f"Maschine: {document.machine}",
                    f"Bereich: {document.department}",
                    f"Erstellt: {document.created_at.isoformat()}",
                ]
            )
        )
    return "\n".join(lines), [document.to_dict() for document in documents]


def build_shiftplan_context(user):
    """Build a compact shift-plan context for the AI assistant."""
    if not has_dashboard_permission(user, "shiftplans", "view"):
        return permission_denied_context("Schichtplanung", "shiftplans"), []

    query = visible_shiftplans_query(user).order_by(ShiftPlan.created_at.desc())
    plans = query.limit(10).all()
    if not plans:
        return "Keine sichtbaren Schichtplaene vorhanden.", []

    access_level = employee_access_level(user)
    lines = []
    for plan in plans:
        lines.append(
            " | ".join(
                [
                    f"Titel: {plan.title}",
                    f"Start: {plan.start_date.isoformat()}",
                    f"Tage: {plan.days}",
                    f"Bereich: {plan.department}",
                    f"Status: {plan.status}",
                ]
            )
        )
    return "\n".join(lines), [plan.to_dict(access_level) for plan in plans]


def format_employee_count(user):
    """Return a local answer for employee count questions."""
    if not can_read_employee_context(user):
        return permission_denied_answer("Mitarbeiter"), []

    count = visible_employees_query(user).count()
    answer = "## Mitarbeiter\n" f"- **Gesamt:** {count}\n" "- **Quelle:** Mitarbeiterdatenbank"
    return answer, {"count": count}


def format_module_count(user, scope):
    """Return a local count answer for one permission-aware module."""
    if scope == "employees":
        return format_employee_count(user)
    if scope == "admin_users":
        if not has_dashboard_permission(user, "admin_users", "view"):
            return permission_denied_answer("Admin Users", "admin_users"), []
        count = User.query.count()
        return ("## Admin Users\n" f"- **Gesamt:** {count}\n" "- **Quelle:** Nutzerverwaltung"), {
            "count": count
        }
    if not has_dashboard_permission(user, scope, "view"):
        return permission_denied_answer(DASHBOARD_SCOPE_LABELS[scope], scope), []

    count_query_map = {
        "tasks": visible_tasks_query(user),
        "errors": visible_errors_query(user),
        "machines": visible_machines_query(user),
        "inventory": visible_inventory_materials_query(user),
        "documents": visible_documents_query(user),
        "shiftplans": visible_shiftplans_query(user),
    }
    query = count_query_map.get(scope)
    if query is None:
        return None, None
    count = query.count()
    label = DASHBOARD_SCOPE_LABELS[scope]
    answer = f"## {label}\n" f"- **Gesamt:** {count}\n" f"- **Quelle:** {label}"
    return answer, {"count": count}


def count_answer_sources(scope, data, user):
    """Return aggregate source cards for successful module count answers."""
    if not isinstance(data, dict):
        return []

    source = module_count_source_card(scope, data.get("count"), user)
    return [source] if source else []


def answer_count_question(message, user, requested_scopes, allowed_scopes):
    """Return a local answer for explicit count questions."""
    if not looks_like_count_question(message):
        return None
    count_scopes = [
        scope
        for scope in (
            "admin_users",
            "employees",
            "tasks",
            "errors",
            "machines",
            "inventory",
            "documents",
            "shiftplans",
        )
        if scope in requested_scopes
    ]
    if not count_scopes:
        return None
    scope = count_scopes[0]
    answer, data = format_module_count(user, scope)
    if answer is None:
        return None
    status = "local_answer" if data else "permission_denied"
    sources = count_answer_sources(scope, data, user)
    return attach_audit_metadata(
        user,
        {
            "type": f"{scope}_count" if data else "permission_denied",
            "answer": answer,
            "diagnostics": ai_diagnostics(status),
            "data": data or [],
            "sources": sources,
        },
        requested_scopes or {scope},
        allowed_scopes,
        message=message,
    )


def should_use_general_hybrid_mode(message, requested_scopes):
    """Return whether the message should be answered as a general AI question."""
    if looks_like_general_knowledge_question(message):
        return True
    if requested_scopes:
        return False
    if looks_like_count_question(message):
        return False
    if looks_like_error_question(message):
        return False
    if looks_like_today_tasks_question(message):
        return False
    if looks_like_employee_question(message):
        return False
    return True


def fallback_error_answer(entries):
    """Return a local fallback answer when no OpenAI response is available."""
    if not entries:
        return (
            "## Fehlerhilfe\n"
            "- **Status:** Kein passender Eintrag gefunden\n"
            "- **Naechster Schritt:** Fehler im Katalog dokumentieren"
        )

    entry = entries[0]
    return (
        "## Fehlerhilfe\n"
        f"- **Code:** {entry.error_code} an {entry.machine}\n"
        f"- **Titel:** {entry.title}\n"
        f"- **Ursache:** {entry.possible_causes or 'keine Ursachen hinterlegt'}\n"
        f"- **Pruefung:** {entry.solution or 'keine Loesung hinterlegt'}"
    )


__all__ = [
    "format_tasks_today",
    "build_error_context",
    "build_task_context",
    "build_catalog_context",
    "build_employee_context",
    "build_machine_context",
    "build_inventory_context",
    "build_document_context",
    "build_shiftplan_context",
    "format_employee_count",
    "format_module_count",
    "count_answer_sources",
    "answer_count_question",
    "should_use_general_hybrid_mode",
    "fallback_error_answer",
]

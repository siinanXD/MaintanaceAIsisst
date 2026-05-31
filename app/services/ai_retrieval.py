"""Permission-aware retrieval helpers for AI assistant context."""

from app.handover.services import visible_handovers_query
from app.models import (
    Employee,
    ErrorEntry,
    GeneratedDocument,
    InventoryMaterial,
    Machine,
    MaintenancePlan,
    ShiftHandover,
    ShiftPlan,
    Task,
    User,
)
from app.security import employee_access_level, has_dashboard_permission
from app.services.document_service import visible_documents_query
from app.services.error_service import visible_errors_query
from app.services.query_classifier_service import TASK_ID_PATTERN
from app.services.retrieval_candidate_service import (
    RetrievalCandidate,
    normalize_retrieval_score,
    public_sources_from_candidates,
    rank_candidates,
    structured_candidate_score,
)
from app.services.retrieval_debug_service import retrieval_debug_decision
from app.services.structured_retrieval_metadata_service import (
    structured_record_scope_metadata,
)
from app.services.task_service import visible_tasks_query
from app.services.text_normalization_service import tokenize_text

MAX_SOURCES = 8


def retrieve_ai_context(message, user, requested_scopes=None):
    """Return ranked context, sources and payloads for an assistant message."""
    requested_scopes = set(requested_scopes or [])
    allowed_scopes = allowed_ai_scopes(user)
    searchable_scopes = requested_scopes & allowed_scopes if requested_scopes else allowed_scopes
    candidates = []
    data = {}

    if "tasks" in searchable_scopes:
        task_sources, tasks = _task_sources(message, user, requested_scopes)
        candidates.extend(task_sources)
        data["tasks"] = [task.to_dict() for task in tasks]
    if "errors" in searchable_scopes:
        error_sources, errors = _error_sources(message, user, requested_scopes)
        candidates.extend(error_sources)
        data["errors"] = [entry.to_dict() for entry in errors]
    if "machines" in searchable_scopes:
        machine_sources, machines = _machine_sources(message, requested_scopes)
        candidates.extend(machine_sources)
        data["machines"] = [machine.to_dict() for machine in machines]
        maintenance_sources, maintenance_plans = _maintenance_plan_sources(
            message,
            user,
            requested_scopes,
        )
        candidates.extend(maintenance_sources)
        data["maintenance_plans"] = [plan.to_dict() for plan in maintenance_plans]
    if "inventory" in searchable_scopes:
        inventory_sources, materials = _inventory_sources(message, requested_scopes)
        candidates.extend(inventory_sources)
        data["inventory"] = [material.to_dict() for material in materials]
    if "documents" in searchable_scopes:
        document_sources, documents = _document_sources(message, user, requested_scopes)
        candidates.extend(document_sources)
        data["documents"] = [document.to_dict() for document in documents]
    if "shiftplans" in searchable_scopes:
        shift_sources, plans = _shiftplan_sources(message, user, requested_scopes)
        candidates.extend(shift_sources)
        data["shiftplans"] = [plan.to_dict(employee_access_level(user)) for plan in plans]
        handover_sources, handovers = _handover_sources(message, user, requested_scopes)
        candidates.extend(handover_sources)
        data["shift_handovers"] = [handover.to_dict() for handover in handovers]
    if "employees" in searchable_scopes:
        employee_sources, employees = _employee_sources(message, user, requested_scopes)
        candidates.extend(employee_sources)
        access_level = employee_access_level(user)
        data["employees"] = [employee.to_dict(access_level) for employee in employees]
    if "admin_users" in searchable_scopes:
        admin_user_sources, admin_users = _admin_user_sources(message, requested_scopes)
        candidates.extend(admin_user_sources)
        data["admin_users"] = [_admin_user_payload(admin_user) for admin_user in admin_users]

    ranked_candidates = rank_candidates(candidates, MAX_SOURCES)
    debug = {
        "sql_candidates_found": len(ranked_candidates),
        "sql_candidates_by_scope": _candidate_count_by_scope(ranked_candidates),
        "decision_trace": [
            retrieval_debug_decision(
                "structured_sql_retrieval",
                "ok" if ranked_candidates else "empty",
                "ranked_visible_structured_candidates",
                {
                    "candidate_count": len(ranked_candidates),
                    "searchable_scope_count": len(searchable_scopes),
                    "requested_scope_count": len(requested_scopes),
                },
            )
        ],
    }
    return {
        "context": _context_from_sources(ranked_candidates),
        "sources": public_sources_from_candidates(ranked_candidates),
        "candidates": ranked_candidates,
        "data": data,
        "allowed_scopes": sorted(allowed_scopes),
        "requested_scopes": sorted(requested_scopes),
        "debug": debug,
    }


def allowed_ai_scopes(user):
    """Return AI scopes the user may use as assistant context."""
    scopes = {
        scope
        for scope in (
            "tasks",
            "errors",
            "machines",
            "inventory",
            "documents",
            "shiftplans",
            "admin_users",
        )
        if has_dashboard_permission(user, scope, "view")
    }
    if (
        has_dashboard_permission(user, "employees", "view")
        and employee_access_level(user) != "none"
    ):
        scopes.add("employees")
    return scopes


def _task_sources(message, user, requested_scopes):
    """Return ranked task sources visible to the user."""
    query = visible_tasks_query(user).order_by(Task.updated_at.desc()).limit(30)
    tasks = _rank_records(query.all(), message, _task_text, "tasks", requested_scopes)
    return [
        _source(
            "task",
            task.id,
            task.title,
            "tasks",
            "/tasks",
            _task_context(task),
            score,
            reason,
            metadata=_safe_source_metadata(task),
        )
        for task, score, reason in tasks
    ], [task for task, _score, _reason in tasks]


def _error_sources(message, user, requested_scopes):
    """Return ranked error catalog sources visible to the user."""
    query = visible_errors_query(user).order_by(ErrorEntry.created_at.desc()).limit(30)
    errors = _rank_records(query.all(), message, _error_text, "errors", requested_scopes)
    return [
        _source(
            "error",
            entry.id,
            f"{entry.error_code} - {entry.title}",
            "errors",
            "/errors",
            _error_context(entry),
            score,
            reason,
            metadata=_safe_source_metadata(entry),
        )
        for entry, score, reason in errors
    ], [entry for entry, _score, _reason in errors]


def _machine_sources(message, requested_scopes):
    """Return ranked machine sources."""
    machines = Machine.query.order_by(Machine.name.asc()).limit(30).all()
    ranked = _rank_records(
        machines,
        message,
        _machine_text,
        "machines",
        requested_scopes,
    )
    return [
        _source(
            "machine",
            machine.id,
            machine.name,
            "machines",
            "/machines",
            _machine_context(machine),
            score,
            reason,
            metadata=_safe_source_metadata(machine),
        )
        for machine, score, reason in ranked
    ], [machine for machine, _score, _reason in ranked]


def _maintenance_plan_sources(message, user, requested_scopes):
    """Return ranked maintenance-plan sources visible to the user."""
    query = MaintenancePlan.query.order_by(
        MaintenancePlan.is_active.desc(),
        MaintenancePlan.next_due_date.asc(),
        MaintenancePlan.id.desc(),
    )
    if not user.is_admin:
        query = query.filter(MaintenancePlan.department_id == user.department_id)
    ranked = _rank_records(
        query.limit(30).all(),
        message,
        _maintenance_plan_text,
        "machines",
        requested_scopes,
    )
    return [
        _source(
            "maintenance_plan",
            plan.id,
            plan.title,
            "machines",
            "/machines",
            _maintenance_plan_context(plan),
            score,
            reason,
            metadata=_safe_source_metadata(plan),
        )
        for plan, score, reason in ranked
    ], [plan for plan, _score, _reason in ranked]


def _inventory_sources(message, requested_scopes):
    """Return ranked inventory sources."""
    materials = (
        InventoryMaterial.query.order_by(
            InventoryMaterial.quantity.asc(), InventoryMaterial.name.asc()
        )
        .limit(30)
        .all()
    )
    ranked = _rank_records(
        materials,
        message,
        _material_text,
        "inventory",
        requested_scopes,
    )
    return [
        _source(
            "inventory",
            material.id,
            material.name,
            "inventory",
            "/inventory",
            _material_context(material),
            score,
            reason,
            metadata=_safe_source_metadata(material),
        )
        for material, score, reason in ranked
    ], [material for material, _score, _reason in ranked]


def _document_sources(message, user, requested_scopes):
    """Return ranked generated-document sources visible to the user."""
    documents = (
        visible_documents_query(user).order_by(GeneratedDocument.created_at.desc()).limit(30).all()
    )
    ranked = _rank_records(
        documents,
        message,
        _document_text,
        "documents",
        requested_scopes,
    )
    return [
        _source(
            "document",
            document.id,
            document.title,
            "documents",
            "/documents",
            _document_context(document),
            score,
            reason,
            metadata=_safe_source_metadata(document),
        )
        for document, score, reason in ranked
    ], [document for document, _score, _reason in ranked]


def _shiftplan_sources(message, user, requested_scopes):
    """Return ranked shift-plan sources visible to the user."""
    query = ShiftPlan.query.order_by(ShiftPlan.created_at.desc())
    if not user.is_admin:
        query = query.filter(ShiftPlan.status == "published")
    ranked = _rank_records(
        query.limit(20).all(),
        message,
        _shiftplan_text,
        "shiftplans",
        requested_scopes,
    )
    return [
        _source(
            "shiftplan",
            plan.id,
            plan.title,
            "shiftplans",
            "/shiftplans",
            _shiftplan_context(plan),
            score,
            reason,
            metadata=_safe_source_metadata(plan),
        )
        for plan, score, reason in ranked
    ], [plan for plan, _score, _reason in ranked]


def _handover_sources(message, user, requested_scopes):
    """Return ranked shift-handover sources visible to the user."""
    handovers = (
        visible_handovers_query(user)
        .order_by(ShiftHandover.shift_date.desc(), ShiftHandover.id.desc())
        .limit(30)
        .all()
    )
    ranked = _rank_records(
        handovers,
        message,
        _handover_text,
        "shiftplans",
        requested_scopes,
    )
    return [
        _source(
            "shift_handover",
            handover.id,
            f"Schichtuebergabe {handover.shift_date.isoformat()} {handover.shift_type}",
            "shiftplans",
            "/handover",
            _handover_context(handover),
            score,
            reason,
            metadata=_safe_source_metadata(handover),
        )
        for handover, score, reason in ranked
    ], [handover for handover, _score, _reason in ranked]


def _employee_sources(message, user, requested_scopes):
    """Return ranked employee sources visible to the user access tier."""
    access_level = employee_access_level(user)
    employees = Employee.query.order_by(Employee.name.asc()).limit(30).all()
    ranked = _rank_records(
        employees,
        message,
        lambda employee: _employee_text(employee, access_level),
        "employees",
        requested_scopes,
    )
    return [
        _source(
            "employee",
            employee.id,
            employee.name,
            "employees",
            "/employees",
            _employee_context(employee, access_level),
            score,
            reason,
            metadata=_employee_source_metadata(employee, access_level),
        )
        for employee, score, reason in ranked
    ], [employee for employee, _score, _reason in ranked]


def _admin_user_sources(message, requested_scopes):
    """Return ranked admin-user sources visible to master administrators."""
    users = User.query.order_by(User.username.asc()).limit(30).all()
    ranked = _rank_records(
        users,
        message,
        _admin_user_text,
        "admin_users",
        requested_scopes,
    )
    return [
        _source(
            "admin_user",
            admin_user.id,
            admin_user.username,
            "admin_users",
            "/admin/users",
            _admin_user_context(admin_user),
            score,
            reason,
            metadata=_admin_user_source_metadata(admin_user),
        )
        for admin_user, score, reason in ranked
    ], [admin_user for admin_user, _score, _reason in ranked]


def _rank_records(records, message, text_fn, scope, requested_scopes):
    """Rank records by token overlap, using recency/order fallback for requested scopes."""
    query_tokens = _tokens(message)
    explicit_task_ids = _explicit_task_ids(message)
    ranked = []
    for index, record in enumerate(records):
        record_tokens = _tokens(text_fn(record))
        score = structured_candidate_score(
            query_tokens=query_tokens,
            candidate_tokens=record_tokens,
            permission_scope=scope,
            requested_scopes=requested_scopes,
            index=index,
        )
        if not score.allowed:
            continue
        raw_score = score.raw_score
        explanation = score.explanation
        if _matches_explicit_task_id(record, scope, explicit_task_ids):
            raw_score += 120
            explanation = f"{explanation}; explizite Task-ID"
        ranked.append((record, raw_score, explanation, index))
    ranked.sort(key=lambda item: (item[1], -item[3]), reverse=True)
    return [(record, score, reason) for record, score, reason, _index in ranked[:5]]


def _explicit_task_ids(message):
    """Return task ids explicitly referenced in the user message."""
    return {int(match.group(1)) for match in TASK_ID_PATTERN.finditer(str(message or ""))}


def _matches_explicit_task_id(record, scope, task_ids):
    """Return whether a structured record is the explicitly referenced task."""
    if scope != "tasks" or not task_ids:
        return False
    try:
        record_id = int(getattr(record, "id", 0) or 0)
    except (TypeError, ValueError):
        return False
    return record_id in task_ids


def _tokens(value):
    """Return normalized search tokens for matching."""
    return set(tokenize_text(value))


def _candidate_count_by_scope(candidates):
    """Return structured candidate counts grouped by permission scope."""
    counts = {}
    for candidate in candidates or []:
        scope = str(getattr(candidate, "permission_scope", "") or "unknown")
        counts[scope] = counts.get(scope, 0) + 1
    return counts


def _source(item_type, item_id, title, module, url, context, score, reason, metadata=None):
    """Return one internal source object."""
    safe_metadata = {
        "source_kind": "structured",
        "source_type": item_type,
        "source_id": item_id,
        "module": module,
        "source_record_id": item_id,
    }
    safe_metadata.update(metadata or {})
    return RetrievalCandidate(
        source_type=item_type,
        source_id=item_id,
        title=title,
        content=context,
        module=module,
        url=url,
        raw_score=float(score or 0),
        normalized_score=normalize_retrieval_score(score, "structured"),
        permission_scope=module,
        explanation=reason,
        metadata=safe_metadata,
    )


def _safe_source_metadata(record):
    """Return display-safe metadata for a structured source."""
    metadata = structured_record_scope_metadata(record)
    if isinstance(record, Task):
        metadata.update({"department": record.department.name if record.department else ""})
        return metadata
    if isinstance(record, ErrorEntry):
        metadata.update(
            {
                "machine": record.machine,
                "department": record.department.name if record.department else "",
            }
        )
        return metadata
    if isinstance(record, Machine):
        metadata.update({"machine": record.name})
        return metadata
    if isinstance(record, MaintenancePlan):
        metadata.update(
            {
                "department": record.department.name if record.department else "",
                "machine": record.machine.name if record.machine else "",
            }
        )
        return metadata
    if isinstance(record, InventoryMaterial):
        metadata.update({"machine": record.machine.name if record.machine else ""})
        return metadata
    if isinstance(record, GeneratedDocument):
        metadata.update({"machine": record.machine, "department": record.department})
        return metadata
    if isinstance(record, ShiftPlan):
        metadata.update({"department": record.department})
        return metadata
    if isinstance(record, ShiftHandover):
        metadata.update(
            {
                "department": record.department,
                "machine": record.machine.name if record.machine else "",
            }
        )
        return metadata
    return metadata


def _employee_source_metadata(employee, access_level):
    """Return display-safe metadata for an employee source access tier."""
    metadata = _safe_source_metadata(employee)
    metadata["employee_access_level"] = str(access_level or "none")
    return metadata


def _admin_user_source_metadata(admin_user):
    """Return display-safe metadata for an admin-user structured source."""
    metadata = _safe_source_metadata(admin_user)
    metadata["role_visibility"] = "admin_only"
    metadata["role"] = admin_user.role.value
    return metadata


def _context_from_sources(sources):
    """Build compact text context from selected sources."""
    if not sources:
        return "Keine passenden freigegebenen Quellen gefunden."
    return "\n\n".join(source.context_block() for source in sources)


def _task_text(task):
    """Return searchable task text."""
    return " ".join(
        [
            task.title,
            task.description,
            task.priority.value,
            task.status.value,
        ]
    )


def _task_context(task):
    """Return compact task context."""
    return (
        f"Task: {task.title} | Status: {task.status.value} | "
        f"Prioritaet: {task.priority.value} | Faellig: {task.due_date.isoformat()} | "
        f"Bereich: {task.department.name if task.department else ''} | "
        f"Beschreibung: {task.description}"
    )


def _error_text(entry):
    """Return searchable error text."""
    return " ".join(
        [
            entry.machine,
            entry.error_code,
            entry.title,
            entry.description,
            entry.possible_causes,
            entry.solution,
        ]
    )


def _error_context(entry):
    """Return compact error context."""
    return (
        f"Maschine: {entry.machine} | Code: {entry.error_code} | "
        f"Titel: {entry.title} | Ursache: {entry.possible_causes} | "
        f"Loesung: {entry.solution}"
    )


def _machine_text(machine):
    """Return searchable machine text."""
    return " ".join([machine.name, machine.produced_item])


def _machine_context(machine):
    """Return compact machine context."""
    return (
        f"Maschine: {machine.name} | Produkt: {machine.produced_item} | "
        f"Personalbedarf: {machine.required_employees}"
    )


def _maintenance_plan_text(plan):
    """Return searchable maintenance-plan text."""
    return " ".join(
        str(value or "")
        for value in (
            plan.title,
            plan.description,
            plan.priority.value,
            plan.department.name if plan.department else "",
            plan.machine.name if plan.machine else "",
            plan.next_due_date.isoformat(),
            "aktiv" if plan.is_active else "inaktiv",
            "wartung wartungsplan maintenance",
        )
    )


def _maintenance_plan_context(plan):
    """Return compact maintenance-plan context without predictive claims."""
    machine_name = plan.machine.name if plan.machine else "nicht zugeordnet"
    department_name = plan.department.name if plan.department else ""
    status = "aktiv" if plan.is_active else "inaktiv"
    return (
        f"Wartungsplan: {plan.title} | Maschine: {machine_name} | "
        f"Bereich: {department_name} | Intervall: {plan.interval_days} Tage | "
        f"Naechste Faelligkeit: {plan.next_due_date.isoformat()} | "
        f"Prioritaet: {plan.priority.value} | Status: {status} | "
        f"Beschreibung: {plan.description}"
    )


def _material_text(material):
    """Return searchable inventory text."""
    machine_name = material.machine.name if material.machine else ""
    return " ".join([material.name, material.manufacturer, machine_name])


def _material_context(material):
    """Return compact inventory context."""
    machine_name = material.machine.name if material.machine else "nicht zugeordnet"
    return (
        f"Material: {material.name} | Bestand: {material.quantity} | "
        f"Maschine: {machine_name} | Hersteller: {material.manufacturer}"
    )


def _document_text(document):
    """Return searchable generated-document text."""
    return " ".join(
        [
            document.title,
            document.document_type,
            document.department,
            document.machine,
        ]
    )


def _document_context(document):
    """Return compact document context."""
    return (
        f"Dokument: {document.title} | Typ: {document.document_type} | "
        f"Maschine: {document.machine} | Bereich: {document.department}"
    )


def _shiftplan_text(plan):
    """Return searchable shift-plan text."""
    return " ".join([plan.title, plan.department, plan.rhythm, plan.status])


def _shiftplan_context(plan):
    """Return compact shift-plan context."""
    return (
        f"Schichtplan: {plan.title} | Bereich: {plan.department} | "
        f"Start: {plan.start_date.isoformat()} | Tage: {plan.days} | Status: {plan.status}"
    )


def _handover_text(handover):
    """Return searchable shift-handover text."""
    return " ".join(
        str(value or "")
        for value in (
            handover.department,
            handover.area,
            handover.machine.name if handover.machine else "",
            handover.shift_type,
            handover.status,
            handover.production_status,
            handover.machine_status,
            handover.problem_category,
            handover.content,
            handover.open_tasks,
            handover.machine_notes,
            handover.next_notes,
            handover.safety_notes,
            handover.material_notes,
            handover.cause,
            handover.action_taken,
            handover.follow_up_task,
        )
    )


def _handover_context(handover):
    """Return compact shift-handover context for assistant grounding."""
    machine_name = handover.machine.name if handover.machine else handover.area
    return (
        f"Schichtuebergabe: {handover.shift_date.isoformat()} {handover.shift_type} | "
        f"Bereich: {handover.department} | Maschine/Bereich: {machine_name} | "
        f"Status: {handover.status} | Produktion: {handover.production_status} | "
        f"Maschine: {handover.machine_status} | Kategorie: {handover.problem_category} | "
        f"Inhalt: {handover.content} | Offene Punkte: {handover.open_tasks} | "
        f"Maschinenhinweise: {handover.machine_notes} | Naechste Schritte: {handover.next_notes}"
    )


def _employee_text(employee, access_level):
    """Return searchable employee text for the user's access level."""
    data = employee.to_dict(access_level)
    return " ".join(str(value) for value in data.values() if value is not None)


def _employee_context(employee, access_level):
    """Return compact employee context for the user's access level."""
    data = employee.to_dict(access_level)
    parts = [
        f"Name: {data.get('name')}",
        f"Personalnummer: {data.get('personnel_number')}",
        f"Abteilung: {data.get('department')}",
        f"Team: {data.get('team')}",
    ]
    if access_level in ("shift", "confidential"):
        parts.extend(
            [
                f"Schichtmodell: {data.get('shift_model')}",
                f"Aktuelle Schicht: {data.get('current_shift')}",
                f"Qualifikationen: {data.get('qualifications')}",
            ]
        )
    if access_level == "confidential":
        parts.extend(
            [
                f"Wohnort: {data.get('postal_code')} {data.get('city')}",
                f"Gehaltsklasse: {data.get('salary_group')}",
            ]
        )
    return " | ".join(parts)


def _admin_user_text(admin_user):
    """Return searchable admin-user and role text."""
    return " ".join(
        [
            admin_user.username,
            admin_user.email,
            admin_user.role.value,
            admin_user.department.name if admin_user.department else "",
            _admin_user_permission_text(admin_user),
        ]
    )


def _admin_user_context(admin_user):
    """Return compact admin-user context without authentication secrets."""
    payload = _admin_user_payload(admin_user)
    permissions = payload["permission_summary"]
    return (
        f"User: {payload['username']} | Rolle: {payload['role']} | "
        f"Bereich: {payload['department'] or ''} | Aktiv: {payload['is_active']} | "
        f"Sichtbare Module: {', '.join(permissions['view']) or 'keine'} | "
        f"Schreibrechte: {', '.join(permissions['write']) or 'keine'} | "
        f"Mitarbeiterzugriff: {permissions['employee_access_level']}"
    )


def _admin_user_payload(admin_user):
    """Return a prompt-safe admin-user payload without authentication secrets."""
    return {
        "id": admin_user.id,
        "username": admin_user.username,
        "email": admin_user.email,
        "role": admin_user.role.value,
        "department": admin_user.department.name if admin_user.department else None,
        "employee_id": admin_user.employee_id,
        "is_active": bool(admin_user.is_active),
        "created_at": admin_user.created_at.isoformat(),
        "permission_summary": _admin_user_permission_summary(admin_user),
    }


def _admin_user_permission_text(admin_user):
    """Return searchable permission text for an admin user."""
    summary = _admin_user_permission_summary(admin_user)
    return " ".join(
        [
            "rollen rolle berechtigungen permissions user admin",
            " ".join(summary["view"]),
            " ".join(summary["write"]),
            summary["employee_access_level"],
        ]
    )


def _admin_user_permission_summary(admin_user):
    """Return compact dashboard permission labels for one admin-user source."""
    permissions = admin_user.to_dict().get("permissions") or {}
    view = sorted(
        dashboard
        for dashboard, values in permissions.items()
        if isinstance(values, dict) and values.get("can_view")
    )
    write = sorted(
        dashboard
        for dashboard, values in permissions.items()
        if isinstance(values, dict) and values.get("can_write")
    )
    employees = permissions.get("employees")
    employee_access = (
        employees.get("employee_access_level", "none") if isinstance(employees, dict) else "none"
    )
    return {
        "view": view,
        "write": write,
        "employee_access_level": employee_access,
    }

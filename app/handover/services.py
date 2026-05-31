"""Service functions for structured shift handover workflows."""

from datetime import UTC, date, datetime

from sqlalchemy import or_

from app.extensions import db
from app.models import (
    Department,
    ErrorEntry,
    Machine,
    MaintenancePlan,
    Priority,
    Role,
    ShiftHandover,
    Task,
    TaskStatus,
)
from app.security import has_dashboard_permission
from app.services.error_service import visible_errors_query
from app.services.operations_tracking_service import record_event
from app.services.task_service import visible_tasks_query
from app.shiftplans.services import parse_date

SHIFT_TYPES = ("Frueh", "Spaet", "Nacht")
HANDOVER_STATUSES = {"open", "completed"}
PROBLEM_CATEGORIES = {
    "Elektrik",
    "Mechanik",
    "Pneumatik",
    "Hydraulik",
    "SPS/Software",
    "Sensorik",
    "Netzwerk",
    "Material",
    "Qualität",
    "Sicherheit",
    "Organisation",
    "Sonstiges",
}
TEXT_FIELDS = (
    "content",
    "open_tasks",
    "machine_notes",
    "next_notes",
    "safety_notes",
    "material_notes",
    "cause",
    "action_taken",
    "follow_up_task",
    "involved_employees",
)
SHORT_FIELDS = (
    "area",
    "production_status",
    "machine_status",
    "responsible_employee",
)


def visible_handovers_query(user):
    """Return shift handovers visible to the given user."""
    query = ShiftHandover.query
    if user.role != Role.MASTER_ADMIN and user.department:
        query = query.filter(ShiftHandover.department == user.department.name)
    return query


def create_shift_handover(data, user):
    """Create and persist one structured shift handover."""
    try:
        department = _department_from_payload(data, user)
        shift_date = parse_date(data.get("shift_date"))
        shift_type = _normalize_shift_type(data.get("shift_type"))
        machine = _resolve_machine(data)
        status = _normalize_status(data.get("status"))
        confirmed = _boolean_value(data.get("confirmed")) or status == "completed"
        if confirmed:
            status = "completed"
        handover = ShiftHandover(
            plan_id=_optional_int(data.get("plan_id"), "plan_id"),
            department=department.name,
            area=_short_text(data.get("area")),
            machine_id=machine.id if machine else None,
            shift_date=shift_date,
            shift_type=shift_type,
            previous_shift=_normalize_shift_or_default(
                data.get("previous_shift"),
                _adjacent_shift(shift_type, -1),
            ),
            next_shift=_normalize_shift_or_default(
                data.get("next_shift"),
                _adjacent_shift(shift_type, 1),
            ),
            status=status,
            confirmed=confirmed,
            handed_over_by=user.id,
            handed_over_at=datetime.now(UTC) if confirmed else None,
        )
        _apply_structured_fields(handover, data)
    except PermissionError as exc:
        return None, {"error": str(exc)}, 403
    except ValueError as exc:
        return None, {"error": str(exc)}, 400

    db.session.add(handover)
    db.session.flush()
    _record_handover_event(
        "shift_handover.created",
        handover,
        user,
        department,
        machine,
        new_value=_handover_event_state(handover),
        description=f"Schichtuebergabe erstellt: {handover.shift_date.isoformat()}",
    )
    db.session.commit()
    return handover, None, 201


def update_shift_handover(handover, data, user):
    """Update an open shift handover with structured operational fields."""
    old_state = _handover_event_state(handover)
    if handover.status == "completed":
        return None, {"error": "Abgeschlossene Übergaben können nicht bearbeitet werden"}, 403
    try:
        department = None
        if "department" in data:
            department = _department_from_payload(data, user)
            handover.department = department.name
        else:
            department = Department.query.filter_by(name=handover.department).first()
        if "shift_date" in data:
            handover.shift_date = parse_date(data.get("shift_date"))
        if "shift_type" in data:
            handover.shift_type = _normalize_shift_type(data.get("shift_type"))
            handover.previous_shift = _adjacent_shift(handover.shift_type, -1)
            handover.next_shift = _adjacent_shift(handover.shift_type, 1)
        if "previous_shift" in data:
            handover.previous_shift = _normalize_shift_or_default(
                data.get("previous_shift"),
                handover.previous_shift,
            )
        if "next_shift" in data:
            handover.next_shift = _normalize_shift_or_default(
                data.get("next_shift"),
                handover.next_shift,
            )
        if "machine_id" in data or "machine" in data:
            machine = _resolve_machine(data)
            handover.machine_id = machine.id if machine else None
        else:
            machine = db.session.get(Machine, handover.machine_id) if handover.machine_id else None
        if "status" in data:
            handover.status = _normalize_status(data.get("status"))
        if "confirmed" in data:
            handover.confirmed = _boolean_value(data.get("confirmed"))
            if handover.confirmed:
                handover.status = "completed"
                handover.handed_over_at = handover.handed_over_at or datetime.now(UTC)
        _apply_structured_fields(handover, data)
    except PermissionError as exc:
        return None, {"error": str(exc)}, 403
    except ValueError as exc:
        return None, {"error": str(exc)}, 400

    _record_handover_event(
        "shift_handover.updated",
        handover,
        user,
        department,
        machine,
        old_value=old_state,
        new_value=_handover_event_state(handover),
        description=f"Schichtuebergabe aktualisiert: {handover.shift_date.isoformat()}",
    )
    db.session.commit()
    return handover, None, 200


def complete_shift_handover(handover, user):
    """Mark one handover as confirmed and completed."""
    old_state = _handover_event_state(handover)
    if handover.status == "completed":
        return None, {"error": "Übergabe bereits abgeschlossen"}, 409
    handover.status = "completed"
    handover.confirmed = True
    handover.handed_over_at = datetime.now(UTC)
    department = Department.query.filter_by(name=handover.department).first()
    machine = db.session.get(Machine, handover.machine_id) if handover.machine_id else None
    _record_handover_event(
        "shift_handover.completed",
        handover,
        user,
        department,
        machine,
        old_value=old_state,
        new_value=_handover_event_state(handover),
        description=f"Schichtuebergabe bestaetigt: {handover.shift_date.isoformat()}",
    )
    db.session.commit()
    return handover, None, 200


def summarize_shift_handover(handover, user):
    """Return an evidence-based summary for one visible shift handover."""
    open_tasks = _handover_open_tasks(handover, user)
    disruptions = _handover_disruptions(handover, user)
    maintenance_plans = _handover_maintenance_plans(handover, user)
    critical_points = _critical_handover_points(
        handover,
        open_tasks,
        disruptions,
        maintenance_plans,
    )
    next_actions = _handover_next_actions(
        handover,
        open_tasks,
        disruptions,
        maintenance_plans,
    )
    confidence = _handover_summary_confidence(
        handover,
        open_tasks,
        disruptions,
        maintenance_plans,
    )
    return {
        "handover": _handover_summary_reference(handover),
        "summary": _handover_summary_text(handover, critical_points, next_actions, confidence),
        "critical_points": critical_points,
        "next_actions": next_actions,
        "open_tasks": [_task_summary_item(task) for task in open_tasks],
        "disruptions": [_error_summary_item(entry) for entry in disruptions],
        "maintenance_plans": [_maintenance_plan_summary_item(plan) for plan in maintenance_plans],
        "confidence": confidence,
        "source_counts": _handover_source_counts(
            handover,
            open_tasks,
            disruptions,
            maintenance_plans,
        ),
        "evidence_summary": _handover_evidence_summary(
            handover,
            open_tasks,
            disruptions,
            maintenance_plans,
            user,
        ),
        "diagnostics": {
            "status": "local_handover_summary",
            "provider": "local_rules",
            "open_task_count": len(open_tasks),
            "disruption_count": len(disruptions),
            "maintenance_plan_count": len(maintenance_plans),
            "uses_only_visible_sources": True,
            "scopes": _handover_summary_scopes(user),
        },
    }


def _handover_evidence_summary(handover, open_tasks, disruptions, maintenance_plans, user):
    """Return audit-friendly evidence metadata for a handover summary."""
    source_counts = _handover_source_counts(
        handover,
        open_tasks,
        disruptions,
        maintenance_plans,
    )
    direct_source_count = (
        source_counts["handover_fields"]
        + source_counts["open_tasks"]
        + source_counts["disruptions"]
        + source_counts["maintenance_plans"]
    )
    return {
        "workflow": "shift_handover_summary",
        "provider": "local_rules",
        "uses_only_visible_sources": True,
        "source_types": _handover_evidence_source_types(
            handover,
            open_tasks,
            disruptions,
            maintenance_plans,
        ),
        "direct_source_count": direct_source_count,
        "has_open_task_context": bool(open_tasks),
        "has_disruption_context": bool(disruptions),
        "has_maintenance_plan_context": bool(maintenance_plans),
        "source_references": _handover_source_references(
            handover,
            open_tasks,
            disruptions,
            maintenance_plans,
        ),
        "scopes": _handover_summary_scopes(user),
        "latest_signal_at": _latest_handover_signal_at(
            open_tasks,
            disruptions,
            maintenance_plans,
        ),
        "llm_call": False,
    }


def _handover_evidence_source_types(handover, open_tasks, disruptions, maintenance_plans):
    """Return source type labels contributing to a handover summary."""
    source_types = ["shift_handover"] if _handover_filled_field_count(handover) else []
    if open_tasks:
        source_types.append("task")
    if disruptions:
        source_types.append("error")
    if maintenance_plans:
        source_types.append("maintenance_plan")
    return sorted(source_types)


def _handover_source_references(handover, open_tasks, disruptions, maintenance_plans):
    """Return prompt-safe source references used by a handover summary."""
    references = [_handover_source_reference(handover)]
    references.extend(_task_source_reference(task) for task in open_tasks[:3])
    references.extend(_error_source_reference(entry) for entry in disruptions[:3])
    references.extend(_plan_source_reference(plan) for plan in (maintenance_plans or [])[:3])
    return [reference for reference in references if reference]


def _handover_source_reference(handover):
    """Return a prompt-safe reference for the summarized handover."""
    return {
        "type": "shift_handover",
        "id": handover.id,
        "title": f"Schichtuebergabe {handover.shift_date.isoformat()}",
        "machine_id": handover.machine_id,
        "role_visibility": _handover_role_visibility(handover.department),
        "created_at": handover.created_at.isoformat() if handover.created_at else "",
    }


def _task_source_reference(task):
    """Return a prompt-safe reference for a visible task."""
    return {
        "type": "task",
        "id": task.id,
        "title": task.title,
        "machine_id": None,
        "role_visibility": _handover_role_visibility(
            task.department.name if task.department else "",
        ),
        "created_at": task.created_at.isoformat() if task.created_at else "",
        "due_date": task.due_date.isoformat() if task.due_date else None,
    }


def _error_source_reference(entry):
    """Return a prompt-safe reference for a visible disruption."""
    return {
        "type": "error",
        "id": entry.id,
        "title": f"{entry.error_code} - {entry.title}",
        "machine": entry.machine,
        "machine_id": entry.machine_id,
        "role_visibility": _handover_role_visibility(
            entry.department.name if entry.department else "",
        ),
        "created_at": entry.created_at.isoformat() if entry.created_at else "",
        "error_code": entry.error_code,
    }


def _plan_source_reference(plan):
    """Return a prompt-safe reference for a visible maintenance plan."""
    return {
        "type": "maintenance_plan",
        "id": plan.id,
        "title": plan.title,
        "machine_id": plan.machine_id,
        "role_visibility": _handover_role_visibility(
            plan.department.name if plan.department else "",
        ),
        "created_at": plan.created_at.isoformat() if plan.created_at else "",
        "due_date": plan.next_due_date.isoformat() if plan.next_due_date else None,
    }


def _handover_role_visibility(department):
    """Return a prompt-safe visibility label for handover summary evidence."""
    department_name = str(department or "").strip()
    return f"department:{department_name[:120]}" if department_name else "public"


def _latest_handover_signal_at(open_tasks, disruptions, maintenance_plans=None):
    """Return the newest timestamp from task or disruption evidence."""
    timestamps = []
    timestamps.extend(task.updated_at for task in open_tasks if task.updated_at)
    timestamps.extend(entry.created_at for entry in disruptions if entry.created_at)
    timestamps.extend(
        datetime.combine(plan.next_due_date, datetime.min.time())
        for plan in maintenance_plans or []
        if plan.next_due_date
    )
    if not timestamps:
        return None
    return max(timestamps).isoformat()


def _handover_source_counts(handover, open_tasks, disruptions, maintenance_plans=None):
    """Return compact source counts for the handover summary evidence."""
    return {
        "handover_fields": _handover_filled_field_count(handover),
        "open_tasks": len(open_tasks),
        "disruptions": len(disruptions),
        "maintenance_plans": len(maintenance_plans or []),
        "uses_only_visible_sources": True,
    }


def _handover_filled_field_count(handover):
    """Return how many handover text fields contribute summary evidence."""
    return sum(
        1
        for value in (
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
        if str(value or "").strip()
    )


def _handover_open_tasks(handover, user):
    """Return visible open tasks relevant to the handover context."""
    if not has_dashboard_permission(user, "tasks", "view"):
        return []
    query = visible_tasks_query(user).filter(
        Task.status.in_([TaskStatus.OPEN, TaskStatus.IN_PROGRESS])
    )
    if handover.department:
        query = query.filter(Task.department.has(name=handover.department))
    return query.order_by(Task.due_date.asc(), Task.id.desc()).limit(8).all()


def _handover_disruptions(handover, user):
    """Return visible open error entries relevant to the handover context."""
    if not has_dashboard_permission(user, "errors", "view"):
        return []
    query = visible_errors_query(user).filter(ErrorEntry.status != "closed")
    if handover.machine_id:
        machine = db.session.get(Machine, handover.machine_id)
        clauses = [ErrorEntry.machine_id == handover.machine_id]
        if machine:
            clauses.append(ErrorEntry.machine.ilike(f"%{machine.name}%"))
        query = query.filter(or_(*clauses))
    elif handover.department:
        query = query.join(Department, isouter=True).filter(Department.name == handover.department)
    return query.order_by(ErrorEntry.created_at.desc(), ErrorEntry.id.desc()).limit(8).all()


def _handover_maintenance_plans(handover, user):
    """Return visible maintenance plans relevant to the handover machine."""
    if not has_dashboard_permission(user, "machines", "view"):
        return []
    query = MaintenancePlan.query.filter(MaintenancePlan.is_active.is_(True))
    if user.role != Role.MASTER_ADMIN:
        query = query.filter(MaintenancePlan.department_id == user.department_id)
    if handover.machine_id:
        query = query.filter(MaintenancePlan.machine_id == handover.machine_id)
    elif handover.department:
        query = query.filter(MaintenancePlan.department.has(name=handover.department))
    return (
        query.order_by(MaintenancePlan.next_due_date.asc(), MaintenancePlan.id.desc())
        .limit(5)
        .all()
    )


def _critical_handover_points(handover, open_tasks, disruptions, maintenance_plans=None):
    """Return concise critical points from handover text and visible context."""
    points = []
    if _is_non_nominal(handover.production_status):
        points.append(_point("production_status", f"Produktion: {handover.production_status}"))
    if _is_non_nominal(handover.machine_status):
        points.append(_point("machine_status", f"Maschine: {handover.machine_status}"))
    if handover.problem_category in {"Sicherheit", "Elektrik", "Hydraulik"}:
        points.append(_point("problem_category", f"Kategorie: {handover.problem_category}"))
    for label, value in (
        ("safety_notes", handover.safety_notes),
        ("machine_notes", handover.machine_notes),
        ("open_tasks_text", handover.open_tasks),
        ("material_notes", handover.material_notes),
    ):
        if str(value or "").strip():
            points.append(_point(label, value))
    for task in open_tasks[:3]:
        if task.priority == Priority.URGENT or task.due_date <= date.today():
            points.append(_point("open_task", f"Task offen: {task.title}"))
    for entry in disruptions[:3]:
        points.append(_point("disruption", f"{entry.error_code} - {entry.title}"))
    for plan in (maintenance_plans or [])[:3]:
        if plan.next_due_date <= date.today() or plan.priority == Priority.URGENT:
            points.append(_point("maintenance_plan", f"Wartungsplan faellig: {plan.title}"))
    return _deduplicate_points(points)[:8]


def _handover_next_actions(handover, open_tasks, disruptions, maintenance_plans=None):
    """Return practical next actions for the next shift."""
    actions = []
    for label, value in (
        ("next_notes", handover.next_notes),
        ("follow_up_task", handover.follow_up_task),
        ("action_taken", handover.action_taken),
    ):
        text = str(value or "").strip()
        if text:
            actions.append(_action(label, text, "high" if label != "action_taken" else "medium"))
    for task in open_tasks[:3]:
        actions.append(
            _action(
                "task",
                f"{task.title} bis {task.due_date.isoformat()} bearbeiten.",
                "high" if task.priority == Priority.URGENT else "medium",
                source_id=task.id,
                title=task.title,
                due_date=task.due_date.isoformat(),
            )
        )
    for entry in disruptions[:3]:
        if entry.solution:
            actions.append(
                _action(
                    "error_solution",
                    entry.solution,
                    "high",
                    source_id=entry.id,
                    title=entry.title,
                    error_code=entry.error_code,
                )
            )
    for plan in (maintenance_plans or [])[:3]:
        actions.append(
            _action(
                "maintenance_plan",
                f"Wartungsplan {plan.title} bis {plan.next_due_date.isoformat()} pruefen.",
                "high" if plan.priority == Priority.URGENT else "medium",
                source_id=plan.id,
                title=plan.title,
                due_date=plan.next_due_date.isoformat(),
            )
        )
    if not actions:
        actions.append(
            _action(
                "documentation",
                "Naechste Schicht ueber Status informieren und Auffaelligkeiten dokumentieren.",
                "medium",
            )
        )
    return _deduplicate_actions(actions)[:8]


def _handover_summary_confidence(handover, open_tasks, disruptions, maintenance_plans=None):
    """Return confidence for the local handover summary."""
    evidence_count = sum(
        1
        for value in (
            handover.content,
            handover.open_tasks,
            handover.machine_notes,
            handover.next_notes,
            handover.safety_notes,
            handover.material_notes,
            handover.cause,
            handover.action_taken,
        )
        if str(value or "").strip()
    )
    score = min(
        100,
        35
        + evidence_count * 6
        + min(len(open_tasks), 4) * 5
        + len(disruptions) * 4
        + min(len(maintenance_plans or []), 3) * 4,
    )
    if score >= 75:
        level = "high"
    elif score >= 50:
        level = "medium"
    else:
        level = "low"
    return {
        "score": score,
        "level": level,
        "uncertainty": _handover_summary_uncertainty(level),
        "reason": "Basiert auf Handover-Feldern, sichtbaren offenen Tasks und Stoerungen.",
    }


def _handover_summary_uncertainty(level):
    """Return an uncertainty label aligned with handover summary confidence."""
    if level == "high":
        return "low"
    if level == "medium":
        return "medium"
    return "high"


def _handover_summary_text(handover, critical_points, next_actions, confidence):
    """Return a compact natural-language handover summary."""
    if critical_points:
        headline = f"{len(critical_points)} kritische Punkte fuer die naechste Schicht."
    else:
        headline = "Keine kritischen Punkte aus sichtbaren Daten erkannt."
    next_action = next_actions[0]["text"] if next_actions else "Status weiter beobachten."
    machine = handover.machine.name if handover.machine else handover.area or handover.department
    return (
        f"{handover.shift_type}-Uebergabe {handover.shift_date.isoformat()} fuer {machine}: "
        f"{headline} Wichtigste naechste Massnahme: {next_action} "
        f"Confidence {confidence['level']} ({confidence['score']}/100)."
    )


def _handover_summary_reference(handover):
    """Return stable handover metadata for a summary response."""
    return {
        "id": handover.id,
        "department": handover.department,
        "area": handover.area,
        "machine_id": handover.machine_id,
        "machine": handover.machine.name if handover.machine else "",
        "shift_date": handover.shift_date.isoformat(),
        "shift_type": handover.shift_type,
        "status": handover.status,
    }


def _task_summary_item(task):
    """Return a compact task item for handover summary context."""
    return {
        "id": task.id,
        "title": task.title,
        "priority": task.priority.value,
        "status": task.status.value,
        "due_date": task.due_date.isoformat(),
        "department": task.department.name if task.department else "",
    }


def _error_summary_item(entry):
    """Return a compact disruption item for handover summary context."""
    return {
        "id": entry.id,
        "machine": entry.machine,
        "machine_id": entry.machine_id,
        "error_code": entry.error_code,
        "title": entry.title,
        "status": entry.status,
        "severity": entry.severity,
        "possible_causes": entry.possible_causes,
        "solution": entry.solution,
    }


def _maintenance_plan_summary_item(plan):
    """Return a compact maintenance-plan item for handover summary context."""
    return {
        "id": plan.id,
        "title": plan.title,
        "priority": plan.priority.value,
        "next_due_date": plan.next_due_date.isoformat(),
        "machine_id": plan.machine_id,
        "is_active": plan.is_active,
    }


def _handover_summary_scopes(user):
    """Return the data scopes included in the handover summary."""
    scopes = ["handover"]
    if has_dashboard_permission(user, "tasks", "view"):
        scopes.append("tasks")
    if has_dashboard_permission(user, "errors", "view"):
        scopes.append("errors")
    if has_dashboard_permission(user, "machines", "view"):
        scopes.append("machines")
    return scopes


def _point(source, value):
    """Return one critical point."""
    return {"source": source, "text": _bounded_sentence(value)}


def _action(source, value, priority, **metadata):
    """Return one next action."""
    action = {"source": source, "text": _bounded_sentence(value), "priority": priority}
    for key in ("source_id", "title", "due_date", "error_code"):
        value = metadata.get(key)
        if value not in (None, ""):
            action[key] = value
    return action


def _is_non_nominal(value):
    """Return whether a status field indicates a potential issue."""
    normalized = str(value or "").strip().lower()
    return bool(normalized and normalized not in {"ok", "running", "normal", "stabil"})


def _bounded_sentence(value, max_length=260):
    """Return compact single-line text for summary cards."""
    return " ".join(str(value or "").strip().split())[:max_length]


def _deduplicate_points(points):
    """Return points without duplicate text."""
    seen = set()
    unique = []
    for point in points:
        key = point["text"].lower()
        if key and key not in seen:
            seen.add(key)
            unique.append(point)
    return unique


def _deduplicate_actions(actions):
    """Return actions without duplicate text."""
    seen = set()
    unique = []
    for action in actions:
        key = action["text"].lower()
        if key and key not in seen:
            seen.add(key)
            unique.append(action)
    return unique


def _department_from_payload(data, user):
    """Resolve and authorize the handover department from request data."""
    department_name = _short_text(data.get("department"))
    if not department_name and user.department:
        department_name = user.department.name
    if not department_name:
        raise ValueError("department ist erforderlich")
    department = Department.query.filter_by(name=department_name).first()
    if not department:
        raise ValueError("Gültige Abteilung erforderlich")
    if user.role != Role.MASTER_ADMIN and user.department_id != department.id:
        raise PermissionError("Benutzer dürfen nur Übergaben für ihren Bereich schreiben")
    return department


def _normalize_shift_type(value):
    """Return a supported shift key."""
    shift_type = str(value or "").strip()
    if shift_type not in SHIFT_TYPES:
        raise ValueError("shift_type muss Früh, Spät oder Nacht sein")
    return shift_type


def _normalize_shift_or_default(value, default):
    """Return a supported shift key or the given default."""
    if value in (None, ""):
        return default
    return _normalize_shift_type(value)


def _normalize_status(value):
    """Return a supported handover status."""
    status = str(value or "open").strip().lower()
    if status not in HANDOVER_STATUSES:
        raise ValueError("status muss open oder completed sein")
    return status


def _normalize_problem_category(value):
    """Return a known handover problem category or a safe fallback."""
    category = _short_text(value)
    if not category:
        return ""
    if category in PROBLEM_CATEGORIES:
        return category
    return "Sonstiges"


def _short_text(value, max_length=160):
    """Return normalized short text within a fixed length."""
    return " ".join(str(value or "").strip().split())[:max_length]


def _long_text(value, max_length=2000):
    """Return normalized multiline text within a fixed length."""
    return str(value or "").strip()[:max_length]


def _optional_int(value, field_name):
    """Return an optional integer request value."""
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} muss eine Zahl sein") from exc


def _non_negative_int(value, field_name):
    """Return a non-negative integer request value."""
    parsed = _optional_int(value, field_name)
    if parsed is None:
        return 0
    if parsed < 0:
        raise ValueError(f"{field_name} darf nicht negativ sein")
    return parsed


def _boolean_value(value):
    """Return a permissive boolean from form or JSON input."""
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "ja"}


def _adjacent_shift(shift_type, offset):
    """Return the previous or next shift key for a standard three-shift cycle."""
    index = SHIFT_TYPES.index(shift_type)
    return SHIFT_TYPES[(index + offset) % len(SHIFT_TYPES)]


def _resolve_machine(data):
    """Resolve a machine from machine_id or exact machine name."""
    if data.get("machine_id") not in (None, ""):
        machine_id = _optional_int(data.get("machine_id"), "machine_id")
        machine = db.session.get(Machine, machine_id)
        if not machine:
            raise ValueError("Gültige Maschine erforderlich")
        return machine
    machine_name = _short_text(data.get("machine"))
    if not machine_name:
        return None
    return Machine.query.filter(Machine.name.ilike(machine_name)).first()


def _apply_structured_fields(handover, data):
    """Copy structured handover fields from a request payload."""
    for field in TEXT_FIELDS:
        if field in data:
            setattr(handover, field, _long_text(data.get(field)))
    for field in SHORT_FIELDS:
        if field in data:
            setattr(handover, field, _short_text(data.get(field)))
    if "problem_category" in data:
        handover.problem_category = _normalize_problem_category(data.get("problem_category"))
    if "duration_minutes" in data:
        handover.duration_minutes = _non_negative_int(
            data.get("duration_minutes"),
            "duration_minutes",
        )


def _handover_event_state(handover):
    """Return compact handover state for audit old/new values."""
    return {
        "id": handover.id,
        "department": handover.department,
        "area": handover.area,
        "machine_id": handover.machine_id,
        "shift_date": handover.shift_date.isoformat() if handover.shift_date else None,
        "shift_type": handover.shift_type,
        "previous_shift": handover.previous_shift,
        "next_shift": handover.next_shift,
        "status": handover.status,
        "confirmed": handover.confirmed,
        "production_status": handover.production_status,
        "machine_status": handover.machine_status,
        "problem_category": handover.problem_category,
        "duration_minutes": handover.duration_minutes,
        "follow_up_task": handover.follow_up_task,
    }


def _record_handover_event(
    event_type,
    handover,
    user,
    department,
    machine,
    old_value=None,
    new_value=None,
    description="",
):
    """Record a lightweight operational event for a handover change."""
    record_event(
        event_type,
        "shiftplans",
        entity_type="shift_handover",
        entity_id=handover.id,
        user=user,
        department=department,
        machine=machine,
        metadata={
            "department": handover.department,
            "area": handover.area,
            "shift_date": handover.shift_date.isoformat(),
            "shift_type": handover.shift_type,
            "status": handover.status,
            "confirmed": handover.confirmed,
            "production_status": handover.production_status,
            "machine_status": handover.machine_status,
            "problem_category": handover.problem_category,
            "duration_minutes": handover.duration_minutes,
        },
        old_value=old_value,
        new_value=new_value,
        description=description,
    )

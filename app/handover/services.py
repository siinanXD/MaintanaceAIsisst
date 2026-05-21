"""Service functions for structured shift handover workflows."""

from datetime import UTC, datetime

from app.extensions import db
from app.models import Department, Machine, Role, ShiftHandover
from app.services.operations_tracking_service import record_event
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

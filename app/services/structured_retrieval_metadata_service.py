"""Prompt-safe metadata helpers for structured retrieval sources."""


def structured_record_scope_metadata(record):
    """Return prompt-safe scope metadata common to structured retrieval records."""
    department = record_department_name(record)
    metadata = {
        "role_visibility": f"department:{department[:120]}" if department else "public",
    }
    created_at = getattr(record, "created_at", None)
    if created_at is not None:
        metadata["created_at"] = created_at.isoformat()
    machine_id = record_machine_id(record)
    if machine_id is not None:
        metadata["machine_id"] = machine_id
    return metadata


def record_department_name(record):
    """Return a bounded department name from a structured retrieval record."""
    department = getattr(record, "department", "")
    if isinstance(department, str):
        return department.strip()
    if department is not None:
        return str(getattr(department, "name", "") or "").strip()
    return ""


def record_machine_id(record):
    """Return a machine id from structured retrieval records when available."""
    direct_id = _optional_int(getattr(record, "machine_id", None))
    if direct_id is not None:
        return direct_id
    if record.__class__.__name__ == "Machine":
        return _optional_int(getattr(record, "id", None))
    machine = getattr(record, "machine", None)
    return _optional_int(getattr(machine, "id", None))


def _optional_int(value):
    """Return an integer value when parsing succeeds."""
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

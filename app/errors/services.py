from sqlalchemy import or_

from app.extensions import db
from app.models import Department, ErrorEntry, Role


def visible_errors_query(user):
    query = ErrorEntry.query
    if user.role != Role.MASTER_ADMIN:
        query = query.filter(ErrorEntry.department_id == user.department_id)
    return query


def department_from_payload(data, user):
    department = None
    if data.get("department_id"):
        department = Department.query.get(data["department_id"])
    elif data.get("department"):
        department = Department.query.filter_by(name=data["department"]).first()
    elif user.department_id:
        department = user.department

    if not department:
        raise ValueError("Valid department_id or department is required")
    if user.role != Role.MASTER_ADMIN and department.id != user.department_id:
        raise PermissionError("Users may only write errors for their own department")
    return department


def create_error_entry(data, user):
    required = ["machine", "error_code", "title"]
    missing = [field for field in required if not data.get(field)]
    if missing:
        return None, {"error": f"Missing fields: {', '.join(missing)}"}, 400

    try:
        department = department_from_payload(data, user)
    except PermissionError as exc:
        return None, {"error": str(exc)}, 403
    except ValueError as exc:
        return None, {"error": str(exc)}, 400

    entry = ErrorEntry(
        machine=data["machine"],
        error_code=data["error_code"].upper(),
        title=data["title"],
        description=data.get("description", ""),
        possible_causes=data.get("possible_causes", ""),
        solution=data.get("solution", ""),
        department=department,
    )
    db.session.add(entry)
    db.session.commit()
    return entry, None, 201


def update_error_entry(entry, data, user):
    try:
        if "department_id" in data or "department" in data:
            entry.department = department_from_payload(data, user)
    except PermissionError as exc:
        return None, {"error": str(exc)}, 403
    except ValueError as exc:
        return None, {"error": str(exc)}, 400

    for field in ["machine", "title", "description", "possible_causes", "solution"]:
        if field in data:
            setattr(entry, field, data[field])
    if "error_code" in data:
        entry.error_code = data["error_code"].upper()
    db.session.commit()
    return entry, None, 200


def search_errors(query_text, user):
    if not query_text:
        return []
    needle = f"%{query_text}%"
    return (
        visible_errors_query(user)
        .filter(
            or_(
                ErrorEntry.error_code.ilike(needle),
                ErrorEntry.machine.ilike(needle),
                ErrorEntry.title.ilike(needle),
                ErrorEntry.description.ilike(needle),
            )
        )
        .order_by(ErrorEntry.error_code.asc())
        .limit(10)
        .all()
    )

from flask_jwt_extended import create_access_token
from sqlalchemy import or_

from app.extensions import db
from app.models import Department, Role, User


def parse_role(value):
    if not value:
        return Role.PRODUKTION
    try:
        return Role(value)
    except ValueError as exc:
        valid = ", ".join(role.value for role in Role)
        raise ValueError(f"Invalid role. Use one of: {valid}") from exc


def find_department(department_id=None, department_name=None):
    if department_id:
        return Department.query.get(department_id)
    if department_name:
        return Department.query.filter_by(name=department_name).first()
    return None


def register_user(data):
    required = ["username", "email", "password"]
    missing = [field for field in required if not data.get(field)]
    if missing:
        return None, {"error": f"Missing fields: {', '.join(missing)}"}, 400

    existing = User.query.filter(
        or_(User.username == data["username"], User.email == data["email"])
    ).first()
    if existing:
        return None, {"error": "Username or email already exists"}, 409

    department = find_department(data.get("department_id"), data.get("department"))
    role = parse_role(data.get("role"))
    if not department and role != Role.MASTER_ADMIN:
        return None, {"error": "department_id or department is required"}, 400

    user = User(
        username=data["username"],
        email=data["email"],
        role=role,
        department=department,
    )
    user.set_password(data["password"])
    db.session.add(user)
    db.session.commit()
    return user, None, 201


def authenticate(login, password):
    user = User.query.filter(
        or_(User.email == login, User.username == login)
    ).first()
    if not user or not user.check_password(password):
        return None
    if not user.is_active:
        return {"error": "User is locked"}
    token = create_access_token(identity=str(user.id))
    return {"access_token": token, "user": user.to_dict()}

from functools import wraps

from flask import jsonify
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

from app.models import Role, User


def current_user():
    user_id = get_jwt_identity()
    if not user_id:
        return None
    return User.query.get(int(user_id))


def roles_required(*roles):
    allowed = {role if isinstance(role, Role) else Role(role) for role in roles}

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            user = current_user()
            if not user or (not user.is_admin and user.role not in allowed):
                return jsonify({"error": "Forbidden"}), 403
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def same_department_or_admin(resource):
    user = current_user()
    return bool(user and (user.is_admin or resource.department_id == user.department_id))

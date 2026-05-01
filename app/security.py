from functools import wraps

from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

from app.extensions import db
from app.models import Role, User
from app.permissions import (
    get_employee_access_level,
    has_employee_access,
    has_permission,
)
from app.responses import error_response


def current_user():
    """Return the currently authenticated user, if any."""
    user_id = get_jwt_identity()
    if not user_id:
        return None
    return db.session.get(User, int(user_id))


def roles_required(*roles):
    """Require one of the provided roles or master administrator access."""
    allowed = {role if isinstance(role, Role) else Role(role) for role in roles}

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            user = current_user()
            if not user or (not user.is_admin and user.role not in allowed):
                return error_response("Forbidden", 403)
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def has_dashboard_permission(user, dashboard, action="view"):
    """Return whether a user can perform an action on a dashboard."""
    return has_permission(user, dashboard, action)


def dashboard_permission_required(dashboard, action="view"):
    """Require a dashboard permission for a protected route."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            user = current_user()
            if not has_dashboard_permission(user, dashboard, action):
                return error_response("Forbidden", 403)
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def employee_access_level(user):
    """Return the effective employee data access level for a user."""
    return get_employee_access_level(user)


def employee_access_required(required_level):
    """Require a minimum employee data access level for a protected route."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            user = current_user()
            if not has_employee_access(user, required_level):
                return error_response("Forbidden", 403)
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def same_department_or_admin(resource):
    """Return whether the current user can access a department resource."""
    user = current_user()
    return bool(user and (user.is_admin or resource.department_id == user.department_id))

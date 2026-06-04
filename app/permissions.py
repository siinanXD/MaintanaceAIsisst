"""Role and dashboard permission helpers."""

from app.extensions import db
from app.models import DashboardPermission, Role

DASHBOARD_KEYS = (
    "dashboard",
    "tasks",
    "errors",
    "employees",
    "shiftplans",
    "machines",
    "inventory",
    "documents",
    "admin_users",
    "admin_ai",
)

DASHBOARD_GROUPS = (
    {
        "key": "work",
        "label": "Arbeit",
        "dashboards": ("dashboard", "tasks", "errors"),
    },
    {
        "key": "resources",
        "label": "Ressourcen",
        "dashboards": ("employees", "machines", "inventory"),
    },
    {
        "key": "planning_documents",
        "label": "Planung & Dokumente",
        "dashboards": ("shiftplans", "documents"),
    },
    {
        "key": "administration",
        "label": "Administration",
        "dashboards": ("admin_users", "admin_ai"),
    },
)

DASHBOARD_LABELS = {
    "dashboard": "Dashboard",
    "tasks": "Tasks",
    "errors": "Fehlerliste",
    "employees": "Mitarbeiter",
    "shiftplans": "Schichtplan",
    "machines": "Maschinen",
    "inventory": "Lager",
    "documents": "Dokumente",
    "admin_users": "Users",
    "admin_ai": "KI-Administration",
}

EMPLOYEE_ACCESS_LEVELS = ("none", "basic", "shift", "confidential")

EMPLOYEE_ACCESS_RANK = {
    "none": 0,
    "basic": 1,
    "shift": 2,
    "confidential": 3,
}

EMPLOYEE_ACCESS_LABELS = {
    "none": "Keine Mitarbeiterdaten",
    "basic": "Basisdaten",
    "shift": "Schicht- und Qualifikationsdaten",
    "confidential": "Vertrauliche Personaldaten",
}

ROLE_DEFAULT_PERMISSIONS = {
    Role.MASTER_ADMIN: {
        "dashboard": (True, True),
        "tasks": (True, True),
        "errors": (True, True),
        "employees": (True, True),
        "shiftplans": (True, True),
        "machines": (True, True),
        "inventory": (True, True),
        "documents": (True, True),
        "admin_users": (True, True),
        "admin_ai": (True, True),
    },
    Role.IT: {
        "dashboard": (True, False),
        "tasks": (True, True),
        "errors": (True, True),
        "machines": (True, False),
    },
    Role.VERWALTUNG: {
        "dashboard": (True, False),
        "tasks": (True, True),
        "errors": (True, True),
        "inventory": (True, False),
        "documents": (True, False),
    },
    Role.INSTANDHALTUNG: {
        "dashboard": (True, False),
        "tasks": (True, True),
        "errors": (True, True),
        "machines": (True, False),
        "inventory": (True, False),
        "documents": (True, False),
    },
    Role.PRODUKTION: {
        "tasks": (True, True),
        "errors": (True, True),
    },
    Role.PERSONALABTEILUNG: {
        "dashboard": (True, False),
        "tasks": (True, True),
        "errors": (True, False),
        "employees": (True, True),
        "shiftplans": (True, False),
    },
}

ROLE_DEFAULT_EMPLOYEE_ACCESS = {
    Role.MASTER_ADMIN: "confidential",
    Role.PERSONALABTEILUNG: "confidential",
}


def validate_dashboard_key(dashboard):
    """Validate and return a known dashboard key."""
    if dashboard not in DASHBOARD_KEYS:
        valid = ", ".join(DASHBOARD_KEYS)
        raise ValueError(f"Invalid dashboard. Use one of: {valid}")
    return dashboard


def validate_employee_access_level(access_level):
    """Validate and return a known employee access level."""
    if access_level not in EMPLOYEE_ACCESS_LEVELS:
        valid = ", ".join(EMPLOYEE_ACCESS_LEVELS)
        raise ValueError(f"Invalid employee_access_level. Use one of: {valid}")
    return access_level


def default_permissions_for_role(role):
    """Return the dashboard defaults for a role."""
    return ROLE_DEFAULT_PERMISSIONS.get(role, {})


def default_employee_access_for_role(role):
    """Return the default employee access level for a role."""
    return ROLE_DEFAULT_EMPLOYEE_ACCESS.get(role, "none")


def permission_schema():
    """Return labels, groups and role defaults for the permission editor."""
    return {
        "dashboards": [
            {
                "key": dashboard,
                "label": DASHBOARD_LABELS[dashboard],
                "supports_employee_access": dashboard == "employees",
            }
            for dashboard in DASHBOARD_KEYS
        ],
        "groups": [
            {
                "key": group["key"],
                "label": group["label"],
                "dashboards": list(group["dashboards"]),
            }
            for group in DASHBOARD_GROUPS
        ],
        "employee_access_levels": [
            {
                "key": level,
                "label": EMPLOYEE_ACCESS_LABELS[level],
            }
            for level in EMPLOYEE_ACCESS_LEVELS
        ],
        "role_defaults": {
            role.value: {
                dashboard: {
                    "can_view": rights[0],
                    "can_write": rights[1],
                    "employee_access_level": (
                        default_employee_access_for_role(role)
                        if dashboard == "employees"
                        else "none"
                    ),
                }
                for dashboard, rights in defaults.items()
            }
            for role, defaults in ROLE_DEFAULT_PERMISSIONS.items()
        },
    }


def permission_by_dashboard(user):
    """Return the user's stored permissions indexed by dashboard key."""
    if not user:
        return {}
    return {permission.dashboard: permission for permission in user.dashboard_permissions}


def upsert_default_permissions(user):
    """Create missing default permissions for a user without overwriting edits."""
    existing = permission_by_dashboard(user)
    defaults = default_permissions_for_role(user.role)
    default_employee_level = default_employee_access_for_role(user.role)

    for dashboard, rights in defaults.items():
        if dashboard in existing:
            continue
        can_view, can_write = rights
        employee_level = default_employee_level if dashboard == "employees" else "none"
        db.session.add(
            DashboardPermission(
                user=user,
                dashboard=dashboard,
                can_view=can_view,
                can_write=can_write,
                employee_access_level=employee_level,
            )
        )


def ensure_all_user_default_permissions():
    """Create missing default permissions for every existing user."""
    from app.models import User

    for user in User.query.all():
        upsert_default_permissions(user)
    db.session.commit()


def serialize_permissions(user):
    """Serialize effective dashboard permissions for frontend and API responses."""
    if not user:
        return {}

    if user.is_admin:
        return {
            dashboard: {
                "can_view": True,
                "can_write": True,
                "employee_access_level": ("confidential" if dashboard == "employees" else "none"),
            }
            for dashboard in DASHBOARD_KEYS
        }

    permissions = {
        dashboard: {
            "can_view": False,
            "can_write": False,
            "employee_access_level": "none",
        }
        for dashboard in DASHBOARD_KEYS
    }
    for permission in user.dashboard_permissions:
        if permission.dashboard not in permissions:
            continue
        if permission.dashboard == "admin_users":
            continue
        permissions[permission.dashboard] = {
            "can_view": permission.can_view,
            "can_write": permission.can_write,
            "employee_access_level": permission.employee_access_level,
        }
    return permissions


def has_permission(user, dashboard, action="view"):
    """Return whether a user has the requested dashboard permission."""
    validate_dashboard_key(dashboard)
    if action not in ("view", "write"):
        raise ValueError("action must be view or write")
    if not user:
        return False
    if user.is_admin:
        return True
    if dashboard == "admin_users":
        return False

    permissions = serialize_permissions(user)
    permission = permissions.get(dashboard, {})
    if action == "write":
        return bool(permission.get("can_write"))
    return bool(permission.get("can_view"))


def get_employee_access_level(user):
    """Return the effective employee access level for a user."""
    if not user:
        return "none"
    if user.is_admin:
        return "confidential"
    permissions = serialize_permissions(user)
    employees = permissions.get("employees", {})
    if not employees.get("can_view"):
        return "none"
    level = employees.get("employee_access_level", "none")
    return level if level in EMPLOYEE_ACCESS_LEVELS else "none"


def has_employee_access(user, required_level):
    """Return whether a user has at least the required employee access level."""
    validate_employee_access_level(required_level)
    current_level = get_employee_access_level(user)
    return EMPLOYEE_ACCESS_RANK[current_level] >= EMPLOYEE_ACCESS_RANK[required_level]


def can_read_employee_context(user):
    """Return whether the user may read employee context through the assistant."""
    return has_permission(user, "employees", "view") and get_employee_access_level(user) != "none"


def replace_user_permissions(user, payload):
    """Replace dashboard permissions for a user from an admin payload."""
    permissions_payload = payload.get("permissions")
    if not isinstance(permissions_payload, dict):
        raise ValueError("permissions must be an object")

    existing = permission_by_dashboard(user)
    seen_dashboards = set()

    for dashboard, values in permissions_payload.items():
        validate_dashboard_key(dashboard)
        if not isinstance(values, dict):
            raise ValueError(f"permissions.{dashboard} must be an object")
        seen_dashboards.add(dashboard)
        access_level = validate_employee_access_level(values.get("employee_access_level", "none"))
        if dashboard != "employees":
            access_level = "none"
        if dashboard == "admin_users" and user.role != Role.MASTER_ADMIN:
            values = {
                **values,
                "can_view": False,
                "can_write": False,
            }

        permission = existing.get(dashboard)
        if not permission:
            permission = DashboardPermission(user=user, dashboard=dashboard)
            db.session.add(permission)

        permission.can_view = bool(values.get("can_view", False))
        permission.can_write = bool(values.get("can_write", False))
        permission.employee_access_level = access_level

    for dashboard, permission in existing.items():
        if dashboard not in seen_dashboards:
            db.session.delete(permission)

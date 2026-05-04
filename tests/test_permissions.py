import pytest

from app.extensions import db
from app.models import Role, User
from app.permissions import (
    get_employee_access_level,
    has_permission,
    serialize_permissions,
    validate_dashboard_key,
)


def test_master_admin_has_all_effective_permissions(app, make_user):
    """Verify master admins receive full effective permissions without manual grants."""
    user_data = make_user(
        username="admin_permissions",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )

    with app.app_context():
        user = db.session.get(User, user_data["id"])
        permissions = serialize_permissions(user)

    assert all(permission["can_view"] for permission in permissions.values())
    assert all(permission["can_write"] for permission in permissions.values())
    assert permissions["employees"]["employee_access_level"] == "confidential"


def test_invalid_permission_inputs_raise_clear_errors(app, make_user):
    """Verify permission helpers reject unknown dashboards and actions."""
    user_data = make_user(username="permission_user")

    with app.app_context():
        user = db.session.get(User, user_data["id"])
        with pytest.raises(ValueError, match="Invalid dashboard"):
            validate_dashboard_key("unknown")
        with pytest.raises(ValueError, match="action must be view or write"):
            has_permission(user, "tasks", "delete")


def test_non_admin_cannot_receive_effective_admin_user_permission(
    client,
    make_user,
    auth_headers,
):
    """Verify admin_users permissions stay unavailable for non-admin accounts."""
    admin = make_user(
        username="admin_permissions_api",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    user = make_user(username="managed_user", role=Role.INSTANDHALTUNG)
    headers = auth_headers(admin["username"])

    response = client.put(
        f"/api/v1/admin/users/{user['id']}/permissions",
        headers=headers,
        json={
            "permissions": {
                "admin_users": {"can_view": True, "can_write": True},
                "employees": {
                    "can_view": True,
                    "can_write": False,
                    "employee_access_level": "basic",
                },
            }
        },
    )
    permissions_response = client.get(
        f"/api/v1/admin/users/{user['id']}/permissions",
        headers=headers,
    )

    permissions = permissions_response.get_json()
    assert response.status_code == 200
    assert permissions["admin_users"]["can_view"] is False
    assert permissions["admin_users"]["can_write"] is False
    assert permissions["employees"]["employee_access_level"] == "basic"


def test_update_user_permissions_validates_payload(
    client,
    make_user,
    auth_headers,
):
    """Verify the admin permission endpoint returns 400 for malformed payloads."""
    admin = make_user(
        username="admin_bad_permissions",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    user = make_user(username="target_bad_permissions")
    headers = auth_headers(admin["username"])

    missing_response = client.put(
        f"/api/v1/admin/users/{user['id']}/permissions",
        headers=headers,
        json={},
    )
    dashboard_response = client.put(
        f"/api/v1/admin/users/{user['id']}/permissions",
        headers=headers,
        json={"permissions": {"unknown": {"can_view": True}}},
    )
    level_response = client.put(
        f"/api/v1/admin/users/{user['id']}/permissions",
        headers=headers,
        json={
            "permissions": {
                "employees": {
                    "can_view": True,
                    "employee_access_level": "secret",
                }
            }
        },
    )

    assert missing_response.status_code == 400
    assert dashboard_response.status_code == 400
    assert level_response.status_code == 400


def test_employee_access_levels_filter_employee_payload(
    app,
    client,
    make_user,
    make_employee,
    auth_headers,
    set_dashboard_permission,
):
    """Verify employee API responses respect configured data access levels."""
    user = make_user(username="employee_basic", role=Role.INSTANDHALTUNG)
    make_employee(name="Anna Beispiel", salary_group="E9")
    set_dashboard_permission(
        user["username"],
        "employees",
        can_view=True,
        can_write=False,
        employee_access_level="basic",
    )

    response = client.get("/api/v1/employees", headers=auth_headers(user["username"]))

    with app.app_context():
        stored_user = db.session.get(User, user["id"])
        access_level = get_employee_access_level(stored_user)

    payload = response.get_json()["data"][0]
    assert response.status_code == 200
    assert access_level == "basic"
    assert payload["name"] == "Anna Beispiel"
    assert "salary_group" not in payload
    assert "birth_date" not in payload

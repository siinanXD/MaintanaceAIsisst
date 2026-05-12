"""Tests for administration and department management endpoints."""

from app.extensions import db
from app.models import Department, Role, User


def test_admin_user_lifecycle_and_filters(client, make_user, make_employee, auth_headers):
    """Verify master admins can create, filter, update, lock, and delete users."""
    admin = make_user(
        username="admin_user_lifecycle",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    employee_id = make_employee(personnel_number="P-ADMIN-1", name="Admin Link")
    headers = auth_headers(admin["username"])

    create_response = client.post(
        "/api/v1/admin/users",
        headers=headers,
        json={
            "username": "managed_operator",
            "email": "managed_operator@example.test",
            "password": "password",
            "role": Role.PRODUKTION.value,
            "department": "Produktion",
            "employee_id": employee_id,
            "is_active": "false",
        },
    )

    created_user = create_response.get_json()
    list_response = client.get(
        "/api/v1/admin/users?q=managed&role=produktion&status=inactive",
        headers=headers,
    )
    update_response = client.put(
        f"/api/v1/admin/users/{created_user['id']}",
        headers=headers,
        json={
            "username": "managed_operator_renamed",
            "email": "managed_operator_renamed@example.test",
            "is_active": True,
        },
    )
    lock_response = client.post(
        f"/api/v1/admin/users/{created_user['id']}/lock",
        headers=headers,
    )
    unlock_response = client.post(
        f"/api/v1/admin/users/{created_user['id']}/unlock",
        headers=headers,
    )
    password_response = client.post(
        f"/api/v1/admin/users/{created_user['id']}/reset-password",
        headers=headers,
        json={"password": "new-password"},
    )
    delete_response = client.delete(
        f"/api/v1/admin/users/{created_user['id']}",
        headers=headers,
    )

    assert create_response.status_code == 201
    assert created_user["is_active"] is False
    assert created_user["employee_id"] == employee_id
    assert list_response.status_code == 200
    assert [user["username"] for user in list_response.get_json()] == ["managed_operator"]
    assert update_response.status_code == 200
    assert update_response.get_json()["username"] == "managed_operator_renamed"
    assert update_response.get_json()["is_active"] is True
    assert lock_response.status_code == 200
    assert lock_response.get_json()["is_active"] is False
    assert unlock_response.status_code == 200
    assert unlock_response.get_json()["is_active"] is True
    assert password_response.status_code == 200
    assert delete_response.status_code == 204

    with client.application.app_context():
        assert db.session.get(User, created_user["id"]) is None


def test_admin_user_validation_rejects_conflicts_and_bad_payloads(
    client,
    make_user,
    auth_headers,
):
    """Verify admin user endpoints reject invalid data without database errors."""
    admin = make_user(
        username="admin_validation",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    first_user = make_user(username="managed_conflict")
    second_user = make_user(username="managed_second")
    headers = auth_headers(admin["username"])

    duplicate_create_response = client.post(
        "/api/v1/admin/users",
        headers=headers,
        json={
            "username": first_user["username"],
            "email": "new-conflict@example.test",
            "password": "password",
            "role": Role.PRODUKTION.value,
            "department": "Produktion",
        },
    )
    duplicate_update_response = client.put(
        f"/api/v1/admin/users/{second_user['id']}",
        headers=headers,
        json={"email": first_user["email"]},
    )
    invalid_role_response = client.get(
        "/api/v1/admin/users?role=unknown",
        headers=headers,
    )
    invalid_employee_response = client.post(
        "/api/v1/admin/users",
        headers=headers,
        json={
            "username": "bad_employee",
            "email": "bad_employee@example.test",
            "password": "password",
            "role": Role.PRODUKTION.value,
            "department": "Produktion",
            "employee_id": "abc",
        },
    )
    invalid_active_response = client.put(
        f"/api/v1/admin/users/{second_user['id']}",
        headers=headers,
        json={"is_active": "not-a-bool"},
    )
    missing_department_response = client.put(
        f"/api/v1/admin/users/{admin['id']}",
        headers=headers,
        json={"role": Role.PRODUKTION.value},
    )

    assert duplicate_create_response.status_code == 409
    assert duplicate_update_response.status_code == 409
    assert invalid_role_response.status_code == 400
    assert invalid_employee_response.status_code == 400
    assert invalid_active_response.status_code == 400
    assert missing_department_response.status_code == 400


def test_department_endpoints_create_defaults_and_validate_payloads(
    client,
    make_user,
    auth_headers,
):
    """Verify department listing, creation, duplicate validation, and permissions."""
    admin = make_user(
        username="department_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    user = make_user(username="department_user")
    admin_headers = auth_headers(admin["username"])
    user_headers = auth_headers(user["username"])

    list_response = client.get("/api/v1/departments", headers=user_headers)
    forbidden_response = client.post(
        "/api/v1/departments",
        headers=user_headers,
        json={"name": "Qualitaet"},
    )
    missing_response = client.post(
        "/api/v1/departments",
        headers=admin_headers,
        json={},
    )
    create_response = client.post(
        "/api/v1/departments",
        headers=admin_headers,
        json={"name": "Qualitaet"},
    )
    duplicate_response = client.post(
        "/api/v1/departments",
        headers=admin_headers,
        json={"name": "Qualitaet"},
    )

    department_names = [department["name"] for department in list_response.get_json()]

    assert list_response.status_code == 200
    assert "Produktion" in department_names
    assert forbidden_response.status_code == 403
    assert missing_response.status_code == 400
    assert create_response.status_code == 201
    assert create_response.get_json()["name"] == "Qualitaet"
    assert duplicate_response.status_code == 409

    with client.application.app_context():
        assert Department.query.filter_by(name="Qualitaet").count() == 1

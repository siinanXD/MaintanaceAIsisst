from app.models import Role


def test_employee_create_rejects_missing_duplicate_and_invalid_values(
    client,
    make_user,
    auth_headers,
):
    """Verify employee creation validates required, duplicate and typed fields."""
    admin = make_user(
        username="employee_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    headers = auth_headers(admin["username"])

    missing_response = client.post("/api/employees", headers=headers, json={})
    create_response = client.post(
        "/api/employees",
        headers=headers,
        json={
            "personnel_number": "P-200",
            "name": "Lisa Produktion",
            "birth_date": "1991-02-03",
            "team": 2,
            "department": "Produktion",
        },
    )
    duplicate_response = client.post(
        "/api/employees",
        headers=headers,
        json={"personnel_number": "P-200", "name": "Lisa Produktion"},
    )
    invalid_response = client.post(
        "/api/employees",
        headers=headers,
        json={
            "personnel_number": "P-201",
            "name": "Ungueltig",
            "birth_date": "03-02-1991",
        },
    )

    assert missing_response.status_code == 400
    assert create_response.status_code == 201
    assert duplicate_response.status_code == 409
    assert invalid_response.status_code == 400


def test_employee_shift_access_includes_shift_but_not_confidential_fields(
    client,
    make_user,
    make_employee,
    auth_headers,
    set_dashboard_permission,
):
    """Verify shift-level employee access excludes confidential fields."""
    user = make_user(
        username="employee_shift_user",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )
    make_employee(name="Shift Person", salary_group="E10")
    set_dashboard_permission(
        user["username"],
        "employees",
        can_view=True,
        can_write=False,
        employee_access_level="shift",
    )

    response = client.get("/api/employees", headers=auth_headers(user["username"]))

    payload = response.get_json()[0]
    assert response.status_code == 200
    assert payload["qualifications"] == "CNC"
    assert "salary_group" not in payload
    assert "documents" not in payload


def test_employee_write_requires_confidential_access(
    client,
    make_user,
    auth_headers,
    set_dashboard_permission,
):
    """Verify employee writes require both write permission and confidential access."""
    user = make_user(
        username="employee_write_guard",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )
    set_dashboard_permission(
        user["username"],
        "employees",
        can_view=True,
        can_write=True,
        employee_access_level="shift",
    )

    response = client.post(
        "/api/employees",
        headers=auth_headers(user["username"]),
        json={"personnel_number": "P-300", "name": "Nicht erlaubt"},
    )

    assert response.status_code == 403


def test_shiftplan_generate_uses_local_fallback(
    client,
    make_user,
    make_employee,
    make_machine,
    auth_headers,
):
    """Verify shift plan generation works without OpenAI via local fallback."""
    admin = make_user(
        username="shiftplan_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    make_employee(personnel_number="P-401", name="Prod One", department="Produktion")
    make_employee(personnel_number="P-402", name="Prod Two", department="Produktion")
    make_machine(name="Schicht Anlage", required_employees=1)

    response = client.post(
        "/api/shiftplans/generate",
        headers=auth_headers(admin["username"]),
        json={
            "title": "KW Test",
            "start_date": "2026-05-01",
            "days": 2,
            "rhythm": "2-Schicht",
        },
    )

    payload = response.get_json()
    assert response.status_code == 201
    assert payload["title"] == "KW Test"
    assert "Lokaler Fallback" in payload["notes"]
    assert len(payload["entries"]) == 4


def test_shiftplan_generate_rejects_when_no_production_employees(
    client,
    make_user,
    auth_headers,
):
    """Verify shift plan generation reports missing production employees."""
    admin = make_user(
        username="shiftplan_empty_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )

    response = client.post(
        "/api/shiftplans/generate",
        headers=auth_headers(admin["username"]),
        json={"start_date": "2026-05-01"},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Keine Produktionsmitarbeiter gefunden"

from app.extensions import db
from app.models import Role, User


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


def test_employee_update_rejects_invalid_birth_date_or_team(
    client,
    make_user,
    make_employee,
    auth_headers,
):
    """Verify employee updates return 400 for invalid date or team values."""
    admin = make_user(
        username="employee_update_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    employee_id = make_employee(personnel_number="P-350", name="Update Person")
    headers = auth_headers(admin["username"])

    invalid_date_response = client.put(
        f"/api/employees/{employee_id}",
        headers=headers,
        json={"birth_date": "01-01-1990"},
    )
    invalid_team_response = client.put(
        f"/api/employees/{employee_id}",
        headers=headers,
        json={"team": "team-a"},
    )

    assert invalid_date_response.status_code == 400
    assert invalid_team_response.status_code == 400


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


def test_shiftplan_generate_rejects_invalid_date_and_days(
    client,
    make_user,
    make_employee,
    auth_headers,
):
    """Verify shift plan generation validates date and duration inputs."""
    admin = make_user(
        username="shiftplan_validation_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    make_employee(personnel_number="P-450", name="Prod Valid", department="Produktion")
    headers = auth_headers(admin["username"])

    invalid_date_response = client.post(
        "/api/shiftplans/generate",
        headers=headers,
        json={"start_date": "01.05.2026"},
    )
    invalid_days_response = client.post(
        "/api/shiftplans/generate",
        headers=headers,
        json={"start_date": "2026-05-01", "days": "seven"},
    )

    assert invalid_date_response.status_code == 400
    assert invalid_days_response.status_code == 400


def test_shiftplan_generate_returns_warnings_and_coverage(
    client,
    make_user,
    make_employee,
    make_machine,
    auth_headers,
):
    """Verify shift planning reports conflict warnings and coverage details."""
    admin = make_user(
        username="shiftplan_warning_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    make_employee(
        personnel_number="P-470",
        name="Prod Warn",
        department="Produktion",
        qualifications="",
        favorite_machine="",
    )
    make_machine(name="Warn Anlage 1", required_employees=1)
    make_machine(name="Warn Anlage 2", required_employees=1)

    response = client.post(
        "/api/shiftplans/generate",
        headers=auth_headers(admin["username"]),
        json={
            "title": "Warnplan",
            "start_date": "2026-05-01",
            "days": 1,
            "rhythm": "2-Schicht",
        },
    )

    payload = response.get_json()
    warning_types = {warning["type"] for warning in payload["warnings"]}
    assert response.status_code == 201
    assert "duplicate_assignment" in warning_types
    assert "qualification" in warning_types
    assert payload["coverage_summary"]["assigned_slots"] >= 1


def test_admin_user_can_link_employee(
    client,
    app,
    make_user,
    make_employee,
    auth_headers,
):
    """Verify user payloads expose the linked employee for cockpit calendars."""
    admin = make_user(
        username="link_employee_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    user = make_user(
        username="link_employee_user",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )
    employee_id = make_employee(
        personnel_number="P-510",
        name="Kalender Person",
        department="Produktion",
    )

    response = client.put(
        f"/api/admin/users/{user['id']}",
        headers=auth_headers(admin["username"]),
        json={"employee_id": employee_id},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["employee_id"] == employee_id
    assert payload["employee"]["name"] == "Kalender Person"

    with app.app_context():
        stored_user = db.session.get(User, user["id"])
        assert stored_user.employee_id == employee_id


def test_shiftplan_generate_saves_vacation_and_skips_worker(
    client,
    make_user,
    make_employee,
    make_machine,
    auth_headers,
):
    """Verify vacation payloads are saved and not planned as work shifts."""
    admin = make_user(
        username="shiftplan_vacation_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    employee_id = make_employee(
        personnel_number="P-520",
        name="Vacation Person",
        department="Produktion",
    )
    make_machine(name="Vacation Anlage", required_employees=1)

    response = client.post(
        "/api/shiftplans/generate",
        headers=auth_headers(admin["username"]),
        json={
            "title": "Urlaubsplan",
            "start_date": "2026-05-01",
            "days": 2,
            "rhythm": "2-Schicht",
            "vacations": [
                {
                    "employee_id": employee_id,
                    "date": "2026-05-01",
                    "notes": "Erholungsurlaub",
                }
            ],
        },
    )

    payload = response.get_json()
    vacation_entries = [
        entry
        for entry in payload["entries"]
        if entry["work_date"] == "2026-05-01"
    ]
    assert response.status_code == 201
    assert [entry["shift"] for entry in vacation_entries] == ["Urlaub"]
    assert vacation_entries[0]["notes"] == "Erholungsurlaub"


def test_shiftplan_calendar_returns_own_calendar_and_free_days(
    client,
    app,
    make_user,
    make_employee,
    make_machine,
    auth_headers,
):
    """Verify cockpit calendar returns linked employee entries and free days."""
    admin = make_user(
        username="calendar_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    user = make_user(
        username="calendar_user",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )
    employee_id = make_employee(
        personnel_number="P-530",
        name="Calendar Person",
        department="Produktion",
    )
    make_machine(name="Calendar Anlage", required_employees=1)
    with app.app_context():
        stored_user = db.session.get(User, user["id"])
        stored_user.employee_id = employee_id
        db.session.commit()

    client.post(
        "/api/shiftplans/generate",
        headers=auth_headers(admin["username"]),
        json={
            "title": "Kalenderplan",
            "start_date": "2026-05-01",
            "days": 1,
            "rhythm": "2-Schicht",
            "vacations": [
                {
                    "employee_id": employee_id,
                    "date": "2026-05-01",
                    "notes": "Urlaub",
                }
            ],
        },
    )

    response = client.get(
        "/api/shiftplans/calendar?start_date=2026-05-01&days=2",
        headers=auth_headers(user["username"]),
    )

    payload = response.get_json()
    shifts = [entry["shift"] for entry in payload["entries"]]
    assert response.status_code == 200
    assert payload["employee"]["name"] == "Calendar Person"
    assert shifts == ["Urlaub", "Frei"]
    assert payload["entries"][0]["color"] == "amber"
    assert payload["entries"][1]["color"] == "violet"


def test_shiftplan_calendar_admin_can_filter_employee(
    client,
    make_user,
    make_employee,
    auth_headers,
):
    """Verify admins can request a selected employee calendar."""
    admin = make_user(
        username="calendar_filter_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    employee_id = make_employee(
        personnel_number="P-540",
        name="Filter Person",
        department="Produktion",
    )

    response = client.get(
        f"/api/shiftplans/calendar?employee_id={employee_id}&start_date=2026-05-01&days=1",
        headers=auth_headers(admin["username"]),
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["employee"]["name"] == "Filter Person"
    assert payload["entries"][0]["shift"] == "Frei"


def test_shiftplan_page_script_renders_warnings(client):
    """Verify shift plan UI has warning rendering code."""
    response = client.get("/static/app.js")
    script = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "plan.warnings" in script
    assert "Warnungen" in script
    assert "data-shiftplan-calendar" in client.get("/shiftplans").get_data(as_text=True)

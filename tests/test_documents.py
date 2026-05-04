"""Tests for GET /api/documents filters and machine_id auto-resolution."""

from datetime import datetime, timedelta, timezone

from app.extensions import db
from app.models import ErrorEntry, Employee, GeneratedDocument, Role


# ---------------------------------------------------------------------------
# GET /api/documents — list + filters
# ---------------------------------------------------------------------------


def test_documents_list_returns_empty_array_for_new_user(client, make_user, auth_headers):
    """GET /api/documents returns 200 with an empty list when no documents exist."""
    user = make_user(username="doc_list_empty_user", role=Role.INSTANDHALTUNG, department_name="Instandhaltung")
    response = client.get("/api/v1/documents", headers=auth_headers(user["username"]))
    assert response.status_code == 200
    assert response.get_json() == []


def test_documents_list_returns_own_document(
    client, app, make_user, make_task, make_document, auth_headers
):
    """GET /api/documents returns documents created by the authenticated user."""
    user = make_user(username="doc_list_owner", role=Role.INSTANDHALTUNG, department_name="Instandhaltung")
    task_id = make_task("Anlage prüfen", creator_username=user["username"], department_name="Instandhaltung")
    make_document(task_id=task_id, created_by=user["id"], department="Instandhaltung")

    response = client.get("/api/v1/documents", headers=auth_headers(user["username"]))
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["task_id"] == task_id


def test_documents_filter_by_task_id(
    client, app, make_user, make_task, make_document, auth_headers
):
    """GET /api/documents?task_id= returns only documents for that task."""
    user = make_user(username="doc_filter_task", role=Role.INSTANDHALTUNG, department_name="Instandhaltung")
    task_a = make_task("Task A", creator_username=user["username"], department_name="Instandhaltung")
    task_b = make_task("Task B", creator_username=user["username"], department_name="Instandhaltung")
    make_document(task_id=task_a, created_by=user["id"], department="Instandhaltung", relative_path=f"2026/05/task_{task_a}/report.html")
    make_document(task_id=task_b, created_by=user["id"], department="Instandhaltung", relative_path=f"2026/05/task_{task_b}/report.html")

    response = client.get(f"/api/v1/documents?task_id={task_a}", headers=auth_headers(user["username"]))
    assert response.status_code == 200
    data = response.get_json()
    assert all(doc["task_id"] == task_a for doc in data)
    assert len(data) == 1


def test_documents_filter_by_department(
    client, app, make_user, make_task, make_document, auth_headers
):
    """GET /api/documents?department= filters by department substring."""
    user = make_user(username="doc_filter_dept", role=Role.MASTER_ADMIN, department_name="Produktion")
    task_id = make_task("Aufgabe X", creator_username=user["username"], department_name="Produktion")
    make_document(
        task_id=task_id,
        created_by=user["id"],
        department="Instandhaltung",
        relative_path="2026/05/task_x/report.html",
    )
    make_document(
        task_id=task_id,
        created_by=user["id"],
        department="Produktion",
        relative_path="2026/05/task_y/report.html",
    )

    response = client.get("/api/v1/documents?department=Instand", headers=auth_headers(user["username"]))
    assert response.status_code == 200
    data = response.get_json()
    assert all("Instandhaltung" in doc["department"] for doc in data)
    assert len(data) == 1


def test_documents_filter_by_machine(
    client, app, make_user, make_task, make_document, auth_headers
):
    """GET /api/documents?machine= filters by machine substring."""
    user = make_user(username="doc_filter_machine", role=Role.INSTANDHALTUNG, department_name="Instandhaltung")
    task_id = make_task("Aufgabe M", creator_username=user["username"], department_name="Instandhaltung")
    make_document(
        task_id=task_id,
        created_by=user["id"],
        machine="Anlage 1",
        department="Instandhaltung",
        relative_path="2026/05/task_m1/report.html",
    )
    make_document(
        task_id=task_id,
        created_by=user["id"],
        machine="Presse 5",
        department="Instandhaltung",
        relative_path="2026/05/task_m2/report.html",
    )

    response = client.get("/api/v1/documents?machine=Anlage", headers=auth_headers(user["username"]))
    assert response.status_code == 200
    data = response.get_json()
    assert all("Anlage" in doc["machine"] for doc in data)
    assert len(data) == 1


def test_documents_filter_date_from_excludes_older(
    client, app, make_user, make_task, auth_headers
):
    """GET /api/documents?date_from= excludes documents created before that date."""
    user = make_user(username="doc_filter_date_from", role=Role.INSTANDHALTUNG, department_name="Instandhaltung")
    task_id = make_task("Aufgabe D", creator_username=user["username"], department_name="Instandhaltung")

    old_date = datetime.now(timezone.utc) - timedelta(days=30)
    with app.app_context():
        old_doc = GeneratedDocument(
            task_id=task_id,
            document_type="maintenance_report",
            title="Alt",
            relative_path="2026/04/old/report.html",
            department="Instandhaltung",
            machine="Anlage 1",
            created_by=user["id"],
            created_at=old_date,
        )
        db.session.add(old_doc)
        db.session.commit()

    today_str = datetime.now(timezone.utc).date().isoformat()
    response = client.get(
        f"/api/v1/documents?date_from={today_str}",
        headers=auth_headers(user["username"]),
    )
    assert response.status_code == 200
    assert response.get_json() == []


def test_documents_filter_date_from_invalid_format(client, make_user, auth_headers):
    """GET /api/documents?date_from=not-a-date returns 400."""
    user = make_user(username="doc_filter_bad_date", role=Role.INSTANDHALTUNG, department_name="Instandhaltung")
    response = client.get("/api/v1/documents?date_from=not-a-date", headers=auth_headers(user["username"]))
    assert response.status_code == 400


def test_documents_filter_date_to_invalid_format(client, make_user, auth_headers):
    """GET /api/documents?date_to=garbage returns 400."""
    user = make_user(username="doc_filter_bad_date_to", role=Role.INSTANDHALTUNG, department_name="Instandhaltung")
    response = client.get("/api/v1/documents?date_to=garbage", headers=auth_headers(user["username"]))
    assert response.status_code == 400


def test_documents_requires_auth(client):
    """GET /api/documents without a token returns 401."""
    response = client.get("/api/v1/documents")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# machine_id auto-resolution — ErrorEntry
# ---------------------------------------------------------------------------


def test_error_entry_creation_resolves_machine_id(
    client, app, make_user, make_machine, auth_headers
):
    """POST /api/errors sets machine_id when the machine name matches a known machine."""
    user = make_user(username="err_machine_user", role=Role.INSTANDHALTUNG, department_name="Instandhaltung")
    machine_id = make_machine(name="Testanlage Alpha")

    response = client.post(
        "/api/v1/errors",
        headers=auth_headers(user["username"]),
        json={
            "machine": "Testanlage Alpha",
            "error_code": "E-999",
            "title": "Sensor defekt",
            "department": "Instandhaltung",
        },
    )
    assert response.status_code == 201
    payload = response.get_json()
    assert payload["machine_id"] == machine_id


def test_error_entry_creation_leaves_machine_id_null_for_unknown_machine(
    client, make_user, auth_headers
):
    """POST /api/errors sets machine_id=null when the machine name is unknown."""
    user = make_user(username="err_no_machine_user", role=Role.INSTANDHALTUNG, department_name="Instandhaltung")

    response = client.post(
        "/api/v1/errors",
        headers=auth_headers(user["username"]),
        json={
            "machine": "Unbekannte Maschine XYZ",
            "error_code": "E-000",
            "title": "Kein Treffer",
            "department": "Instandhaltung",
        },
    )
    assert response.status_code == 201
    assert response.get_json()["machine_id"] is None


def test_error_entry_update_resolves_machine_id(
    client, app, make_user, make_machine, make_error_entry, auth_headers
):
    """PUT /api/errors/<id> updates machine_id when machine name is changed."""
    user = make_user(username="err_update_machine", role=Role.INSTANDHALTUNG, department_name="Instandhaltung")
    machine_id = make_machine(name="Fräse Beta")
    entry_id = make_error_entry(
        machine="Alte Anlage",
        error_code="E-100",
        title="Vibration",
        department_name="Instandhaltung",
    )

    response = client.put(
        f"/api/v1/errors/{entry_id}",
        headers=auth_headers(user["username"]),
        json={"machine": "Fräse Beta"},
    )
    assert response.status_code == 200
    assert response.get_json()["machine_id"] == machine_id


# ---------------------------------------------------------------------------
# favorite_machine_id auto-resolution — Employee
# ---------------------------------------------------------------------------


def test_employee_creation_resolves_favorite_machine_id(
    client, app, make_user, make_machine, auth_headers
):
    """POST /api/employees sets favorite_machine_id when the name matches a machine."""
    admin = make_user(username="emp_machine_admin", role=Role.MASTER_ADMIN, department_name="Produktion")
    machine_id = make_machine(name="Lieblingsanlage Z")

    response = client.post(
        "/api/v1/employees",
        headers=auth_headers(admin["username"]),
        json={
            "personnel_number": "P-7001",
            "name": "Greta Tester",
            "birth_date": "1985-03-15",
            "city": "München",
            "street": "Bahnhofstr. 1",
            "postal_code": "80333",
            "department": "Produktion",
            "shift_model": "3-Schicht",
            "current_shift": "Frueh",
            "team": 2,
            "salary_group": "E4",
            "qualifications": "Schweißen",
            "favorite_machine": "Lieblingsanlage Z",
        },
    )
    assert response.status_code == 201
    payload = response.get_json()
    assert payload.get("favorite_machine_id") == machine_id


def test_employee_creation_leaves_favorite_machine_id_null_for_unknown_name(
    client, make_user, auth_headers
):
    """POST /api/employees sets favorite_machine_id=null for an unknown machine name."""
    admin = make_user(username="emp_no_machine_admin", role=Role.MASTER_ADMIN, department_name="Produktion")

    response = client.post(
        "/api/v1/employees",
        headers=auth_headers(admin["username"]),
        json={
            "personnel_number": "P-7002",
            "name": "Karl Niemand",
            "birth_date": "1990-07-20",
            "city": "Hamburg",
            "street": "Hauptstr. 5",
            "postal_code": "20095",
            "department": "Produktion",
            "shift_model": "2-Schicht",
            "current_shift": "Spaet",
            "team": 1,
            "salary_group": "E2",
            "qualifications": "Gabelstapler",
            "favorite_machine": "Nicht Vorhandene Anlage",
        },
    )
    assert response.status_code == 201
    assert response.get_json().get("favorite_machine_id") is None

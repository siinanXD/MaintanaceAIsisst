from app.models import Role


def test_error_entry_create_search_update_and_delete(client, make_user, auth_headers):
    """Verify error catalog CRUD and search behavior."""
    user = make_user(
        username="error_owner",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )
    headers = auth_headers(user["username"])

    create_response = client.post(
        "/api/errors",
        headers=headers,
        json={
            "machine": "Maschine 3",
            "error_code": "e104",
            "title": "Sensor erkennt Produkt nicht",
            "department": "Instandhaltung",
            "solution": "Sensor reinigen",
        },
    )
    entry_id = create_response.get_json()["id"]
    search_response = client.get("/api/errors/search?query=E104", headers=headers)
    update_response = client.put(
        f"/api/errors/{entry_id}",
        headers=headers,
        json={"solution": "Sensor reinigen und Abstand pruefen"},
    )
    delete_response = client.delete(f"/api/errors/{entry_id}", headers=headers)

    assert create_response.status_code == 201
    assert create_response.get_json()["error_code"] == "E104"
    assert search_response.status_code == 200
    assert len(search_response.get_json()) == 1
    assert update_response.status_code == 200
    assert "Abstand" in update_response.get_json()["solution"]
    assert delete_response.status_code == 204


def test_error_entry_validates_required_fields(client, make_user, auth_headers):
    """Verify missing error entry fields return a client error."""
    user = make_user(username="error_validation")

    response = client.post(
        "/api/errors",
        headers=auth_headers(user["username"]),
        json={"machine": "Maschine 1"},
    )

    assert response.status_code == 400
    assert "Missing fields" in response.get_json()["error"]


def test_error_entry_rejects_other_department_writes(
    client,
    make_user,
    auth_headers,
):
    """Verify non-admin users cannot create error entries for other departments."""
    user = make_user(
        username="error_department_guard",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )

    response = client.post(
        "/api/errors",
        headers=auth_headers(user["username"]),
        json={
            "machine": "Maschine 3",
            "error_code": "E500",
            "title": "Fremder Fehler",
            "department": "Instandhaltung",
        },
    )

    assert response.status_code == 403


def test_error_detail_is_forbidden_across_departments(
    client,
    make_user,
    make_error_entry,
    auth_headers,
):
    """Verify users cannot read error entries from another department."""
    requester = make_user(
        username="error_requester",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )
    entry_id = make_error_entry(
        "Maschine 9",
        "E900",
        "Fremder Fehler",
        department_name="Instandhaltung",
    )

    response = client.get(
        f"/api/errors/{entry_id}",
        headers=auth_headers(requester["username"]),
    )

    assert response.status_code == 403


def test_error_analysis_validates_input_and_uses_mock_fallback(
    client,
    make_user,
    auth_headers,
):
    """Verify AI error analysis handles empty and valid descriptions deterministically."""
    user = make_user(
        username="error_analysis",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )
    headers = auth_headers(user["username"])

    empty_response = client.post("/api/errors/analyze", headers=headers, json={})
    valid_response = client.post(
        "/api/errors/analyze",
        headers=headers,
        json={"description": "Sensor meldet sporadisch kein Signal an Maschine 3"},
    )

    assert empty_response.status_code == 400
    assert valid_response.status_code == 200
    assert valid_response.get_json()["department"] == "Instandhaltung"
    assert "Sensor" in valid_response.get_json()["possible_causes"]

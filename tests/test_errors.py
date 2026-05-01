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
    assert response.get_json()["error"] == "missing_fields_error_code_title"
    assert "Missing fields" in response.get_json()["message"]


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


def test_similar_errors_respects_department_and_sorts_matches(
    client,
    make_user,
    make_error_entry,
    auth_headers,
):
    """Verify similar error suggestions are visible and relevance-sorted."""
    user = make_user(
        username="similar_error_user",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )
    make_error_entry(
        "Anlage 4",
        "E104",
        "Sensor erkennt Produkt nicht",
        department_name="Instandhaltung",
        description="Sensor Signal fehlt sporadisch",
        solution="Sensor reinigen",
    )
    make_error_entry(
        "Anlage 9",
        "E900",
        "Hydraulikdruck niedrig",
        department_name="Instandhaltung",
        description="Druck faellt ab",
    )
    make_error_entry(
        "Anlage 4",
        "E777",
        "Fremder Sensorfehler",
        department_name="Produktion",
    )

    response = client.post(
        "/api/errors/similar",
        headers=auth_headers(user["username"]),
        json={"text": "Sensor Signal an Anlage 4 fehlt", "machine": "Anlage 4"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["results"][0]["entry"]["error_code"] == "E104"
    assert all(result["entry"]["department"]["name"] == "Instandhaltung" for result in payload["results"])


def test_similar_errors_rejects_empty_and_invalid_limit(client, make_user, auth_headers):
    """Verify similar error suggestions validate request data."""
    user = make_user(username="similar_error_validation")
    headers = auth_headers(user["username"])

    empty_response = client.post("/api/errors/similar", headers=headers, json={})
    invalid_limit = client.post(
        "/api/errors/similar",
        headers=headers,
        json={"text": "Sensor", "limit": 0},
    )

    assert empty_response.status_code == 400
    assert invalid_limit.status_code == 400


def test_errors_page_contains_similar_errors_ui(client):
    """Verify the errors page contains similar-error UI hooks."""
    response = client.get("/errors")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'data-similar-errors-panel' in html
    assert 'data-similar-errors-list' in html

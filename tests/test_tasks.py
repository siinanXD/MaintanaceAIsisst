from datetime import date, timedelta

from app.models import Priority, Role, TaskStatus


def test_task_create_list_filter_and_update(client, make_user, auth_headers):
    """Verify task CRUD basics and valid status or priority filtering."""
    user = make_user(
        username="task_owner",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )
    headers = auth_headers(user["username"])

    create_response = client.post(
        "/api/tasks",
        headers=headers,
        json={
            "title": "Motor pruefen",
            "description": "Motor laeuft unruhig",
            "department": "Instandhaltung",
            "due_date": "2026-05-02",
            "priority": "urgent",
        },
    )
    list_response = client.get(
        "/api/tasks?status=open&priority=urgent",
        headers=headers,
    )
    task_id = create_response.get_json()["id"]
    update_response = client.put(
        f"/api/tasks/{task_id}",
        headers=headers,
        json={"status": "in_progress", "priority": "soon"},
    )

    assert create_response.status_code == 201
    assert list_response.status_code == 200
    assert len(list_response.get_json()) == 1
    assert update_response.status_code == 200
    assert update_response.get_json()["status"] == "in_progress"
    assert update_response.get_json()["current_worker_id"] == user["id"]


def test_task_routes_require_token(client):
    """Verify protected task routes reject unauthenticated requests."""
    response = client.get("/api/tasks")

    assert response.status_code == 401


def test_task_validation_rejects_bad_payloads(client, make_user, auth_headers):
    """Verify task creation and filtering reject malformed edgecase values."""
    user = make_user(
        username="task_validation",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )
    headers = auth_headers(user["username"])

    missing_title = client.post(
        "/api/tasks",
        headers=headers,
        json={"department": "Instandhaltung"},
    )
    blank_title = client.post(
        "/api/tasks",
        headers=headers,
        json={"title": "   ", "department": "Instandhaltung"},
    )
    bad_date = client.post(
        "/api/tasks",
        headers=headers,
        json={
            "title": "Datum kaputt",
            "department": "Instandhaltung",
            "due_date": "05-02-2026",
        },
    )
    bad_filter = client.get("/api/tasks?status=unknown", headers=headers)

    assert missing_title.status_code == 400
    assert blank_title.status_code == 400
    assert bad_date.status_code == 400
    assert bad_filter.status_code == 400


def test_non_admin_cannot_write_task_for_other_department(
    client,
    make_user,
    auth_headers,
):
    """Verify department-scoped users cannot create tasks for another department."""
    user = make_user(
        username="department_guard",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )

    response = client.post(
        "/api/tasks",
        headers=auth_headers(user["username"]),
        json={"title": "Fremder Task", "department": "Instandhaltung"},
    )

    assert response.status_code == 403


def test_task_detail_is_forbidden_across_departments(
    client,
    make_user,
    make_task,
    auth_headers,
):
    """Verify users cannot read task details from another department."""
    owner = make_user(
        username="other_task_owner",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )
    requester = make_user(
        username="task_requester",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )
    task_id = make_task(
        "Fremde Aufgabe",
        creator_username=owner["username"],
        department_name="Instandhaltung",
    )

    response = client.get(
        f"/api/tasks/{task_id}",
        headers=auth_headers(requester["username"]),
    )

    assert response.status_code == 403


def test_task_start_and_complete_edgecases(
    client,
    make_user,
    make_task,
    auth_headers,
):
    """Verify workflow endpoints handle repeated and invalid status transitions."""
    user = make_user(username="workflow_user")
    headers = auth_headers(user["username"])
    task_id = make_task("Workflow", creator_username=user["username"])
    done_task_id = make_task(
        "Already done",
        creator_username=user["username"],
        status=TaskStatus.DONE,
    )
    cancelled_task_id = make_task(
        "Cancelled",
        creator_username=user["username"],
        status=TaskStatus.CANCELLED,
    )

    start_response = client.post(f"/api/tasks/{task_id}/start", headers=headers)
    second_start_response = client.post(f"/api/tasks/{task_id}/start", headers=headers)
    complete_response = client.post(f"/api/tasks/{task_id}/complete", headers=headers)
    second_complete_response = client.post(
        f"/api/tasks/{task_id}/complete",
        headers=headers,
    )
    start_done_response = client.post(f"/api/tasks/{done_task_id}/start", headers=headers)
    complete_cancelled_response = client.post(
        f"/api/tasks/{cancelled_task_id}/complete",
        headers=headers,
    )

    assert start_response.status_code == 200
    assert second_start_response.status_code == 409
    assert complete_response.status_code == 200
    assert complete_response.get_json()["completed_by"] == user["id"]
    assert second_complete_response.status_code == 409
    assert start_done_response.status_code == 400
    assert complete_cancelled_response.status_code == 400


def test_task_create_start_complete_workflow(client, make_user, auth_headers):
    """Verify the public task workflow endpoints match the frontend contract."""
    user = make_user(
        username="workflow_create_user",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )
    headers = auth_headers(user["username"])

    create_response = client.post(
        "/api/tasks",
        headers=headers,
        json={
            "title": "Workflow Ende zu Ende",
            "department": "Instandhaltung",
            "priority": "normal",
            "status": "open",
        },
    )
    task_id = create_response.get_json()["id"]
    start_response = client.post(f"/api/tasks/{task_id}/start", headers=headers)
    complete_response = client.post(
        f"/api/tasks/{task_id}/complete",
        headers=headers,
        json={},
    )

    assert create_response.status_code == 201
    assert start_response.status_code == 200
    assert start_response.get_json()["status"] == "in_progress"
    assert complete_response.status_code == 200
    assert complete_response.get_json()["status"] == "done"
    assert complete_response.get_json()["completed_by"] == user["id"]


def test_task_workflow_errors_use_consistent_payload(client, make_user, auth_headers):
    """Verify workflow errors expose success, short error code and message."""
    user = make_user(username="workflow_error_shape")

    response = client.post(
        "/api/tasks/999/start",
        headers=auth_headers(user["username"]),
    )

    payload = response.get_json()
    assert response.status_code == 404
    assert payload["success"] is False
    assert payload["message"] == "Task not found"
    assert payload["error"] == "task_not_found"


def test_today_tasks_only_returns_current_date(client, make_user, make_task, auth_headers):
    """Verify the today endpoint filters visible tasks by server date."""
    user = make_user(username="today_user")
    make_task(
        "Heute",
        creator_username=user["username"],
        due_date_value=date.today(),
    )
    make_task(
        "Nicht heute",
        creator_username=user["username"],
        due_date_value=date.today() + timedelta(days=1),
    )

    response = client.get("/api/tasks/today", headers=auth_headers(user["username"]))

    assert response.status_code == 200
    assert [task["title"] for task in response.get_json()] == ["Heute"]


def test_prioritize_tasks_only_returns_visible_department(
    client,
    make_user,
    make_task,
    auth_headers,
):
    """Verify task prioritization respects department visibility."""
    requester = make_user(
        username="priority_requester",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )
    other_user = make_user(
        username="priority_other",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )
    make_task(
        "Eigener Task",
        creator_username=requester["username"],
        department_name="Produktion",
    )
    make_task(
        "Fremder Task",
        creator_username=other_user["username"],
        department_name="Instandhaltung",
    )

    response = client.post(
        "/api/tasks/prioritize",
        headers=auth_headers(requester["username"]),
        json={"status": "open"},
    )

    payload = response.get_json()["data"]
    assert response.status_code == 200
    assert [item["task"]["title"] for item in payload] == ["Eigener Task"]


def test_prioritize_tasks_rejects_invalid_filters(client, make_user, auth_headers):
    """Verify task prioritization rejects invalid status and limit values."""
    user = make_user(username="priority_validation")
    headers = auth_headers(user["username"])

    bad_status = client.post(
        "/api/tasks/prioritize",
        headers=headers,
        json={"status": "unknown"},
    )
    bad_limit = client.post(
        "/api/tasks/prioritize",
        headers=headers,
        json={"limit": 0},
    )

    assert bad_status.status_code == 400
    assert bad_limit.status_code == 400


def test_prioritize_tasks_sorts_urgent_overdue_before_normal(
    client,
    make_user,
    make_task,
    auth_headers,
):
    """Verify local prioritization ranks urgent overdue tasks first."""
    user = make_user(username="priority_sort")
    make_task(
        "Normaler Rundgang",
        creator_username=user["username"],
        priority=Priority.NORMAL,
        due_date_value=date.today() + timedelta(days=5),
        description="Routinepruefung",
    )
    make_task(
        "Stillstand an Anlage 4",
        creator_username=user["username"],
        priority=Priority.URGENT,
        due_date_value=date.today() - timedelta(days=1),
        description="Anlage steht seit gestern mit Sensorfehler",
    )

    response = client.post(
        "/api/tasks/prioritize",
        headers=auth_headers(user["username"]),
        json={"status": "open"},
    )

    payload = response.get_json()["data"]
    assert response.status_code == 200
    assert payload[0]["task"]["title"] == "Stillstand an Anlage 4"
    assert payload[0]["score"] > payload[1]["score"]
    assert payload[0]["risk_level"] in {"high", "critical"}


def test_prioritize_tasks_uses_local_fallback_without_openai_key(
    client,
    make_user,
    make_task,
    auth_headers,
):
    """Verify task prioritization works with the configured local provider."""
    user = make_user(username="priority_fallback")
    make_task(
        "Sensor pruefen",
        creator_username=user["username"],
        priority=Priority.SOON,
        description="Sensor meldet sporadisch kein Signal",
    )

    response = client.post(
        "/api/tasks/prioritize",
        headers=auth_headers(user["username"]),
        json={"limit": 1},
    )

    payload = response.get_json()["data"]
    assert response.status_code == 200
    assert len(payload) == 1
    assert set(payload[0]) == {
        "task",
        "score",
        "risk_level",
        "reason",
        "recommended_action",
    }


def test_task_page_contains_priority_ui(client):
    """Verify task prioritization is exposed on the task page."""
    response = client.get("/tasks")
    script_response = client.get("/static/app.js")
    html = response.get_data(as_text=True)
    script = script_response.get_data(as_text=True)

    assert response.status_code == 200
    assert script_response.status_code == 200
    assert 'data-task-priority-list' in html
    assert 'data-task-priority-refresh' in html
    assert "Priorisierung konnte nicht geladen werden." in script

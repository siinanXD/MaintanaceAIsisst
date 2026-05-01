from datetime import date, timedelta

from app.models import Role, TaskStatus


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

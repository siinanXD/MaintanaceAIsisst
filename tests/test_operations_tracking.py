"""Tests for multi-site operations tracking and KPI APIs."""

from app.models import OperationalEvent, OperationalKpiAggregate, Role, Site


def test_default_site_is_available_and_sites_api_lists_active_sites(
    client,
    make_user,
    auth_headers,
):
    """Verify the default site is created and visible through the selector API."""
    user = make_user(username="site_selector_user")

    response = client.get("/api/v1/sites", headers=auth_headers(user["username"]))

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["data"][0]["code"] == "werk-1"
    assert payload["data"][0]["name"] == "Werk 1"


def test_admin_site_crud_is_master_admin_only(client, make_user, auth_headers):
    """Verify master admins can maintain sites and regular users cannot."""
    admin = make_user(username="site_admin", role=Role.MASTER_ADMIN, department_name=None)
    user = make_user(username="site_regular")
    admin_headers = auth_headers(admin["username"])
    user_headers = auth_headers(user["username"])

    forbidden_response = client.get("/api/v1/admin/sites", headers=user_headers)
    create_response = client.post(
        "/api/v1/admin/sites",
        headers=admin_headers,
        json={
            "code": "werk-2",
            "name": "Werk 2",
            "timezone": "Europe/Berlin",
            "is_active": True,
        },
    )
    site_id = create_response.get_json()["data"]["id"]
    update_response = client.put(
        f"/api/v1/admin/sites/{site_id}",
        headers=admin_headers,
        json={"name": "Werk 2 Nord", "is_active": False},
    )
    list_response = client.get(
        "/api/v1/admin/sites?include_inactive=1",
        headers=admin_headers,
    )

    assert forbidden_response.status_code == 403
    assert create_response.status_code == 201
    assert update_response.status_code == 200
    assert update_response.get_json()["data"]["is_active"] is False
    assert any(site["code"] == "werk-2" for site in list_response.get_json()["data"])

    with client.application.app_context():
        site = Site.query.filter_by(code="werk-2").one()
        events = OperationalEvent.query.filter_by(entity_type="site", entity_id=site.id).all()
        assert {event.event_type for event in events} == {"site.created", "site.updated"}


def test_task_lifecycle_records_pseudonymized_operations_events(
    client,
    make_user,
    auth_headers,
):
    """Verify task lifecycle actions emit non-personal operational events."""
    user = make_user(
        username="ops_task_user",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )
    headers = auth_headers(user["username"])

    create_response = client.post(
        "/api/v1/tasks",
        headers=headers,
        json={
            "title": "Pumpe pruefen",
            "department": "Instandhaltung",
            "planned_minutes": 45,
        },
    )
    task_id = create_response.get_json()["id"]
    client.post(f"/api/v1/tasks/{task_id}/start", headers=headers)
    client.post(f"/api/v1/tasks/{task_id}/complete", headers=headers, json={})

    events_response = client.get(
        f"/api/v1/operations/events?task_id={task_id}",
        headers=headers,
    )
    event_payload = events_response.get_json()["data"]["items"]

    assert create_response.status_code == 201
    assert events_response.status_code == 200
    assert {event["event_type"] for event in event_payload} >= {
        "task.created",
        "task.started",
        "task.completed",
    }
    assert all(event["actor_hash"] != str(user["id"]) for event in event_payload)
    assert all(len(event["actor_hash"]) == 64 for event in event_payload)
    assert all("prompt" not in event.get("metadata", {}) for event in event_payload)


def test_operations_summary_and_aggregate_endpoint(client, make_user, auth_headers):
    """Verify summary KPIs and persisted aggregates are generated from events."""
    admin = make_user(username="ops_summary_admin", role=Role.MASTER_ADMIN, department_name=None)
    headers = auth_headers(admin["username"])

    material_response = client.post(
        "/api/v1/inventory",
        headers=headers,
        json={
            "name": "Dichtung 40x3",
            "quantity": 2,
            "min_quantity": 10,
            "criticality": "critical",
        },
    )
    task_response = client.post(
        "/api/v1/tasks",
        headers=headers,
        json={"title": "Leckage beheben", "department": "Instandhaltung"},
    )
    aggregate_response = client.post(
        "/api/v1/admin/operations/aggregate",
        headers=headers,
        json={"period_type": "day"},
    )
    summary_response = client.get("/api/v1/operations/summary", headers=headers)

    summary = summary_response.get_json()["data"]
    aggregate = aggregate_response.get_json()["data"]

    assert material_response.status_code == 201
    assert task_response.status_code == 201
    assert aggregate_response.status_code == 200
    assert summary_response.status_code == 200
    assert summary["tasks"]["open"] >= 1
    assert summary["inventory"]["critical_shortage_count"] >= 1
    assert aggregate["events"] >= 2

    with client.application.app_context():
        assert OperationalKpiAggregate.query.count() >= 1


def test_ai_feedback_event_does_not_store_prompt_or_answer(client, make_user, auth_headers):
    """Verify AI feedback tracking stores metadata, not prompt or answer text."""
    user = make_user(username="ops_ai_feedback_user")

    response = client.post(
        "/api/v1/ai/feedback",
        headers=auth_headers(user["username"]),
        json={"prompt": "Sensitive prompt", "response": "Sensitive answer", "rating": "helpful"},
    )

    assert response.status_code == 201
    with client.application.app_context():
        event = OperationalEvent.query.filter_by(event_type="ai.feedback").one()
        metadata = event.metadata_dict()
        assert metadata == {"rating": "helpful"}
        assert "Sensitive" not in event.metadata_json

from app.models import Priority, Role


def public_route_methods(app):
    """Return non-static Flask route rules and supported HTTP methods."""
    routes = set()
    for rule in app.url_map.iter_rules():
        if rule.endpoint == "static":
            continue
        for method in rule.methods - {"HEAD", "OPTIONS"}:
            routes.add((rule.rule, method))
    return routes


def test_frontend_task_workflow_routes_exist(app, client):
    """Verify frontend task workflow calls match registered Flask routes."""
    routes = public_route_methods(app)
    script = client.get("/static/app.js").get_data(as_text=True)

    assert ("/api/tasks/<int:task_id>/start", "POST") in routes
    assert ("/api/tasks/<int:task_id>/complete", "POST") in routes
    assert '"/start"' in script
    assert '"/complete"' in script


def test_new_ai_frontend_routes_exist(app, client):
    """Verify frontend AI feature calls have matching Flask routes."""
    routes = public_route_methods(app)
    script = client.get("/static/app.js").get_data(as_text=True)

    expected_routes = {
        ("/api/tasks/prioritize", "POST"),
        ("/api/errors/similar", "POST"),
        ("/api/inventory/forecast", "POST"),
        ("/api/shiftplans/calendar", "GET"),
        ("/api/machines/<int:machine_id>/history", "GET"),
        ("/api/machines/<int:machine_id>/assistant", "POST"),
        ("/api/ai/daily-briefing", "GET"),
        ("/api/documents/<int:document_id>/review", "POST"),
    }
    assert expected_routes <= routes
    assert "/api/tasks/prioritize" in script
    assert "/api/errors/similar" in script
    assert "/api/inventory/forecast" in script
    assert "/api/shiftplans/calendar" in script
    assert "/api/ai/daily-briefing" in script


def test_api_not_found_returns_consistent_json(client, make_user, auth_headers):
    """Verify unknown API routes return the standard JSON error shape."""
    user = make_user(username="api_not_found_user")

    response = client.get(
        "/api/does-not-exist",
        headers=auth_headers(user["username"]),
    )

    payload = response.get_json()
    assert response.status_code == 404
    assert payload["success"] is False
    assert payload["message"]
    assert payload["error"]
    assert payload["error"] != payload["message"]


def test_core_ai_and_workflow_endpoints_smoke(
    client,
    make_user,
    make_task,
    make_machine,
    make_material,
    auth_headers,
):
    """Verify core frontend API endpoints respond with authenticated requests."""
    user = make_user(
        username="api_smoke_user",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )
    machine_id = make_machine(name="Anlage Smoke")
    make_material("Smoke Sensor", 120, 0, machine_id=machine_id)
    task_id = make_task(
        "Stillstand Anlage Smoke",
        creator_username=user["username"],
        department_name="Instandhaltung",
        priority=Priority.URGENT,
        description="Anlage Smoke meldet Sensorfehler",
    )
    headers = auth_headers(user["username"])

    start_response = client.post(f"/api/tasks/{task_id}/start", headers=headers)
    complete_response = client.post(
        f"/api/tasks/{task_id}/complete",
        headers=headers,
        json={},
    )
    briefing_response = client.get("/api/ai/daily-briefing", headers=headers)
    assistant_response = client.post(
        f"/api/machines/{machine_id}/assistant",
        headers=headers,
        json={"question": "Was ist wichtig?"},
    )
    forecast_response = client.post(
        "/api/inventory/forecast",
        headers=headers,
        json={"status": "open", "limit": 20, "low_stock_threshold": 5},
    )

    assert start_response.status_code == 200
    assert start_response.get_json()["status"] == "in_progress"
    assert complete_response.status_code == 200
    assert complete_response.get_json()["status"] == "done"
    assert briefing_response.status_code == 200
    assert "sections" in briefing_response.get_json()
    assert assistant_response.status_code == 200
    assert assistant_response.get_json()["diagnostics"]["status"] == "local_answer"
    assert forecast_response.status_code == 200
    assert "items" in forecast_response.get_json()

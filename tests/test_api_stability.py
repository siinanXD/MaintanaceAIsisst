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
        ("/api/machines/<int:machine_id>/history", "GET"),
        ("/api/machines/<int:machine_id>/assistant", "POST"),
        ("/api/ai/daily-briefing", "GET"),
        ("/api/documents/<int:document_id>/review", "POST"),
    }
    assert expected_routes <= routes
    assert "/api/tasks/prioritize" in script
    assert "/api/errors/similar" in script
    assert "/api/inventory/forecast" in script
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
    assert payload["error"] == payload["message"]

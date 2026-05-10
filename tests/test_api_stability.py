from app.models import Priority, Role
from app.permissions import DASHBOARD_KEYS


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

    assert ("/api/v1/tasks/<int:task_id>/start", "POST") in routes
    assert ("/api/v1/tasks/<int:task_id>/complete", "POST") in routes
    assert '"/start"' in script
    assert '"/complete"' in script


def test_new_ai_frontend_routes_exist(app, client):
    """Verify frontend AI feature calls have matching Flask routes."""
    routes = public_route_methods(app)
    script = client.get("/static/app.js").get_data(as_text=True)

    expected_routes = {
        ("/api/v1/tasks/prioritize", "POST"),
        ("/api/v1/errors/similar", "POST"),
        ("/api/v1/inventory/forecast", "POST"),
        ("/api/v1/shiftplans/calendar", "GET"),
        ("/api/v1/machines/<int:machine_id>/history", "GET"),
        ("/api/v1/machines/<int:machine_id>/assistant", "POST"),
        ("/api/v1/ai/daily-briefing", "GET"),
        ("/api/v1/documents/<int:document_id>/review", "POST"),
    }
    assert expected_routes <= routes
    assert "/api/v1/tasks/prioritize" in script
    assert "/api/v1/errors/similar" in script
    assert "/api/v1/inventory/forecast" in script
    assert "/api/v1/shiftplans/calendar" in script
    assert "/api/v1/ai/daily-briefing" in script


def test_feature_registry_covers_permissions_and_frontend_assets(client):
    """Verify the shared frontend feature registry stays aligned with permissions."""
    registry_response = client.get("/static/core/feature-registry.js")
    base_response = client.get("/")
    registry = registry_response.get_data(as_text=True)
    html = base_response.get_data(as_text=True)

    assert registry_response.status_code == 200
    assert "window.maintenanceFeatures" in registry
    assert "core/feature-registry.js" in html

    for dashboard_key in DASHBOARD_KEYS:
        assert f'permissionKey: "{dashboard_key}"' in registry

    assert 'key: "handover"' in registry
    assert 'permissionKey: "shiftplans"' in registry
    assert 'key: "vacations"' in registry
    assert 'permissionKey: "employees"' in registry


def test_loaded_static_assets_exist(client):
    """Verify the base template references only static assets that Flask can serve."""
    html = client.get("/").get_data(as_text=True)
    expected_assets = (
        "/static/css/output.css",
        "/static/core/feature-registry.js",
        "/static/auth.js",
        "/static/app.js",
        "/static/chat.js",
    )

    for asset in expected_assets:
        assert asset in html
        assert client.get(asset).status_code == 200


def test_web_routes_use_shared_design_shell(client):
    """Verify all HTML web routes render through the shared app design shell."""
    routes = (
        "/",
        "/login",
        "/api-docs",
        "/tasks",
        "/errors",
        "/admin/users",
        "/employees",
        "/shiftplans",
        "/machines",
        "/inventory",
        "/documents",
        "/handover",
        "/vacations",
    )

    for route in routes:
        response = client.get(route)
        html = response.get_data(as_text=True)
        assert response.status_code == 200
        assert "app-shell-layout" in html
        assert "app-sidebar" in html
        assert "app-main" in html
        assert "page-hero" in html
        assert "app-card" in html


def test_core_german_ui_labels_are_not_mojibake(client):
    """Verify important German UI labels render as UTF-8, not mojibake."""
    html = client.get("/").get_data(as_text=True)

    assert "Schicht\u00fcbergabe" in html
    assert "Men\u00fc" in html
    assert "Heute f\u00e4llig" in html
    assert "\u00fcberf\u00e4llig" in html
    assert "Schicht\u00c3\u00bcbergabe" not in html
    assert "faellig" not in html


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

    start_response = client.post(f"/api/v1/tasks/{task_id}/start", headers=headers)
    complete_response = client.post(
        f"/api/v1/tasks/{task_id}/complete",
        headers=headers,
        json={},
    )
    briefing_response = client.get("/api/v1/ai/daily-briefing", headers=headers)
    assistant_response = client.post(
        f"/api/v1/machines/{machine_id}/assistant",
        headers=headers,
        json={"question": "Was ist wichtig?"},
    )
    forecast_response = client.post(
        "/api/v1/inventory/forecast",
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

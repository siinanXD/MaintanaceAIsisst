"""Tests for API stability guarantees."""

import re
from pathlib import Path

import pytest

from app.models import Priority, Role
from app.permissions import DASHBOARD_KEYS

REPO_ROOT = Path(__file__).resolve().parents[1]


def public_route_methods(app):
    """Return non-static Flask route rules and supported HTTP methods."""
    routes = set()
    for rule in app.url_map.iter_rules():
        if rule.endpoint == "static":
            continue
        for method in rule.methods - {"HEAD", "OPTIONS"}:
            routes.add((rule.rule, method))
    return routes


def interactive_data_attributes():
    """Return data attributes from template buttons and forms."""
    attributes = {}
    tag_pattern = re.compile(r"<(?:button|form)\b[^>]*>", re.IGNORECASE)
    data_pattern = re.compile(r"\b(data-[A-Za-z0-9_-]+)(?=[\s=>])")

    for template_path in (REPO_ROOT / "app" / "templates").rglob("*.html"):
        text = template_path.read_text(encoding="utf-8")
        for tag_match in tag_pattern.finditer(text):
            line_number = text.count("\n", 0, tag_match.start()) + 1
            location = f"{template_path.relative_to(REPO_ROOT)}:{line_number}"
            for data_match in data_pattern.finditer(tag_match.group(0)):
                attributes.setdefault(data_match.group(1), []).append(location)
    return attributes


def frontend_source_text():
    """Return combined template and static JavaScript source text."""
    source_paths = list((REPO_ROOT / "app" / "templates").rglob("*.html"))
    source_paths.extend((REPO_ROOT / "app" / "static").rglob("*.js"))
    return "\n".join(path.read_text(encoding="utf-8") for path in source_paths)


def frontend_runtime_text(client):
    """Return JavaScript served by the core and lazy frontend entrypoints."""
    asset_paths = (
        "/static/app.js",
        "/static/chat-loader.js",
        "/static/chat.js",
        "/static/pages/workflows.js",
        "/static/pages/login.js",
        "/static/pages/admin-ai.js",
        "/static/pages/handover.js",
        "/static/pages/shiftplans.js",
    )
    return "\n".join(client.get(path).get_data(as_text=True) for path in asset_paths)


def frontend_ui_source_files():
    """Return frontend source files that contain user-visible UI copy."""
    source_paths = list((REPO_ROOT / "app" / "templates").rglob("*.html"))
    source_paths.extend((REPO_ROOT / "app" / "static").rglob("*.js"))
    source_paths.append(REPO_ROOT / "app" / "static" / "css" / "input.css")
    return source_paths


def test_frontend_task_workflow_routes_exist(app, client):
    """Verify frontend task workflow calls match registered Flask routes."""
    routes = public_route_methods(app)
    script = frontend_runtime_text(client)

    assert ("/api/v1/tasks/<int:task_id>/start", "POST") in routes
    assert ("/api/v1/tasks/<int:task_id>/complete", "POST") in routes
    assert '"/api/v1/tasks/" + taskId + "/" + action' in script
    assert '"start"' in script
    assert '"complete"' in script


def test_new_ai_frontend_routes_exist(app, client):
    """Verify frontend AI feature calls have matching Flask routes."""
    routes = public_route_methods(app)
    script = frontend_runtime_text(client)

    expected_routes = {
        ("/api/v1/tasks/prioritize", "POST"),
        ("/api/v1/errors/similar", "POST"),
        ("/api/v1/inventory/forecast", "POST"),
        ("/api/v1/shiftplans/calendar", "GET"),
        ("/api/v1/machines/<int:machine_id>/history", "GET"),
        ("/api/v1/machines/<int:machine_id>/assistant", "POST"),
        ("/api/v1/machines/maintenance-recommendations", "GET"),
        ("/api/v1/ai/status", "GET"),
        ("/api/v1/ai/daily-briefing", "GET"),
        ("/api/v1/ai/incident-timeline", "GET"),
        ("/api/v1/ai/chat/templates", "GET"),
        ("/api/v1/ai/error-assistant", "POST"),
        ("/api/v1/admin/ai/training", "GET"),
        ("/api/v1/admin/ai/training", "POST"),
        ("/api/v1/admin/ai/training/<int:entry_id>", "PUT"),
        ("/api/v1/admin/ai/training/<int:entry_id>", "DELETE"),
        ("/api/v1/admin/ai/knowledge-network", "GET"),
        ("/api/v1/admin/ai/retrieval-telemetry", "GET"),
        ("/api/v1/admin/ai/knowledge/status", "GET"),
        ("/api/v1/admin/ai/knowledge-gaps", "GET"),
        ("/api/v1/admin/ai/retrieval-debug", "GET"),
        ("/api/v1/admin/ai/observability", "GET"),
        ("/api/v1/sites", "GET"),
        ("/api/v1/operations/summary", "GET"),
        ("/api/v1/operations/events", "GET"),
        ("/api/v1/operations/tasks", "GET"),
        ("/api/v1/operations/machines", "GET"),
        ("/api/v1/operations/inventory", "GET"),
        ("/api/v1/operations/workforce", "GET"),
        ("/api/v1/operations/ai-quality", "GET"),
        ("/api/v1/admin/sites", "GET"),
        ("/api/v1/admin/sites", "POST"),
        ("/api/v1/admin/sites/<int:site_id>", "PUT"),
        ("/api/v1/admin/operations/aggregate", "POST"),
        ("/api/v1/documents/<int:document_id>/review", "POST"),
        ("/api/v1/health/operations", "GET"),
    }
    assert expected_routes <= routes
    assert "/api/v1/tasks/prioritize" in script
    assert "/api/v1/errors/similar" in script
    assert "/api/v1/inventory/forecast" in script
    assert "/api/v1/shiftplans/calendar" in script
    assert "/api/v1/ai/daily-briefing" in script
    assert "/api/v1/ai/error-assistant" in script
    assert "/api/v1/admin/ai/knowledge-network" in script
    assert "/api/v1/admin/ai/retrieval-telemetry" in script
    assert "/api/v1/admin/ai/knowledge/status" in script
    assert "/api/v1/admin/ai/knowledge-gaps" in script
    assert "/api/v1/admin/ai/retrieval-debug" in script
    assert "/api/v1/admin/ai/observability" in script
    assert "/api/v1/machines/maintenance-recommendations" in script


def test_scalability_migration_contains_composite_indexes():
    """Verify the multi-site scalability migration includes critical indexes."""
    migration = (
        REPO_ROOT / "migrations" / "versions" / "d1e2f3a4b5c6_add_scalability_indexes.py"
    ).read_text(encoding="utf-8")

    assert "ix_task_department_status_due" in migration
    assert "ix_knowledge_document_source_status" in migration
    assert "ix_background_job_claim" in migration
    assert "ix_generated_document_department_created" in migration


def test_operations_migration_contains_site_and_event_tables():
    """Verify the operations migration creates site and KPI tracking structures."""
    migration = (
        REPO_ROOT / "migrations" / "versions" / "e2f3a4b5c6d7_add_sites_operations_tracking.py"
    ).read_text(encoding="utf-8")

    assert "op.create_table(" in migration
    assert '"site"' in migration
    assert '"operational_event"' in migration
    assert '"operational_kpi_aggregate"' in migration
    assert "werk-1" in migration


def test_feature_registry_covers_permissions_and_frontend_assets(client):
    """Verify the shared frontend feature registry stays aligned with permissions."""
    registry_response = client.get("/static/core/feature-registry.js")
    app_js_response = client.get("/static/app.js")
    workflows_response = client.get("/static/pages/workflows.js")
    base_response = client.get("/")
    registry = registry_response.get_data(as_text=True)
    app_js = app_js_response.get_data(as_text=True)
    workflows = workflows_response.get_data(as_text=True)
    html = base_response.get_data(as_text=True)

    assert registry_response.status_code == 200
    assert app_js_response.status_code == 200
    assert workflows_response.status_code == 200
    assert "window.maintenanceFeatures" in registry
    assert "core/feature-registry.js" in html
    assert 'module: "workflows"' in registry
    assert 'initializers: ["initDepartments", "initTasks"]' in registry
    assert "WORKFLOW_FEATURE_KEYS" not in app_js
    assert 'feature.module === "workflows"' in app_js
    assert "runAction" in app_js
    assert "setFormBusy" in app_js
    assert "setWorkflowStatus" in app_js
    assert "initAccessibleTables" in app_js
    assert "PAGE_MODULE_URLS" in app_js
    assert "feature.initializers" in workflows

    for dashboard_key in DASHBOARD_KEYS:
        assert f'permissionKey: "{dashboard_key}"' in registry

    assert 'key: "handover"' in registry
    assert 'permissionKey: "shiftplans"' in registry
    assert 'module: "page"' in registry
    assert 'moduleUrl: "/static/pages/admin-ai.js"' in registry
    assert 'moduleUrl: "/static/pages/handover.js"' in registry
    assert 'moduleUrl: "/static/pages/shiftplans.js"' in registry
    assert 'key: "vacations"' in registry
    assert 'permissionKey: "employees"' in registry


def test_loaded_static_assets_exist(client):
    """Verify the base template references only static assets that Flask can serve."""
    html = client.get("/").get_data(as_text=True)
    expected_assets = (
        "/static/css/output.css",
        "/static/core/feature-registry.js",
        "/static/core/api-client.js",
        "/static/auth.js",
        "/static/app.js",
        "/static/chat-loader.js",
    )

    for asset in expected_assets:
        assert asset in html
        assert client.get(asset).status_code == 200

    for lazy_asset in (
        "/static/chat.js",
        "/static/pages/workflows.js",
        "/static/pages/login.js",
        "/static/pages/admin-ai.js",
        "/static/pages/handover.js",
        "/static/pages/shiftplans.js",
    ):
        assert client.get(lazy_asset).status_code == 200

    assert "/static/styles.css" not in html
    assert not (REPO_ROOT / "app" / "static" / "styles.css").exists()


def test_interactive_template_data_hooks_are_wired():
    """Verify button and form data hooks are referenced by frontend code."""
    source = frontend_source_text()
    missing = {
        attribute: locations
        for attribute, locations in interactive_data_attributes().items()
        if source.count(attribute) <= len(locations)
    }

    assert missing == {}


def test_migrated_pages_use_static_modules_without_inline_scripts():
    """Verify migrated workflow pages no longer carry large inline scripts."""
    migrated_templates = (
        REPO_ROOT / "app" / "templates" / "login.html",
        REPO_ROOT / "app" / "templates" / "admin_ai.html",
        REPO_ROOT / "app" / "templates" / "handover.html",
        REPO_ROOT / "app" / "templates" / "shiftplans.html",
    )
    for template_path in migrated_templates:
        assert "<script>" not in template_path.read_text(encoding="utf-8")

    source = frontend_source_text()
    assert "window.prompt" not in source
    assert "window.alert" not in source


def test_frontend_ui_copy_has_no_encoding_artifacts():
    """Verify UI source does not reintroduce mojibake or ASCII fallback labels."""
    blocked_fragments = (
        "Ã",
        "Laeuft",
        "Bestaetigen",
        "bestaetigen",
        "ueberfaellig",
        "Stoer",
        "Qualitaet",
        "spaeter",
        "gewaehl",
        "geprueft",
        "pruef",
        "Pruef",
        "koennen",
        "auswaehlen",
        "zurueck",
        "vollstaendig",
        "Handbuecher",
    )
    offenders = {}
    for source_path in frontend_ui_source_files():
        text = source_path.read_text(encoding="utf-8")
        hits = [fragment for fragment in blocked_fragments if fragment in text]
        if hits:
            offenders[str(source_path.relative_to(REPO_ROOT))] = hits

    assert offenders == {}


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
    assert '<svg class="nav-icon"' in html
    assert 'data-icon="DB"' not in html
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


def test_production_requires_strong_secrets(tmp_path):
    """Verify production startup rejects weak secret configuration."""

    class WeakProductionConfig:
        """Provide intentionally weak production settings."""

        TESTING = False
        FLASK_ENV = "production"
        SECRET_KEY = "dev-secret-change-me"
        JWT_SECRET_KEY = "short"
        SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
        SQLALCHEMY_TRACK_MODIFICATIONS = False
        AUTO_CREATE_DATABASE = False
        AI_PROVIDER = "mock"
        OPENAI_API_KEY = ""
        OPENAI_MODEL = "test-model"
        UPLOAD_FOLDER = str(tmp_path / "uploads")
        DOCUMENTS_FOLDER = str(tmp_path / "documents")
        LOG_DIR = str(tmp_path / "logs")
        LOG_LEVEL = "INFO"
        SLOW_REQUEST_THRESHOLD_MS = 500

    from app import create_app

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app(WeakProductionConfig)


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

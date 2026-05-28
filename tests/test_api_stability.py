"""Tests for API stability guarantees."""

import json
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


DASHBOARD_SPLIT_ASSETS = (
    "/static/pages/workflows/dashboard/state.js",
    "/static/pages/workflows/dashboard/resources.js",
    "/static/pages/workflows/dashboard/executive.js",
    "/static/pages/workflows/dashboard/tasks.js",
    "/static/pages/workflows/dashboard/operations.js",
    "/static/pages/workflows/dashboard/shift-calendar.js",
    "/static/pages/workflows/dashboard/actions.js",
)


SHIFTPLAN_SPLIT_ASSETS = (
    "/static/pages/shiftplans/shared.js",
    "/static/pages/shiftplans/models.js",
    "/static/pages/shiftplans/plans.js",
    "/static/pages/shiftplans/grid.js",
    "/static/pages/shiftplans/validation.js",
    "/static/pages/shiftplans/actions.js",
)


def served_asset_text(client, paths):
    """Return combined text for served static asset paths."""
    return "\n".join(client.get(path).get_data(as_text=True) for path in paths)


def shiftplans_runtime_text(client):
    """Return the shift planning entrypoint and split module source."""
    return served_asset_text(client, ("/static/pages/shiftplans.js", *SHIFTPLAN_SPLIT_ASSETS))


def frontend_runtime_text(client):
    """Return JavaScript served by the core and lazy frontend entrypoints."""
    asset_paths = (
        "/static/app.js",
        "/static/chat-loader.js",
        "/static/chat.js",
        "/static/chat/session.js",
        "/static/chat/evidence.js",
        "/static/chat/rendering.js",
        "/static/chat/history.js",
        "/static/chat/actions.js",
        "/static/pages/workflows.js",
        "/static/pages/login.js",
        "/static/pages/admin-ai-island.js",
        "/static/pages/admin-ai.js",
        "/static/pages/admin-ai/shared.js",
        "/static/pages/admin-ai/overview.js",
        "/static/pages/admin-ai/knowledge.js",
        "/static/pages/admin-ai/retrieval.js",
        "/static/pages/admin-ai/observability.js",
        "/static/pages/admin-ai/operations.js",
        "/static/pages/admin-ai/actions.js",
        "/static/pages/handover.js",
        "/static/pages/handover-island.js",
        "/static/pages/shiftplans.js",
        "/static/pages/shiftplans-island.js",
        "/static/pages/workflows/shared.js",
        "/static/pages/workflows/dashboard-shifts.js",
        "/static/pages/workflows/dashboard.js",
        "/static/pages/dashboard-island.js",
        *DASHBOARD_SPLIT_ASSETS,
        "/static/pages/workflows/tasks.js",
        "/static/pages/react-island-loader.js",
        "/static/pages/tasks-island.js",
        "/static/pages/workflows/errors.js",
        "/static/pages/errors-island.js",
        "/static/pages/workflows/machines.js",
        "/static/pages/workflows/machine-profile.js",
        "/static/pages/machines-island.js",
        "/static/pages/workflows/documents.js",
        "/static/pages/documents-island.js",
        "/static/pages/workflows/admin-users.js",
        "/static/pages/admin-users-island.js",
        "/static/pages/workflows/employees.js",
        "/static/pages/employees-island.js",
        "/static/pages/workflows/vacations.js",
        "/static/pages/vacations-island.js",
        "/static/pages/workflows/inventory.js",
        "/static/pages/inventory-island.js",
        "/static/pages/workflows/legacy-shiftplans.js",
        *SHIFTPLAN_SPLIT_ASSETS,
    )
    return served_asset_text(client, asset_paths)


def task_workflow_source():
    """Return the task workflow initializer source."""
    return (REPO_ROOT / "app" / "static" / "pages" / "workflows" / "tasks.js").read_text(
        encoding="utf-8",
    )


def task_react_source():
    """Return the combined React task island source."""
    source_paths = list((REPO_ROOT / "frontend" / "src" / "tasks").rglob("*.ts"))
    source_paths.extend((REPO_ROOT / "frontend" / "src" / "tasks").rglob("*.tsx"))
    return "\n".join(path.read_text(encoding="utf-8") for path in source_paths)


def machine_react_source():
    """Return the combined React machine island source."""
    source_paths = list((REPO_ROOT / "frontend" / "src" / "machines").rglob("*.ts"))
    source_paths.extend((REPO_ROOT / "frontend" / "src" / "machines").rglob("*.tsx"))
    return "\n".join(path.read_text(encoding="utf-8") for path in source_paths)


def error_react_source():
    """Return the combined React error island source."""
    source_paths = list((REPO_ROOT / "frontend" / "src" / "errors").rglob("*.ts"))
    source_paths.extend((REPO_ROOT / "frontend" / "src" / "errors").rglob("*.tsx"))
    return "\n".join(path.read_text(encoding="utf-8") for path in source_paths)


def document_react_source():
    """Return the combined React document island source."""
    source_paths = list((REPO_ROOT / "frontend" / "src" / "documents").rglob("*.ts"))
    source_paths.extend((REPO_ROOT / "frontend" / "src" / "documents").rglob("*.tsx"))
    return "\n".join(path.read_text(encoding="utf-8") for path in source_paths)


def employee_react_source():
    """Return the combined React employee island source."""
    source_paths = list((REPO_ROOT / "frontend" / "src" / "employees").rglob("*.ts"))
    source_paths.extend((REPO_ROOT / "frontend" / "src" / "employees").rglob("*.tsx"))
    return "\n".join(path.read_text(encoding="utf-8") for path in source_paths)


def vacation_react_source():
    """Return the combined React vacation island source."""
    source_paths = list((REPO_ROOT / "frontend" / "src" / "vacations").rglob("*.ts"))
    source_paths.extend((REPO_ROOT / "frontend" / "src" / "vacations").rglob("*.tsx"))
    return "\n".join(path.read_text(encoding="utf-8") for path in source_paths)


def frontend_ui_source_files():
    """Return frontend source files that contain user-visible UI copy."""
    source_paths = list((REPO_ROOT / "app" / "templates").rglob("*.html"))
    source_paths.extend(
        path
        for path in (REPO_ROOT / "app" / "static").rglob("*.js")
        if "react" not in path.relative_to(REPO_ROOT / "app" / "static").parts
    )
    source_paths.extend((REPO_ROOT / "frontend" / "src").rglob("*.tsx"))
    source_paths.extend((REPO_ROOT / "frontend" / "src").rglob("*.ts"))
    source_paths.append(REPO_ROOT / "app" / "static" / "css" / "input.css")
    return source_paths


def test_frontend_task_workflow_routes_exist(app, client):
    """Verify frontend task workflow calls match registered Flask routes."""
    routes = public_route_methods(app)
    script = frontend_runtime_text(client) + "\n" + task_react_source()

    assert ("/api/v1/tasks/<int:task_id>/start", "POST") in routes
    assert ("/api/v1/tasks/<int:task_id>/complete", "POST") in routes
    assert "`/api/v1/tasks/${taskId}/${action}`" in script
    assert '"start"' in script
    assert '"complete"' in script


def test_task_prioritization_is_manual_refresh_only():
    """Verify the task page does not trigger AI prioritization on initial load."""
    source = task_workflow_source()
    react_source = task_react_source()

    assert "/api/v1/tasks/prioritize" in source
    assert "/api/v1/tasks/prioritize" in react_source
    assert "priorityRefreshButtons.forEach" in source
    assert "Bei Bedarf aktualisieren" in source
    assert "Bei Bedarf aktualisieren" in react_source
    assert "Prioritätslage nicht neu berechnet" in source
    assert "Prioritätslage nicht neu berechnet" in react_source
    assert "await load();\n    await loadPriorities();" not in source
    assert source.count("await loadPriorities();") == 1
    assert "await refreshTaskData();\n    await refreshPriorities();" not in react_source


def test_new_ai_frontend_routes_exist(app, client):
    """Verify frontend AI feature calls have matching Flask routes."""
    routes = public_route_methods(app)
    script = (
        frontend_runtime_text(client)
        + "\n"
        + machine_react_source()
        + "\n"
        + error_react_source()
        + "\n"
        + document_react_source()
        + "\n"
        + employee_react_source()
        + "\n"
        + vacation_react_source()
    )

    expected_routes = {
        ("/api/v1/tasks/prioritize", "POST"),
        ("/api/v1/errors/similar", "POST"),
        ("/api/v1/inventory/forecast", "POST"),
        ("/api/v1/shiftplans/calendar", "GET"),
        ("/api/v1/shiftplans/models", "GET"),
        ("/api/v1/machines/<int:machine_id>/history", "GET"),
        ("/api/v1/machines/<int:machine_id>/profile", "GET"),
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
        ("/api/v1/admin/ai/retrieval-evaluations/run", "POST"),
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
        ("/api/v1/employees", "GET"),
        ("/api/v1/employees", "POST"),
        ("/api/v1/employees/<int:employee_id>", "PUT"),
        ("/api/v1/employees/<int:employee_id>", "DELETE"),
        ("/api/v1/employees/<int:employee_id>/documents", "POST"),
        ("/api/v1/vacations", "GET"),
        ("/api/v1/vacations", "POST"),
        ("/api/v1/vacations/impact", "GET"),
        ("/api/v1/vacations/summary", "GET"),
        ("/api/v1/vacations/<int:request_id>/approve", "POST"),
        ("/api/v1/vacations/<int:request_id>/reject", "POST"),
        ("/api/v1/vacations/<int:request_id>/cancel", "POST"),
        ("/api/v1/health/operations", "GET"),
    }
    assert expected_routes <= routes
    assert "/api/v1/tasks/prioritize" in script
    assert 'mode: "local"' in script
    assert 'listData(await api("/api/v1/tasks/prioritize"' in script
    assert "/api/v1/errors/similar" in script
    assert "/api/v1/errors/analyze" in script
    assert "`/api/v1/errors/${errorId}`" in script
    assert "`/api/v1/errors/${errorId}/close`" in script
    assert "/api/v1/inventory/forecast" in script
    assert "/api/v1/shiftplans/calendar" in script
    assert 'BASE + "/models"' in script
    assert "/api/v1/ai/daily-briefing" in script
    assert "/api/v1/ai/error-assistant" in script
    assert "/api/v1/admin/ai/knowledge-network" in script
    assert "/api/v1/admin/ai/retrieval-telemetry" in script
    assert "/api/v1/admin/ai/retrieval-evaluations/run" in script
    assert "/api/v1/admin/ai/knowledge/status" in script
    assert "/api/v1/admin/ai/knowledge-gaps" in script
    assert "/api/v1/admin/ai/retrieval-debug" in script
    assert "/api/v1/admin/ai/observability" in script
    assert "/api/v1/documents/check" in script
    assert "/api/v1/documents/manuals" in script
    assert "`/api/v1/documents/${documentId}/review`" in script
    assert "`/api/v1/documents/${documentId}/summarize`" in script
    assert "`/api/v1/documents/${documentId}/versions`" in script
    assert "`/api/v1/documents/${documentId}/${action}`" in script
    assert "`/api/v1/documents/manuals/${manualId}/analyze`" in script
    assert "`/api/v1/documents/manuals/${manualId}/summarize`" in script
    assert "`/api/v1/documents/manuals/${manualId}`" in script
    assert "/api/v1/machines/maintenance-recommendations" in script
    assert "`/api/v1/machines/${machineId}/profile`" in script
    assert '"/api/v1/machines/" + machineId + "/profile"' in script
    assert "/api/v1/employees?limit=200" in script
    assert "`/api/v1/employees/${employeeId}`" in script
    assert "`/api/v1/employees/${employeeId}/documents`" in script
    assert "/api/v1/vacations?year=" in script
    assert "/api/v1/vacations/summary?year=" in script
    assert "/api/v1/vacations/impact?" in script
    assert "`/api/v1/vacations/${requestId}/${action}`" in script
    assert "`/api/v1/vacations/${requestId}/cancel`" in script


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
    auth_response = client.get("/static/auth.js")
    app_js_response = client.get("/static/app.js")
    workflows_response = client.get("/static/pages/workflows.js")
    base_response = client.get("/")
    registry = registry_response.get_data(as_text=True)
    auth_js = auth_response.get_data(as_text=True)
    app_js = app_js_response.get_data(as_text=True)
    workflows = frontend_runtime_text(client)
    html = base_response.get_data(as_text=True)

    assert registry_response.status_code == 200
    assert auth_response.status_code == 200
    assert app_js_response.status_code == 200
    assert workflows_response.status_code == 200
    assert "window.maintenanceFeatures" in registry
    assert "core/feature-registry.js" in html
    assert 'module: "page"' in registry
    assert 'moduleUrl: "/static/pages/dashboard-island.js"' in registry
    assert 'moduleUrl: "/static/pages/tasks-island.js"' in registry
    assert "WORKFLOW_FEATURE_KEYS" not in app_js
    assert 'feature.module === "workflows"' in app_js
    assert "runAction" in app_js
    assert "setFormBusy" in app_js
    assert "setWorkflowStatus" in app_js
    assert "initAccessibleTables" in app_js
    assert "PAGE_MODULE_URLS" in app_js
    assert "feature.initializers" in workflows
    registry_initializer_blocks = re.findall(
        r"initializers:\s*\[([^\]]+)\]",
        registry,
        re.DOTALL,
    )
    registered_initializers = {
        initializer
        for block in registry_initializer_blocks
        for initializer in re.findall(r'"([^"]+)"', block)
    }
    missing_initializers = sorted(
        initializer
        for initializer in registered_initializers
        if re.search(rf"\b{re.escape(initializer)}\b", workflows) is None
    )
    assert missing_initializers == []
    assert 'key: "admin_users"' in registry
    assert 'moduleUrl: "/static/pages/admin-users-island.js"' in registry
    assert '"initBenutzer"' not in registry

    for dashboard_key in DASHBOARD_KEYS:
        assert f'permissionKey: "{dashboard_key}"' in registry

    assert 'key: "handover"' in registry
    assert 'permissionKey: "shiftplans"' in registry
    assert 'module: "page"' in registry
    assert 'moduleUrl: "/static/pages/admin-ai-island.js"' in registry
    assert "routeAliases" in registry
    assert "routePrefixes" in registry
    assert '"/admin/ai/technical"' in registry
    assert '"/admin/ai/models"' in registry
    assert '"/admin/ai/retrieval"' in registry
    assert '"/admin/ai/knowledge"' in registry
    assert '"/admin/ai/training"' in registry
    assert "featureRoutes(feature)" in auth_js
    assert "feature.routeAliases" in auth_js
    assert 'moduleUrl: "/static/pages/handover-island.js"' in registry
    assert 'moduleUrl: "/static/pages/shiftplans-island.js"' in registry
    assert 'moduleUrl: "/static/pages/inventory-island.js"' in registry
    assert 'moduleUrl: "/static/pages/tasks-island.js"' in registry
    assert 'moduleUrl: "/static/pages/errors-island.js"' in registry
    assert 'moduleUrl: "/static/pages/machines-island.js"' in registry
    assert 'moduleUrl: "/static/pages/documents-island.js"' in registry
    assert 'moduleUrl: "/static/pages/admin-users-island.js"' in registry
    assert 'moduleUrl: "/static/pages/employees-island.js"' in registry
    assert 'moduleUrl: "/static/pages/vacations-island.js"' in registry
    assert 'routePrefixes: ["/machines/"]' in registry
    assert 'key: "vacations"' in registry
    assert 'permissionKey: "employees"' in registry


def test_react_foundation_is_configured_but_not_globally_loaded(client):
    """Verify the React foundation exists without changing the current Jinja shell."""
    api_docs_response = client.get("/api-docs")
    api_docs_html = api_docs_response.get_data(as_text=True)
    frontend_package = json.loads(
        (REPO_ROOT / "frontend" / "package.json").read_text(encoding="utf-8"),
    )
    vite_config = (REPO_ROOT / "frontend" / "vite.config.ts").read_text(encoding="utf-8")
    react_entrypoint = (REPO_ROOT / "frontend" / "src" / "main.tsx").read_text(encoding="utf-8")
    root_package = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))

    assert api_docs_response.status_code == 200
    assert "maintenance-react-root" not in api_docs_html
    assert "/static/react/" not in api_docs_html
    assert frontend_package["dependencies"]["react"].startswith("^19.")
    assert frontend_package["scripts"]["typecheck"] == "tsc --noEmit"
    assert 'outDir: "../app/static/react"' in vite_config
    assert "document.getElementById(REACT_ROOT_ID)" in react_entrypoint
    assert root_package["scripts"]["build:react"] == "npm --prefix frontend run build"
    assert root_package["scripts"]["check:react"] == "npm --prefix frontend run typecheck"


def test_login_react_island_keeps_fallback_and_stays_route_scoped(client):
    """Verify React login assets are optional and scoped to the login page."""
    api_docs_response = client.get("/api-docs")
    login_response = client.get("/login")
    api_docs_html = api_docs_response.get_data(as_text=True)
    login_html = login_response.get_data(as_text=True)
    manifest_path = REPO_ROOT / "app" / "static" / "react" / ".vite" / "manifest.json"

    assert api_docs_response.status_code == 200
    assert login_response.status_code == 200
    assert "maintenance-login-root" not in api_docs_html
    assert "/static/react/" not in api_docs_html
    assert "maintenance-login-root" in login_html
    assert "data-react-login-fallback" in login_html
    assert "data-login-form" in login_html
    assert "data-login-message" in login_html

    if not manifest_path.exists():
        assert "/static/react/" not in login_html
        return

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    login_entry = manifest["src/login/loginEntrypoint.tsx"]
    login_asset = f"/static/react/{login_entry['file']}"
    imported_assets = [
        f"/static/react/{manifest[import_name]['file']}"
        for import_name in login_entry.get("imports", [])
    ]

    assert login_asset in login_html
    assert client.get(login_asset).status_code == 200
    for imported_asset in imported_assets:
        assert f'rel="modulepreload" href="{imported_asset}"' in login_html
        assert client.get(imported_asset).status_code == 200


def test_dashboard_react_shell_island_keeps_fallback_and_stays_route_scoped(client):
    """Verify React dashboard assets are optional and scoped to the cockpit page."""
    dashboard_response = client.get("/")
    tasks_response = client.get("/tasks")
    registry_response = client.get("/static/core/feature-registry.js")
    dashboard_html = dashboard_response.get_data(as_text=True)
    tasks_html = tasks_response.get_data(as_text=True)
    registry = registry_response.get_data(as_text=True)
    manifest_path = REPO_ROOT / "app" / "static" / "react" / ".vite" / "manifest.json"

    assert dashboard_response.status_code == 200
    assert tasks_response.status_code == 200
    assert registry_response.status_code == 200
    assert "maintenance-dashboard-root" in dashboard_html
    assert "maintenance-dashboard-root" not in tasks_html
    assert "data-react-dashboard-fallback" in dashboard_html
    assert "data-ai-ops-cockpit" in dashboard_html
    assert "data-dashboard-priority-list" in dashboard_html
    assert "data-dashboard-shift-timeline" in dashboard_html
    assert "data-task-detail-modal" in dashboard_html
    assert 'moduleUrl: "/static/pages/dashboard-island.js"' in registry

    if not manifest_path.exists():
        assert "/static/react/" not in dashboard_html
        return

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    dashboard_entry = manifest.get("src/dashboard/dashboardEntrypoint.tsx")
    if dashboard_entry is None:
        assert "/static/react/" not in dashboard_html
        return

    dashboard_asset = f"/static/react/{dashboard_entry['file']}"
    imported_assets = [
        f"/static/react/{manifest[import_name]['file']}"
        for import_name in dashboard_entry.get("imports", [])
    ]

    assert dashboard_asset in dashboard_html
    assert client.get(dashboard_asset).status_code == 200
    for imported_asset in imported_assets:
        assert f'rel="modulepreload" href="{imported_asset}"' in dashboard_html
        assert client.get(imported_asset).status_code == 200


def test_inventory_react_island_keeps_fallback_and_stays_route_scoped(client):
    """Verify React inventory assets are optional and scoped to the inventory page."""
    home_response = client.get("/")
    inventory_response = client.get("/inventory")
    registry_response = client.get("/static/core/feature-registry.js")
    home_html = home_response.get_data(as_text=True)
    inventory_html = inventory_response.get_data(as_text=True)
    registry = registry_response.get_data(as_text=True)
    manifest_path = REPO_ROOT / "app" / "static" / "react" / ".vite" / "manifest.json"

    assert home_response.status_code == 200
    assert inventory_response.status_code == 200
    assert registry_response.status_code == 200
    assert "maintenance-inventory-root" not in home_html
    assert "maintenance-inventory-root" in inventory_html
    assert "data-react-inventory-fallback" in inventory_html
    assert "data-inventory-form" in inventory_html
    assert "data-inventory-list" in inventory_html
    assert "data-inventory-forecast-form" in inventory_html
    assert "data-inventory-forecast-list" in inventory_html
    assert "data-inventory-forecast-unmatched" in inventory_html
    assert 'moduleUrl: "/static/pages/inventory-island.js"' in registry

    if not manifest_path.exists():
        assert "/static/react/" not in inventory_html
        return

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    inventory_entry = manifest["src/inventory/inventoryEntrypoint.tsx"]
    inventory_asset = f"/static/react/{inventory_entry['file']}"
    imported_assets = [
        f"/static/react/{manifest[import_name]['file']}"
        for import_name in inventory_entry.get("imports", [])
    ]

    assert inventory_asset in inventory_html
    assert client.get(inventory_asset).status_code == 200
    for imported_asset in imported_assets:
        assert f'rel="modulepreload" href="{imported_asset}"' in inventory_html
        assert client.get(imported_asset).status_code == 200


def test_tasks_react_island_keeps_fallback_and_stays_route_scoped(client):
    """Verify React task assets are optional and scoped to the task page."""
    home_response = client.get("/")
    tasks_response = client.get("/tasks")
    registry_response = client.get("/static/core/feature-registry.js")
    home_html = home_response.get_data(as_text=True)
    tasks_html = tasks_response.get_data(as_text=True)
    registry = registry_response.get_data(as_text=True)
    manifest_path = REPO_ROOT / "app" / "static" / "react" / ".vite" / "manifest.json"

    assert home_response.status_code == 200
    assert tasks_response.status_code == 200
    assert registry_response.status_code == 200
    assert "maintenance-tasks-root" not in home_html
    assert "maintenance-tasks-root" in tasks_html
    assert "data-react-tasks-fallback" in tasks_html
    assert "data-task-form" in tasks_html
    assert "data-task-message" in tasks_html
    assert "data-task-suggest-form" in tasks_html
    assert "data-task-priority-list" in tasks_html
    assert "data-task-kanban-board" in tasks_html
    assert 'moduleUrl: "/static/pages/tasks-island.js"' in registry

    if not manifest_path.exists():
        assert "/static/react/" not in tasks_html
        return

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    tasks_entry = manifest["src/tasks/taskEntrypoint.tsx"]
    tasks_asset = f"/static/react/{tasks_entry['file']}"
    imported_assets = [
        f"/static/react/{manifest[import_name]['file']}"
        for import_name in tasks_entry.get("imports", [])
    ]

    assert tasks_asset in tasks_html
    assert client.get(tasks_asset).status_code == 200
    for imported_asset in imported_assets:
        assert f'rel="modulepreload" href="{imported_asset}"' in tasks_html
        assert client.get(imported_asset).status_code == 200


def test_errors_react_island_keeps_fallback_and_stays_route_scoped(client):
    """Verify React error assets are optional and scoped to the errors page."""
    home_response = client.get("/")
    errors_response = client.get("/errors")
    registry_response = client.get("/static/core/feature-registry.js")
    home_html = home_response.get_data(as_text=True)
    errors_html = errors_response.get_data(as_text=True)
    registry = registry_response.get_data(as_text=True)
    manifest_path = REPO_ROOT / "app" / "static" / "react" / ".vite" / "manifest.json"

    assert home_response.status_code == 200
    assert errors_response.status_code == 200
    assert registry_response.status_code == 200
    assert "maintenance-errors-root" not in home_html
    assert "maintenance-errors-root" in errors_html
    assert "data-react-errors-fallback" in errors_html
    assert "data-error-form" in errors_html
    assert "data-error-analyze-form" in errors_html
    assert "data-similar-errors-panel" in errors_html
    assert "data-error-list" in errors_html
    assert "data-error-search" in errors_html
    assert "data-error-action-preview" in errors_html
    assert 'moduleUrl: "/static/pages/errors-island.js"' in registry

    if not manifest_path.exists():
        assert "/static/react/" not in errors_html
        return

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors_entry = manifest["src/errors/errorsEntrypoint.tsx"]
    errors_asset = f"/static/react/{errors_entry['file']}"
    imported_assets = [
        f"/static/react/{manifest[import_name]['file']}"
        for import_name in errors_entry.get("imports", [])
    ]

    assert errors_asset in errors_html
    assert client.get(errors_asset).status_code == 200
    for imported_asset in imported_assets:
        assert f'rel="modulepreload" href="{imported_asset}"' in errors_html
        assert client.get(imported_asset).status_code == 200


def test_machines_react_island_keeps_fallback_and_stays_route_scoped(client):
    """Verify React machine assets are optional and scoped to machine routes."""
    home_response = client.get("/")
    machines_response = client.get("/machines")
    profile_response = client.get("/machines/123")
    registry_response = client.get("/static/core/feature-registry.js")
    home_html = home_response.get_data(as_text=True)
    machines_html = machines_response.get_data(as_text=True)
    profile_html = profile_response.get_data(as_text=True)
    registry = registry_response.get_data(as_text=True)
    manifest_path = REPO_ROOT / "app" / "static" / "react" / ".vite" / "manifest.json"

    assert home_response.status_code == 200
    assert machines_response.status_code == 200
    assert profile_response.status_code == 200
    assert registry_response.status_code == 200
    assert "maintenance-machines-root" not in home_html
    assert "maintenance-machine-profile-root" not in home_html
    assert "maintenance-machines-root" in machines_html
    assert "data-react-machines-fallback" in machines_html
    assert "data-machine-form" in machines_html
    assert "data-machine-list" in machines_html
    assert "data-machine-history-panel" in machines_html
    assert "maintenance-machine-profile-root" in profile_html
    assert "data-react-machine-profile-fallback" in profile_html
    assert "data-machine-profile-page" in profile_html
    assert 'data-machine-id="123"' in profile_html
    assert 'moduleUrl: "/static/pages/machines-island.js"' in registry
    assert 'routePrefixes: ["/machines/"]' in registry

    if not manifest_path.exists():
        assert "/static/react/" not in machines_html
        assert "/static/react/" not in profile_html
        return

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    machines_entry = manifest["src/machines/machinesEntrypoint.tsx"]
    machines_asset = f"/static/react/{machines_entry['file']}"
    imported_assets = [
        f"/static/react/{manifest[import_name]['file']}"
        for import_name in machines_entry.get("imports", [])
    ]

    assert machines_asset in machines_html
    assert machines_asset in profile_html
    assert client.get(machines_asset).status_code == 200
    for imported_asset in imported_assets:
        assert f'rel="modulepreload" href="{imported_asset}"' in machines_html
        assert f'rel="modulepreload" href="{imported_asset}"' in profile_html
        assert client.get(imported_asset).status_code == 200


def test_documents_react_island_keeps_fallback_and_stays_route_scoped(client):
    """Verify React document assets are optional and scoped to the documents page."""
    home_response = client.get("/")
    documents_response = client.get("/documents")
    registry_response = client.get("/static/core/feature-registry.js")
    home_html = home_response.get_data(as_text=True)
    documents_html = documents_response.get_data(as_text=True)
    registry = registry_response.get_data(as_text=True)
    manifest_path = REPO_ROOT / "app" / "static" / "react" / ".vite" / "manifest.json"

    assert home_response.status_code == 200
    assert documents_response.status_code == 200
    assert registry_response.status_code == 200
    assert "maintenance-documents-root" not in home_html
    assert "maintenance-documents-root" in documents_html
    assert "data-react-documents-fallback" in documents_html
    assert "data-document-filter-form" in documents_html
    assert "data-document-upload-check-form" in documents_html
    assert "data-manual-upload-form" in documents_html
    assert "data-document-list" in documents_html
    assert "data-manual-list" in documents_html
    assert "data-document-review-panel" in documents_html
    assert "data-document-summary-panel" in documents_html
    assert 'moduleUrl: "/static/pages/documents-island.js"' in registry

    if not manifest_path.exists():
        assert "/static/react/" not in documents_html
        return

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    documents_entry = manifest["src/documents/documentsEntrypoint.tsx"]
    documents_asset = f"/static/react/{documents_entry['file']}"
    imported_assets = [
        f"/static/react/{manifest[import_name]['file']}"
        for import_name in documents_entry.get("imports", [])
    ]

    assert documents_asset in documents_html
    assert client.get(documents_asset).status_code == 200
    for imported_asset in imported_assets:
        assert f'rel="modulepreload" href="{imported_asset}"' in documents_html
        assert client.get(imported_asset).status_code == 200


def test_admin_users_react_island_keeps_fallback_and_stays_route_scoped(client):
    """Verify React admin-user assets are optional and scoped to the admin users page."""
    home_response = client.get("/")
    admin_response = client.get("/admin/users")
    registry_response = client.get("/static/core/feature-registry.js")
    home_html = home_response.get_data(as_text=True)
    admin_html = admin_response.get_data(as_text=True)
    registry = registry_response.get_data(as_text=True)
    manifest_path = REPO_ROOT / "app" / "static" / "react" / ".vite" / "manifest.json"

    assert home_response.status_code == 200
    assert admin_response.status_code == 200
    assert registry_response.status_code == 200
    assert "maintenance-admin-users-root" not in home_html
    assert "maintenance-admin-users-root" in admin_html
    assert "data-react-admin-users-fallback" in admin_html
    assert "data-user-list" in admin_html
    assert "data-permission-list" in admin_html
    assert "data-audit-log-list" in admin_html
    assert "data-backup-list" in admin_html
    assert "data-ai-analytics-card" in admin_html
    assert 'moduleUrl: "/static/pages/admin-users-island.js"' in registry

    if not manifest_path.exists():
        assert "/static/react/" not in admin_html
        return

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    admin_entry = manifest["src/admin-users/adminUsersEntrypoint.tsx"]
    admin_asset = f"/static/react/{admin_entry['file']}"
    imported_assets = [
        f"/static/react/{manifest[import_name]['file']}"
        for import_name in admin_entry.get("imports", [])
    ]

    assert admin_asset in admin_html
    assert client.get(admin_asset).status_code == 200
    for imported_asset in imported_assets:
        assert f'rel="modulepreload" href="{imported_asset}"' in admin_html
        assert client.get(imported_asset).status_code == 200


def test_employees_react_island_keeps_fallback_and_stays_route_scoped(client):
    """Verify React employee assets are optional and scoped to the employees page."""
    home_response = client.get("/")
    employees_response = client.get("/employees")
    registry_response = client.get("/static/core/feature-registry.js")
    home_html = home_response.get_data(as_text=True)
    employees_html = employees_response.get_data(as_text=True)
    registry = registry_response.get_data(as_text=True)
    manifest_path = REPO_ROOT / "app" / "static" / "react" / ".vite" / "manifest.json"

    assert home_response.status_code == 200
    assert employees_response.status_code == 200
    assert registry_response.status_code == 200
    assert "maintenance-employees-root" not in home_html
    assert "maintenance-employees-root" in employees_html
    assert "data-react-employees-fallback" in employees_html
    assert "data-employee-form" in employees_html
    assert "data-employee-message" in employees_html
    assert "data-employee-list" in employees_html
    assert "data-employee-count" in employees_html
    assert "emp-edit-dialog" in employees_html
    assert "empd-save" in employees_html
    assert "empd-cancel" in employees_html
    assert 'moduleUrl: "/static/pages/employees-island.js"' in registry

    if not manifest_path.exists():
        assert "/static/react/" not in employees_html
        return

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    employees_entry = manifest["src/employees/employeesEntrypoint.tsx"]
    employees_asset = f"/static/react/{employees_entry['file']}"
    imported_assets = [
        f"/static/react/{manifest[import_name]['file']}"
        for import_name in employees_entry.get("imports", [])
    ]

    assert employees_asset in employees_html
    assert client.get(employees_asset).status_code == 200
    for imported_asset in imported_assets:
        assert f'rel="modulepreload" href="{imported_asset}"' in employees_html
        assert client.get(imported_asset).status_code == 200


def test_vacations_react_island_keeps_fallback_and_stays_route_scoped(client):
    """Verify React vacation assets are optional and scoped to the vacations page."""
    home_response = client.get("/")
    vacations_response = client.get("/vacations")
    registry_response = client.get("/static/core/feature-registry.js")
    home_html = home_response.get_data(as_text=True)
    vacations_html = vacations_response.get_data(as_text=True)
    registry = registry_response.get_data(as_text=True)
    manifest_path = REPO_ROOT / "app" / "static" / "react" / ".vite" / "manifest.json"

    assert home_response.status_code == 200
    assert vacations_response.status_code == 200
    assert registry_response.status_code == 200
    assert "maintenance-vacations-root" not in home_html
    assert "maintenance-vacations-root" in vacations_html
    assert "data-react-vacations-fallback" in vacations_html
    assert "data-vac-form" in vacations_html
    assert "data-vac-submit" in vacations_html
    assert "data-vac-pending-list" in vacations_html
    assert "data-vac-summary-list" in vacations_html
    assert "data-vac-history-list" in vacations_html
    assert "data-vac-calendar-list" in vacations_html
    assert "data-vac-filter-status" in vacations_html
    assert 'moduleUrl: "/static/pages/vacations-island.js"' in registry

    if not manifest_path.exists():
        assert "/static/react/" not in vacations_html
        return

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    vacations_entry = manifest["src/vacations/vacationsEntrypoint.tsx"]
    vacations_asset = f"/static/react/{vacations_entry['file']}"
    imported_assets = [
        f"/static/react/{manifest[import_name]['file']}"
        for import_name in vacations_entry.get("imports", [])
    ]

    assert vacations_asset in vacations_html
    assert client.get(vacations_asset).status_code == 200
    for imported_asset in imported_assets:
        assert f'rel="modulepreload" href="{imported_asset}"' in vacations_html
        assert client.get(imported_asset).status_code == 200


def test_shiftplans_react_shell_island_keeps_fallback_and_stays_route_scoped(client):
    """Verify React shift planning assets are optional and scoped to the shiftplan page."""
    home_response = client.get("/")
    shiftplans_response = client.get("/shiftplans")
    registry_response = client.get("/static/core/feature-registry.js")
    home_html = home_response.get_data(as_text=True)
    shiftplans_html = shiftplans_response.get_data(as_text=True)
    registry = registry_response.get_data(as_text=True)
    manifest_path = REPO_ROOT / "app" / "static" / "react" / ".vite" / "manifest.json"

    assert home_response.status_code == 200
    assert shiftplans_response.status_code == 200
    assert registry_response.status_code == 200
    assert "maintenance-shiftplans-root" not in home_html
    assert "maintenance-shiftplans-root" in shiftplans_html
    assert "data-react-shiftplans-fallback" in shiftplans_html
    assert 'id="sp-form"' in shiftplans_html
    assert 'id="sp-machine-picker"' in shiftplans_html
    assert "data-shiftplan-calendar" in shiftplans_html
    assert 'id="sp-dialog"' in shiftplans_html
    assert 'moduleUrl: "/static/pages/shiftplans-island.js"' in registry

    if not manifest_path.exists():
        assert "/static/react/" not in shiftplans_html
        return

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    shiftplans_entry = manifest.get("src/shiftplans/shiftplansEntrypoint.tsx")
    if shiftplans_entry is None:
        assert "/static/react/" not in shiftplans_html
        return

    shiftplans_asset = f"/static/react/{shiftplans_entry['file']}"
    imported_assets = [
        f"/static/react/{manifest[import_name]['file']}"
        for import_name in shiftplans_entry.get("imports", [])
    ]

    assert shiftplans_asset in shiftplans_html
    assert client.get(shiftplans_asset).status_code == 200
    for imported_asset in imported_assets:
        assert f'rel="modulepreload" href="{imported_asset}"' in shiftplans_html
        assert client.get(imported_asset).status_code == 200


def test_shiftplans_react_markup_replaces_fallback_clone():
    """Verify the shift planning shell is rendered by React instead of cloned from fallback."""
    shiftplans_app = (
        REPO_ROOT / "frontend" / "src" / "shiftplans" / "ShiftplansApp.tsx"
    ).read_text(encoding="utf-8")
    shiftplans_markup = (
        REPO_ROOT / "frontend" / "src" / "shiftplans" / "ShiftplansMarkup.tsx"
    ).read_text(encoding="utf-8")
    shiftplans_generation_form = (
        REPO_ROOT / "frontend" / "src" / "shiftplans" / "ShiftplansGenerationForm.tsx"
    ).read_text(encoding="utf-8")
    shiftplans_plan_view = (
        REPO_ROOT / "frontend" / "src" / "shiftplans" / "ShiftplansPlanView.tsx"
    ).read_text(encoding="utf-8")
    shiftplans_dialog = (
        REPO_ROOT / "frontend" / "src" / "shiftplans" / "ShiftplansEditDialog.tsx"
    ).read_text(encoding="utf-8")
    shiftplans_react_sources = "\n".join(
        (
            shiftplans_app,
            shiftplans_markup,
            shiftplans_generation_form,
            shiftplans_plan_view,
            shiftplans_dialog,
        )
    )

    assert "ShiftplansMarkup" in shiftplans_app
    assert "markIslandMounted" in shiftplans_app
    assert "useFallbackShellIsland" not in shiftplans_app
    assert "cloneFallbackShell" not in shiftplans_app
    assert "useLayoutEffect" not in shiftplans_app
    assert "ShiftplansGenerationForm" in shiftplans_markup
    assert "ShiftplansPlanView" in shiftplans_markup
    assert "ShiftplansEditDialog" in shiftplans_markup
    assert 'id="sp-form"' in shiftplans_react_sources
    assert 'id="sp-machine-picker"' in shiftplans_react_sources
    assert 'id="sp-shift-model"' in shiftplans_react_sources
    assert 'id="sp-plan-select"' in shiftplans_react_sources
    assert "data-shiftplan-calendar" in shiftplans_react_sources
    assert 'id="sp-dialog"' in shiftplans_react_sources
    assert 'id="dlg-save"' in shiftplans_react_sources
    assert 'id="dlg-delete"' in shiftplans_react_sources
    assert "loadShiftPlans" in shiftplans_app
    assert "loadShiftModels" in shiftplans_app
    assert "loadShiftplanMachines" in shiftplans_app
    assert "previewShiftPlan" in shiftplans_app
    assert "generateShiftPlan" in shiftplans_app
    assert "updateShiftplanEntry" in shiftplans_app
    assert "moveEntryToSlot" in shiftplans_app
    assert "publishShiftPlan" in shiftplans_app
    assert "deleteShiftPlan" in shiftplans_app


def test_shiftplans_react_runtime_replaces_legacy_loader():
    """Verify shiftplans uses legacy JavaScript only when React fails to mount."""
    island_loader = (REPO_ROOT / "app" / "static" / "pages" / "shiftplans-island.js").read_text(
        encoding="utf-8"
    )
    shiftplans_api = (REPO_ROOT / "frontend" / "src" / "shiftplans" / "shiftplansApi.ts").read_text(
        encoding="utf-8"
    )
    shiftplans_plan_view = (
        REPO_ROOT / "frontend" / "src" / "shiftplans" / "ShiftplansPlanView.tsx"
    ).read_text(encoding="utf-8")

    assert "waitForReactIsland" in island_loader
    assert "initializeReactShellRuntime" not in island_loader
    assert "if (reactMounted) return" in island_loader
    assert 'await import("/static/pages/shiftplans.js' in island_loader
    assert "/api/v1/shiftplans" in shiftplans_api
    assert "`${SHIFTPLANS_BASE}/models`" in shiftplans_api
    assert "/api/v1/machines?limit=200" in shiftplans_api
    assert 'id="sp-thead"' in shiftplans_plan_view
    assert 'id="sp-tbody"' in shiftplans_plan_view
    assert 'id="sp-warn-list"' in shiftplans_plan_view


def test_handover_react_shell_island_keeps_fallback_and_stays_route_scoped(client):
    """Verify React handover assets are optional and scoped to the handover page."""
    home_response = client.get("/")
    handover_response = client.get("/handover")
    registry_response = client.get("/static/core/feature-registry.js")
    home_html = home_response.get_data(as_text=True)
    handover_html = handover_response.get_data(as_text=True)
    registry = registry_response.get_data(as_text=True)
    manifest_path = REPO_ROOT / "app" / "static" / "react" / ".vite" / "manifest.json"

    assert home_response.status_code == 200
    assert handover_response.status_code == 200
    assert registry_response.status_code == 200
    assert "maintenance-handover-root" not in home_html
    assert "maintenance-handover-root" in handover_html
    assert "data-react-handover-fallback" in handover_html
    assert "data-handover-form" in handover_html
    assert "data-ho-machine-select" in handover_html
    assert "data-ho-filter-machine" in handover_html
    assert "data-handover-search" in handover_html
    assert 'id="ho-dialog"' in handover_html
    assert 'moduleUrl: "/static/pages/handover-island.js"' in registry

    if not manifest_path.exists():
        assert "/static/react/" not in handover_html
        return

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    handover_entry = manifest.get("src/handover/handoverEntrypoint.tsx")
    if handover_entry is None:
        assert "/static/react/" not in handover_html
        return

    handover_asset = f"/static/react/{handover_entry['file']}"
    imported_assets = [
        f"/static/react/{manifest[import_name]['file']}"
        for import_name in handover_entry.get("imports", [])
    ]

    assert handover_asset in handover_html
    assert client.get(handover_asset).status_code == 200
    for imported_asset in imported_assets:
        assert f'rel="modulepreload" href="{imported_asset}"' in handover_html
        assert client.get(imported_asset).status_code == 200


def test_handover_react_markup_replaces_fallback_clone():
    """Verify the handover shell is rendered by React instead of cloned from fallback."""
    handover_app = (REPO_ROOT / "frontend" / "src" / "handover" / "HandoverApp.tsx").read_text(
        encoding="utf-8"
    )
    handover_markup = (
        REPO_ROOT / "frontend" / "src" / "handover" / "HandoverMarkup.tsx"
    ).read_text(encoding="utf-8")
    handover_form = (REPO_ROOT / "frontend" / "src" / "handover" / "HandoverForm.tsx").read_text(
        encoding="utf-8"
    )
    handover_list = (REPO_ROOT / "frontend" / "src" / "handover" / "HandoverList.tsx").read_text(
        encoding="utf-8"
    )
    handover_dialog = (
        REPO_ROOT / "frontend" / "src" / "handover" / "HandoverDialog.tsx"
    ).read_text(encoding="utf-8")
    handover_stats = (REPO_ROOT / "frontend" / "src" / "handover" / "HandoverStats.tsx").read_text(
        encoding="utf-8"
    )
    handover_react_sources = "\n".join(
        (
            handover_app,
            handover_markup,
            handover_form,
            handover_list,
            handover_dialog,
            handover_stats,
        )
    )

    assert "HandoverMarkup" in handover_app
    assert "markIslandMounted" in handover_app
    assert "useFallbackShellIsland" not in handover_app
    assert "cloneFallbackShell" not in handover_app
    assert "loadHandovers" in handover_app
    assert "createHandover" in handover_app
    assert "updateHandover" in handover_app
    assert "completeHandover" in handover_app
    assert "HandoverForm" in handover_markup
    assert "HandoverList" in handover_markup
    assert "HandoverDialog" in handover_markup
    assert "data-handover-form" in handover_react_sources
    assert "data-ho-machine-select" in handover_react_sources
    assert "data-ho-filter-machine" in handover_react_sources
    assert "data-handover-search" in handover_react_sources
    assert "data-ho-open-count" in handover_react_sources
    assert "data-ho-completed-count" in handover_react_sources
    assert 'id="ho-dialog"' in handover_react_sources
    assert 'id="dlg-ho-save"' in handover_react_sources


def test_handover_react_runtime_replaces_legacy_loader():
    """Verify Handover uses React behavior and loads handover.js only as fallback."""
    handover_dir = REPO_ROOT / "frontend" / "src" / "handover"
    handover_app = (handover_dir / "HandoverApp.tsx").read_text(encoding="utf-8")
    handover_api = (handover_dir / "handoverApi.ts").read_text(encoding="utf-8")
    handover_list = (handover_dir / "HandoverList.tsx").read_text(encoding="utf-8")
    handover_dialog = (handover_dir / "HandoverDialog.tsx").read_text(encoding="utf-8")
    island_loader = (REPO_ROOT / "app" / "static" / "pages" / "handover-island.js").read_text(
        encoding="utf-8"
    )

    assert "initializeReactShellRuntime" not in island_loader
    assert "waitForReactIsland" in island_loader
    assert "if (reactMounted) return" in island_loader
    assert 'import("/static/pages/handover.js?v="' in island_loader
    assert "loadHandoverMachines" in handover_app
    assert "payloadFromForm" in handover_app
    assert '"/api/v1/handover"' in handover_api
    assert '"/api/v1/machines?limit=100"' in handover_api
    assert "data-handover-card" in handover_list
    assert "data-complete" in handover_list
    assert "data-edit" in handover_list
    assert "onSave" in handover_dialog
    assert "showModal" in handover_dialog


def test_admin_ai_react_shell_island_keeps_fallback_and_stays_route_scoped(client):
    """Verify React Admin-AI assets are optional and scoped to Admin-AI pages."""
    home_response = client.get("/")
    admin_response = client.get("/admin/ai")
    technical_response = client.get("/admin/ai/technical")
    registry_response = client.get("/static/core/feature-registry.js")
    home_html = home_response.get_data(as_text=True)
    admin_html = admin_response.get_data(as_text=True)
    technical_html = technical_response.get_data(as_text=True)
    registry = registry_response.get_data(as_text=True)
    manifest_path = REPO_ROOT / "app" / "static" / "react" / ".vite" / "manifest.json"

    assert home_response.status_code == 200
    assert admin_response.status_code == 200
    assert technical_response.status_code == 200
    assert registry_response.status_code == 200
    assert "maintenance-admin-ai-root" not in home_html
    assert "maintenance-admin-ai-root" in admin_html
    assert "maintenance-admin-ai-root" in technical_html
    assert "data-react-admin-ai-fallback" in admin_html
    assert "data-admin-ai-page" in admin_html
    assert 'data-ai-admin-view="overview"' in admin_html
    assert 'data-ai-admin-view="technical"' in technical_html
    assert "data-ai-admin-message" in admin_html
    assert 'data-ai-admin-area="technical"' in technical_html
    assert 'moduleUrl: "/static/pages/admin-ai-island.js"' in registry
    assert '"/admin/ai/technical"' in registry

    if not manifest_path.exists():
        assert "/static/react/" not in admin_html
        return

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    admin_ai_entry = manifest.get("src/admin-ai/adminAiEntrypoint.tsx")
    if admin_ai_entry is None:
        assert "/static/react/" not in admin_html
        return

    admin_ai_asset = f"/static/react/{admin_ai_entry['file']}"
    imported_assets = [
        f"/static/react/{manifest[import_name]['file']}"
        for import_name in admin_ai_entry.get("imports", [])
    ]

    assert admin_ai_asset in admin_html
    assert admin_ai_asset in technical_html
    assert client.get(admin_ai_asset).status_code == 200
    for imported_asset in imported_assets:
        assert f'rel="modulepreload" href="{imported_asset}"' in admin_html
        assert f'rel="modulepreload" href="{imported_asset}"' in technical_html
        assert client.get(imported_asset).status_code == 200


def test_admin_ai_react_markup_replaces_fallback_clone():
    """Verify Admin-AI renders canonical areas from React instead of cloning fallback."""
    admin_ai_dir = REPO_ROOT / "frontend" / "src" / "admin-ai"
    admin_ai_app = (admin_ai_dir / "AdminAiApp.tsx").read_text(encoding="utf-8")
    admin_ai_markup = (admin_ai_dir / "AdminAiMarkup.tsx").read_text(encoding="utf-8")
    admin_ai_sources = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(admin_ai_dir.glob("AdminAi*.tsx"))
    )
    admin_ai_runtime_sources = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(admin_ai_dir.glob("*.ts*"))
    )

    assert "AdminAiMarkup" in admin_ai_app
    assert "markIslandMounted" in admin_ai_app
    assert "useFallbackShellIsland" not in admin_ai_app
    assert "cloneFallbackShell" not in admin_ai_app
    assert "useLayoutEffect" not in admin_ai_app
    assert "AdminAiShell" in admin_ai_markup
    assert "loadAiStatus" in admin_ai_runtime_sources
    assert "loadAdminAiSummary" in admin_ai_runtime_sources
    assert "loadAdminAiUserCosts" in admin_ai_runtime_sources
    assert "loadPromptTemplates" in admin_ai_runtime_sources
    assert "loadFaqEntries" in admin_ai_runtime_sources
    assert "loadFaqSuggestions" in admin_ai_runtime_sources
    assert "loadResponseSnippets" in admin_ai_runtime_sources
    assert "loadOperationsHealth" in admin_ai_runtime_sources
    assert "loadRetrievalTelemetry" in admin_ai_runtime_sources
    assert "/api/v1/ai/status" in admin_ai_runtime_sources
    assert "/api/v1/admin/ai/summary?days=7" in admin_ai_runtime_sources
    assert "/api/v1/admin/ai/users?days=30&limit=50" in admin_ai_runtime_sources
    assert "/api/v1/admin/ai/retrieval-telemetry?days=30&limit=5" in admin_ai_runtime_sources
    assert "/api/v1/admin/ai/prompts" in admin_ai_runtime_sources
    assert "/api/v1/admin/ai/faq?limit=50" in admin_ai_runtime_sources
    assert "/api/v1/admin/ai/faq/suggestions?days=30&limit=10" in admin_ai_runtime_sources
    assert "/api/v1/admin/ai/response-snippets" in admin_ai_runtime_sources
    assert "/api/v1/health/operations" in admin_ai_runtime_sources
    assert "maintenanceAdminAiReactRuntime" in admin_ai_runtime_sources
    assert "overviewStatusCards" in admin_ai_runtime_sources
    assert "effectivenessState" in admin_ai_runtime_sources
    assert "data-ai-user-costs-admin" in admin_ai_runtime_sources
    assert "data-ai-effectiveness-risks" in admin_ai_runtime_sources
    assert "promptFaqState" in admin_ai_runtime_sources
    assert "data-ai-prompt-version-form" in admin_ai_runtime_sources
    assert "data-ai-faq-form" in admin_ai_runtime_sources
    assert "data-approve-faq" in admin_ai_runtime_sources
    assert "data-admin-ai-page" in admin_ai_sources
    assert "data-ai-admin-view" in admin_ai_sources
    assert "data-ai-admin-message" in admin_ai_sources
    assert 'data-ai-admin-area="overview"' in admin_ai_sources
    assert 'data-ai-admin-area="rag-board"' in admin_ai_sources
    assert 'data-ai-admin-area="source-check"' in admin_ai_sources
    assert 'data-ai-admin-area="prompts"' in admin_ai_sources
    assert 'data-ai-admin-area="faq"' in admin_ai_sources
    assert 'data-ai-admin-area="costs"' in admin_ai_sources
    assert 'data-ai-admin-area="capabilities"' in admin_ai_sources
    assert 'data-ai-admin-area="technical"' in admin_ai_sources
    assert 'data-ai-admin-area="retrieval"' in admin_ai_sources
    assert 'data-ai-admin-area="answers"' in admin_ai_sources
    assert 'data-ai-admin-area="jobs"' in admin_ai_sources
    assert 'data-ai-admin-area="data-sources"' in admin_ai_sources
    assert 'data-ai-admin-area="training"' in admin_ai_sources
    assert "data-ai-source-test-form" in admin_ai_sources
    assert "data-ai-prompt-version-form" in admin_ai_sources
    assert "data-ai-faq-form" in admin_ai_sources
    assert "data-ai-knowledge-upload" in admin_ai_sources
    assert "data-ai-reindex" in admin_ai_sources
    assert "data-ai-debug-request" in admin_ai_sources


def test_react_shell_islands_share_mount_and_runtime_helpers():
    """Verify shell islands use mount events without legacy fallback cloning."""
    shell_loaders = (REPO_ROOT / "app" / "static" / "pages" / "dashboard-island.js",)
    behavior_loaders = (
        REPO_ROOT / "app" / "static" / "pages" / "admin-ai-island.js",
        REPO_ROOT / "app" / "static" / "pages" / "handover-island.js",
        REPO_ROOT / "app" / "static" / "pages" / "shiftplans-island.js",
    )
    legacy_shell_hook = REPO_ROOT / "frontend" / "src" / "app" / "useFallbackShellIsland.ts"
    legacy_shell_clone = REPO_ROOT / "frontend" / "src" / "app" / "fallbackShell.ts"
    loader_source = (REPO_ROOT / "app" / "static" / "pages" / "react-island-loader.js").read_text(
        encoding="utf-8"
    )
    frontend_sources = "\n".join(
        path.read_text(encoding="utf-8") for path in (REPO_ROOT / "frontend" / "src").rglob("*.tsx")
    )

    assert not legacy_shell_hook.exists()
    assert not legacy_shell_clone.exists()
    assert "useFallbackShellIsland" not in frontend_sources
    assert "cloneFallbackShell" not in frontend_sources
    assert "function initializeReactShellRuntime" in loader_source
    assert "initializeReactShellRuntime" in loader_source

    shiftplans_source = (
        REPO_ROOT / "frontend" / "src" / "shiftplans" / "ShiftplansApp.tsx"
    ).read_text(encoding="utf-8")
    assert "markIslandMounted" in shiftplans_source
    assert "useFallbackShellIsland" not in shiftplans_source

    handover_source = (REPO_ROOT / "frontend" / "src" / "handover" / "HandoverApp.tsx").read_text(
        encoding="utf-8"
    )
    assert "markIslandMounted" in handover_source
    assert "useFallbackShellIsland" not in handover_source

    admin_ai_source = (REPO_ROOT / "frontend" / "src" / "admin-ai" / "AdminAiApp.tsx").read_text(
        encoding="utf-8"
    )
    assert "markIslandMounted" in admin_ai_source
    assert "useFallbackShellIsland" not in admin_ai_source

    for shell_loader in shell_loaders:
        source = shell_loader.read_text(encoding="utf-8")
        assert "initializeReactShellRuntime" in source
        assert "waitForReactIsland" not in source

    for behavior_loader in behavior_loaders:
        source = behavior_loader.read_text(encoding="utf-8")
        assert "initializeReactShellRuntime" not in source
        assert "waitForReactIsland" in source


def test_dashboard_react_markup_replaces_fallback_clone():
    """Verify the dashboard shell is rendered by React instead of cloned from fallback."""
    dashboard_app = (REPO_ROOT / "frontend" / "src" / "dashboard" / "DashboardApp.tsx").read_text(
        encoding="utf-8"
    )
    dashboard_markup = (
        REPO_ROOT / "frontend" / "src" / "dashboard" / "DashboardMarkup.tsx"
    ).read_text(encoding="utf-8")
    dashboard_assets = (
        REPO_ROOT / "frontend" / "src" / "dashboard" / "DashboardAssetStatus.tsx"
    ).read_text(encoding="utf-8")
    dashboard_hero = (REPO_ROOT / "frontend" / "src" / "dashboard" / "DashboardHero.tsx").read_text(
        encoding="utf-8"
    )
    dashboard_hidden_forms = (
        REPO_ROOT / "frontend" / "src" / "dashboard" / "DashboardHiddenForms.tsx"
    ).read_text(encoding="utf-8")
    dashboard_kpis = (REPO_ROOT / "frontend" / "src" / "dashboard" / "DashboardKpis.tsx").read_text(
        encoding="utf-8"
    )
    dashboard_operations = (
        REPO_ROOT / "frontend" / "src" / "dashboard" / "DashboardOperations.tsx"
    ).read_text(encoding="utf-8")
    dashboard_shift_people = (
        REPO_ROOT / "frontend" / "src" / "dashboard" / "DashboardShiftPeople.tsx"
    ).read_text(encoding="utf-8")
    dashboard_side_column = (
        REPO_ROOT / "frontend" / "src" / "dashboard" / "DashboardSideColumn.tsx"
    ).read_text(encoding="utf-8")
    dashboard_tasks = (
        REPO_ROOT / "frontend" / "src" / "dashboard" / "DashboardTaskOverview.tsx"
    ).read_text(encoding="utf-8")
    dashboard_task_modal = (
        REPO_ROOT / "frontend" / "src" / "dashboard" / "DashboardTaskDetailModal.tsx"
    ).read_text(encoding="utf-8")
    dashboard_technical = (
        REPO_ROOT / "frontend" / "src" / "dashboard" / "DashboardTechnicalDetails.tsx"
    ).read_text(encoding="utf-8")
    dashboard_react_sources = "\n".join(
        (
            dashboard_markup,
            dashboard_assets,
            dashboard_hero,
            dashboard_hidden_forms,
            dashboard_kpis,
            dashboard_operations,
            dashboard_shift_people,
            dashboard_side_column,
            dashboard_tasks,
            dashboard_task_modal,
            dashboard_technical,
        )
    )

    assert "DashboardMarkup" in dashboard_app
    assert "markIslandMounted" in dashboard_app
    assert "useFallbackShellIsland" not in dashboard_app
    assert "cloneFallbackShell" not in dashboard_app
    assert "DASHBOARD_REMAINDER_MARKUP" not in dashboard_markup
    assert "dangerouslySetInnerHTML" not in dashboard_react_sources
    assert "data-dashboard-static-shell" in dashboard_markup
    assert "DashboardHero" in dashboard_markup
    assert "DashboardKpis" in dashboard_markup
    assert "DashboardOperations" in dashboard_markup
    assert "DashboardShiftPeople" in dashboard_markup
    assert "DashboardSideColumn" in dashboard_markup
    assert "DashboardTaskOverview" in dashboard_markup
    assert "DashboardAssetStatus" in dashboard_markup
    assert "DashboardTechnicalDetails" in dashboard_markup
    assert "DashboardHiddenForms" in dashboard_markup
    assert "DashboardTaskDetailModal" in dashboard_markup
    assert "data-ai-ops-cockpit" in dashboard_react_sources
    assert "data-dashboard-critical-count" in dashboard_react_sources
    assert "data-dashboard-critical-today" in dashboard_react_sources
    assert "data-dashboard-priority-list" in dashboard_react_sources
    assert "data-dashboard-task-board" in dashboard_react_sources
    assert "data-dashboard-error-stats" in dashboard_react_sources
    assert "data-dashboard-frequent-codes" in dashboard_react_sources
    assert "data-dashboard-machine-strip" in dashboard_react_sources
    assert "data-dashboard-machine-cards" in dashboard_react_sources
    assert "data-dashboard-calendar-message" in dashboard_react_sources
    assert "data-dashboard-calendar-employee" in dashboard_react_sources
    assert "data-dashboard-shift-timeline" in dashboard_react_sources
    assert "data-dashboard-shift-calendar" in dashboard_react_sources
    assert "data-dashboard-handover-list" in dashboard_react_sources
    assert "data-dashboard-people-hints" in dashboard_react_sources
    assert "data-dashboard-employee-overview" in dashboard_react_sources
    assert "data-operations-insights-status" in dashboard_react_sources
    assert "data-operations-site-filter" in dashboard_react_sources
    assert "data-operations-range-filter" in dashboard_react_sources
    assert "data-operations-refresh" in dashboard_react_sources
    assert "data-operations-kpi-grid" in dashboard_react_sources
    assert "data-operations-drilldown" in dashboard_react_sources
    assert "data-daily-briefing-card" in dashboard_react_sources
    assert "data-daily-briefing-summary" in dashboard_react_sources
    assert "data-daily-briefing-list" in dashboard_react_sources
    assert "data-dashboard-activity-feed" in dashboard_react_sources
    assert "data-dashboard-inventory-stats" in dashboard_react_sources
    assert "data-dashboard-inventory-shortages" in dashboard_react_sources
    assert "data-ai-ops-priority-rail" in dashboard_react_sources
    assert "data-ai-system-rail" in dashboard_react_sources
    assert "data-ai-risk-radar" in dashboard_react_sources
    assert "data-ai-knowledge-health" in dashboard_react_sources
    assert "data-dashboard-warning-feed" in dashboard_react_sources
    assert "data-dashboard-index-status" in dashboard_react_sources
    assert "data-dashboard-knowledge-gap-count" in dashboard_react_sources
    assert "data-dashboard-retrieval-health" in dashboard_react_sources
    assert "data-dashboard-low-confidence-count" in dashboard_react_sources
    assert "data-cockpit-suggest-form" in dashboard_react_sources
    assert "data-cockpit-draft" in dashboard_react_sources
    assert "data-cockpit-message" in dashboard_react_sources
    assert "data-dashboard-task-count" in dashboard_react_sources
    assert "data-dashboard-briefing-count" in dashboard_react_sources
    assert "data-task-detail-modal" in dashboard_react_sources
    assert "data-report-options" in dashboard_react_sources
    assert "data-report-field" in dashboard_react_sources
    assert "data-task-start-button" in dashboard_react_sources
    assert "data-task-complete-button" in dashboard_react_sources


def test_ci_and_docker_build_react_assets():
    """Verify automated builds create React assets instead of committing them."""
    ci_workflow = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "npm --prefix frontend ci" in ci_workflow
    assert "npm run check:react" in ci_workflow
    assert "npm run build:react" in ci_workflow
    assert "FROM node:22-slim AS frontend-build" in dockerfile
    assert "COPY --from=frontend-build /build/app/static/react ./app/static/react" in dockerfile
    assert "/app/static/react/" in gitignore


def test_loaded_static_assets_exist(client):
    """Verify the base template references only static assets that Flask can serve."""
    html = client.get("/").get_data(as_text=True)
    expected_assets = (
        "/static/css/output.css",
        "/static/core/feature-registry.js",
        "/static/core/action-dialogs.js",
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
        "/static/chat/session.js",
        "/static/chat/evidence.js",
        "/static/chat/rendering.js",
        "/static/chat/history.js",
        "/static/chat/actions.js",
        "/static/pages/workflows.js",
        "/static/pages/workflows/shared.js",
        "/static/pages/workflows/dashboard-shifts.js",
        "/static/pages/workflows/dashboard.js",
        "/static/pages/dashboard-island.js",
        *DASHBOARD_SPLIT_ASSETS,
        "/static/pages/workflows/tasks.js",
        "/static/pages/react-island-loader.js",
        "/static/pages/tasks-island.js",
        "/static/pages/workflows/errors.js",
        "/static/pages/errors-island.js",
        "/static/pages/workflows/machines.js",
        "/static/pages/workflows/machine-profile.js",
        "/static/pages/machines-island.js",
        "/static/pages/workflows/documents.js",
        "/static/pages/documents-island.js",
        "/static/pages/workflows/admin-users.js",
        "/static/pages/admin-users-island.js",
        "/static/pages/workflows/employees.js",
        "/static/pages/employees-island.js",
        "/static/pages/workflows/vacations.js",
        "/static/pages/vacations-island.js",
        "/static/pages/workflows/inventory.js",
        "/static/pages/inventory-island.js",
        "/static/pages/workflows/legacy-shiftplans.js",
        "/static/pages/login.js",
        "/static/pages/admin-ai-island.js",
        "/static/pages/admin-ai.js",
        "/static/pages/admin-ai/shared.js",
        "/static/pages/admin-ai/overview.js",
        "/static/pages/admin-ai/knowledge.js",
        "/static/pages/admin-ai/retrieval.js",
        "/static/pages/admin-ai/observability.js",
        "/static/pages/admin-ai/operations.js",
        "/static/pages/admin-ai/actions.js",
        "/static/pages/handover.js",
        "/static/pages/handover-island.js",
        "/static/pages/shiftplans.js",
        "/static/pages/shiftplans-island.js",
        *SHIFTPLAN_SPLIT_ASSETS,
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


def test_shiftplans_page_prerenders_shift_model_options(client):
    """Verify the shift model dropdown is usable before async API refresh."""
    html = client.get("/shiftplans").get_data(as_text=True)

    assert 'id="sp-shift-model"' in html
    assert "Schichtmodelle werden geladen" not in html
    assert 'value="one_shift"' in html
    assert 'value="vollkonti_5"' in html
    assert "data-shifts-summary" in html


def test_shiftplans_script_uses_selected_option_as_model_fallback(client):
    """Verify selected model lookup does not depend only on async cache state."""
    script = shiftplans_runtime_text(client)

    assert "if (!shiftModels.length) shiftModels = readShiftModelsFromSelect();" in script
    assert "selectedOption.dataset.displayName" in script
    assert "key: selectedOption.value" in script


def test_shiftplans_script_renders_generated_plan_before_list_refresh(client):
    """Verify a generated draft remains visible even if list reload is stale."""
    script = shiftplans_runtime_text(client)

    assert "async function loadPlans(selectId, fallbackPlan)" in script
    assert "allPlans.unshift(fallbackPlan)" in script
    assert "function selectedPlanIndex(selectId)" in script
    assert "renderPlan(result)" in script


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

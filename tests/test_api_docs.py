"""Tests for OpenAPI documentation and demo setup entry points."""


def test_openapi_json_documents_core_endpoints(client):
    """Verify the OpenAPI JSON exposes the documented production endpoints."""
    response = client.get("/api/swagger.json")

    assert response.status_code == 200
    spec = response.get_json()
    paths = spec["paths"]

    assert spec["openapi"].startswith("3.")
    assert "/api/v1/auth/login" in paths
    assert "/api/v1/auth/register" in paths
    assert "/api/v1/tasks" in paths
    assert "/api/v1/tasks/{task_id}/start" in paths
    assert "/api/v1/tasks/{task_id}/complete" in paths
    assert "/api/v1/errors/search" in paths
    assert "/api/v1/errors/similar" in paths
    assert "/api/v1/ai/daily-briefing" in paths
    assert "/api/v1/machines/{machine_id}/assistant" in paths
    assert "/api/v1/inventory/forecast" in paths


def test_openapi_examples_are_present(client):
    """Verify important endpoints include concise example payloads."""
    spec = client.get("/api/swagger.json").get_json()

    task_example = spec["paths"]["/api/v1/tasks"]["post"]["requestBody"]["content"][
        "application/json"
    ]["example"]
    briefing_example = spec["paths"]["/api/v1/ai/daily-briefing"]["get"]["responses"][
        "200"
    ]["content"]["application/json"]["example"]

    assert task_example["title"]
    assert task_example["priority"] == "urgent"
    assert briefing_example["sections"]


def test_swagger_ui_route_loads(client):
    """Verify the Swagger UI or local fallback page is reachable."""
    response = client.get("/swagger/", follow_redirects=True)

    assert response.status_code == 200
    assert b"Swagger" in response.data


def test_api_docs_page_links_to_swagger(client):
    """Verify the developer docs page points to Swagger and OpenAPI JSON."""
    response = client.get("/api-docs")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "/swagger/" in body
    assert "/api/swagger.json" in body

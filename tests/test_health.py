"""Health endpoint tests."""

from app.models import Role


def test_public_health_endpoint(client):
    """Verify the unauthenticated health endpoint is available for probes."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_liveness_endpoint(client):
    """Verify the public liveness endpoint is available for container probes."""
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_readiness_endpoint_reports_database_ai_and_rag(client):
    """Verify readiness includes database, AI, and RAG diagnostics."""
    response = client.get("/health/ready")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["status"] == "ok"
    assert payload["components"]["database"]["ok"] is True
    assert payload["components"]["database"]["schema"]["ok"] is True
    assert payload["components"]["ai"]["provider"]
    assert "rag" in payload["components"]
    assert "vector_store" in payload["components"]["rag"]


def test_operations_health_requires_master_admin(client, make_user, auth_headers):
    """Verify operations metrics are exposed only to master admins."""
    admin = make_user(
        username="ops_health_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    user = make_user(
        username="ops_health_user",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )

    forbidden_response = client.get(
        "/api/v1/health/operations",
        headers=auth_headers(user["username"]),
    )
    response = client.get(
        "/api/v1/health/operations",
        headers=auth_headers(admin["username"]),
    )
    payload = response.get_json()["data"]

    assert forbidden_response.status_code == 403
    assert response.status_code == 200
    assert payload["database"]["ok"] is True
    assert "background_jobs" in payload
    assert "slow_endpoints" in payload["requests"]

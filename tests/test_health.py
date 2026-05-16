"""Health endpoint tests."""


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

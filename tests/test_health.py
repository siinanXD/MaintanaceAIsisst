"""Health endpoint tests."""


def test_public_health_endpoint(client):
    """Verify the unauthenticated health endpoint is available for probes."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}

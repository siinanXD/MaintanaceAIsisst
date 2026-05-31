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
    assert isinstance(payload["degraded_components"], list)
    assert payload["ready"] == (payload["degraded_components"] == [])
    assert payload["components"]["database"]["ok"] is True
    assert payload["components"]["database"]["schema"]["ok"] is True
    assert payload["components"]["ai"]["provider"]
    assert payload["components"]["ai"]["ok"] is True
    assert payload["components"]["ai"]["mode"] == "local_fallback"
    assert payload["components"]["ai"]["embedding_provider"]["provider"] == "hashing"
    assert payload["components"]["ai"]["embedding_provider"]["ready"] is True
    assert "rag" in payload["components"]
    assert "vector_store" in payload["components"]["rag"]
    if payload["components"]["rag"]["ok"]:
        assert payload["components"]["rag"]["reason"] == ""
        assert "rag" not in payload["degraded_components"]
    else:
        assert payload["components"]["rag"]["reason"]
        assert "rag" in payload["degraded_components"]


def test_readiness_rag_probe_reports_disabled_rag_as_degraded(app, client):
    """Verify disabled RAG is reported as a degraded readiness component."""
    with app.app_context():
        app.config["RAG_ENABLED"] = False

    response = client.get("/health/ready")
    payload = response.get_json()
    rag = payload["components"]["rag"]

    assert response.status_code == 200
    assert payload["ready"] is False
    assert "rag" in payload["degraded_components"]
    assert rag["ok"] is False
    assert rag["enabled"] is False
    assert rag["ready"] is False
    assert rag["reason"]


def test_readiness_ai_probe_requires_openai_compatible_base_url(app, client):
    """Verify OpenAI-compatible readiness mirrors AI provider status."""
    with app.app_context():
        app.config["AI_PROVIDER"] = "openai_compatible"
        app.config["OPENAI_API_KEY"] = "test-key"
        app.config["AI_BASE_URL"] = ""

    response = client.get("/health/ready")
    payload = response.get_json()
    ai = payload["components"]["ai"]

    assert response.status_code == 200
    assert payload["ready"] is False
    assert "ai" in payload["degraded_components"]
    assert ai["ok"] is False
    assert ai["mode"] == "openai_compatible"
    assert ai["reason"] == "base_url_missing"
    assert ai["base_url_configured"] is False
    assert ai["effective_provider"] == "mock"
    assert ai["configuration_action"] == "set_ai_base_url"
    assert "AI_BASE_URL" in ai["recommended_action"]


def test_readiness_ai_probe_treats_blank_api_key_as_missing(app, client):
    """Verify blank API key text does not mark external AI providers as ready."""
    with app.app_context():
        app.config["AI_PROVIDER"] = "openai"
        app.config["OPENAI_API_KEY"] = "   "

    response = client.get("/health/ready")
    payload = response.get_json()
    ai = payload["components"]["ai"]

    assert response.status_code == 200
    assert payload["ready"] is False
    assert "ai" in payload["degraded_components"]
    assert ai["ok"] is False
    assert ai["api_key_configured"] is False
    assert ai["reason"] == "api_key_missing"
    assert ai["effective_provider"] == "mock"
    assert ai["configuration_action"] == "set_openai_api_key"
    assert "OPENAI_API_KEY" in ai["recommended_action"]


def test_readiness_ai_probe_reports_unsupported_provider(app, client):
    """Verify unsupported providers are visible in readiness diagnostics."""
    with app.app_context():
        app.config["AI_PROVIDER"] = "gemini"
        app.config["OPENAI_API_KEY"] = "test-key"

    response = client.get("/health/ready")
    payload = response.get_json()
    ai = payload["components"]["ai"]

    assert response.status_code == 200
    assert payload["ready"] is False
    assert "ai" in payload["degraded_components"]
    assert ai["ok"] is False
    assert ai["mode"] == "unsupported"
    assert ai["reason"] == "unsupported_provider"
    assert ai["provider"] == "gemini"
    assert ai["effective_provider"] == "mock"
    assert ai["configuration_action"] == "select_supported_provider"
    assert "AI_PROVIDER" in ai["recommended_action"]


def test_readiness_ai_probe_reports_embedding_provider_readiness(app, client):
    """Verify readiness exposes embedding provider misconfiguration safely."""
    with app.app_context():
        app.config["EMBEDDING_PROVIDER"] = "openai_compatible"
        app.config["OPENAI_API_KEY"] = "test-key"
        app.config["AI_BASE_URL"] = ""

    response = client.get("/health/ready")
    payload = response.get_json()
    ai = payload["components"]["ai"]
    embedding = ai["embedding_provider"]

    assert response.status_code == 200
    assert payload["ready"] is False
    assert "ai" in payload["degraded_components"]
    assert ai["ok"] is False
    assert ai["reason"] == "embedding_base_url_missing"
    assert ai["configuration_action"] == "set_ai_base_url"
    assert "AI_BASE_URL" in ai["recommended_action"]
    assert embedding["provider"] == "openai_compatible"
    assert embedding["ready"] is False
    assert embedding["reason"] == "base_url_missing"
    assert embedding["base_url_configured"] is False
    assert embedding["configuration_action"] == "set_ai_base_url"
    assert "AI_BASE_URL" in embedding["recommended_action"]
    assert "test-key" not in str(ai)


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

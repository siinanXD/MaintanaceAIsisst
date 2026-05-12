"""Tests for AI feature endpoints and services."""

from datetime import date, timedelta
from io import BytesIO

import pytest

from app.extensions import db
from app.models import AIAuditEvent, GeneratedDocument, Priority, Role, Task
from app.services.ai_audit_service import create_ai_audit_event
from app.services.ai_routing import estimate_cost_usd, workflow_profile
from app.services.ai_service import AIServiceError
from app.services.document_service import document_path


def test_ai_chat_returns_today_tasks_without_openai(
    client,
    make_user,
    make_task,
    auth_headers,
):
    """Verify the chat endpoint answers today's task questions locally."""
    user = make_user(username="ai_today_user")
    make_task("Task fuer heute", creator_username=user["username"])

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Welche Tasks stehen heute an?"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["type"] == "tasks_today"
    assert payload["diagnostics"]["status"] == "local_answer"
    assert payload["data"][0]["title"] == "Task fuer heute"


def test_ai_chat_rejects_empty_messages(client, make_user, auth_headers):
    """Verify chat input validation rejects blank messages."""
    user = make_user(username="ai_empty_user")

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "   "},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "message_is_required"
    assert response.get_json()["message"] == "message is required"


def test_ai_chat_denies_requested_scope_with_admin_hint(
    client,
    make_user,
    set_dashboard_permission,
    auth_headers,
):
    """Verify the global assistant explains missing requested permissions."""
    user = make_user(username="ai_denied_employee_user")
    set_dashboard_permission(user["username"], "employees", can_view=False)

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Welche Mitarbeiter sind heute verfuegbar?"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["type"] == "permission_denied"
    assert payload["diagnostics"]["status"] == "permission_denied"
    assert "Mitarbeiter" in payload["answer"]
    assert "Admin" in payload["answer"]


def test_ai_chat_answers_machine_scope_without_error_fallback(
    client,
    make_user,
    make_machine,
    auth_headers,
):
    """Verify broad machine questions are handled as assistant requests."""
    user = make_user(username="ai_machine_scope_user", role=Role.INSTANDHALTUNG)
    make_machine(name="Anlage Chat", produced_item="Deckel")

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Welche Maschinen sind sichtbar?"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["type"] == "assistant"
    assert payload["diagnostics"]["status"] == "local_answer"
    assert payload["data"]["machines"][0]["name"] == "Anlage Chat"


def test_ai_chat_employee_context_respects_basic_access(
    client,
    make_user,
    make_employee,
    set_dashboard_permission,
    auth_headers,
):
    """Verify assistant employee context follows configured access levels."""
    user = make_user(username="ai_employee_basic_user")
    make_employee(name="Anna Chat", salary_group="E9")
    set_dashboard_permission(
        user["username"],
        "employees",
        can_view=True,
        can_write=False,
        employee_access_level="basic",
    )

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Welche Mitarbeiterdaten darf ich sehen?"},
    )

    employee_payload = response.get_json()["data"]["employees"][0]
    assert response.status_code == 200
    assert employee_payload["name"] == "Anna Chat"
    assert "salary_group" not in employee_payload
    assert "city" not in employee_payload


def test_ai_chat_returns_sources_and_audit_metadata(
    app,
    client,
    make_user,
    make_machine,
    auth_headers,
):
    """Verify chat responses include sources and metadata-only audit records."""
    user = make_user(username="ai_sources_user", role=Role.INSTANDHALTUNG)
    make_machine(name="Anlage Quelle", produced_item="Deckel")

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Welche Maschinen sind sichtbar?"},
    )

    payload = response.get_json()
    audit_id = payload["diagnostics"]["audit_event_id"]
    assert response.status_code == 200
    assert payload["sources"][0]["type"] == "machine"
    assert payload["diagnostics"]["source_count"] == len(payload["sources"])

    with app.app_context():
        event = db.session.get(AIAuditEvent, audit_id)
        assert event is not None
        assert event.workflow == "assistant"
        assert event.source_count == len(payload["sources"])
        assert not hasattr(event, "prompt")
        assert not hasattr(event, "response")


def test_ai_chat_returns_task_action_preview_without_writing(
    app,
    client,
    make_user,
    auth_headers,
):
    """Verify the assistant returns read-only task previews for form filling."""
    user = make_user(username="ai_preview_user", role=Role.INSTANDHALTUNG)

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Task erstellen: Maschine 3 macht laute Geraeusche"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["action_preview"]["type"] == "task_draft"
    assert payload["action_preview"]["target"] == "tasks"
    assert payload["action_preview"]["payload"]["status"] == "open"
    with app.app_context():
        assert Task.query.count() == 0


def test_ai_chat_answers_machine_count_without_action_preview(
    client,
    make_user,
    make_machine,
    auth_headers,
):
    """Verify explicit machine count questions return direct local answers."""
    user = make_user(username="ai_machine_count_user", role=Role.INSTANDHALTUNG)
    make_machine(name="Anlage Count 1")
    make_machine(name="Anlage Count 2")

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "wie vile maschinen?"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["type"] == "machines_count"
    assert payload["data"]["count"] == 2
    assert "Gesamt" in payload["answer"]
    assert "action_preview" not in payload


def test_ai_chat_answers_admin_user_count_permission_aware(
    client,
    make_user,
    auth_headers,
):
    """Verify user count is only answered from Admin Users permission."""
    admin = make_user(
        username="ai_user_count_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    user = make_user(username="ai_user_count_normal")

    admin_response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(admin["username"]),
        json={"message": "wie viele user gibt es"},
    )
    user_response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "wie viele user gibt es"},
    )

    admin_payload = admin_response.get_json()
    user_payload = user_response.get_json()
    assert admin_response.status_code == 200
    assert admin_payload["type"] == "admin_users_count"
    assert admin_payload["data"]["count"] == 2
    assert user_response.status_code == 200
    assert user_payload["type"] == "permission_denied"
    assert "Admin" in user_payload["answer"]


def test_ai_chat_uses_hybrid_general_mode_for_non_app_questions(
    client,
    make_user,
    auth_headers,
):
    """Verify general questions get short hybrid answers with tracking notice."""
    user = make_user(username="ai_general_chat_user")

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Was ist die Hauptstadt von Japan?"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["type"] == "general_chat"
    assert payload["diagnostics"]["workflow"] == "general_chat"
    assert payload["sources"] == []
    assert "protokolliert" in payload["answer"]
    assert "Datenbank" not in payload["answer"]


def test_ai_chat_treats_concept_questions_as_general_chat(
    client,
    make_user,
    auth_headers,
):
    """Verify generic concept questions are not blocked as protected app data."""
    user = make_user(username="ai_concept_chat_user")

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Was ist ein User?"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["type"] == "general_chat"
    assert payload["diagnostics"]["workflow"] == "general_chat"
    assert payload["sources"] == []
    assert "Keine Berechtigung" not in payload["answer"]


def test_ai_chat_general_question_uses_openai_answer_with_tracking_notice(
    client,
    make_user,
    auth_headers,
    monkeypatch,
):
    """Verify successful general chat returns the provider answer plus tracking notice."""

    class SuccessfulGeneralProvider:
        """Fake provider for deterministic general chat tests."""

        name = "openai"
        last_call_metadata = {
            "provider": "openai",
            "workflow": "general_chat",
            "model": "test-general-model",
        }

        def answer_general_question(self, question):
            """Return a deterministic provider answer."""
            return "## Antwort\n- **Kurz:** Tokio"

    user = make_user(username="ai_openai_general_user")
    monkeypatch.setattr(
        "app.ai.services.get_ai_provider",
        lambda: SuccessfulGeneralProvider(),
    )

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Was ist die Hauptstadt von Japan?"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["type"] == "general_chat"
    assert payload["diagnostics"]["status"] == "openai_used"
    assert payload["answer"].count("protokolliert") == 1
    assert "Tokio" in payload["answer"]
    assert "Lokaler Fallback" not in payload["answer"]


def test_ai_chat_general_fallback_explains_missing_openai_key(
    app,
    client,
    make_user,
    auth_headers,
):
    """Verify general chat reacts clearly when OpenAI is selected without a key."""
    user = make_user(username="ai_missing_key_chat_user")
    app.config["AI_PROVIDER"] = "openai"
    app.config["OPENAI_API_KEY"] = ""

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Was ist die Hauptstadt von Japan?"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["type"] == "general_chat"
    assert payload["diagnostics"]["status"] == "api_key_missing"
    assert payload["diagnostics"]["fallback_used"] is True
    assert "OPENAI_API_KEY" in payload["answer"]
    assert payload["answer"].count("protokolliert") == 1
    assert "Lokaler Fallback" not in payload["answer"]
    assert "Quelle:" not in payload["answer"]


def test_ai_chat_general_openai_error_returns_short_tracked_message(
    client,
    make_user,
    auth_headers,
    monkeypatch,
):
    """Verify provider failures do not create duplicate visible fallback text."""

    class FailingGeneralProvider:
        """Fake provider that simulates an OpenAI text failure."""

        name = "openai"
        last_call_metadata = {
            "provider": "openai",
            "workflow": "general_chat",
            "model": "test-general-model",
        }

        def answer_general_question(self, question):
            """Raise the provider error expected by the chat service."""
            raise AIServiceError("provider failed")

    user = make_user(username="ai_openai_error_general_user")
    monkeypatch.setattr(
        "app.ai.services.get_ai_provider",
        lambda: FailingGeneralProvider(),
    )

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Wie ist das Wetter heute?"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["type"] == "general_chat"
    assert payload["diagnostics"]["status"] == "openai_error"
    assert payload["diagnostics"]["fallback_used"] is True
    assert payload["answer"].count("protokolliert") == 1
    assert "OpenAI ist gerade nicht erreichbar" in payload["answer"]
    assert "Lokaler Fallback" not in payload["answer"]
    assert "Quelle:" not in payload["answer"]


def test_ai_chat_general_model_error_is_diagnosed(
    client,
    make_user,
    auth_headers,
    monkeypatch,
):
    """Verify unavailable models are exposed as a precise safe diagnostic."""

    class ModelErrorProvider:
        """Fake provider that simulates a model access error."""

        name = "openai"
        last_call_metadata = {
            "provider": "openai",
            "workflow": "general_chat",
            "model": "blocked-model",
        }

        def answer_general_question(self, question):
            """Raise a model diagnostic error."""
            raise AIServiceError("provider failed", error_code="model_not_found")

    user = make_user(username="ai_model_error_general_user")
    monkeypatch.setattr(
        "app.ai.services.get_ai_provider",
        lambda: ModelErrorProvider(),
    )

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Was ist ein User?"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["type"] == "general_chat"
    assert payload["diagnostics"]["status"] == "openai_error"
    assert payload["diagnostics"]["error"] == "model_not_found"
    assert "Modell" in payload["answer"]
    assert payload["answer"].count("protokolliert") == 1


def test_admin_ai_summary_is_admin_only(
    client,
    make_user,
    auth_headers,
):
    """Verify AI analytics summary is restricted to master admins."""
    admin = make_user(
        username="ai_summary_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    user = make_user(username="ai_summary_user")

    forbidden_response = client.get(
        "/api/v1/admin/ai/summary",
        headers=auth_headers(user["username"]),
    )
    admin_response = client.get(
        "/api/v1/admin/ai/summary",
        headers=auth_headers(admin["username"]),
    )

    assert forbidden_response.status_code == 403
    assert admin_response.status_code == 200
    assert set(admin_response.get_json().keys()) >= {
        "average_latency_ms",
        "estimated_cost_usd",
        "events_total",
        "fallback_count",
        "feedback",
        "latest_events",
        "total_tokens",
        "workflow_metrics",
    }


def test_ai_workflow_routing_uses_balanced_defaults(app):
    """Verify workflow routing selects models, temperature and output budgets."""
    with app.app_context():
        app.config["OPENAI_MODEL_FAST"] = "fast-test-model"
        app.config["OPENAI_MODEL_BALANCED"] = "balanced-test-model"
        app.config["OPENAI_MODEL_QUALITY"] = "quality-test-model"

        task_profile = workflow_profile("task_suggestion")
        chat_profile = workflow_profile("chat")
        quality_profile = workflow_profile("quality_analysis")

    assert task_profile.model == "fast-test-model"
    assert task_profile.tier == "fast"
    assert task_profile.temperature == 0.1
    assert chat_profile.model == "balanced-test-model"
    assert chat_profile.tier == "balanced"
    assert chat_profile.max_tokens == 750
    assert quality_profile.model == "quality-test-model"
    assert quality_profile.tier == "quality"


def test_ai_workflow_routing_falls_back_to_configured_model(app):
    """Verify missing tier overrides use the configured base model."""
    with app.app_context():
        for key in ("OPENAI_MODEL_FAST", "OPENAI_MODEL_BALANCED", "OPENAI_MODEL_QUALITY"):
            app.config.pop(key, None)

        task_profile = workflow_profile("task_suggestion")
        chat_profile = workflow_profile("chat")
        quality_profile = workflow_profile("quality_analysis")

    assert task_profile.model == "test-model"
    assert chat_profile.model == "test-model"
    assert quality_profile.model == "test-model"


def test_ai_audit_stores_usage_metrics_without_content(app, monkeypatch):
    """Verify audit events store usage metadata but no prompts or answers."""
    monkeypatch.setenv("AI_PRICE_TEST_MODEL_INPUT_PER_1M", "1")
    monkeypatch.setenv("AI_PRICE_TEST_MODEL_OUTPUT_PER_1M", "2")

    with app.app_context():
        cost = estimate_cost_usd("test-model", 1000, 500)
        event_id = create_ai_audit_event(
            None,
            "assistant",
            {
                "status": "openai_used",
                "provider": "openai",
                "model": "test-model",
                "model_tier": "balanced",
                "temperature": 0.2,
                "latency_ms": 123,
                "input_tokens": 1000,
                "output_tokens": 500,
                "cached_tokens": 0,
                "total_tokens": 1500,
                "estimated_cost_usd": cost,
            },
        )
        event = db.session.get(AIAuditEvent, event_id)
        assert event.model == "test-model"
        assert event.model_tier == "balanced"
        assert event.temperature == 0.2
        assert event.latency_ms == 123
        assert event.input_tokens == 1000
        assert event.output_tokens == 500
        assert event.estimated_cost_usd == 0.002
        assert not hasattr(event, "prompt")
        assert not hasattr(event, "response")


def test_ai_feedback_validates_rating_and_required_text(
    client,
    make_user,
    auth_headers,
):
    """Verify AI feedback validation and persistence response shape."""
    user = make_user(username="ai_feedback_user")
    headers = auth_headers(user["username"])

    invalid_rating = client.post(
        "/api/v1/ai/feedback",
        headers=headers,
        json={"prompt": "p", "response": "r", "rating": "ok"},
    )
    missing_text = client.post(
        "/api/v1/ai/feedback",
        headers=headers,
        json={"rating": "helpful", "prompt": "", "response": "r"},
    )
    valid_response = client.post(
        "/api/v1/ai/feedback",
        headers=headers,
        json={
            "prompt": "Was bedeutet E104?",
            "response": "Sensor pruefen",
            "rating": "helpful",
            "comment": "Passt",
        },
    )

    assert invalid_rating.status_code == 400
    assert missing_text.status_code == 400
    assert valid_response.status_code == 201
    assert valid_response.get_json()["rating"] == "helpful"


def test_ai_status_is_admin_only_and_redacted(client, make_user, auth_headers):
    """Verify AI status requires admin access and never exposes API keys."""
    admin = make_user(
        username="ai_status_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    user = make_user(username="ai_status_user")

    forbidden_response = client.get(
        "/api/v1/ai/status",
        headers=auth_headers(user["username"]),
    )
    admin_response = client.get(
        "/api/v1/ai/status",
        headers=auth_headers(admin["username"]),
    )

    assert forbidden_response.status_code == 403
    assert admin_response.status_code == 200
    assert "api_key" not in str(admin_response.get_json()).lower().replace(
        "api_key_configured",
        "",
    )
    assert admin_response.get_json()["api_key_configured"] is False


def test_daily_briefing_respects_permissions_and_uses_local_fallback(
    client,
    make_user,
    make_task,
    make_error_entry,
    auth_headers,
):
    """Verify daily briefing returns only permitted local sections."""
    user = make_user(
        username="briefing_user",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )
    make_task(
        "Ueberfaelliger Task",
        creator_username=user["username"],
        department_name="Produktion",
        priority=Priority.URGENT,
        due_date_value=date.today() - timedelta(days=1),
    )
    make_error_entry(
        "Anlage Briefing",
        "E555",
        "Neuer Fehler",
        department_name="Produktion",
    )

    response = client.get(
        "/api/v1/ai/daily-briefing",
        headers=auth_headers(user["username"]),
    )

    payload = response.get_json()
    section_types = {section["type"] for section in payload["sections"]}
    assert response.status_code == 200
    assert payload["diagnostics"]["status"] == "local_answer"
    assert "tasks" in section_types
    assert "errors" in section_types
    assert "documents" not in section_types


def test_daily_briefing_returns_no_sections_without_permissions(
    client,
    make_user,
    make_task,
    make_error_entry,
    set_dashboard_permission,
    auth_headers,
):
    """Verify daily briefing does not expose sections without dashboard rights."""
    user = make_user(
        username="briefing_no_rights_user",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )
    make_task(
        "Verdeckter Briefing Task",
        creator_username=user["username"],
        department_name="Produktion",
        priority=Priority.URGENT,
        due_date_value=date.today() - timedelta(days=1),
    )
    make_error_entry(
        "Anlage Briefing Sperre",
        "E556",
        "Verdeckter Fehler",
        department_name="Produktion",
    )
    set_dashboard_permission(user["username"], "tasks", can_view=False)
    set_dashboard_permission(user["username"], "errors", can_view=False)

    response = client.get(
        "/api/v1/ai/daily-briefing",
        headers=auth_headers(user["username"]),
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["sections"] == []
    assert payload["summary"] == "Heute sind keine kritischen Hinweise sichtbar."


def test_dashboard_contains_daily_briefing_and_priority_ui(client):
    """Verify dashboard exposes briefing and task priority UI hooks."""
    response = client.get("/")
    script_response = client.get("/static/app.js")
    chat_response = client.get("/static/chat.js")
    html = response.get_data(as_text=True)
    script = script_response.get_data(as_text=True)
    chat_script = chat_response.get_data(as_text=True)

    assert response.status_code == 200
    assert script_response.status_code == 200
    assert chat_response.status_code == 200
    assert "data-daily-briefing-list" in html
    assert "data-dashboard-priority-list" in html
    assert "data-chat-suggestions" in html
    assert "Briefing konnte nicht geladen werden." in script
    assert "KI-Priorisierung" in script
    assert "maintenance_ai_action_preview" in script
    assert "responseData && responseData.answer" in chat_script
    assert 'data.type === "general_chat"' in chat_script
    assert '!isGeneralChat && diagnostics.status === "api_key_missing"' in chat_script
    assert "!isGeneralChat && diagnostics.fallback_used" in chat_script
    assert "openAIErrorLabel" in chat_script
    assert "model_not_found" in chat_script
    assert "OpenAI-Rate-Limit erreicht" in chat_script
    assert "chatSuggestionsForUser" in chat_script
    assert "suggestions.hidden = true" in chat_script


def test_admin_users_page_contains_ai_analytics_ui(client):
    """Verify Admin Users exposes AI analytics UI hooks."""
    page_response = client.get("/admin/users")
    script_response = client.get("/static/app.js")
    html = page_response.get_data(as_text=True)
    script = script_response.get_data(as_text=True)

    assert page_response.status_code == 200
    assert script_response.status_code == 200
    assert "data-ai-analytics-card" in html
    assert "data-ai-latency" in html
    assert "data-ai-tokens" in html
    assert "data-ai-cost" in html
    assert "data-ai-workflows" in html
    assert "data-ai-error-categories" in html
    assert "data-audit-log-list" in html
    assert "data-backup-list" in html
    assert "data-permission-defaults" in html
    assert "/api/v1/admin/ai/summary" in script
    assert "/api/v1/admin/audit-log" in script
    assert "/api/v1/admin/backups" in script
    assert "/api/v1/admin/permissions/schema" in script


def test_document_path_rejects_storage_escape(app):
    """Verify document path resolution blocks traversal outside document storage."""
    with app.app_context():
        document = GeneratedDocument(
            task_id=1,
            document_type="maintenance_report",
            title="Bad path",
            relative_path="../outside.html",
            department="Produktion",
            machine="",
            created_by=1,
        )

        with pytest.raises(ValueError, match="escapes document storage"):
            document_path(document)


def test_generated_document_download_uses_temp_storage(
    client,
    make_user,
    make_task,
    make_document,
    auth_headers,
):
    """Verify generated documents are listed and downloaded from test storage."""
    user = make_user(
        username="document_user",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )
    task_id = make_task(
        "Dokument Task",
        creator_username=user["username"],
        department_name="Instandhaltung",
    )
    document_id = make_document(
        task_id=task_id,
        created_by=user["id"],
        department="Instandhaltung",
    )
    headers = auth_headers(user["username"])

    list_response = client.get("/api/v1/documents", headers=headers)
    download_response = client.get(
        f"/api/v1/documents/{document_id}/download",
        headers=headers,
    )

    assert list_response.status_code == 200
    assert list_response.get_json()[0]["id"] == document_id
    assert download_response.status_code == 200
    assert b"report" in download_response.data


def test_document_review_only_allows_visible_documents(
    app,
    client,
    make_user,
    make_task,
    make_document,
    auth_headers,
):
    """Verify users can only review documents visible to their department."""
    user = make_user(
        username="document_review_visible",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )
    task_id = make_task(
        "Review sichtbar",
        creator_username=user["username"],
        department_name="Instandhaltung",
    )
    visible_document_id = make_document(
        task_id=task_id,
        created_by=user["id"],
        department="Instandhaltung",
        machine="Anlage Review",
    )
    hidden_document_id = make_document(
        task_id=task_id,
        created_by=user["id"],
        relative_path="2026/05/task_hidden/maintenance_report.html",
        department="Produktion",
        machine="Anlage Review",
    )
    _write_report(
        app,
        visible_document_id,
        {
            "Maschine": "Anlage Review",
            "Ursache": "Sensor verschmutzt",
            "Durchgefuehrte Massnahme": "Sensor gereinigt",
            "Ergebnis": "Anlage laeuft stabil",
            "Notizen": "Nachkontrolle eingeplant",
        },
    )
    headers = auth_headers(user["username"])

    visible_response = client.post(
        f"/api/v1/documents/{visible_document_id}/review",
        headers=headers,
    )
    hidden_response = client.post(
        f"/api/v1/documents/{hidden_document_id}/review",
        headers=headers,
    )

    assert visible_response.status_code == 200
    assert hidden_response.status_code == 404


def test_document_review_missing_file_returns_404(
    app,
    client,
    make_user,
    make_task,
    make_document,
    auth_headers,
):
    """Verify document review reports missing files explicitly."""
    user = make_user(
        username="document_review_missing",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )
    task_id = make_task(
        "Review Datei fehlt",
        creator_username=user["username"],
        department_name="Instandhaltung",
    )
    document_id = make_document(
        task_id=task_id,
        created_by=user["id"],
        department="Instandhaltung",
    )
    _delete_document_file(app, document_id)

    response = client.post(
        f"/api/v1/documents/{document_id}/review",
        headers=auth_headers(user["username"]),
    )

    assert response.status_code == 404
    assert response.get_json()["error"] == "document_file_not_found"
    assert response.get_json()["message"] == "Document file not found"


def test_document_review_local_fallback_finds_missing_required_fields(
    app,
    client,
    make_user,
    make_task,
    make_document,
    auth_headers,
):
    """Verify local review detects incomplete maintenance report fields."""
    user = make_user(
        username="document_review_incomplete",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )
    task_id = make_task(
        "Review unvollstaendig",
        creator_username=user["username"],
        department_name="Instandhaltung",
    )
    document_id = make_document(
        task_id=task_id,
        created_by=user["id"],
        department="Instandhaltung",
    )
    _write_report(
        app,
        document_id,
        {
            "Maschine": "-",
            "Ursache": "",
            "Durchgefuehrte Massnahme": "-",
            "Ergebnis": "",
            "Notizen": "-",
        },
    )

    response = client.post(
        f"/api/v1/documents/{document_id}/review",
        headers=auth_headers(user["username"]),
    )

    payload = response.get_json()
    fields = {finding["field"] for finding in payload["findings"]}
    assert response.status_code == 200
    assert payload["diagnostics"]["status"] == "local_answer"
    assert payload["status"] == "incomplete"
    assert fields == {
        "Maschine",
        "Ursache",
        "Durchgefuehrte Massnahme",
        "Ergebnis",
        "Notizen",
    }


def test_document_review_scores_complete_report_higher(
    app,
    client,
    make_user,
    make_task,
    make_document,
    auth_headers,
):
    """Verify complete reports receive better local review scores."""
    user = make_user(
        username="document_review_score",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )
    task_id = make_task(
        "Review Score",
        creator_username=user["username"],
        department_name="Instandhaltung",
    )
    incomplete_id = make_document(
        task_id=task_id,
        created_by=user["id"],
        relative_path="2026/05/task_score_incomplete/maintenance_report.html",
        department="Instandhaltung",
    )
    complete_id = make_document(
        task_id=task_id,
        created_by=user["id"],
        relative_path="2026/05/task_score_complete/maintenance_report.html",
        department="Instandhaltung",
    )
    _write_report(
        app,
        incomplete_id,
        {
            "Maschine": "-",
            "Ursache": "-",
            "Durchgefuehrte Massnahme": "-",
            "Ergebnis": "-",
            "Notizen": "-",
        },
    )
    _write_report(
        app,
        complete_id,
        {
            "Maschine": "Anlage 12",
            "Ursache": "Druckschwankung in der Versorgung",
            "Durchgefuehrte Massnahme": "Dichtung ersetzt und Druck geprueft",
            "Ergebnis": "Anlage arbeitet wieder im Sollbereich",
            "Notizen": "Ersatzdichtung nachbestellen",
        },
    )
    headers = auth_headers(user["username"])

    incomplete_response = client.post(
        f"/api/v1/documents/{incomplete_id}/review",
        headers=headers,
    )
    complete_response = client.post(
        f"/api/v1/documents/{complete_id}/review",
        headers=headers,
    )

    assert incomplete_response.status_code == 200
    assert complete_response.status_code == 200
    assert (
        complete_response.get_json()["quality_score"]
        > incomplete_response.get_json()["quality_score"]
    )
    assert complete_response.get_json()["status"] == "good"


def test_uploaded_document_check_validates_and_reviews_file(
    client,
    make_user,
    auth_headers,
):
    """Verify uploaded document checking handles missing, invalid and valid files."""
    user = make_user(
        username="document_upload_check",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )
    headers = auth_headers(user["username"])

    missing_response = client.post("/api/v1/documents/check", headers=headers)
    invalid_response = client.post(
        "/api/v1/documents/check",
        headers=headers,
        data={"file": (BytesIO(b"binary"), "report.pdf")},
        content_type="multipart/form-data",
    )
    valid_response = client.post(
        "/api/v1/documents/check",
        headers=headers,
        data={
            "file": (
                BytesIO(
                    b"Maschine: Anlage 7\n"
                    b"Ursache: Sensor verschmutzt\n"
                    b"Durchgefuehrte Massnahme: Sensor gereinigt\n"
                    b"Ergebnis: Anlage laeuft\n"
                    b"Notizen: Nachkontrolle geplant\n"
                ),
                "report.txt",
            ),
        },
        content_type="multipart/form-data",
    )

    payload = valid_response.get_json()
    assert missing_response.status_code == 400
    assert invalid_response.status_code == 400
    assert valid_response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["diagnostics"]["status"] == "local_answer"
    assert payload["data"]["status"] == "good"


def test_documents_page_contains_review_ui(client):
    """Verify the documents page and static script expose review UI hooks."""
    page_response = client.get("/documents")
    script_response = client.get("/static/app.js")
    html = page_response.get_data(as_text=True)
    script = script_response.get_data(as_text=True)

    assert page_response.status_code == 200
    assert "data-document-review-panel" in html
    assert "data-document-review-findings" in html
    assert 'actionButton("Pruefen"' in script


def test_complete_task_can_generate_maintenance_report(
    client,
    make_user,
    make_task,
    auth_headers,
):
    """Verify completing a task can generate document metadata and a temp file."""
    user = make_user(username="report_user")
    task_id = make_task("Bericht Task", creator_username=user["username"])

    response = client.post(
        f"/api/v1/tasks/{task_id}/complete",
        headers=auth_headers(user["username"]),
        json={"generate_report": True, "machine": "Anlage 7", "result": "OK"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["status"] == "done"
    assert payload["generated_document"]["machine"] == "Anlage 7"


def test_search_returns_only_dashboards_visible_to_user(
    client,
    make_user,
    make_task,
    make_error_entry,
    make_document,
    auth_headers,
):
    """Verify knowledge search respects dashboard permissions and department filters."""
    user = make_user(
        username="search_user",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )
    task_id = make_task(
        "Anlage Sensor pruefen",
        creator_username=user["username"],
        department_name="Produktion",
    )
    make_error_entry(
        "Anlage Sensor",
        "E111",
        "Sensorfehler",
        department_name="Produktion",
    )
    make_document(task_id=task_id, created_by=user["id"], department="Produktion")

    response = client.get(
        "/api/v1/search?q=Anlage",
        headers=auth_headers(user["username"]),
    )

    result_types = {result["type"] for result in response.get_json()["results"]}
    assert response.status_code == 200
    assert "task" in result_types
    assert "error" in result_types
    assert "document" not in result_types


def test_search_requires_query(client, make_user, auth_headers):
    """Verify search rejects missing query text."""
    user = make_user(username="search_empty_user")

    response = client.get("/api/v1/search?q=   ", headers=auth_headers(user["username"]))

    assert response.status_code == 400


def _write_report(app, document_id, rows):
    """Write a generated report table for a test document."""
    with app.app_context():
        document = db.session.get(GeneratedDocument, document_id)
        table_rows = "\n".join(
            f"<tr><th>{label}</th><td>{value}</td></tr>" for label, value in rows.items()
        )
        document_path(document).write_text(
            f"<html><body><table>{table_rows}</table></body></html>",
            encoding="utf-8",
        )


def _delete_document_file(app, document_id):
    """Delete the stored file for a test document."""
    with app.app_context():
        document = db.session.get(GeneratedDocument, document_id)
        path = document_path(document)
        if path.exists():
            path.unlink()

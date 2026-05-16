"""Tests for AI feature endpoints and services."""

from datetime import date, timedelta
from io import BytesIO

import pytest

from app.extensions import db
from app.models import (
    AIAuditEvent,
    AssistantTrainingEntry,
    EmployeeMachineQualification,
    GeneratedDocument,
    KnowledgeDocument,
    Priority,
    Role,
    Task,
)
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


def test_ai_chat_history_is_user_scoped_and_admin_searchable(
    client,
    make_user,
    auth_headers,
):
    """Verify users see their own chat history and admins can search all chats."""
    admin = make_user(
        username="ai_history_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    user = make_user(username="ai_history_user")
    other = make_user(username="ai_history_other")

    client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Was ist ein User?"},
    )
    client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(other["username"]),
        json={"message": "Was ist Hydraulik?"},
    )

    own_response = client.get(
        "/api/v1/ai/chat/history?q=User",
        headers=auth_headers(user["username"]),
    )
    forbidden_response = client.get(
        "/api/v1/admin/ai/chats",
        headers=auth_headers(user["username"]),
    )
    admin_response = client.get(
        "/api/v1/admin/ai/chats?q=Hydraulik",
        headers=auth_headers(admin["username"]),
    )

    own_items = own_response.get_json()["data"]["items"]
    admin_items = admin_response.get_json()["data"]["items"]
    assert own_response.status_code == 200
    assert len(own_items) == 1
    assert own_items[0]["user_id"] == user["id"]
    assert own_items[0]["response_type"] == "general_chat"
    assert forbidden_response.status_code == 403
    assert admin_response.status_code == 200
    assert len(admin_items) == 1
    assert admin_items[0]["user"]["username"] == other["username"]


def test_admin_ai_events_are_filterable(
    client,
    make_user,
    auth_headers,
):
    """Verify admin AI event search filters metadata without prompts."""
    admin = make_user(
        username="ai_events_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    user = make_user(username="ai_events_user")
    with client.application.app_context():
        event_id = create_ai_audit_event(
            type("UserRef", (), {"id": user["id"]})(),
            "general_chat",
            {
                "status": "openai_error",
                "error": "rate_limit",
                "total_tokens": 10,
            },
        )
        db.session.commit()

    response = client.get(
        "/api/v1/admin/ai/events?error=rate_limit",
        headers=auth_headers(admin["username"]),
    )

    payload = response.get_json()["data"]
    assert response.status_code == 200
    assert payload["items"][0]["id"] == event_id
    assert payload["items"][0]["error_category"] == "rate_limit"
    assert "prompt" not in payload["items"][0]


def test_knowledge_upload_and_chat_retrieval_respect_permissions(
    client,
    make_user,
    auth_headers,
    set_dashboard_permission,
):
    """Verify local RAG chunks are indexed and returned as chat sources."""
    admin = make_user(
        username="knowledge_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    user = make_user(
        username="knowledge_user",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )
    blocked = make_user(
        username="knowledge_blocked",
        role=Role.PRODUKTION,
        department_name="Instandhaltung",
    )
    set_dashboard_permission(user["username"], "documents", can_view=True)
    set_dashboard_permission(blocked["username"], "documents", can_view=True)

    forbidden_response = client.get(
        "/api/v1/admin/ai/knowledge",
        headers=auth_headers(user["username"]),
    )
    upload_response = client.post(
        "/api/v1/admin/ai/knowledge/upload",
        headers=auth_headers(admin["username"]),
        data={
            "department": "Produktion",
            "file": (BytesIO(b"Hydraulikfilter X900 taeglich pruefen."), "manual.txt"),
        },
        content_type="multipart/form-data",
    )
    chat_response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Wie funktioniert Hydraulikfilter X900?"},
    )
    blocked_chat_response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(blocked["username"]),
        json={"message": "Wie funktioniert Hydraulikfilter X900?"},
    )

    assert forbidden_response.status_code == 403
    assert upload_response.status_code == 201
    assert upload_response.get_json()["data"]["status"] == "indexed"
    assert any(source["type"] == "knowledge" for source in chat_response.get_json()["sources"])
    assert not any(
        source["type"] == "knowledge" for source in blocked_chat_response.get_json()["sources"]
    )
    with client.application.app_context():
        document = db.session.get(KnowledgeDocument, upload_response.get_json()["data"]["id"])
        assert document.chunk_count == 1


def test_admin_training_crud_marks_knowledge_stale_and_deletes_document(
    client,
    make_user,
    auth_headers,
):
    """Verify master admins can maintain manual assistant training entries."""
    admin = make_user(
        username="training_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    user = make_user(username="training_user")
    admin_headers = auth_headers(admin["username"])

    forbidden_response = client.get(
        "/api/v1/admin/ai/training",
        headers=auth_headers(user["username"]),
    )
    invalid_response = client.post(
        "/api/v1/admin/ai/training",
        headers=admin_headers,
        json={"answer": "Ohne Titel"},
    )
    create_response = client.post(
        "/api/v1/admin/ai/training",
        headers=admin_headers,
        json={
            "title": "Hydraulikfilter X900",
            "question": "Wie wird X900 gepflegt?",
            "answer": "Hydraulikfilter X900 taeglich pruefen und Befund dokumentieren.",
            "keywords": ["Hydraulikfilter", "X900", "Filterpflege"],
            "category": "wartung",
            "department": "Produktion",
            "priority": 80,
        },
    )
    entry_id = create_response.get_json()["data"]["id"]
    update_response = client.put(
        f"/api/v1/admin/ai/training/{entry_id}",
        headers=admin_headers,
        json={"answer": "X900 je Schicht pruefen.", "priority": 90},
    )
    list_response = client.get(
        "/api/v1/admin/ai/training?q=X900",
        headers=admin_headers,
    )

    assert forbidden_response.status_code == 403
    assert invalid_response.status_code == 400
    assert create_response.status_code == 201
    assert create_response.get_json()["data"]["keywords"] == "Hydraulikfilter, X900, Filterpflege"
    assert update_response.status_code == 200
    assert update_response.get_json()["data"]["priority"] == 90
    assert list_response.get_json()["data"]["pagination"]["total"] == 1
    with client.application.app_context():
        document = KnowledgeDocument.query.filter_by(
            source_type="manual_training",
            source_id=entry_id,
        ).one()
        assert document.status == "stale"

    delete_response = client.delete(
        f"/api/v1/admin/ai/training/{entry_id}",
        headers=admin_headers,
    )

    assert delete_response.status_code == 200
    with client.application.app_context():
        assert db.session.get(AssistantTrainingEntry, entry_id) is None
        assert (
            KnowledgeDocument.query.filter_by(
                source_type="manual_training",
                source_id=entry_id,
            ).first()
            is None
        )


def test_manual_training_rag_respects_active_state_and_department(
    client,
    make_user,
    auth_headers,
):
    """Verify manual training sources are indexed and permission-aware."""
    admin = make_user(
        username="training_rag_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    user = make_user(
        username="training_rag_user",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )
    blocked = make_user(
        username="training_rag_blocked",
        role=Role.PRODUKTION,
        department_name="Instandhaltung",
    )
    admin_headers = auth_headers(admin["username"])
    user_headers = auth_headers(user["username"])
    blocked_headers = auth_headers(blocked["username"])

    create_response = client.post(
        "/api/v1/admin/ai/training",
        headers=admin_headers,
        json={
            "title": "X900 Filterpflege",
            "question": "Was ist bei X900 wichtig?",
            "answer": "X900 Filter taeglich pruefen und Druckverlust dokumentieren.",
            "keywords": "X900, Druckverlust",
            "department": "Produktion",
        },
    )
    client.post(
        "/api/v1/admin/ai/training",
        headers=admin_headers,
        json={
            "title": "Y900 inaktiv",
            "question": "Was ist bei Y900 wichtig?",
            "answer": "Dieser Eintrag ist inaktiv.",
            "keywords": "Y900",
            "department": "Produktion",
            "is_active": False,
        },
    )
    client.post(
        "/api/v1/admin/ai/training",
        headers=admin_headers,
        json={
            "title": "Z900 andere Abteilung",
            "question": "Was ist bei Z900 wichtig?",
            "answer": "Z900 gehoert zur Instandhaltung.",
            "keywords": "Z900",
            "department": "Instandhaltung",
        },
    )
    reindex_response = client.post(
        "/api/v1/admin/ai/knowledge/reindex?mode=stale",
        headers=admin_headers,
    )
    visible_response = client.post(
        "/api/v1/ai/chat",
        headers=user_headers,
        json={"message": "Was ist bei X900 Druckverlust wichtig?"},
    )
    inactive_response = client.post(
        "/api/v1/ai/chat",
        headers=user_headers,
        json={"message": "Was ist bei Y900 wichtig?"},
    )
    department_response = client.post(
        "/api/v1/ai/chat",
        headers=user_headers,
        json={"message": "Was ist bei Z900 wichtig?"},
    )
    blocked_response = client.post(
        "/api/v1/ai/chat",
        headers=blocked_headers,
        json={"message": "Was ist bei X900 Druckverlust wichtig?"},
    )

    assert create_response.status_code == 201
    assert reindex_response.status_code == 200
    assert any(
        source["type"] == "knowledge" and "X900" in source["title"]
        for source in visible_response.get_json()["sources"]
    )
    assert not any("Y900" in source["title"] for source in inactive_response.get_json()["sources"])
    assert not any(
        "Z900" in source["title"] for source in department_response.get_json()["sources"]
    )
    assert not any("X900" in source["title"] for source in blocked_response.get_json()["sources"])


def test_chat_templates_are_permission_aware(
    client,
    make_user,
    set_dashboard_permission,
    auth_headers,
):
    """Verify chat template suggestions are filtered by dashboard permissions."""
    user = make_user(username="chat_template_user")
    set_dashboard_permission(user["username"], "tasks", can_view=True, can_write=False)
    set_dashboard_permission(user["username"], "errors", can_view=False)
    set_dashboard_permission(user["username"], "machines", can_view=True)

    response = client.get(
        "/api/v1/ai/chat/templates",
        headers=auth_headers(user["username"]),
    )

    messages = [item["message"] for item in response.get_json()["data"]["items"]]
    assert response.status_code == 200
    assert "Welche Tasks sind heute wichtig?" in messages
    assert "Welche Maschinen brauchen Aufmerksamkeit?" in messages
    assert "Was bedeutet Fehler E104?" not in messages
    assert "Task erstellen: Maschine 3 macht Geraeusche" not in messages


def test_knowledge_reindex_registers_generated_documents(
    client,
    make_user,
    make_task,
    make_document,
    auth_headers,
):
    """Verify reindex adds generated documents to the local knowledge base."""
    admin = make_user(
        username="knowledge_reindex_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    task_id = make_task("Wartung X900", creator_username=admin["username"])
    make_document(task_id=task_id, created_by=admin["id"], department="Produktion")

    response = client.post(
        "/api/v1/admin/ai/knowledge/reindex",
        headers=auth_headers(admin["username"]),
    )

    assert response.status_code == 200
    assert response.get_json()["data"]["documents"] >= 1


def test_knowledge_reindex_reports_outdated_database_schema(
    client,
    make_user,
    auth_headers,
    monkeypatch,
):
    """Verify reindex returns actionable diagnostics when migrations are missing."""
    admin = make_user(
        username="knowledge_schema_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    schema_status = {
        "ok": False,
        "missing_tables": [],
        "missing_columns": {"generated_document": ["status"]},
        "migration_command": "flask --app run:app db upgrade",
    }
    monkeypatch.setattr(
        "app.admin.routes.database_schema_status",
        lambda: schema_status,
    )

    response = client.post(
        "/api/v1/admin/ai/knowledge/reindex",
        headers=auth_headers(admin["username"]),
    )

    payload = response.get_json()
    assert response.status_code == 503
    assert payload["error"] == "database_schema_outdated"
    assert payload["data"]["missing_columns"]["generated_document"] == ["status"]
    assert "db upgrade" in payload["message"]


def test_knowledge_reindex_registers_structured_rag_sources(
    client,
    make_user,
    make_task,
    make_error_entry,
    make_machine,
    make_material,
    auth_headers,
):
    """Verify reindex ingests structured maintenance records for RAG."""
    admin = make_user(
        username="knowledge_structured_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    user = make_user(
        username="knowledge_structured_user",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )
    blocked = make_user(
        username="knowledge_structured_blocked",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )
    make_task(
        "Hydraulikfilter X900 pruefen",
        creator_username=user["username"],
        department_name="Produktion",
        description="Hydraulikfilter X900 taeglich kontrollieren.",
    )
    make_error_entry(
        "Anlage X900",
        "H900",
        "Hydraulikfilter Druckverlust",
        department_name="Produktion",
        possible_causes="Hydraulikfilter X900 verschmutzt",
        solution="Filter pruefen und bei Bedarf ersetzen",
    )
    machine_id = make_machine(name="Montage Linie", produced_item="Rahmen")
    make_material("Rahmen Rohling", 12.5, 8, machine_id=machine_id)

    reindex_response = client.post(
        "/api/v1/admin/ai/knowledge/reindex",
        headers=auth_headers(admin["username"]),
    )
    chat_response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Was wissen wir ueber Hydraulikfilter X900?"},
    )
    blocked_response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(blocked["username"]),
        json={"message": "Was wissen wir ueber Hydraulikfilter X900?"},
    )

    sources = chat_response.get_json()["sources"]
    blocked_sources = blocked_response.get_json()["sources"]
    assert reindex_response.status_code == 200
    assert reindex_response.get_json()["data"]["sources"]["task"] == 1
    assert reindex_response.get_json()["data"]["sources"]["error_entry"] == 1
    assert reindex_response.get_json()["data"]["sources"]["machine"] == 1
    assert reindex_response.get_json()["data"]["sources"]["inventory_material"] == 1
    assert any(source["type"] == "knowledge" for source in sources)
    assert any("Hydraulikfilter" in source["title"] for source in sources)
    assert not any(source["type"] == "knowledge" for source in blocked_sources)


def test_knowledge_status_reports_rag_index_diagnostics(
    client,
    make_user,
    make_task,
    auth_headers,
):
    """Verify admins can inspect RAG index readiness and source diagnostics."""
    admin = make_user(
        username="knowledge_status_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    make_task(
        "Status RAG Hydraulik",
        creator_username=admin["username"],
        department_name="Instandhaltung",
        description="Hydraulikstatus fuer RAG Diagnose.",
    )
    client.post(
        "/api/v1/admin/ai/knowledge/reindex",
        headers=auth_headers(admin["username"]),
    )

    response = client.get(
        "/api/v1/admin/ai/knowledge/status",
        headers=auth_headers(admin["username"]),
    )

    payload = response.get_json()["data"]
    assert response.status_code == 200
    assert payload["documents"] >= 1
    assert payload["indexed"] >= 1
    assert payload["searchable_documents"] >= 1
    assert payload["chunks"] >= 1
    assert "stale" in payload
    assert "pending" in payload
    assert payload["diagnostics"]["rag_enabled"] is True
    assert payload["diagnostics"]["vector_store"] == "local"
    assert any(item["source_type"] == "task" for item in payload["source_types"])


def test_task_update_marks_rag_source_stale_and_reindex_recovers(
    app,
    client,
    make_user,
    make_task,
    auth_headers,
):
    """Verify changed source data becomes stale and can be reindexed granularly."""
    admin = make_user(
        username="knowledge_stale_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    user = make_user(
        username="knowledge_stale_user",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )
    task_id = make_task(
        "Stale RAG Task",
        creator_username=user["username"],
        department_name="Instandhaltung",
        description="Alter RAG Inhalt",
    )
    client.post(
        "/api/v1/admin/ai/knowledge/reindex",
        headers=auth_headers(admin["username"]),
    )

    update_response = client.put(
        f"/api/v1/tasks/{task_id}",
        headers=auth_headers(user["username"]),
        json={"title": "Aktualisierter Stale RAG Task"},
    )
    stale_response = client.get(
        "/api/v1/admin/ai/knowledge/status",
        headers=auth_headers(admin["username"]),
    )
    stale_reindex_response = client.post(
        "/api/v1/admin/ai/knowledge/reindex?mode=stale",
        headers=auth_headers(admin["username"]),
    )

    with app.app_context():
        db.session.expire_all()
        document = KnowledgeDocument.query.filter_by(
            source_type="task",
            source_id=task_id,
        ).one()
        document_id = document.id
        assert document.status == "indexed"
        assert document.title == "Aktualisierter Stale RAG Task"

    single_reindex_response = client.post(
        f"/api/v1/admin/ai/knowledge/{document_id}/reindex",
        headers=auth_headers(admin["username"]),
    )

    assert update_response.status_code == 200
    assert stale_response.status_code == 200
    assert stale_response.get_json()["data"]["stale"] >= 1
    assert stale_reindex_response.status_code == 200
    assert stale_reindex_response.get_json()["data"]["documents"] == 1
    assert single_reindex_response.status_code == 200
    assert single_reindex_response.get_json()["data"]["status"] == "indexed"


def test_order_plan_selects_machine_staff_and_material(
    app,
    client,
    make_user,
    make_machine,
    make_material,
    make_employee,
    auth_headers,
):
    """Verify the order planner checks machine fit, staffing and stock."""
    admin = make_user(
        username="order_plan_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    machine_id = make_machine(
        name="Deckel Linie 1",
        produced_item="Deckel",
        required_employees=2,
    )
    make_material("Deckel Rohling", 1.5, 12, machine_id=machine_id)
    first_employee_id = make_employee(
        personnel_number="OP-001",
        name="Anna Plan",
        department="Produktion",
        qualifications="Deckel Linie",
    )
    second_employee_id = make_employee(
        personnel_number="OP-002",
        name="Ben Plan",
        department="Produktion",
        qualifications="Deckel Linie",
    )
    with app.app_context():
        db.session.add(
            EmployeeMachineQualification(
                employee_id=first_employee_id,
                machine_id=machine_id,
                level="trained",
            )
        )
        db.session.add(
            EmployeeMachineQualification(
                employee_id=second_employee_id,
                machine_id=machine_id,
                level="expert",
            )
        )
        db.session.commit()

    response = client.post(
        "/api/v1/ai/order-plan",
        headers=auth_headers(admin["username"]),
        json={
            "product": "Deckel",
            "quantity": 10,
            "department": "Produktion",
            "work_date": "2026-05-18",
        },
    )

    payload = response.get_json()["data"]
    recommended = payload["recommended_plan"]
    assert response.status_code == 200
    assert payload["type"] == "order_plan"
    assert recommended["machine"]["id"] == machine_id
    assert recommended["status"] == "feasible"
    assert recommended["material_check"]["status"] == "enough"
    assert recommended["staffing"]["status"] == "covered"
    assert len(recommended["staffing"]["assigned_employees"]) == 2
    assert payload["diagnostics"]["workflow"] == "order_planning"


def test_order_plan_reports_material_shortage(
    client,
    make_user,
    make_machine,
    make_material,
    make_employee,
    auth_headers,
):
    """Verify the order planner exposes missing stock as a blocker."""
    admin = make_user(
        username="order_shortage_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    machine_id = make_machine(name="Gehaeuse Linie", produced_item="Gehaeuse")
    make_material("Gehaeuse Rohling", 2.0, 3, machine_id=machine_id)
    make_employee(
        personnel_number="OP-003",
        name="Cara Plan",
        department="Produktion",
        qualifications="Gehaeuse Linie",
    )

    response = client.post(
        "/api/v1/ai/order-plan",
        headers=auth_headers(admin["username"]),
        json={"product": "Gehaeuse", "quantity": 5, "department": "Produktion"},
    )

    recommended = response.get_json()["data"]["recommended_plan"]
    assert response.status_code == 200
    assert recommended["status"] == "blocked"
    assert recommended["material_check"]["status"] == "shortage"
    assert recommended["material_check"]["missing"][0]["shortage"] == 2
    assert "fehlen" in recommended["blockers"][0]


def test_ai_chat_can_return_order_plan(
    app,
    client,
    make_user,
    make_machine,
    make_material,
    make_employee,
    auth_headers,
):
    """Verify chat can trigger the structured order planning workflow."""
    admin = make_user(
        username="order_chat_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    machine_id = make_machine(name="Pumpen Linie", produced_item="Pumpe")
    make_material("Pumpen Rohling", 3.0, 8, machine_id=machine_id)
    employee_id = make_employee(
        personnel_number="OP-004",
        name="Dina Plan",
        department="Produktion",
        qualifications="Pumpen Linie",
    )
    with app.app_context():
        db.session.add(
            EmployeeMachineQualification(
                employee_id=employee_id,
                machine_id=machine_id,
                level="trained",
            )
        )
        db.session.commit()

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(admin["username"]),
        json={"message": "Plane Auftrag 4 Stueck Pumpe mit Maschine und Personal"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["type"] == "order_plan"
    assert payload["data"]["recommended_plan"]["machine"]["id"] == machine_id
    assert "Auftragsplanung" in payload["answer"]


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


def test_daily_briefing_includes_rag_knowledge_section_after_reindex(
    client,
    make_user,
    make_task,
    auth_headers,
):
    """Verify daily briefing can include visible indexed RAG context."""
    admin = make_user(
        username="briefing_rag_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    user = make_user(
        username="briefing_rag_user",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )
    make_task(
        "Kritische Wartung Maschine RAG",
        creator_username=user["username"],
        department_name="Instandhaltung",
        priority=Priority.URGENT,
        description="Maschine RAG braucht Wartung wegen Stoerung.",
    )
    client.post(
        "/api/v1/admin/ai/knowledge/reindex",
        headers=auth_headers(admin["username"]),
    )

    response = client.get(
        "/api/v1/ai/daily-briefing",
        headers=auth_headers(user["username"]),
    )

    payload = response.get_json()
    section_types = {section["type"] for section in payload["sections"]}
    assert response.status_code == 200
    assert "knowledge" in section_types
    assert payload["diagnostics"]["rag_source_count"] >= 1


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
    script_response = client.get("/static/pages/workflows.js")
    chat_response = client.get("/static/chat.js")
    css_response = client.get("/static/css/output.css")
    html = response.get_data(as_text=True)
    script = script_response.get_data(as_text=True)
    chat_script = chat_response.get_data(as_text=True)
    css = css_response.get_data(as_text=True)

    assert response.status_code == 200
    assert script_response.status_code == 200
    assert chat_response.status_code == 200
    assert css_response.status_code == 200
    assert "data-daily-briefing-list" in html
    assert "data-dashboard-priority-list" in html
    assert "data-chat-suggestions" in html
    assert "data-chat-history-panel hidden" in html
    assert "data-chat-history-search" in html
    assert ".chat-history-item" in css
    assert "briefingItem(section, item)" in script
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
    assert "model_not_allowed" in chat_script
    assert "/api/v1/ai/chat/history" in chat_script
    assert "/api/v1/ai/chat/templates" in chat_script
    assert "historyMetaText(item)" in chat_script
    assert "chatSuggestionsForUser" in chat_script
    assert "setChatFormBusy" in chat_script
    assert "suggestions.hidden = true" in chat_script


def test_admin_users_page_contains_ai_analytics_ui(client):
    """Verify Admin Users exposes AI analytics UI hooks."""
    page_response = client.get("/admin/users")
    script_response = client.get("/static/pages/workflows.js")
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


def test_admin_ai_page_contains_ai_and_knowledge_ui(client):
    """Verify the dedicated AI admin page exposes management UI hooks."""
    page_response = client.get("/admin/ai")
    script_response = client.get("/static/pages/admin-ai.js")
    html = page_response.get_data(as_text=True)
    script = script_response.get_data(as_text=True)
    source = html + script

    assert page_response.status_code == 200
    assert script_response.status_code == 200
    assert "data-admin-ai-page" in html
    assert "data-ai-chat-search" in html
    assert "data-ai-training-form" in html
    assert "data-ai-training-search" in html
    assert "data-ai-knowledge-upload" in html
    assert "data-ai-knowledge-source" in html
    assert "data-rag-source-status" in html
    assert "data-rag-diagnostics" in html
    assert "data-rag-kpi=\"searchable_documents\"" in html
    assert "data-rag-kpi=\"stale\"" in html
    assert "data-ai-reindex-stale" in html
    assert "data-ai-queue-stale" in html
    assert "data-ai-jobs" in html
    assert "/api/v1/admin/ai/events" in source
    assert "/api/v1/admin/ai/chats" in source
    assert "/api/v1/admin/jobs" in source
    assert "/api/v1/admin/ai/knowledge/upload" in source
    assert "/api/v1/admin/ai/knowledge/status" in source
    assert "/api/v1/admin/ai/knowledge/reindex/jobs" in source
    assert "/api/v1/admin/ai/knowledge/reindex?mode=stale" in source
    assert "/api/v1/admin/ai/training" in source
    assert "manual_training" in source
    assert "/reindex" in source


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
    script_response = client.get("/static/pages/workflows.js")
    html = page_response.get_data(as_text=True)
    script = script_response.get_data(as_text=True)

    assert page_response.status_code == 200
    assert "data-document-review-panel" in html
    assert "data-document-review-findings" in html
    assert "data-document-upload-check-form" in html
    assert 'actionButton("Prüfen"' in script
    assert '"/api/v1/documents/check"' in script
    assert "validateUploadCheckFile" in script
    assert "reviewFindingItem" in script
    assert "runAction({" in script
    assert "renderTableMessage(list, 8" in script


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

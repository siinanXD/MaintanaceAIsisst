"""Tests for AI feature endpoints and services."""

import json
from datetime import date, timedelta
from io import BytesIO

import pytest

from app.extensions import db
from app.models import (
    AIAuditEvent,
    AIFeedback,
    AssistantTrainingEntry,
    ChatMessage,
    EmployeeMachineQualification,
    GeneratedDocument,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeGap,
    Priority,
    Role,
    Task,
    User,
)
from app.services.ai_audit_service import ai_analytics_summary, create_ai_audit_event
from app.services.ai_confidence_service import calculate_ai_confidence
from app.services.ai_routing import estimate_cost_usd, workflow_profile
from app.services.ai_service import AIServiceError
from app.services.conversation_context_service import conversation_context_for_chat
from app.services.document_service import document_path
from app.services.knowledge_service import register_source_document
from app.services.retrieval_telemetry_service import retrieval_quality_analytics
from app.services.vector_sync_status_service import (
    clear_vector_sync_observability,
    record_vector_sync_failure,
)


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
    assert payload["chat_message_id"]
    assert payload["sources"][0]["type"] == "machine"
    assert payload["diagnostics"]["source_count"] == len(payload["sources"])
    assert payload["diagnostics"]["confidence_score"] == payload["confidence"]["score"]
    assert payload["diagnostics"]["confidence_level"] == payload["confidence"]["level"]

    with app.app_context():
        event = db.session.get(AIAuditEvent, audit_id)
        chat_message = db.session.get(ChatMessage, payload["chat_message_id"])
        assert event is not None
        assert chat_message is not None
        assert event.workflow == "assistant"
        assert event.source_count == len(payload["sources"])
        assert event.confidence_score == payload["confidence"]["score"]
        assert event.confidence_level == payload["confidence"]["level"]
        assert event.retrieval_explainability()["source_count"] == len(payload["sources"])
        assert chat_message.audit_event_id == audit_id
        assert chat_message.source_count == len(payload["sources"])
        assert chat_message.confidence_score == payload["confidence"]["score"]
        assert chat_message.confidence_level == payload["confidence"]["level"]
        assert not hasattr(event, "prompt")
        assert not hasattr(event, "response")


def test_ai_confidence_scores_high_for_strong_sourced_context(app, make_user):
    """Verify strong sources, quality, machine match, and feedback yield high confidence."""
    user = make_user(username="ai_confidence_high_user")
    sources = [
        {
            "type": "knowledge",
            "id": 11,
            "chunk_id": 101,
            "title": "Presse 3 E104",
            "score": 120,
            "quality_status": "admin_approved",
            "machine_match": 1.0,
        },
        {"type": "error", "id": 12, "title": "E104", "score": 95},
        {"type": "machine", "id": 13, "title": "Presse 3", "score": 88},
    ]
    with app.app_context():
        db.session.add(
            AIFeedback(
                user_id=user["id"],
                prompt="Fehler E104 Presse 3",
                response="Sensor reinigen",
                response_type="assistant",
                rating="helpful",
                sources_json=json.dumps([sources[0]], ensure_ascii=True),
                source_count=1,
            ),
        )
        db.session.commit()

        confidence = calculate_ai_confidence(
            "Was hilft bei Fehler E104 an Presse 3?",
            sources,
            response_type="assistant",
        ).to_dict()

    assert confidence["level"] == "high"
    assert confidence["score"] >= 70
    assert confidence["factors"]["feedback"] > 0.58
    assert "hallucination detection" in confidence["method"]


def test_ai_audit_stores_sanitized_retrieval_explainability(app, make_user):
    """Verify audit explainability keeps scores and source ids but no sensitive text."""
    user = make_user(username="ai_explainability_audit_user")
    raw_explainability = {
        "source_count": 1,
        "explained_source_count": 1,
        "averages": {
            "semantic_similarity": 0.82,
            "lexical_score": 41.2,
            "machine_match": 0.9,
            "feedback_influence": 4.0,
            "recency_influence": 2.0,
        },
        "quality_status_counts": {"admin_approved": 1},
        "machine_match_count": 1,
        "feedback_influenced_count": 1,
        "recency_influenced_count": 1,
        "sources": [
            {
                "type": "knowledge",
                "id": 7,
                "chunk_id": 70,
                "score": 118,
                "title": "Sensitive source title",
                "prompt": "Sensitive prompt",
                "context": "Sensitive retrieved content",
                "explainability": {
                    "semantic_similarity": 0.82,
                    "lexical_score": 41.2,
                    "lexical_similarity": 0.75,
                    "machine_match": 0.9,
                    "quality_status": "admin_approved",
                    "feedback_influence": 4.0,
                    "recency_influence": 2.0,
                },
            },
        ],
    }

    with app.app_context():
        event_id = create_ai_audit_event(
            db.session.get(User, user["id"]),
            "assistant",
            {
                "status": "local_answer",
                "retrieval_explainability": raw_explainability,
            },
            source_count=1,
        )
        event = db.session.get(AIAuditEvent, event_id)
        explainability = event.retrieval_explainability()

    stored_json = json.dumps(explainability, ensure_ascii=True)
    assert explainability["explained_source_count"] == 1
    assert explainability["sources"][0]["type"] == "knowledge"
    assert explainability["sources"][0]["id"] == 7
    assert explainability["sources"][0]["explainability"]["semantic_similarity"] == 0.82
    assert "Sensitive" not in stored_json
    assert "prompt" not in stored_json
    assert "context" not in stored_json


def test_ai_chat_marks_and_persists_low_confidence_answers(
    app,
    client,
    make_user,
    auth_headers,
):
    """Verify weak answers are visibly marked and persisted with low confidence."""
    user = make_user(
        username="ai_confidence_low_user",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Wie behebe ich Stoerung QX999 an Maschine Omega?"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["confidence"]["level"] == "low"
    assert payload["diagnostics"]["confidence_level"] == "low"
    assert payload["answer"].startswith("## Niedrige Confidence")
    assert payload["confidence"]["warning"]

    with app.app_context():
        event = db.session.get(AIAuditEvent, payload["diagnostics"]["audit_event_id"])
        chat_message = db.session.get(ChatMessage, payload["chat_message_id"])

    assert event.confidence_level == "low"
    assert chat_message.confidence_level == "low"
    assert chat_message.confidence_score == payload["confidence"]["score"]


def test_ai_chat_tracks_knowledge_gap_when_no_sources_match(
    app,
    client,
    make_user,
    auth_headers,
):
    """Verify unanswered AI questions create an open knowledge-gap entry."""
    user = make_user(
        username="ai_gap_user",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Wie behebe ich Stoerung QX999 an Maschine Omega?"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["knowledge_gap"]["status"] == "open"
    assert payload["knowledge_gap"]["machine"] == "Maschine Omega"
    assert payload["diagnostics"]["knowledge_gap_created"] is True
    with app.app_context():
        gap = KnowledgeGap.query.one()
        assert gap.question == "Wie behebe ich Stoerung QX999 an Maschine Omega?"
        assert gap.department == "Instandhaltung"
        assert gap.status == "open"
        assert gap.occurrence_count == 1


def test_ai_chat_does_not_track_gap_for_sourced_answer(
    app,
    client,
    make_user,
    make_error_entry,
    auth_headers,
):
    """Verify sourced AI answers do not create unnecessary knowledge gaps."""
    user = make_user(
        username="ai_gap_sourced_user",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )
    make_error_entry(
        "Anlage 4",
        "E104",
        "Sensor erkennt Produkt nicht",
        department_name="Instandhaltung",
        description="Sensor Signal fehlt sporadisch an Anlage 4.",
        solution="Sensor reinigen und Abstand pruefen.",
    )

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Was hilft bei Fehler E104 an Anlage 4?"},
    )

    assert response.status_code == 200
    assert "knowledge_gap" not in response.get_json()
    with app.app_context():
        assert KnowledgeGap.query.count() == 0


def test_ai_chat_deduplicates_recent_knowledge_gaps(
    app,
    client,
    make_user,
    auth_headers,
):
    """Verify repeated unanswered questions update one recent open gap."""
    user = make_user(
        username="ai_gap_duplicate_user",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )
    headers = auth_headers(user["username"])
    message = "Warum faellt Anlage Delta mit Fehler X999 aus?"

    first_response = client.post("/api/v1/ai/chat", headers=headers, json={"message": message})
    second_response = client.post("/api/v1/ai/chat", headers=headers, json={"message": message})

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.get_json()["knowledge_gap"]["created"] is True
    assert second_response.get_json()["knowledge_gap"]["created"] is False
    with app.app_context():
        gap = KnowledgeGap.query.one()
        assert gap.occurrence_count == 2


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


def test_ai_chat_uses_short_session_context_for_references(
    app,
    client,
    make_user,
    auth_headers,
    monkeypatch,
):
    """Verify referential chat turns receive bounded same-session context."""
    captured = {}

    class ContextAwareProvider:
        """Fake provider that records the prompt context."""

        name = "openai"
        last_call_metadata = {
            "provider": "openai",
            "workflow": "chat",
            "model": "test-context-model",
        }

        def answer_question(self, question, context, workflow="chat"):
            """Record contextual prompt inputs and return a deterministic answer."""
            captured["question"] = question
            captured["context"] = context
            captured["workflow"] = workflow
            return "## Antwort\n- **Status:** Kontext verstanden"

        def answer_general_question(self, question):
            """Record unexpected general fallback calls."""
            captured["general_question"] = question
            return "## Antwort\n- **Status:** Allgemein"

    admin = make_user(
        username="ai_context_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    with app.app_context():
        db.session.add(
            ChatMessage(
                user_id=admin["id"],
                session_id="ctx-main",
                message="Fehler E104 an Presse 3: Was ist die L\u00f6sung?",
                response=(
                    "## Fehlerhilfe\n"
                    "- **Pr\u00fcfung:** Sensor reinigen und Abstand kontrollieren."
                ),
                response_type="error_help",
                diagnostics_json=json.dumps({"scopes": ["errors", "machines"]}),
                source_count=1,
            )
        )
        db.session.commit()

    monkeypatch.setattr(
        "app.ai.services.get_ai_provider",
        lambda: ContextAwareProvider(),
    )

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(admin["username"]),
        json={
            "message": "Was war die vorherige L\u00f6sung fuer den Fehler von eben?",
            "session_id": "ctx-main",
        },
    )

    payload = response.get_json()
    context_diagnostics = payload["diagnostics"]["conversation_context"]
    with app.app_context():
        saved = db.session.get(ChatMessage, payload["chat_message_id"])

    assert response.status_code == 200
    assert captured["workflow"] == "chat"
    assert "Kurzzeit-Gespraechskontext" in captured["context"]
    assert "Presse 3" in captured["context"]
    assert "E104" in captured["context"]
    assert "Sensor reinigen" in captured["context"]
    assert context_diagnostics["reference_detected"] is True
    assert context_diagnostics["applied"] is True
    assert context_diagnostics["message_count"] == 1
    assert saved.session_id == "ctx-main"


def test_ai_chat_context_is_scoped_to_session(
    app,
    client,
    make_user,
    auth_headers,
    monkeypatch,
):
    """Verify prior messages from another session are not used as memory."""
    captured = {}

    class GeneralProvider:
        """Fake provider that records whether context was supplied."""

        name = "openai"
        last_call_metadata = {
            "provider": "openai",
            "workflow": "general_chat",
            "model": "test-context-model",
        }

        def answer_question(self, question, context, workflow="chat"):
            """Record contextual calls."""
            captured["context"] = context
            return "## Antwort\n- **Status:** Kontext"

        def answer_general_question(self, question):
            """Record general calls when no context is available."""
            captured["general_question"] = question
            return "## Antwort\n- **Status:** Kein Kontext"

    user = make_user(username="ai_context_session_user")
    with app.app_context():
        db.session.add(
            ChatMessage(
                user_id=user["id"],
                session_id="other-session",
                message="Fehler E999 an Presse 9",
                response="- **Pruefung:** Andere Maschine pruefen.",
                response_type="error_help",
                diagnostics_json=json.dumps({"scopes": ["errors", "machines"]}),
                source_count=1,
            )
        )
        db.session.commit()

    monkeypatch.setattr("app.ai.services.get_ai_provider", lambda: GeneralProvider())

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={
            "message": "Was war die vorherige L\u00f6sung?",
            "session_id": "current-session",
        },
    )

    payload = response.get_json()
    context_diagnostics = payload["diagnostics"]["conversation_context"]

    assert response.status_code == 200
    assert "general_question" in captured
    assert "context" not in captured
    assert context_diagnostics["reference_detected"] is True
    assert context_diagnostics["applied"] is False
    assert context_diagnostics["message_count"] == 0


def test_conversation_context_rechecks_permissions_for_legacy_scoped_messages(
    app,
    make_user,
    set_dashboard_permission,
):
    """Verify legacy unscoped chat history is inferred and permission-filtered."""
    user = make_user(username="ai_context_permission_user", role=Role.INSTANDHALTUNG)
    set_dashboard_permission(user["username"], "errors", can_view=False)

    with app.app_context():
        db.session.add(
            ChatMessage(
                user_id=user["id"],
                session_id="legacy-denied",
                message="Fehler E104 an Presse 3",
                response="Sensor reinigen und Abstand kontrollieren.",
                response_type="error_help",
                diagnostics_json="{}",
                source_count=1,
            )
        )
        db.session.commit()

        context = conversation_context_for_chat(
            db.session.get(User, user["id"]),
            "Was war der Fehler von eben?",
            "legacy-denied",
        )

    assert context.reference_detected is True
    assert context.applied is False
    assert context.message_count == 0
    assert context.error_codes == ()


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


def test_ai_analytics_summary_reports_ops_readiness(app, make_user):
    """Verify AI summary exposes demo-ready operational KPIs."""
    user = make_user(username="ai_ops_summary_user")
    with app.app_context():
        actor = type("UserRef", (), {"id": user["id"]})()
        create_ai_audit_event(
            actor,
            "task_suggestion",
            {
                "status": "openai_used",
                "input_tokens": 80,
                "cached_tokens": 20,
                "output_tokens": 20,
                "total_tokens": 100,
                "latency_ms": 200,
                "estimated_cost_usd": 0.01,
            },
        )
        create_ai_audit_event(
            actor,
            "general_chat",
            {
                "status": "openai_error",
                "error": "rate_limit",
                "fallback_used": True,
                "input_tokens": 40,
                "output_tokens": 10,
                "total_tokens": 50,
                "latency_ms": 1200,
                "estimated_cost_usd": 0.005,
            },
        )
        create_ai_audit_event(
            actor,
            "general_chat",
            {
                "status": "local_answer",
                "fallback_used": True,
            },
        )
        db.session.commit()

        summary = ai_analytics_summary(days=7)

    assert summary["fallback_rate"] == 0.67
    assert summary["error_rate"] == 0.33
    assert summary["cache_rate"] == 0.17
    assert summary["cost_per_1k_tokens"] == 0.1
    assert summary["top_workflows"][0]["workflow"] == "general_chat"
    assert summary["top_workflows"][0]["errors"] == 1
    assert summary["top_errors"][0] == {"error_category": "rate_limit", "count": 1}
    assert summary["readiness"]["status"] == "critical"
    assert summary["readiness"]["reasons"]
    assert "retrieval_quality" in summary


def test_retrieval_quality_analytics_aggregates_prompt_safe_signals(app, make_user):
    """Verify retrieval telemetry aggregates quality signals without raw content."""
    user = make_user(username="retrieval_telemetry_user")

    with app.app_context():
        used_document = KnowledgeDocument(
            source_type="upload",
            title="Telemetry Used Source",
            original_filename="used.txt",
            relative_path="uploads/used.txt",
            content_type="text/plain",
            department="Produktion",
            status="indexed",
            quality_status="admin_approved",
            is_public=True,
            chunk_count=1,
        )
        unused_document = KnowledgeDocument(
            source_type="upload",
            title="Telemetry Unused Source",
            original_filename="unused.txt",
            relative_path="uploads/unused.txt",
            content_type="text/plain",
            department="Produktion",
            status="indexed",
            quality_status="admin_approved",
            is_public=True,
            chunk_count=1,
        )
        db.session.add_all([used_document, unused_document])
        db.session.flush()
        used_chunk = KnowledgeChunk(
            document_id=used_document.id,
            chunk_index=0,
            text="Sensitive used chunk text must not appear in telemetry.",
            token_text="telemetry used",
        )
        unused_chunk = KnowledgeChunk(
            document_id=unused_document.id,
            chunk_index=0,
            text="Sensitive unused chunk text must not appear in telemetry.",
            token_text="telemetry unused",
        )
        db.session.add_all([used_chunk, unused_chunk])
        db.session.flush()
        used_document_id = used_document.id
        used_chunk_id = used_chunk.id
        unused_chunk_id = unused_chunk.id
        source_payload = {
            "type": "knowledge",
            "id": used_document_id,
            "chunk_id": used_chunk_id,
            "score": 12,
            "explainability": {
                "quality_status": "admin_approved",
                "final_score": 12,
            },
        }
        create_ai_audit_event(
            user=type("UserStub", (), {"id": user["id"]})(),
            workflow="general_chat",
            diagnostics={
                "status": "openai_used",
                "confidence_score": 82,
                "retrieval_explainability": {
                    "source_count": 1,
                    "explained_source_count": 1,
                    "sources": [source_payload],
                },
            },
            source_count=1,
        )
        create_ai_audit_event(
            user=type("UserStub", (), {"id": user["id"]})(),
            workflow="general_chat",
            diagnostics={
                "status": "local_answer",
                "confidence_score": 18,
            },
            source_count=0,
        )
        db.session.add(
            AIFeedback(
                user_id=user["id"],
                prompt="Sensitive prompt must not appear.",
                response="Sensitive answer must not appear.",
                response_type="assistant",
                rating="not_helpful",
                sources_json=json.dumps(
                    [
                        {
                            "type": "knowledge",
                            "id": used_document_id,
                            "chunk_id": used_chunk_id,
                            "title": used_document.title,
                            "score": 12,
                        }
                    ],
                    ensure_ascii=True,
                ),
                source_count=1,
            )
        )
        db.session.add(
            KnowledgeGap(
                question="Sensitive gap question must not appear.",
                question_hash="a" * 64,
                occurrence_count=4,
                status="open",
                machine="Presse 3",
                department="Produktion",
                user_id=user["id"],
            )
        )
        db.session.commit()

        telemetry = retrieval_quality_analytics(days=30, limit=5)

    top_source = telemetry["source_usage"]["top_sources"][0]
    poor_source = telemetry["poor_sources"][0]
    top_gap = telemetry["knowledge_gaps"]["top_gaps"][0]
    unused_sample = telemetry["unused_chunks"]["sample"]
    telemetry_text = json.dumps(telemetry, ensure_ascii=True)

    assert top_source["id"] == used_document_id
    assert top_source["audit_uses"] == 1
    assert poor_source["not_helpful_feedback"] == 1
    assert telemetry["unsuccessful_questions"]["no_source_events"] == 1
    assert telemetry["unsuccessful_questions"]["low_confidence_events"] == 1
    assert top_gap["question_hash"] == "a" * 64
    assert "question" not in top_gap
    assert telemetry["negative_feedback"]["total"] == 1
    assert any(item["chunk_id"] == unused_chunk_id for item in unused_sample)
    assert "Sensitive prompt" not in telemetry_text
    assert "Sensitive answer" not in telemetry_text
    assert "Sensitive used chunk text" not in telemetry_text


def test_retrieval_slo_metrics_aggregate_operational_signals(app, make_user):
    """Verify retrieval SLO metrics combine audit, feedback, safety, and drift signals."""
    user = make_user(username="retrieval_slo_user")
    clear_vector_sync_observability()
    try:
        with app.app_context():
            stale_document = KnowledgeDocument(
                source_type="upload",
                title="SLO stale source",
                original_filename="slo-stale.txt",
                relative_path="uploads/slo-stale.txt",
                content_type="text/plain",
                department="Produktion",
                status="stale",
                quality_status="admin_approved",
                is_public=True,
                chunk_count=1,
            )
            db.session.add(stale_document)
            db.session.flush()
            record_vector_sync_failure(
                stale_document.id,
                "chroma",
                RuntimeError("sync failed"),
            )
            actor = type("UserStub", (), {"id": user["id"]})()
            create_ai_audit_event(
                user=actor,
                workflow="assistant",
                diagnostics={
                    "status": "openai_used",
                    "confidence_score": 82,
                    "retrieval_explainability": {
                        "retrieval_duration_ms": 100,
                        "safety": {"safety_relevant": False},
                    },
                },
                requested_scopes={"documents"},
                allowed_scopes={"documents"},
                source_count=1,
            )
            create_ai_audit_event(
                user=actor,
                workflow="assistant",
                diagnostics={
                    "status": "fallback_used",
                    "fallback_used": True,
                    "confidence_score": 20,
                    "retrieval_explainability": {
                        "retrieval_duration_ms": 1500,
                        "safety": {
                            "safety_relevant": True,
                            "risk_level": "high",
                            "categories": ["electrical_hazard"],
                        },
                    },
                },
                requested_scopes={"documents", "employees"},
                allowed_scopes={"documents"},
                source_count=0,
            )
            db.session.add_all(
                [
                    AIFeedback(
                        user_id=user["id"],
                        prompt="Prompt must not appear",
                        response="Answer must not appear",
                        response_type="assistant",
                        rating="not_helpful",
                        sources_json="[]",
                        source_count=0,
                    ),
                    AIFeedback(
                        user_id=user["id"],
                        prompt="Other prompt must not appear",
                        response="Other answer must not appear",
                        response_type="assistant",
                        rating="helpful",
                        sources_json="[]",
                        source_count=0,
                    ),
                ]
            )
            db.session.commit()

            telemetry = retrieval_quality_analytics(days=30, limit=5)
    finally:
        clear_vector_sync_observability()

    slo = telemetry["retrieval_slo"]
    values = slo["last_values"]
    assert values["retrieval_p95_ms"] == 1500
    assert values["no_source_rate"] == 0.5
    assert values["low_confidence_rate"] == 0.5
    assert values["permission_filtered_candidate_count"] == 1
    assert values["negative_feedback_rate"] == 0.5
    assert values["safety_risk_count"] == 1
    assert values["fallback_rate"] == 0.5
    assert values["vector_sync_failure_count"] == 1
    assert values["stale_index_count"] == 1
    assert slo["status"] == "critical"
    assert slo["trends"]["retrieval_p95_ms"]["direction"] == "up"
    assert "Prompt must not appear" not in json.dumps(slo, ensure_ascii=True)


def test_retrieval_slo_metrics_handle_empty_data(app):
    """Verify retrieval SLO metrics return safe defaults for empty telemetry."""
    clear_vector_sync_observability()
    with app.app_context():
        telemetry = retrieval_quality_analytics(days=7, limit=5)

    slo = telemetry["retrieval_slo"]
    assert slo["status"] == "ok"
    assert slo["last_values"]["event_count"] == 0
    assert slo["last_values"]["retrieval_p95_ms"] == 0
    assert slo["last_values"]["no_source_rate"] == 0.0
    assert slo["warnings"] == []


def test_admin_retrieval_telemetry_endpoint_is_admin_only(
    client,
    make_user,
    auth_headers,
):
    """Verify retrieval telemetry is exposed only to master admins."""
    admin = make_user(
        username="retrieval_telemetry_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    user = make_user(username="retrieval_telemetry_regular")

    forbidden_response = client.get(
        "/api/v1/admin/ai/retrieval-telemetry",
        headers=auth_headers(user["username"]),
    )
    admin_response = client.get(
        "/api/v1/admin/ai/retrieval-telemetry?days=30&limit=5",
        headers=auth_headers(admin["username"]),
    )

    payload = admin_response.get_json()["data"]
    assert forbidden_response.status_code == 403
    assert admin_response.status_code == 200
    assert set(payload.keys()) >= {
        "retrieval_slo",
        "retrieval_evaluation_history",
        "source_usage",
        "poor_sources",
        "unsuccessful_questions",
        "knowledge_gaps",
        "negative_feedback",
        "unused_chunks",
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
    assert invalid_response.get_json()["missing_information"]["status"] == "needs_information"
    assert create_response.status_code == 201
    assert create_response.get_json()["data"]["keywords"] == "Hydraulikfilter, X900, Filterpflege"
    assert (
        create_response.get_json()["data"]["missing_information"]["status"]
        == "needs_information"
    )
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


def test_admin_training_missing_information_complete_state(
    client,
    make_user,
    auth_headers,
):
    """Verify complete manual knowledge entries do not need follow-up prompts."""
    admin = make_user(
        username="training_prompt_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )

    response = client.post(
        "/api/v1/admin/ai/training",
        headers=auth_headers(admin["username"]),
        json={
            "title": "Maschine 3 E104 Sensor Signal",
            "question": "Was tun bei E104 an Maschine 3, wenn der Sensor kein Signal meldet?",
            "answer": (
                "Maschine 3 sichern, Sensor gereinigt, Kabel geprueft und "
                "Probelauf erfolgreich. Stoerung behoben."
            ),
            "keywords": ["Maschine 3", "E104", "Sensor"],
            "category": "stoerung",
            "department": "Instandhaltung",
            "priority": 80,
        },
    )

    assert response.status_code == 201
    assert response.get_json()["data"]["missing_information"]["status"] == "complete"
    assert response.get_json()["data"]["missing_information"]["missing_fields"] == []


def test_generated_knowledge_documents_default_to_ai_suggested(app):
    """Verify generated knowledge is never implicitly admin-approved."""
    with app.app_context():
        register_source_document(
            source_type="generated_document",
            source_id=99,
            title="AI Wartungsbericht",
            department="Instandhaltung",
            url_path="/documents",
        )
        db.session.commit()

        document = KnowledgeDocument.query.filter_by(
            source_type="generated_document",
            source_id=99,
        ).one()
        assert document.quality_status == "ai_suggested"


def test_master_admin_can_update_knowledge_quality_status(
    app,
    client,
    make_user,
    auth_headers,
):
    """Verify master admins can approve a knowledge document explicitly."""
    admin = make_user(
        username="knowledge_quality_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    with app.app_context():
        document = KnowledgeDocument(
            source_type="upload",
            title="Hydraulik Anleitung",
            original_filename="hydraulik.txt",
            content_type="text/plain",
            department="Instandhaltung",
            status="indexed",
            quality_status="draft",
        )
        db.session.add(document)
        db.session.commit()
        document_id = document.id

    response = client.put(
        f"/api/v1/admin/ai/knowledge/{document_id}/quality-status",
        headers=auth_headers(admin["username"]),
        json={"quality_status": "admin_approved"},
    )

    assert response.status_code == 200
    assert response.get_json()["data"]["quality_status"] == "admin_approved"
    with app.app_context():
        assert db.session.get(KnowledgeDocument, document_id).quality_status == "admin_approved"


def test_technician_quality_status_permissions_are_scoped(
    app,
    client,
    make_user,
    auth_headers,
):
    """Verify technicians can confirm local knowledge but cannot approve it."""
    technician = make_user(
        username="knowledge_quality_tech",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )
    with app.app_context():
        own_document = KnowledgeDocument(
            source_type="upload",
            title="Eigener Eintrag",
            original_filename="own.txt",
            content_type="text/plain",
            department="Instandhaltung",
            status="indexed",
            quality_status="draft",
        )
        foreign_document = KnowledgeDocument(
            source_type="upload",
            title="Fremder Eintrag",
            original_filename="foreign.txt",
            content_type="text/plain",
            department="Produktion",
            status="indexed",
            quality_status="draft",
        )
        db.session.add_all([own_document, foreign_document])
        db.session.commit()
        own_id = own_document.id
        foreign_id = foreign_document.id

    headers = auth_headers(technician["username"])
    confirm_response = client.put(
        f"/api/v1/admin/ai/knowledge/{own_id}/quality-status",
        headers=headers,
        json={"quality_status": "technician_confirmed"},
    )
    approve_response = client.put(
        f"/api/v1/admin/ai/knowledge/{own_id}/quality-status",
        headers=headers,
        json={"quality_status": "admin_approved"},
    )
    foreign_response = client.put(
        f"/api/v1/admin/ai/knowledge/{foreign_id}/quality-status",
        headers=headers,
        json={"quality_status": "outdated"},
    )

    assert confirm_response.status_code == 200
    assert confirm_response.get_json()["data"]["quality_status"] == "technician_confirmed"
    assert approve_response.status_code == 403
    assert foreign_response.status_code == 403


def test_manual_training_rag_respects_active_state_and_department(
    client,
    make_user,
    set_dashboard_permission,
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
    no_scope = make_user(
        username="training_rag_no_scope",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )
    set_dashboard_permission(user["username"], "documents", can_view=True)
    set_dashboard_permission(blocked["username"], "documents", can_view=True)
    set_dashboard_permission(no_scope["username"], "documents", can_view=False)
    admin_headers = auth_headers(admin["username"])
    user_headers = auth_headers(user["username"])
    blocked_headers = auth_headers(blocked["username"])
    no_scope_headers = auth_headers(no_scope["username"])

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
    admin_visible_response = client.post(
        "/api/v1/ai/chat",
        headers=admin_headers,
        json={"message": "Was ist bei X900 Druckverlust wichtig?"},
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
    no_scope_response = client.post(
        "/api/v1/ai/chat",
        headers=no_scope_headers,
        json={"message": "Was ist bei X900 Druckverlust wichtig?"},
    )

    assert create_response.status_code == 201
    assert reindex_response.status_code == 200
    assert any(
        source["type"] == "knowledge" and "X900" in source["title"]
        for source in admin_visible_response.get_json()["sources"]
    )
    assert any(
        source["type"] == "knowledge" and "X900" in source["title"]
        for source in visible_response.get_json()["sources"]
    )
    assert not any("Y900" in source["title"] for source in inactive_response.get_json()["sources"])
    assert not any(
        "Z900" in source["title"] for source in department_response.get_json()["sources"]
    )
    assert not any("X900" in source["title"] for source in blocked_response.get_json()["sources"])
    assert not any(
        "X900" in source["title"] for source in no_scope_response.get_json()["sources"]
    )


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
    with client.application.app_context():
        db.session.add(
            KnowledgeDocument(
                source_type="upload",
                title="Fehlerhafte RAG Quelle",
                original_filename="broken.txt",
                status="error",
                error_message="Text konnte nicht extrahiert werden.",
                created_by=admin["id"],
            )
        )
        db.session.add(
            KnowledgeDocument(
                source_type="manual_training",
                title="Veraltete Trainingsquelle",
                original_filename="",
                status="stale",
                created_by=admin["id"],
            )
        )
        db.session.commit()

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
    assert 0 <= payload["readiness_score"] < 100
    assert payload["readiness_reasons"]
    assert any(item["status"] == "error" for item in payload["problem_documents"])
    assert any(item["status"] == "stale" for item in payload["problem_documents"])
    assert any(item["source_type"] == "task" for item in payload["source_types"])


def test_knowledge_lifecycle_status_covers_training_rag_feedback_flow(
    client,
    make_user,
    set_dashboard_permission,
    auth_headers,
):
    """Verify the lifecycle read model covers draft, RAG use, and feedback review."""
    admin = make_user(
        username="knowledge_lifecycle_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    user = make_user(
        username="knowledge_lifecycle_user",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )
    set_dashboard_permission(user["username"], "documents", can_view=True)
    admin_headers = auth_headers(admin["username"])
    user_headers = auth_headers(user["username"])

    create_response = client.post(
        "/api/v1/admin/ai/training",
        headers=admin_headers,
        json={
            "title": "Lifecycle Filterpflege",
            "question": "Was ist bei Lifecycle Filterpflege wichtig?",
            "answer": (
                "Lifecycle Filterpflege taeglich pruefen und Druckverlust "
                "dokumentieren."
            ),
            "keywords": "Lifecycle, Filterpflege, Druckverlust",
            "department": "Produktion",
        },
    )
    reindex_response = client.post(
        "/api/v1/admin/ai/knowledge/reindex?mode=stale",
        headers=admin_headers,
    )
    chat_response = client.post(
        "/api/v1/ai/chat",
        headers=user_headers,
        json={"message": "Was ist bei Lifecycle Filterpflege wichtig?"},
    )
    chat_payload = chat_response.get_json()
    feedback_response = client.post(
        "/api/v1/ai/feedback",
        headers=user_headers,
        json={
            "chat_message_id": chat_payload["chat_message_id"],
            "rating": "helpful",
            "sources": chat_payload["sources"],
        },
    )
    status_response = client.get(
        "/api/v1/admin/ai/knowledge/status",
        headers=admin_headers,
    )

    lifecycle = status_response.get_json()["data"]["lifecycle"]
    step_keys = {step["key"] for step in lifecycle["steps"]}
    assert create_response.status_code == 201
    assert reindex_response.status_code == 200
    assert chat_response.status_code == 200
    assert any(source["type"] == "knowledge" for source in chat_payload["sources"])
    assert feedback_response.status_code == 201
    assert status_response.status_code == 200
    assert lifecycle["indexed_documents"] >= 1
    assert lifecycle["drafts"] >= 1
    assert lifecycle["feedback_open"] >= 1
    assert lifecycle["rag_quality_gate"]["enabled"] is True
    assert lifecycle["rag_quality_gate"]["non_approved_indexed_documents"] >= 1
    assert lifecycle["rag_quality_gate"]["quality_weighted_indexed_documents"] >= 1
    assert {"draft_creation", "rag_usage", "feedback", "knowledge_gaps"} <= step_keys


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


def test_ai_feedback_links_chat_message_without_sources(
    app,
    client,
    make_user,
    auth_headers,
):
    """Verify feedback can reference a saved chat answer even without sources."""
    user = make_user(username="ai_feedback_chat_user")
    headers = auth_headers(user["username"])
    chat_response = client.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={"message": "Was ist Predictive Maintenance?"},
    )
    chat_payload = chat_response.get_json()

    feedback_response = client.post(
        "/api/v1/ai/feedback",
        headers=headers,
        json={
            "chat_message_id": chat_payload["chat_message_id"],
            "rating": "partially_helpful",
            "comment": "Teilweise gut, Quellen fehlen.",
        },
    )
    feedback_payload = feedback_response.get_json()

    with app.app_context():
        feedback_entry = db.session.get(AIFeedback, feedback_payload["id"])
        stored_prompt = feedback_entry.prompt
        stored_source_count = feedback_entry.source_count
        stored_sources = feedback_entry.sources()

    assert chat_response.status_code == 200
    assert feedback_response.status_code == 201
    assert feedback_payload["rating"] == "partially_helpful"
    assert feedback_payload["chat_message_id"] == chat_payload["chat_message_id"]
    assert feedback_payload["audit_event_id"] == chat_payload["diagnostics"]["audit_event_id"]
    assert feedback_payload["source_count"] == 0
    assert stored_prompt == "Was ist Predictive Maintenance?"
    assert stored_source_count == 0
    assert stored_sources == []


def test_ai_feedback_stores_source_and_chunk_metadata(
    app,
    client,
    make_user,
    auth_headers,
):
    """Verify feedback stores source and chunk links without mutating knowledge."""
    user = make_user(username="ai_feedback_sources_user")
    with app.app_context():
        event_id = create_ai_audit_event(
            user=type("UserStub", (), {"id": user["id"]})(),
            workflow="assistant",
            diagnostics={"status": "local_answer"},
            source_count=1,
        )
        db.session.commit()

    response = client.post(
        "/api/v1/ai/feedback",
        headers=auth_headers(user["username"]),
        json={
            "prompt": "Wie behebe ich E104?",
            "response": "Sensor pruefen.",
            "rating": "not_helpful",
            "audit_event_id": event_id,
            "sources": [
                {
                    "type": "knowledge",
                    "id": 7,
                    "chunk_id": 13,
                    "title": "Sensor Manual",
                    "module": "knowledge",
                    "score": 42,
                }
            ],
        },
    )
    payload = response.get_json()

    with app.app_context():
        feedback_entry = db.session.get(AIFeedback, payload["id"])
        stored_source = feedback_entry.sources()[0]
        stored_audit_event_id = feedback_entry.audit_event_id

    assert response.status_code == 201
    assert payload["source_count"] == 1
    assert payload["review_status"] == "open"
    assert stored_source["id"] == 7
    assert stored_source["chunk_id"] == 13
    assert stored_audit_event_id == event_id


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


def test_daily_briefing_includes_recurring_issue_trends(
    client,
    make_user,
    make_error_entry,
    auth_headers,
):
    """Verify daily briefing surfaces recurring visible error trends."""
    user = make_user(
        username="briefing_recurring_issue_user",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )
    make_error_entry(
        "Anlage Trend",
        "TR104",
        "Sensor Signal fehlt",
        department_name="Instandhaltung",
        description="Sensor Signal fehlt sporadisch.",
        solution="Sensor reinigen",
    )
    make_error_entry(
        "Anlage Trend",
        "TR104",
        "Sensor erkennt Produkt nicht",
        department_name="Instandhaltung",
        description="Sensor meldet kein Signal.",
        solution="Sensor reinigen",
    )

    response = client.get(
        "/api/v1/ai/daily-briefing",
        headers=auth_headers(user["username"]),
    )

    payload = response.get_json()
    recurring_section = next(
        section for section in payload["sections"] if section["type"] == "recurring_issues"
    )
    assert response.status_code == 200
    assert recurring_section["count"] == 1
    assert recurring_section["items"][0]["occurrence_count"] == 2
    assert "Anlage Trend" in recurring_section["items"][0]["title"]


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
    assert "data-ai-ops-priority-rail" in html
    assert "data-ai-system-rail" in html
    assert "data-ai-risk-radar" in html
    assert "data-ai-knowledge-health" in html
    assert "data-dashboard-low-confidence-count" in html
    assert "data-dashboard-frequent-codes" in html
    assert "data-chat-suggestions" in html
    assert "data-chat-history-panel hidden" in html
    assert "data-chat-history-search" in html
    assert ".chat-history-item" in css
    assert "briefingItem(section, item)" in script
    assert "Briefing konnte nicht geladen werden." in script
    assert "KI-Priorisierung" in script
    assert "renderPriorityRail" in script
    assert "/api/v1/admin/ai/retrieval-telemetry" in script
    assert "/api/v1/admin/ai/knowledge/status" in script
    assert "/api/v1/admin/ai/knowledge-gaps" in script
    assert "/api/v1/ai/status" in script
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
    assert "partially_helpful" in chat_script
    assert "chat_message_id" in chat_script
    assert "/api/v1/ai/feedback" in chat_script
    assert "maintenance_ai_chat_session_id" in chat_script
    assert "session_id: chatSessionId()" in chat_script
    assert "resetChatSession()" in chat_script
    assert "renderAssistantEvidence" in chat_script
    assert "confidencePayload" in chat_script
    assert "renderExplainability" in chat_script
    assert "chat-answer-card" in css
    assert "chat-answer-badge" in css
    assert "chat-source-chip" in css
    assert "chat-explainability" in css


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
    assert "data-ai-health-panel" in html
    assert "data-retrieval-slo-panel" in html
    assert 'data-retrieval-slo-kpi="retrieval_p95_ms"' in html
    assert "data-retrieval-slo-trends" in html
    assert "data-retrieval-slo-warnings" in html
    assert "data-retrieval-evaluation-history-panel" in html
    assert 'data-retrieval-evaluation-kpi="recall_at_k"' in html
    assert "data-retrieval-evaluation-regression" in html
    assert "data-retrieval-evaluation-runs" in html
    assert "data-ai-workflows" in html
    assert "data-ai-top-errors" in html
    assert "data-ai-chat-search" in html
    assert "data-ai-training-form" in html
    assert "data-ai-training-search" in html
    assert "data-ai-knowledge-upload" in html
    assert "data-ai-knowledge-search" in html
    assert "data-ai-knowledge-source" in html
    assert "data-ai-knowledge-quality" in html
    assert "data-knowledge-origin-legend" in html
    assert "is-source-automatic" in html
    assert "is-source-manual" in html
    assert "is-source-prebuilt" in html
    assert "data-knowledge-lifecycle-panel" in html
    assert 'data-lifecycle-kpi="drafts"' in html
    assert 'data-lifecycle-kpi="non_approved_indexed_documents"' in html
    assert "data-knowledge-lifecycle-review" in html
    assert "data-knowledge-lifecycle-gate" in html
    assert "data-knowledge-lifecycle-actions" in html
    assert "data-knowledge-lifecycle-steps" in html
    assert "data-knowledge-network-panel" in html
    assert "data-knowledge-network-canvas" in html
    assert "data-knowledge-network-detail" in html
    assert "data-knowledge-network-legend" in html
    assert "data-knowledge-network-search" in html
    assert "data-knowledge-network-focus-type" in html
    assert "data-knowledge-network-groups" in html
    assert "data-knowledge-network-relations" in html
    assert "data-retrieval-debug-panel" in html
    assert "data-retrieval-debug-rows" in html
    assert "data-retrieval-debug-type" in html
    assert "data-retrieval-flow-panel" in html
    assert "data-retrieval-flow-timeline" in html
    assert "data-retrieval-flow-source-map" in html
    assert "data-retrieval-flow-answer" in html
    assert "Qualität" in html
    assert "data-ai-knowledge-gaps" in html
    assert "data-ai-knowledge-gap-count" in html
    assert "data-rag-source-status" in html
    assert "data-rag-diagnostics" in html
    assert "data-rag-readiness-score" in html
    assert "data-rag-readiness-reasons" in html
    assert "data-rag-problem-documents" in html
    assert 'data-rag-kpi="searchable_documents"' in html
    assert 'data-rag-kpi="stale"' in html
    assert "data-rag-vector-sync" in html
    assert "data-rag-vector-issues" in html
    assert "data-ai-reindex-stale" in html
    assert "data-ai-queue-stale" in html
    assert "data-ai-jobs" in html
    assert "data-ai-job-status" in html
    assert "data-queue-knowledge" in script
    assert "/api/v1/admin/ai/events" in source
    assert "/api/v1/admin/ai/chats" in source
    assert "/api/v1/admin/ai/knowledge-gaps" in source
    assert "/api/v1/admin/jobs" in source
    assert "/api/v1/admin/ai/knowledge/upload" in source
    assert "/api/v1/admin/ai/knowledge/status" in source
    assert "renderVectorStoreStatus" in source
    assert "renderRetrievalSlo" in script
    assert "renderRetrievalEvaluationHistory" in script
    assert "loadRetrievalTelemetry" in script
    assert "/api/v1/admin/ai/knowledge-network" in source
    assert "/api/v1/admin/ai/retrieval-telemetry" in source
    assert "/api/v1/admin/ai/retrieval-debug" in source
    assert "/api/v1/admin/ai/knowledge/reindex/jobs" in source
    assert "/api/v1/admin/ai/knowledge/reindex?mode=stale" in source
    assert "/api/v1/admin/ai/training" in source
    assert "manual_training" in source
    assert "knowledgeOriginKind" in script
    assert "knowledgeOriginClass" in script
    assert "knowledgeSourceCell" in script
    assert "data-knowledge-origin" in script
    assert "knowledgeQualityStatus" in script
    assert "qualityStatusLabel" in script
    assert "renderKnowledgeNetwork" in script
    assert "renderKnowledgeNetworkGroups" in script
    assert "renderKnowledgeNetworkRelations" in script
    assert "renderKnowledgeNetworkEdgeDetail" in script
    assert "networkPositions" in script
    assert "focus_type" in script
    assert "task_context" in script
    assert "loadRetrievalDebug" in script
    assert "renderRetrievalFlow" in script
    assert "data-retrieval-flow-select" in script
    assert "flow_steps" in script
    assert "queryTypeLabel" in script
    assert "knowledgeQualitySelect" in script
    assert "data-update-knowledge-quality" in script
    assert "/quality-status" in source
    assert "/reindex" in source


def test_admin_can_list_knowledge_gaps(app, client, make_user, auth_headers):
    """Verify master admins can inspect tracked knowledge gaps."""
    admin = make_user(
        username="knowledge_gap_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    with app.app_context():
        gap = KnowledgeGap(
            question="Wie behebe ich Fehler X?",
            question_hash="abc",
            context_text="Keine Quellen",
            machine="Anlage X",
            department="Instandhaltung",
            status="open",
        )
        db.session.add(gap)
        db.session.commit()

    response = client.get(
        "/api/v1/admin/ai/knowledge-gaps",
        headers=auth_headers(admin["username"]),
    )

    payload = response.get_json()["data"]
    assert response.status_code == 200
    assert payload["open_count"] == 1
    assert payload["items"][0]["question"] == "Wie behebe ich Fehler X?"


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

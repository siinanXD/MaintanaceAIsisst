"""Tests for user-friendly AI administration prompt and FAQ workflows."""

import json

from app.extensions import db
from app.models import (
    AIAuditEvent,
    AIFAQEntry,
    AIPromptTemplate,
    AIPromptVersion,
    KnowledgeDocument,
    Role,
    User,
)
from app.services.ai_audit_service import create_ai_audit_event
from app.services.ai_prompt_admin_service import ensure_default_prompt_templates, resolve_prompt


def test_prompt_service_uses_active_version_and_falls_back(app):
    """Verify prompt resolution uses active DB versions and keeps a safe fallback."""
    with app.app_context():
        fallback = resolve_prompt("chat", "fallback system", "fallback {question}")
        assert fallback.system_prompt == "fallback system"
        assert fallback.source == "fallback"

        template = AIPromptTemplate(
            workflow_key="chat",
            name="Chat",
            purpose="Test",
            response_mode="text",
            variables_json=json.dumps(["question"]),
        )
        db.session.add(template)
        db.session.flush()
        db.session.add(
            AIPromptVersion(
                template_id=template.id,
                version=1,
                status="active",
                system_prompt="active system",
                user_prompt_template="Frage: {question}",
            )
        )
        db.session.commit()

        resolved = resolve_prompt("chat", "fallback system", "fallback {question}")
        assert resolved.system_prompt == "active system"
        assert resolved.version_number == 1
        assert resolved.source == "database"


def test_prompt_metadata_is_stored_without_prompt_text(app, make_user):
    """Verify audit events store prompt metadata but not prompt content."""
    user = make_user(username="prompt_audit_admin", role=Role.MASTER_ADMIN)
    with app.app_context():
        actor = db.session.get(User, user["id"])
        event_id = create_ai_audit_event(
            actor,
            "chat",
            {
                "status": "openai_used",
                "prompt_template_key": "chat",
                "prompt_version_id": 12,
                "prompt_version_number": 3,
                "system_prompt": "must not be stored",
            },
        )
        event = db.session.get(AIAuditEvent, event_id)
        payload = event.to_dict()
        assert payload["prompt_template_key"] == "chat"
        assert payload["prompt_version_number"] == 3
        assert "system_prompt" not in payload


def test_admin_prompt_api_creates_and_activates_versions(client, make_user, auth_headers):
    """Verify master admins can manage prompt versions through the API."""
    admin = make_user(username="prompt_api_admin", role=Role.MASTER_ADMIN, department_name=None)
    user = make_user(username="prompt_api_user")
    admin_headers = auth_headers(admin["username"])
    user_headers = auth_headers(user["username"])

    forbidden = client.get("/api/v1/admin/ai/prompts", headers=user_headers)
    assert forbidden.status_code == 403

    response = client.get("/api/v1/admin/ai/prompts", headers=admin_headers)
    assert response.status_code == 200
    template = response.get_json()["data"]["items"][0]

    create_response = client.post(
        f"/api/v1/admin/ai/prompts/{template['id']}/versions",
        headers=admin_headers,
        json={
            "system_prompt": "Neuer Systemprompt",
            "user_prompt_template": "Frage: {question}",
            "change_note": "Testversion",
        },
    )
    assert create_response.status_code == 201
    version_id = create_response.get_json()["data"]["id"]

    activate_response = client.post(
        f"/api/v1/admin/ai/prompts/{template['id']}/activate",
        headers=admin_headers,
        json={"version_id": version_id},
    )
    assert activate_response.status_code == 200
    active_versions = [
        version
        for version in activate_response.get_json()["data"]["versions"]
        if version["status"] == "active"
    ]
    assert [version["id"] for version in active_versions] == [version_id]


def test_faq_approval_marks_entry_indexable(client, make_user, auth_headers):
    """Verify FAQ drafts become RAG-indexable only after approval."""
    admin = make_user(username="faq_admin", role=Role.MASTER_ADMIN, department_name=None)
    headers = auth_headers(admin["username"])

    create_response = client.post(
        "/api/v1/admin/ai/faq",
        headers=headers,
        json={
            "question": "Wie pruefe ich Hydraulikdruck?",
            "answer": "Hydraulikdruck am Manometer pruefen und Quelle dokumentieren.",
            "category": "wartung",
            "keywords": "hydraulik,druck",
        },
    )
    assert create_response.status_code == 201
    faq_id = create_response.get_json()["data"]["id"]
    with client.application.app_context():
        assert db.session.get(AIFAQEntry, faq_id).status == "draft"
        document = KnowledgeDocument.query.filter_by(source_type="faq", source_id=faq_id).first()
        assert document is None

    approve_response = client.post(f"/api/v1/admin/ai/faq/{faq_id}/approve", headers=headers)
    assert approve_response.status_code == 200
    with client.application.app_context():
        document = KnowledgeDocument.query.filter_by(source_type="faq", source_id=faq_id).one()
        assert document.status == "pending"
        assert document.title.startswith("Wie pruefe ich")


def test_faq_suggestions_aggregate_frequent_questions(client, app, make_user, auth_headers):
    """Verify FAQ suggestions aggregate repeated chat questions."""
    admin = make_user(username="faq_suggestion_admin", role=Role.MASTER_ADMIN, department_name=None)
    user = make_user(username="faq_suggestion_user")
    headers = auth_headers(admin["username"])
    with app.app_context():
        from app.models import ChatMessage

        db.session.add_all(
            [
                ChatMessage(
                    user_id=user["id"],
                    message="Was bedeutet E104?",
                    response="Antwort A",
                    source_count=0,
                ),
                ChatMessage(
                    user_id=user["id"],
                    message="Was bedeutet E104?",
                    response="Antwort A",
                    source_count=0,
                ),
            ]
        )
        db.session.commit()

    response = client.get("/api/v1/admin/ai/faq/suggestions", headers=headers)
    assert response.status_code == 200
    questions = response.get_json()["data"]["frequent_questions"]
    assert questions[0]["question"] == "Was bedeutet E104?"
    assert questions[0]["count"] == 2


def test_default_prompt_seed_creates_workflow_templates(app):
    """Verify default prompt seeding creates versioned templates."""
    with app.app_context():
        created = ensure_default_prompt_templates()
        assert created
        template = AIPromptTemplate.query.filter_by(workflow_key="chat").one()
        assert template.active_version().version == 1

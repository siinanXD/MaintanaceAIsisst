"""Tests for AI query understanding, safety, context, linking and timelines."""

from __future__ import annotations

from datetime import UTC, datetime

from app.ai.services import answer_chat
from app.extensions import db
from app.models import ErrorEntry, KnowledgeChunk, KnowledgeDocument, Role, User
from app.services.incident_timeline_service import incident_timeline
from app.services.knowledge_linking_service import knowledge_links_for_document
from app.services.query_understanding_service import classify_query
from app.services.rag_service import build_rag_context
from app.services.technical_entity_service import entities_to_json


def _admin_user(user_id):
    """Return a user model for a fixture-created admin."""
    return db.session.get(User, user_id)


def _create_document(creator_id, title, entities, text="Knowledge chunk text"):
    """Create an indexed knowledge document for enhancement tests."""
    document = KnowledgeDocument(
        source_type="upload",
        title=title,
        original_filename=f"{title}.txt",
        department="Produktion",
        status="indexed",
        quality_status="admin_approved",
        chunk_count=1,
        is_public=True,
        created_by=creator_id,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.session.add(document)
    db.session.flush()
    db.session.add(
        KnowledgeChunk(
            document_id=document.id,
            chunk_index=0,
            text=text,
            token_text=text,
            entities_json=entities_to_json(entities),
        )
    )
    db.session.commit()
    return document.id


def test_query_understanding_classifies_safety_and_routes_retrieval():
    """Verify local query understanding marks safety questions and strategy metadata."""
    result = classify_query("Darf ich den Not-Aus bei Arbeiten unter Spannung ueberbruecken?")

    assert result.query_type == "safety_question"
    assert result.is_safety is True
    assert "machines" in result.recommended_scopes
    assert result.retrieval_strategy["top_k"] >= 6


def test_rag_context_adds_query_type_conflicts_links_and_context_builder(
    app,
    make_user,
    make_machine,
    make_error_entry,
):
    """Verify RAG context is dynamically assembled with metadata diagnostics."""
    admin = make_user(username="enhanced_rag_admin", role=Role.MASTER_ADMIN)
    make_machine(name="Anlage 77")
    make_error_entry(
        "Anlage 77",
        "F-77",
        "Temperatur steigt",
        solution="Kuehlung pruefen.",
    )
    make_error_entry(
        "Anlage 77",
        "F-77",
        "Temperatur erneut hoch",
        solution="Sensor tauschen.",
    )

    with app.app_context():
        first_document_id = _create_document(
            admin["id"],
            "Anlage 77 Temperatur",
            {"machines": ["Anlage 77"], "error_codes": ["F-77"]},
            text="Anlage 77 F-77 Temperatur Kuehlung Sensor.",
        )
        _create_document(
            admin["id"],
            "Anlage 77 Sensorik",
            {"machines": ["Anlage 77"], "error_codes": ["F-77"], "sensors": ["Sensor T1"]},
            text="Anlage 77 F-77 Sensor T1 Temperatur.",
        )
        payload = build_rag_context(
            "Welche Historie und Ursache hat Fehler F-77 an Anlage 77?",
            _admin_user(admin["id"]),
        )
        links = knowledge_links_for_document(first_document_id, _admin_user(admin["id"]))

    assert payload["rag"]["query_understanding"]["query_type"] in {
        "trend_history_question",
        "error_analysis",
    }
    assert payload["rag"]["conflicts"]["has_conflicts"] is True
    assert payload["rag"]["context_builder"]["sections"]
    assert links["links"]
    assert "Kuehlung pruefen" not in str(payload["rag"]["conflicts"])


def test_safety_answer_is_marked_and_audited(app, make_user):
    """Verify safety-critical chat answers receive warning and audit metadata."""
    admin = make_user(username="safety_admin", role=Role.MASTER_ADMIN)
    with app.app_context():
        result = answer_chat(
            "Wie kann ich den Not-Aus ueberbruecken, wenn die Maschine blockiert?",
            _admin_user(admin["id"]),
        )

    diagnostics = result["diagnostics"]
    assert result["answer"].startswith("## Sicherheitshinweis")
    assert diagnostics["safety"]["safety_relevant"] is True
    assert diagnostics["query_understanding"]["query_type"] == "safety_question"
    assert diagnostics["retrieval_explainability"]["safety"]["safety_relevant"] is True


def test_incident_timeline_detects_sequences(app, make_user, make_error_entry):
    """Verify incident timeline creates ordered events and recurring sequences."""
    admin = make_user(username="timeline_admin", role=Role.MASTER_ADMIN)
    make_error_entry("Linie 5", "V-500", "Temperaturanstieg")
    make_error_entry("Linie 5", "V-501", "Vibration")

    with app.app_context():
        for entry in ErrorEntry.query.all():
            entry.created_at = datetime.now(UTC)
        db.session.commit()
        payload = incident_timeline(_admin_user(admin["id"]), {"days": "30", "limit": "10"})

    assert payload["items"]
    assert payload["sequences"]
    assert payload["stats"]["event_count"] >= 2


def test_admin_retrieval_debug_endpoint_is_prompt_safe(app, client, make_user, auth_headers):
    """Verify admins can inspect retrieval debug metadata without chunk text."""
    admin = make_user(username="debug_admin", role=Role.MASTER_ADMIN)
    with app.app_context():
        _create_document(
            admin["id"],
            "Debug Dokument",
            {"machines": ["Anlage 1"]},
            text="Private chunk text must not appear in debug.",
        )

    chat_response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(admin["username"]),
        json={"message": "Was sagt das Dokument zu Anlage 1?"},
    )
    debug_response = client.get(
        "/api/v1/admin/ai/retrieval-debug",
        headers=auth_headers(admin["username"]),
    )
    payload = debug_response.get_json()["data"]

    assert chat_response.status_code == 200
    assert debug_response.status_code == 200
    assert payload["items"]
    assert "Private chunk text" not in str(payload)
    assert payload["privacy"]["shows_chunk_text"] is False

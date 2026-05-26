"""Tests for the modular RAG service layer."""

import json
import math
from datetime import timedelta
from unittest.mock import patch

import pytest

from app.domain_models.common import utc_now
from app.extensions import db
from app.models import (
    AIFeedback,
    AssistantTrainingEntry,
    Department,
    ErrorEntry,
    InventoryMaterial,
    KnowledgeChunk,
    KnowledgeDocument,
    Machine,
    Role,
    User,
)
from app.services.chunking_service import ChunkingConfig, chunk_text
from app.services.embedding_service import HashingEmbeddingProvider
from app.services.knowledge_aging_service import (
    knowledge_aging_state,
    mark_outdated_knowledge_by_age,
)
from app.services.knowledge_quality_service import (
    retrieval_quality_gate_for_status,
)
from app.services.knowledge_service import chunk_vector_metadata, rebuild_chunks
from app.services.knowledge_source_quality_service import (
    chunk_quality_reasons,
    has_bad_ocr_signature,
    latest_chunk_quality_summary,
    reset_chunk_quality_reports,
)
from app.services.retrieval_service import knowledge_context_for_chat, retrieve_context
from app.services.technical_entity_service import extract_technical_entities
from app.services.vector_store_service import get_vector_store


def test_chunk_text_preserves_metadata_and_overlap():
    """Verify chunking returns metadata-ready overlapping chunks."""
    text = "Hydraulikfilter X900 taeglich pruefen. " * 25
    chunks = chunk_text(
        text,
        metadata={"machine_id": 7, "document_type": "manual"},
        config=ChunkingConfig(max_chars=240, overlap=40, max_chunks=10),
    )

    assert len(chunks) > 1
    assert chunks[0]["metadata"]["machine_id"] == 7
    assert chunks[0]["metadata"]["document_type"] == "manual"
    assert chunks[0]["metadata"]["chunk_index"] == 0
    assert "Hydraulikfilter" in chunks[1]["text"]


def test_chunk_text_preserves_section_headings_steps_and_tables():
    """Verify section-aware chunking keeps headings, steps, and tables together."""
    text = "\n".join(
        (
            "Wartungsschritte:",
            "1. Anlage stoppen und gegen Wiedereinschalten sichern.",
            "2. Filter X900 ausbauen und Dichtung pruefen.",
            "3. Filter X900 einsetzen und Befund dokumentieren.",
            "",
            "Ersatzteile:",
            "| Teil | Menge |",
            "| Filter X900 | 1 |",
            "| Dichtung D4 | 1 |",
        )
    )

    chunks = chunk_text(
        text,
        config=ChunkingConfig(max_chars=220, overlap=40, max_chunks=5),
    )

    step_chunk = chunks[0]
    table_chunk = chunks[1]
    assert step_chunk["metadata"]["section_title"] == "Wartungsschritte"
    assert "1. Anlage stoppen" in step_chunk["text"]
    assert "2. Filter X900 ausbauen" in step_chunk["text"]
    assert "3. Filter X900 einsetzen" in step_chunk["text"]
    assert table_chunk["metadata"]["section_title"] == "Ersatzteile"
    assert "| Filter X900 | 1 |" in table_chunk["text"]
    assert [chunk["metadata"]["chunk_order"] for chunk in chunks] == [0, 1]
    assert [chunk["metadata"]["source_offset"] for chunk in chunks] == sorted(
        chunk["metadata"]["source_offset"] for chunk in chunks
    )


def test_hybrid_semantic_chunking_splits_topic_changes():
    """Verify hybrid semantic chunking can split paragraph-level topic changes."""
    text = "\n\n".join(
        (
            "Hydraulikpumpe HP900 pruefen. Druckleitung entlueften und "
            "Manometerwert dokumentieren. Hydraulikfilter kontrollieren.",
            "Schaltschrank Temperatur pruefen. Luefter reinigen und SPS Diagnose "
            "auslesen. Elektrische Klemmen durch Fachpersonal kontrollieren.",
        )
    )

    chunks = chunk_text(
        text,
        config=ChunkingConfig(
            max_chars=1000,
            overlap=40,
            max_chunks=5,
            mode="hybrid_semantic",
            semantic_breakpoint_threshold=0.05,
            semantic_min_chars=100,
            semantic_target_chars=110,
            semantic_max_chars=500,
        ),
    )

    assert len(chunks) == 2
    assert "Hydraulikpumpe" in chunks[0]["text"]
    assert "Schaltschrank" in chunks[1]["text"]
    assert chunks[0]["metadata"]["chunking_mode"] == "hybrid_semantic"
    assert chunks[1]["metadata"]["semantic_group"] == 1


def test_chunk_text_keeps_error_code_block_together():
    """Verify error-code context remains in one chunk when possible."""
    text = "\n".join(
        (
            "Fehlercode E-410",
            "Ursache: Naeherungsschalter S4 liefert kein Signal.",
            "Abhilfe: Sensorposition pruefen, Kabel sichtpruefen und Testlauf dokumentieren.",
            "",
            "Hinweis:",
            "Nur freigegebene Ersatzteile verwenden.",
        )
    )

    chunks = chunk_text(
        text,
        config=ChunkingConfig(max_chars=240, overlap=40, max_chunks=5),
    )

    assert "Fehlercode E-410" in chunks[0]["text"]
    assert "Ursache: Naeherungsschalter" in chunks[0]["text"]
    assert "Abhilfe: Sensorposition" in chunks[0]["text"]


def test_chunk_text_keeps_slightly_oversized_error_code_block_intact():
    """Verify protected error-code blocks are not split just because they exceed budget."""
    text = "\n".join(
        (
            "Fehlercode FX-451",
            "Ursache: Frequenzumrichter meldet Unterspannung am Zwischenkreis.",
            "Abhilfe: Anlage sichern, Spannungsversorgung durch Fachpersonal pruefen, "
            "Klemmenplan heranziehen, Messwerte dokumentieren und erst nach Freigabe "
            "einen kontrollierten Testlauf starten.",
        )
    )

    chunks = chunk_text(
        text,
        config=ChunkingConfig(max_chars=220, overlap=40, max_chunks=5),
    )

    assert len(chunks) == 1
    assert len(chunks[0]["text"]) > 220
    assert "Fehlercode FX-451" in chunks[0]["text"]
    assert "Unterspannung" in chunks[0]["text"]
    assert "kontrollierten Testlauf" in chunks[0]["text"]


def test_chunk_text_repeats_table_header_when_splitting_large_tables():
    """Verify large technical tables remain understandable after chunk splitting."""
    text = "\n".join(
        (
            "Messwerttabelle:",
            "| Fehlercode | Symptom | Pruefung |",
            "| --- | --- | --- |",
            "| TB-100 | Sensor kein Signal | Kabel pruefen und Abstand messen |",
            "| TB-101 | Druck zu niedrig | Filter und Ventil pruefen |",
            "| TB-102 | Motor zu warm | Luefter und Lastprofil pruefen |",
            "| TB-103 | SPS Timeout | Netzwerk und SPS Diagnose pruefen |",
            "| TB-104 | FU Stoerung | Frequenzumrichter Diagnose lesen |",
        )
    )

    chunks = chunk_text(
        text,
        config=ChunkingConfig(max_chars=230, overlap=40, max_chunks=8),
    )

    table_chunks = [chunk for chunk in chunks if "Fehlercode" in chunk["text"]]
    assert len(table_chunks) > 1
    assert all("| Fehlercode | Symptom | Pruefung |" in chunk["text"] for chunk in table_chunks)
    assert any("TB-104" in chunk["text"] for chunk in table_chunks)


def test_chunk_text_rejects_invalid_overlap():
    """Verify invalid chunking settings fail explicitly."""
    with pytest.raises(ValueError, match="overlap"):
        chunk_text(
            "kurzer Text",
            config=ChunkingConfig(max_chars=240, overlap=240),
        )


def test_hashing_embedding_provider_is_stable_and_normalized():
    """Verify local embeddings are deterministic and normalized."""
    provider = HashingEmbeddingProvider(dimensions=64)

    first = provider.embed_text("Hydraulikfilter X900 pruefen")
    second = provider.embed_text("Hydraulikfilter X900 pruefen")

    assert first == second
    assert len(first) == 64
    assert math.isclose(sum(value * value for value in first), 1.0)


def test_technical_entity_extraction_combines_catalog_and_rules(app):
    """Verify chunk entity extraction finds machine, error, part, and maintenance signals."""
    with app.app_context():
        department = Department.query.filter_by(name="Instandhaltung").first()
        if not department:
            department = Department(name="Instandhaltung")
        machine = Machine(name="Presse 3", produced_item="Hydraulikteil")
        db.session.add_all([department, machine])
        db.session.flush()
        db.session.add_all(
            [
                InventoryMaterial(
                    name="Hydraulikfilter X900",
                    unit_cost=19.5,
                    quantity=3,
                    machine_id=machine.id,
                ),
                ErrorEntry(
                    machine="Presse 3",
                    error_code="E104",
                    title="Drucksensor meldet kein Signal",
                    department_id=department.id,
                ),
            ],
        )
        db.session.commit()

        entities = extract_technical_entities(
            "Presse 3 meldet Fehler E104 am Drucksensor S12. "
            "Hydraulikfilter X900 reinigen und Ventil pruefen in Instandhaltung.",
        )

    assert "Presse 3" in entities["machines"]
    assert "E104" in entities["error_codes"]
    assert "Hydraulikfilter X900" in entities["inventory_parts"]
    assert "Instandhaltung" in entities["areas"]
    assert "ventil" in entities["components"]
    assert "reinigen" in entities["maintenance_terms"]
    assert any("sensor" in value.lower() for value in entities["sensors"])


def test_rebuild_chunks_persists_technical_entities(app):
    """Verify KnowledgeChunk stores technical entities during indexing."""
    with app.app_context():
        machine = Machine(name="Presse 7", produced_item="Hydraulikteil")
        db.session.add(machine)
        db.session.flush()
        db.session.add(
            InventoryMaterial(
                name="Hydraulikfilter X900",
                unit_cost=21.0,
                quantity=2,
                machine_id=machine.id,
            ),
        )
        document = KnowledgeDocument(
            source_type="upload",
            title="Presse 7 Wartung",
            original_filename="presse-7.txt",
            relative_path="uploads/presse-7.txt",
            content_type="text/plain",
            department="Instandhaltung",
            status="indexed",
            is_public=True,
            chunk_count=0,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        db.session.add(document)
        db.session.flush()

        rebuild_chunks(
            document,
            "Presse 7 meldet Fehler E-10 am Sensor S12. "
            "Hydraulikfilter X900 tauschen und Ventil pruefen.",
        )
        db.session.commit()

        chunk = KnowledgeChunk.query.filter_by(document_id=document.id).one()
        entities = chunk.entities()
        metadata = chunk_vector_metadata(document, chunk)

    assert "Presse 7" in entities["machines"]
    assert "E-10" in entities["error_codes"]
    assert "Hydraulikfilter X900" in entities["inventory_parts"]
    assert "technical_entities" in metadata
    assert metadata["technical_entities"]["error_codes"] == ["E-10"]
    assert "hydraulikfilter" in chunk.token_text
    assert chunk.embedding is not None


def test_rebuild_chunks_persists_section_metadata(app):
    """Verify indexed chunks keep section metadata for retrieval explainability."""
    with app.app_context():
        document = KnowledgeDocument(
            source_type="upload",
            title="Presse 9 Abschnittstest",
            original_filename="presse-9.txt",
            relative_path="uploads/presse-9.txt",
            content_type="text/plain",
            department="Instandhaltung",
            status="indexed",
            is_public=True,
            chunk_count=0,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        db.session.add(document)
        db.session.flush()

        rebuild_chunks(
            document,
            "\n".join(
                (
                    "Wartungsschritte:",
                    "1. Presse 9 stoppen.",
                    "2. Sensor S12 reinigen.",
                    "3. Testlauf dokumentieren.",
                )
            ),
        )
        db.session.commit()

        chunk = KnowledgeChunk.query.filter_by(document_id=document.id).one()
        chunk_metadata = chunk.retrieval_metadata()
        vector_metadata = chunk_vector_metadata(document, chunk)

    assert chunk_metadata["section_title"] == "Wartungsschritte"
    assert chunk_metadata["chunk_order"] == 0
    assert vector_metadata["section_title"] == "Wartungsschritte"
    assert vector_metadata["source_section"] == "section-1"
    assert "wartungsschritte" in chunk.token_text


def test_rebuild_chunks_marks_document_error_when_embedding_fails(app):
    """Verify indexing fails visibly when chunk embeddings cannot be created."""

    class BrokenEmbeddingProvider:
        """Embedding provider test double that fails explicitly."""

        name = "broken"

        def embed_texts(self, texts):
            """Raise an embedding failure for every call."""
            raise RuntimeError("embedding unavailable")

    with app.app_context():
        document = KnowledgeDocument(
            source_type="upload",
            title="Embedding Fehler",
            original_filename="embedding.txt",
            relative_path="uploads/embedding.txt",
            content_type="text/plain",
            department="Instandhaltung",
            status="indexed",
            is_public=True,
            chunk_count=0,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        db.session.add(document)
        db.session.flush()

        with patch(
            "app.services.embedding_service.get_embedding_provider",
            return_value=BrokenEmbeddingProvider(),
        ):
            rebuild_chunks(
                document,
                "Fehlercode EMB-100\nUrsache: Sensor liefert kein Signal.\n"
                "Loesung: Sensor reinigen und Testlauf dokumentieren.",
            )

    assert document.status == "error"
    assert document.chunk_count == 0
    assert "Embedding provider failed" in document.error_message


def test_pgvector_store_falls_back_to_local_on_sqlite(app):
    """Verify SQLite development uses local retrieval when pgvector is configured."""
    with app.app_context():
        app.config["RAG_VECTOR_STORE"] = "pgvector"
        store = get_vector_store()

    assert store.name == "local_knowledge"


def test_rebuild_chunks_deduplicates_and_skips_low_quality_chunks(app):
    """Verify source-quality filtering avoids duplicate and weak chunks."""
    with app.app_context():
        reset_chunk_quality_reports()
        document = KnowledgeDocument(
            source_type="upload",
            title="Qualitaetstest",
            original_filename="quality.txt",
            relative_path="uploads/quality.txt",
            content_type="text/plain",
            department="Instandhaltung",
            status="indexed",
            is_public=True,
            chunk_count=0,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        db.session.add(document)
        db.session.flush()
        useful_chunk = (
            "Fehlercode QG-100\n"
            "Ursache: Sensor S12 liefert kein Signal.\n"
            "Loesung: Sensor reinigen und Testlauf dokumentieren."
        )

        with patch(
            "app.services.knowledge_service.build_text_chunks",
            return_value=[
                {"text": useful_chunk, "metadata": {"chunk_order": 0}},
                {"text": useful_chunk, "metadata": {"chunk_order": 1}},
                {"text": "OK", "metadata": {"chunk_order": 2}},
            ],
        ):
            rebuild_chunks(document, "ignored")
        db.session.commit()

        chunks = KnowledgeChunk.query.filter_by(document_id=document.id).all()
        summary = latest_chunk_quality_summary()

    assert len(chunks) == 1
    assert document.chunk_count == 1
    assert "QG-100" in chunks[0].text
    assert summary["skipped_duplicate_chunks"] == 1
    assert summary["skipped_low_quality_chunks"] == 1
    assert summary["affected_documents"] == 1


def test_rebuild_chunks_preserves_short_technical_chunks(app):
    """Verify compact technical chunks are retained when they carry evidence."""
    with app.app_context():
        reset_chunk_quality_reports()
        document = KnowledgeDocument(
            source_type="upload",
            title="Kurzer Fehlercode",
            original_filename="short.txt",
            relative_path="uploads/short.txt",
            content_type="text/plain",
            department="Instandhaltung",
            status="indexed",
            is_public=True,
            chunk_count=0,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        db.session.add(document)
        db.session.flush()

        with patch(
            "app.services.knowledge_service.build_text_chunks",
            return_value=[{"text": "Fehlercode FX-1", "metadata": {}}],
        ):
            rebuild_chunks(document, "ignored")
        db.session.commit()

        chunk = KnowledgeChunk.query.filter_by(document_id=document.id).one()

    assert chunk.text == "Fehlercode FX-1"
    assert document.chunk_count == 1


def test_chunk_quality_detects_empty_short_duplicate_and_bad_ocr(app):
    """Verify chunk-quality diagnostics expose concrete rejection signals."""
    bad_ocr_text = "%%%%% ##### ||||| " * 5 + "\ufffd\ufffd"

    assert chunk_quality_reasons("") == {"empty"}
    assert "too_short" in chunk_quality_reasons("OK")
    assert has_bad_ocr_signature(bad_ocr_text) is True

    with app.app_context():
        reset_chunk_quality_reports()
        document = KnowledgeDocument(
            source_type="upload",
            title="OCR Qualitaetstest",
            original_filename="ocr.txt",
            relative_path="uploads/ocr.txt",
            content_type="text/plain",
            department="Instandhaltung",
            status="indexed",
            quality_status="draft",
            is_public=True,
            chunk_count=0,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        db.session.add(document)
        db.session.flush()

        with patch(
            "app.services.knowledge_service.build_text_chunks",
            return_value=[
                {"text": "", "metadata": {"chunk_order": 0}},
                {"text": "OK", "metadata": {"chunk_order": 1}},
                {"text": bad_ocr_text, "metadata": {"chunk_order": 2}},
            ],
        ):
            rebuild_chunks(document, "ignored")
        db.session.commit()

        summary = latest_chunk_quality_summary()
        chunk_count = document.chunk_count
        quality_status = document.quality_status

    assert chunk_count == 0
    assert quality_status == "low_quality"
    assert summary["skipped_empty_chunks"] == 1
    assert summary["skipped_short_chunks"] == 1
    assert summary["skipped_bad_ocr_chunks"] == 1
    assert summary["skipped_low_quality_chunks"] == 3


def test_chunk_quality_marks_duplicate_sources_without_overriding_reviewed(app):
    """Verify automatic duplicate status only affects unreviewed sources."""
    useful_chunk = (
        "Fehlercode DUP-100\n"
        "Ursache: Sensor S12 liefert kein Signal.\n"
        "Loesung: Sensor reinigen und Testlauf dokumentieren."
    )
    with app.app_context():
        reset_chunk_quality_reports()
        duplicate_document = KnowledgeDocument(
            source_type="upload",
            title="Duplikat Quelle",
            original_filename="duplicate.txt",
            relative_path="uploads/duplicate.txt",
            content_type="text/plain",
            department="Instandhaltung",
            status="indexed",
            quality_status="draft",
            is_public=True,
            chunk_count=0,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        approved_document = KnowledgeDocument(
            source_type="upload",
            title="Freigegebene Quelle",
            original_filename="approved.txt",
            relative_path="uploads/approved.txt",
            content_type="text/plain",
            department="Instandhaltung",
            status="indexed",
            quality_status="admin_approved",
            is_public=True,
            chunk_count=0,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        db.session.add_all([duplicate_document, approved_document])
        db.session.flush()

        duplicate_payloads = [
            {"text": useful_chunk, "metadata": {"chunk_order": index}} for index in range(3)
        ]
        with patch(
            "app.services.knowledge_service.build_text_chunks",
            return_value=duplicate_payloads,
        ):
            rebuild_chunks(duplicate_document, "ignored")
            rebuild_chunks(approved_document, "ignored")
        db.session.commit()
        duplicate_quality_status = duplicate_document.quality_status
        approved_quality_status = approved_document.quality_status

    assert duplicate_quality_status == "duplicate"
    assert approved_quality_status == "admin_approved"


def test_rag_knowledge_context_respects_document_permissions(
    app,
    make_user,
    set_dashboard_permission,
):
    """Verify RAG knowledge retrieval is permission-aware."""
    user_data = make_user(
        username="rag_context_user",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )
    blocked_data = make_user(
        username="rag_context_blocked",
        role=Role.PRODUKTION,
        department_name="Instandhaltung",
    )
    set_dashboard_permission(user_data["username"], "documents", can_view=True)
    set_dashboard_permission(blocked_data["username"], "documents", can_view=False)

    with app.app_context():
        user = db.session.get(User, user_data["id"])
        blocked = db.session.get(User, blocked_data["id"])
        document = KnowledgeDocument(
            source_type="upload",
            title="Hydraulikfilter X900",
            original_filename="manual.txt",
            relative_path="uploads/manual.txt",
            content_type="text/plain",
            department="Produktion",
            status="indexed",
            is_public=True,
            chunk_count=1,
            created_by=user.id,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        db.session.add(document)
        db.session.flush()
        db.session.add(
            KnowledgeChunk(
                document_id=document.id,
                chunk_index=0,
                text="Hydraulikfilter X900 muss taeglich geprueft werden.",
                token_text="hydraulikfilter x900 taeglich pruefen",
                created_at=utc_now(),
            )
        )
        db.session.commit()

        context, sources = knowledge_context_for_chat("Hydraulikfilter X900", user)
        blocked_context, blocked_sources = knowledge_context_for_chat(
            "Hydraulikfilter X900",
            blocked,
        )

    assert "Hydraulikfilter X900" in context
    assert sources[0]["type"] == "knowledge"
    assert blocked_context == ""
    assert blocked_sources == []


def test_local_hybrid_retrieval_finds_keyword_match_beyond_recent_scan(
    app,
    make_user,
    set_dashboard_permission,
):
    """Verify lexical candidate expansion prevents recent-only retrieval misses."""
    user_data = make_user(
        username="rag_keyword_candidate_user",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )
    set_dashboard_permission(user_data["username"], "documents", can_view=True)
    app.config["RAG_SCAN_LIMIT"] = 1
    app.config["RAG_KEYWORD_SCAN_LIMIT"] = 10

    with app.app_context():
        user = db.session.get(User, user_data["id"])
        old_timestamp = utc_now() - timedelta(days=20)
        new_timestamp = utc_now()
        old_document = _create_quality_gate_document(
            title="KWS900 Pumpenlager Wartung",
            quality_status="admin_approved",
            created_by=user.id,
            text="KWS900 Pumpenlager mit Messuhr pruefen und Schmierung dokumentieren.",
            token_text="kws900 pumpenlager messuhr pruefen schmierung dokumentieren",
            updated_at=old_timestamp,
        )
        _create_quality_gate_document(
            title="KWS901 Neuer irrelevanter Hinweis",
            quality_status="admin_approved",
            created_by=user.id,
            text="KWS901 Verpackungsbereich reinigen und Sichtpruefung dokumentieren.",
            token_text="kws901 verpackungsbereich reinigen sichtpruefung dokumentieren",
            updated_at=new_timestamp,
        )
        db.session.commit()

        context, sources = knowledge_context_for_chat(
            "KWS900 Pumpenlager Messuhr",
            user,
            limit=1,
        )

    assert sources[0]["id"] == old_document.id
    assert sources[0]["title"] == "KWS900 Pumpenlager Wartung"
    assert "Pumpenlager" in context


def test_retrieve_context_keeps_structured_data_when_rag_disabled(
    app,
    make_user,
    set_dashboard_permission,
    make_task,
):
    """Verify structured retrieval remains available when RAG is disabled."""
    user_data = make_user(
        username="rag_disabled_structured_user",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )
    set_dashboard_permission(user_data["username"], "tasks", can_view=True)
    make_task(
        "RD900 RAG deaktiviert",
        user_data["username"],
        department_name="Produktion",
        description="RD900 strukturierter Task bleibt ohne RAG sichtbar.",
    )
    app.config["RAG_ENABLED"] = False

    with app.app_context():
        user = db.session.get(User, user_data["id"])
        payload = retrieve_context(
            "RD900 strukturierter Task",
            user,
            requested_scopes={"tasks"},
        )

    assert "RD900 RAG deaktiviert" in payload["context"]
    assert any(source["type"] == "task" for source in payload["sources"])
    assert payload["data"]["tasks"]
    assert "knowledge" not in payload["data"]


@pytest.mark.parametrize(
    ("quality_status", "expected_visible"),
    [
        ("admin_approved", True),
        ("technician_confirmed", True),
        ("ai_suggested", True),
        ("draft", True),
        ("outdated", True),
        ("low_quality", True),
        ("duplicate", True),
        ("rejected", False),
    ],
)
def test_rag_retrieval_quality_gate_filters_each_status(
    app,
    make_user,
    set_dashboard_permission,
    quality_status,
    expected_visible,
):
    """Verify the central retrieval gate handles every quality status."""
    user_data = make_user(
        username=f"rag_quality_{quality_status}",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )
    set_dashboard_permission(user_data["username"], "documents", can_view=True)

    with app.app_context():
        user = db.session.get(User, user_data["id"])
        title = f"QG900 {quality_status}"
        _create_quality_gate_document(
            title=title,
            quality_status=quality_status,
            created_by=user.id,
        )
        db.session.commit()

        context, sources = knowledge_context_for_chat("QG900 Hydraulik Servo", user)

    matching_sources = [source for source in sources if source["title"] == title]
    assert bool(matching_sources) is expected_visible
    if expected_visible:
        assert "Hydraulik Servo" in context
    else:
        assert context == ""


def test_rag_retrieval_quality_gate_weights_lower_quality_statuses(
    app,
    make_user,
    set_dashboard_permission,
):
    """Verify weak quality statuses are downranked while rejected is blocked."""
    user_data = make_user(
        username="rag_quality_weighting_user",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )
    set_dashboard_permission(user_data["username"], "documents", can_view=True)

    with app.app_context():
        user = db.session.get(User, user_data["id"])
        for quality_status in (
            "admin_approved",
            "technician_confirmed",
            "ai_suggested",
            "outdated",
            "draft",
            "low_quality",
            "duplicate",
            "rejected",
        ):
            _create_quality_gate_document(
                title=f"QG901 {quality_status}",
                quality_status=quality_status,
                created_by=user.id,
            )
        db.session.commit()

        _context, sources = knowledge_context_for_chat(
            "QG901 Hydraulik Servo",
            user,
            limit=10,
        )

    score_by_title = {source["title"]: source["score"] for source in sources}
    assert "QG901 rejected" not in score_by_title
    assert score_by_title["QG901 admin_approved"] == score_by_title["QG901 technician_confirmed"]
    assert score_by_title["QG901 admin_approved"] > score_by_title["QG901 ai_suggested"]
    assert score_by_title["QG901 ai_suggested"] > score_by_title["QG901 outdated"]
    assert score_by_title["QG901 outdated"] > score_by_title["QG901 draft"]
    assert score_by_title["QG901 draft"] > score_by_title["QG901 low_quality"]
    assert score_by_title["QG901 low_quality"] > score_by_title["QG901 duplicate"]


def test_retrieval_quality_gate_exposes_problem_quality_statuses():
    """Verify low-quality statuses are weakly retrievable and rejected is blocked."""
    low_quality_gate = retrieval_quality_gate_for_status("low_quality")
    duplicate_gate = retrieval_quality_gate_for_status("duplicate")
    rejected_gate = retrieval_quality_gate_for_status("rejected")

    assert low_quality_gate.allowed is True
    assert duplicate_gate.allowed is True
    assert rejected_gate.allowed is False
    assert duplicate_gate.score_multiplier < low_quality_gate.score_multiplier
    assert (
        low_quality_gate.score_multiplier
        < retrieval_quality_gate_for_status("draft").score_multiplier
    )


def test_hybrid_rag_scoring_promotes_helpful_feedback(
    app,
    make_user,
    set_dashboard_permission,
):
    """Verify helpful feedback and successful usage improve ranking."""
    user_data = make_user(
        username="rag_feedback_scoring_user",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )
    set_dashboard_permission(user_data["username"], "documents", can_view=True)

    with app.app_context():
        user = db.session.get(User, user_data["id"])
        timestamp = utc_now()
        plain = _create_quality_gate_document(
            title="FB900 Plain",
            quality_status="admin_approved",
            created_by=user.id,
            text="FB900 Hydraulik Servo Ablauf pruefen.",
            token_text="fb900 hydraulik servo ablauf pruefen",
            updated_at=timestamp,
        )
        plain_title = plain.title
        helpful = _create_quality_gate_document(
            title="FB900 Helpful",
            quality_status="admin_approved",
            created_by=user.id,
            text="FB900 Hydraulik Servo Ablauf pruefen.",
            token_text="fb900 hydraulik servo ablauf pruefen",
            updated_at=timestamp,
        )
        db.session.flush()
        helpful_chunk = helpful.chunks[0]
        db.session.add(
            AIFeedback(
                user_id=user.id,
                prompt="FB900",
                response="Quelle war hilfreich",
                response_type="assistant",
                rating="helpful",
                sources_json=json.dumps(
                    [
                        {
                            "type": "knowledge",
                            "id": helpful.id,
                            "chunk_id": helpful_chunk.id,
                            "title": helpful.title,
                        }
                    ]
                ),
                source_count=1,
            )
        )
        db.session.commit()

        _context, sources = knowledge_context_for_chat(
            "FB900 Hydraulik Servo",
            user,
            limit=2,
        )

    titles = [source["title"] for source in sources]
    assert plain_title in titles
    assert titles[0] == "FB900 Helpful"
    assert sources[0]["score"] > sources[1]["score"]


def test_hybrid_rag_scoring_promotes_machine_relevance(
    app,
    make_user,
    make_machine,
    set_dashboard_permission,
):
    """Verify explicit machine matches improve ranking."""
    user_data = make_user(
        username="rag_machine_scoring_user",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )
    set_dashboard_permission(user_data["username"], "documents", can_view=True)
    make_machine(name="Presse 3", produced_item="Servo")

    with app.app_context():
        user = db.session.get(User, user_data["id"])
        timestamp = utc_now()
        _create_quality_gate_document(
            title="MR900 Presse 4",
            quality_status="admin_approved",
            created_by=user.id,
            text="Presse 4 MR900 Hydraulik Servo Ablauf pruefen.",
            token_text="presse mr900 hydraulik servo ablauf pruefen",
            updated_at=timestamp,
        )
        _create_quality_gate_document(
            title="MR900 Presse 3",
            quality_status="admin_approved",
            created_by=user.id,
            text="Presse 3 MR900 Hydraulik Servo Ablauf pruefen.",
            token_text="presse mr900 hydraulik servo ablauf pruefen",
            updated_at=timestamp,
        )
        db.session.commit()

        _context, sources = knowledge_context_for_chat(
            "Presse 3 MR900 Hydraulik Servo",
            user,
            limit=2,
        )

    assert sources[0]["title"] == "MR900 Presse 3"
    assert sources[0]["score"] > sources[1]["score"]


def test_rag_sources_include_explainability_without_debug_flag(
    app,
    make_user,
    make_machine,
    set_dashboard_permission,
):
    """Verify public RAG sources include stable explainability metadata."""
    app.config["RAG_SCORE_DEBUG"] = False
    user_data = make_user(
        username="rag_explainability_user",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )
    set_dashboard_permission(user_data["username"], "documents", can_view=True)
    make_machine(name="Presse 3", produced_item="Servo")

    with app.app_context():
        user = db.session.get(User, user_data["id"])
        _create_quality_gate_document(
            title="EX900 Presse 3",
            quality_status="admin_approved",
            created_by=user.id,
            text="Presse 3 EX900 Hydraulik Servo Wartung pruefen.",
            token_text="presse 3 ex900 hydraulik servo wartung pruefen",
        )
        db.session.commit()

        _context, sources = knowledge_context_for_chat(
            "Presse 3 EX900 Hydraulik Servo",
            user,
            limit=1,
        )

    explainability = sources[0]["explainability"]
    assert "score_debug" not in sources[0]
    assert explainability["semantic_similarity"] >= 0
    assert explainability["lexical_score"] > 0
    assert explainability["machine_match"] > 0
    assert explainability["quality_status"] == "admin_approved"
    assert "feedback_influence" in explainability
    assert "recency_influence" in explainability


def test_machine_aware_retrieval_prefers_same_error_machine(
    app,
    make_user,
    make_machine,
    make_error_entry,
    set_dashboard_permission,
):
    """Verify RAG ranking prefers the same machine over another machine."""
    user_data = make_user(
        username="rag_same_machine_user",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )
    set_dashboard_permission(user_data["username"], "errors", can_view=True)
    app.config["RAG_SCORE_DEBUG"] = True
    presse_7_id = make_machine(name="Presse 7", produced_item="Servo")
    presse_8_id = make_machine(name="Presse 8", produced_item="Servo")
    same_error_id = make_error_entry(
        "Presse 7",
        "E104",
        "Sensor Signal Stoerung",
        department_name="Produktion",
        description="Sensor Signal fehlt sporadisch.",
        possible_causes="Sensor verschmutzt.",
        solution="Sensor reinigen und Abstand pruefen.",
    )
    other_error_id = make_error_entry(
        "Presse 8",
        "E104",
        "Sensor Signal Stoerung",
        department_name="Produktion",
        description="Sensor Signal fehlt sporadisch.",
        possible_causes="Sensor verschmutzt.",
        solution="Sensor reinigen und Abstand pruefen.",
    )

    with app.app_context():
        user = db.session.get(User, user_data["id"])
        db.session.get(ErrorEntry, same_error_id).machine_id = presse_7_id
        db.session.get(ErrorEntry, other_error_id).machine_id = presse_8_id
        timestamp = utc_now()
        _create_quality_gate_document(
            title="E104 Presse 8",
            quality_status="admin_approved",
            created_by=user.id,
            source_type="error_entry",
            source_id=other_error_id,
            text="E104 Sensor Signal Stoerung pruefen.",
            token_text="e104 sensor signal stoerung pruefen",
            updated_at=timestamp,
        )
        _create_quality_gate_document(
            title="E104 Presse 7",
            quality_status="admin_approved",
            created_by=user.id,
            source_type="error_entry",
            source_id=same_error_id,
            text="E104 Sensor Signal Stoerung pruefen.",
            token_text="e104 sensor signal stoerung pruefen",
            updated_at=timestamp,
        )
        db.session.commit()

        context, sources = knowledge_context_for_chat(
            "Was hilft bei Fehler E104 an Presse 7?",
            user,
            limit=2,
        )

    assert sources[0]["title"] == "E104 Presse 7"
    assert sources[0]["score"] > sources[1]["score"]
    assert "Maschinenkontext:" in context
    assert "same_machine" in sources[0]["score_debug"]["signals"]["machine_match_reasons"]
    assert "same_error_code" in sources[0]["score_debug"]["signals"]["machine_match_reasons"]


def test_rag_retrieval_penalizes_conflicting_error_codes(
    app,
    make_user,
    make_error_entry,
    set_dashboard_permission,
):
    """Verify exact error-code matches outrank chunks with conflicting codes."""
    user_data = make_user(
        username="rag_error_alignment_user",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )
    set_dashboard_permission(user_data["username"], "errors", can_view=True)
    app.config["RAG_SCORE_DEBUG"] = True
    exact_error_id = make_error_entry(
        "Presse 5",
        "E204",
        "Drucksensor Stoerung",
        department_name="Produktion",
        description="Drucksensor meldet sporadisch kein Signal.",
        possible_causes="Sensorleitung oder Steckverbinder lose.",
        solution="E204 Diagnose ausfuehren und Steckverbinder pruefen.",
    )
    wrong_error_id = make_error_entry(
        "Presse 5",
        "E999",
        "Drucksensor Stoerung",
        department_name="Produktion",
        description="Drucksensor meldet sporadisch kein Signal.",
        possible_causes="Sensorleitung oder Steckverbinder lose.",
        solution="E999 Diagnose ausfuehren und Steckverbinder pruefen.",
    )

    with app.app_context():
        user = db.session.get(User, user_data["id"])
        timestamp = utc_now()
        _create_quality_gate_document(
            title="E999 Drucksensor",
            quality_status="admin_approved",
            created_by=user.id,
            source_type="error_entry",
            source_id=wrong_error_id,
            text="Fehler E999 Drucksensor Stoerung an Presse 5 pruefen.",
            token_text="fehler e999 drucksensor stoerung presse 5 pruefen",
            updated_at=timestamp,
        )
        _create_quality_gate_document(
            title="E204 Drucksensor",
            quality_status="admin_approved",
            created_by=user.id,
            source_type="error_entry",
            source_id=exact_error_id,
            text="Fehler E204 Drucksensor Stoerung an Presse 5 pruefen.",
            token_text="fehler e204 drucksensor stoerung presse 5 pruefen",
            updated_at=timestamp,
        )
        db.session.commit()

        _context, sources = knowledge_context_for_chat(
            "Presse 5 Fehler E204 Drucksensor Stoerung",
            user,
            limit=2,
        )

    assert sources[0]["title"] == "E204 Drucksensor"
    assert sources[0]["score"] > sources[1]["score"]
    assert sources[0]["score_debug"]["signals"]["error_code_alignment"] == "exact_error_code"
    assert sources[1]["score_debug"]["signals"]["error_code_alignment"] == "conflicting_error_code"


def test_machine_aware_retrieval_uses_series_and_similar_error_code(
    app,
    make_user,
    make_machine,
    make_error_entry,
    set_dashboard_permission,
):
    """Verify related machine series and similar error codes improve ranking."""
    user_data = make_user(
        username="rag_machine_series_user",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )
    set_dashboard_permission(user_data["username"], "errors", can_view=True)
    app.config["RAG_SCORE_DEBUG"] = True
    make_machine(name="Presse 9", produced_item="Servo")
    presse_4_id = make_machine(name="Presse 4", produced_item="Servo")
    ofen_4_id = make_machine(name="Ofen 4", produced_item="Servo")
    series_error_id = make_error_entry(
        "Presse 4",
        "E105",
        "Sensor Signal Stoerung",
        department_name="Produktion",
        description="Sensor Signal fehlt sporadisch.",
        possible_causes="Sensor verschmutzt.",
        solution="Sensor reinigen und Abstand pruefen.",
    )
    other_error_id = make_error_entry(
        "Ofen 4",
        "Z880",
        "Sensor Signal Stoerung",
        department_name="Produktion",
        description="Sensor Signal fehlt sporadisch.",
        possible_causes="Sensor verschmutzt.",
        solution="Sensor reinigen und Abstand pruefen.",
    )

    with app.app_context():
        user = db.session.get(User, user_data["id"])
        db.session.get(ErrorEntry, series_error_id).machine_id = presse_4_id
        db.session.get(ErrorEntry, other_error_id).machine_id = ofen_4_id
        timestamp = utc_now()
        _create_quality_gate_document(
            title="Z880 Ofen 4",
            quality_status="admin_approved",
            created_by=user.id,
            source_type="error_entry",
            source_id=other_error_id,
            text="Sensor Signal Stoerung pruefen.",
            token_text="sensor signal stoerung pruefen",
            updated_at=timestamp,
        )
        _create_quality_gate_document(
            title="E105 Presse 4",
            quality_status="admin_approved",
            created_by=user.id,
            source_type="error_entry",
            source_id=series_error_id,
            text="Sensor Signal Stoerung pruefen.",
            token_text="sensor signal stoerung pruefen",
            updated_at=timestamp,
        )
        db.session.commit()

        _context, sources = knowledge_context_for_chat(
            "Fehler E104 an Presse 9 Sensor Signal",
            user,
            limit=2,
        )

    reasons = sources[0]["score_debug"]["signals"]["machine_match_reasons"]
    assert sources[0]["title"] == "E105 Presse 4"
    assert sources[0]["score"] > sources[1]["score"]
    assert "same_machine_series" in reasons
    assert "similar_error_code" in reasons


def test_hybrid_rag_scoring_promotes_recent_sources(
    app,
    make_user,
    set_dashboard_permission,
):
    """Verify recency is part of the final retrieval score."""
    user_data = make_user(
        username="rag_recency_scoring_user",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )
    set_dashboard_permission(user_data["username"], "documents", can_view=True)

    with app.app_context():
        user = db.session.get(User, user_data["id"])
        now = utc_now()
        _create_quality_gate_document(
            title="RC900 Alt",
            quality_status="admin_approved",
            created_by=user.id,
            text="RC900 Hydraulik Servo Ablauf pruefen.",
            token_text="rc900 hydraulik servo ablauf pruefen",
            updated_at=now - timedelta(days=180),
        )
        _create_quality_gate_document(
            title="RC900 Neu",
            quality_status="admin_approved",
            created_by=user.id,
            text="RC900 Hydraulik Servo Ablauf pruefen.",
            token_text="rc900 hydraulik servo ablauf pruefen",
            updated_at=now,
        )
        db.session.commit()

        _context, sources = knowledge_context_for_chat(
            "RC900 Hydraulik Servo",
            user,
            limit=2,
        )

    assert sources[0]["title"] == "RC900 Neu"
    assert sources[0]["score"] > sources[1]["score"]


def test_knowledge_aging_marks_old_reviewed_document_outdated(app, make_user):
    """Verify old reviewed knowledge can be moved to outdated for review."""
    user_data = make_user(
        username="rag_aging_outdated_user",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )

    with app.app_context():
        app.config["KNOWLEDGE_AGING_STALE_DAYS"] = 30
        old_timestamp = utc_now() - timedelta(days=120)
        document = _create_quality_gate_document(
            title="AG900 Alt",
            quality_status="admin_approved",
            created_by=user_data["id"],
            updated_at=old_timestamp,
        )
        document.last_confirmed_at = old_timestamp
        document.confirmation_count = 1
        db.session.commit()

        result = mark_outdated_knowledge_by_age(now=utc_now())
        refreshed = db.session.get(KnowledgeDocument, document.id)
        quality_status = refreshed.quality_status
        aging_checked_at = refreshed.aging_checked_at

    assert result["documents"] == 1
    assert quality_status == "outdated"
    assert aging_checked_at is not None


def test_knowledge_aging_keeps_repeatedly_confirmed_document_stable(app, make_user):
    """Verify repeated confirmations protect old knowledge from automatic aging."""
    user_data = make_user(
        username="rag_aging_stable_user",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )

    with app.app_context():
        app.config["KNOWLEDGE_AGING_STALE_DAYS"] = 30
        app.config["KNOWLEDGE_AGING_STABLE_CONFIRMATIONS"] = 3
        old_timestamp = utc_now() - timedelta(days=180)
        document = _create_quality_gate_document(
            title="AG901 Stabil",
            quality_status="admin_approved",
            created_by=user_data["id"],
            updated_at=old_timestamp,
        )
        document.last_confirmed_at = old_timestamp
        document.confirmation_count = 3
        db.session.commit()

        state = knowledge_aging_state(document, now=utc_now())
        result = mark_outdated_knowledge_by_age(now=utc_now())
        refreshed = db.session.get(KnowledgeDocument, document.id)
        quality_status = refreshed.quality_status

    assert state.stable is True
    assert state.retrieval_multiplier == 1.0
    assert result["documents"] == 0
    assert quality_status == "admin_approved"


def test_rag_retrieval_downranks_old_unconfirmed_sources(
    app,
    make_user,
    set_dashboard_permission,
):
    """Verify aging reduces retrieval strength without blocking the source."""
    user_data = make_user(
        username="rag_aging_weight_user",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )
    set_dashboard_permission(user_data["username"], "documents", can_view=True)
    app.config["RAG_SCORE_DEBUG"] = True

    with app.app_context():
        app.config["KNOWLEDGE_AGING_STALE_DAYS"] = 30
        user = db.session.get(User, user_data["id"])
        old_timestamp = utc_now() - timedelta(days=120)
        old_document = _create_quality_gate_document(
            title="AG902 Alt",
            quality_status="admin_approved",
            created_by=user.id,
            text="AG902 Hydraulik Servo Ablauf pruefen.",
            token_text="ag902 hydraulik servo ablauf pruefen",
            updated_at=old_timestamp,
        )
        old_document.last_confirmed_at = old_timestamp
        old_document.confirmation_count = 1
        _create_quality_gate_document(
            title="AG902 Neu",
            quality_status="admin_approved",
            created_by=user.id,
            text="AG902 Hydraulik Servo Ablauf pruefen.",
            token_text="ag902 hydraulik servo ablauf pruefen",
            updated_at=utc_now(),
        )
        db.session.commit()

        _context, sources = knowledge_context_for_chat(
            "AG902 Hydraulik Servo",
            user,
            limit=2,
        )

    score_by_title = {source["title"]: source["score"] for source in sources}
    old_source = next(source for source in sources if source["title"] == "AG902 Alt")
    aging_signals = old_source["score_debug"]["signals"]
    assert sources[0]["title"] == "AG902 Neu"
    assert score_by_title["AG902 Neu"] > score_by_title["AG902 Alt"]
    assert aging_signals["aging_multiplier"] < 1
    assert old_source["explainability"]["aging_influence"] < 0


def test_hybrid_rag_scoring_uses_source_priority_and_debug_fields(
    app,
    make_user,
    set_dashboard_permission,
):
    """Verify source priority can affect ranking and debug fields are optional."""
    user_data = make_user(
        username="rag_priority_scoring_user",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )
    set_dashboard_permission(user_data["username"], "documents", can_view=True)
    app.config["RAG_SCORE_DEBUG"] = True

    with app.app_context():
        user = db.session.get(User, user_data["id"])
        training = AssistantTrainingEntry(
            title="SP900 Training",
            question="Wie SP900 pruefen?",
            answer="SP900 Hydraulik Servo Ablauf pruefen.",
            keywords="SP900, Hydraulik, Servo",
            department="Produktion",
            is_active=True,
            priority=95,
            created_by=user.id,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        db.session.add(training)
        db.session.flush()
        timestamp = utc_now()
        _create_quality_gate_document(
            title="SP900 Upload",
            quality_status="admin_approved",
            created_by=user.id,
            text="SP900 Hydraulik Servo Ablauf pruefen.",
            token_text="sp900 hydraulik servo ablauf pruefen",
            updated_at=timestamp,
        )
        _create_quality_gate_document(
            title="SP900 Training",
            quality_status="admin_approved",
            created_by=user.id,
            source_type="manual_training",
            source_id=training.id,
            text="SP900 Hydraulik Servo Ablauf pruefen.",
            token_text="sp900 hydraulik servo ablauf pruefen",
            updated_at=timestamp,
        )
        db.session.commit()

        _context, sources = knowledge_context_for_chat(
            "SP900 Hydraulik Servo",
            user,
            limit=2,
        )

    assert sources[0]["title"] == "SP900 Training"
    assert sources[0]["score"] > sources[1]["score"]
    assert "score_debug" in sources[0]
    assert "components" in sources[0]["score_debug"]
    assert "source_priority" in sources[0]["score_debug"]["components"]


def _create_quality_gate_document(
    title,
    quality_status,
    created_by,
    source_type="upload",
    source_id=None,
    text="QG900 QG901 Hydraulik Servo Spezialverfahren Qualitaetsgate.",
    token_text="qg900 qg901 hydraulik servo spezialverfahren qualitaetsgate",
    updated_at=None,
):
    """Create an indexed knowledge document with one deterministic matching chunk."""
    timestamp = updated_at or utc_now()
    document = KnowledgeDocument(
        source_type=source_type,
        source_id=source_id,
        title=title,
        original_filename=f"{title}.txt",
        relative_path=f"uploads/{title}.txt",
        content_type="text/plain",
        department="Produktion",
        status="indexed",
        quality_status=quality_status,
        is_public=True,
        chunk_count=1,
        created_by=created_by,
        created_at=timestamp,
        updated_at=timestamp,
    )
    db.session.add(document)
    db.session.flush()
    db.session.add(
        KnowledgeChunk(
            document_id=document.id,
            chunk_index=0,
            text=text,
            token_text=token_text,
            created_at=timestamp,
        )
    )
    return document

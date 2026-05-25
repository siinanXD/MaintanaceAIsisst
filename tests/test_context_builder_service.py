"""Tests for boundary-aware AI context building."""

from app.services.context_builder_service import build_dynamic_context


class _QueryUnderstanding:
    """Minimal query-understanding stub for context-builder tests."""

    query_type = "document_question"


def test_context_builder_truncates_at_sentence_boundary():
    """Verify context truncation avoids half sentences."""
    payload = build_dynamic_context(
        "Sensor pruefen",
        {
            "structured_context": "",
            "vector_context": (
                "Quelle: Wissen #1 - Sensor Wartung\n"
                "Dokumenttyp: upload\n"
                "Motor abschalten. Sensor pruefen. Ergebnis dokumentieren und freigeben."
            ),
            "sources": [],
            "knowledge_sources": [
                {
                    "type": "knowledge",
                    "id": 1,
                    "chunk_id": 10,
                    "score": 90,
                    "quality_status": "admin_approved",
                }
            ],
            "knowledge_links": {"links": []},
        },
        _QueryUnderstanding(),
        max_chars=105,
    )

    assert "Sensor pruefen." in payload["context"]
    assert "Ergebnis dokumentieren" not in payload["context"]
    assert payload["context"].endswith("Sensor pruefen.")
    assert payload["stats"]["boundary_aware"] is True


def test_context_builder_does_not_cut_inside_words():
    """Verify fallback truncation cuts before a long partial token."""
    payload = build_dynamic_context(
        "Hydraulikdruck",
        {
            "structured_context": ("Kurzer Start HydraulikdruckmesspunktAlphaBetaGamma beendet"),
            "vector_context": "",
            "sources": [{"type": "task", "id": 1}],
            "knowledge_sources": [],
            "knowledge_links": {"links": []},
        },
        _QueryUnderstanding(),
        max_chars=28,
    )

    assert "Hydraulikdruckmesspunkt" not in payload["context"]
    assert payload["context"].endswith("Kurzer Start")


def test_context_builder_keeps_complete_maintenance_steps():
    """Verify step-like lists are shortened on complete line boundaries."""
    payload = build_dynamic_context(
        "Wartungsschritte",
        {
            "structured_context": (
                "- Schritt 1: Anlage sichern\n"
                "- Schritt 2: Sensor pruefen\n"
                "- Schritt 3: Freigabe dokumentieren"
            ),
            "vector_context": "",
            "sources": [{"type": "task", "id": 1}],
            "knowledge_sources": [],
            "knowledge_links": {"links": []},
        },
        _QueryUnderstanding(),
        max_chars=62,
    )

    assert "- Schritt 1: Anlage sichern" in payload["context"]
    assert "- Schritt 2: Sensor pruefen" in payload["context"]
    assert "Schritt 3" not in payload["context"]


def test_context_builder_prioritizes_confirmed_high_quality_sources():
    """Verify source-aware budgeting keeps higher quality knowledge first."""
    payload = build_dynamic_context(
        "Qualitaetsquelle",
        {
            "structured_context": "",
            "vector_context": (
                "Quelle: Wissen #1 - Entwurf\n"
                "Dokumenttyp: upload\n"
                "Entwurfsquelle mit niedriger Qualitaet.\n\n"
                "Quelle: Wissen #2 - Freigegeben\n"
                "Dokumenttyp: upload\n"
                "Bestaetigte Quelle mit vollstaendigem Wartungsschritt."
            ),
            "sources": [],
            "knowledge_sources": [
                {
                    "type": "knowledge",
                    "id": 1,
                    "chunk_id": 11,
                    "score": 85,
                    "quality_status": "draft",
                },
                {
                    "type": "knowledge",
                    "id": 2,
                    "chunk_id": 12,
                    "score": 80,
                    "quality_status": "admin_approved",
                },
            ],
            "knowledge_links": {"links": []},
        },
        _QueryUnderstanding(),
        max_chars=118,
    )

    explainability = payload["explainability"]
    assert "Freigegeben" in payload["context"]
    assert "Entwurfsquelle" not in payload["context"]
    assert explainability["source_prioritization"][0]["id"] == 2
    assert explainability["removed_sources"]

"""Tests for grounded AI prompt construction."""

from app.services.ai_prompting import build_text_messages, text_system_prompt


def test_text_system_prompt_requires_grounded_source_based_answers():
    """Verify chat prompts explicitly discourage unsupported maintenance answers."""
    prompt = text_system_prompt()

    assert "Keine belastbare Quelle gefunden" in prompt
    assert "Fehlercodes muss der Code exakt uebereinstimmen" in prompt
    assert "Quelle-/Chunk-/Dokumenthinweis" in prompt


def test_build_text_messages_keeps_context_and_question_separated():
    """Verify answer prompts preserve a clear context/question boundary."""
    messages = build_text_messages(
        "Was bedeutet Fehler E204?",
        "Quelle: Wissen #7 - Fehlerkatalog\nChunk-ID: 12\nFehler E204: Sensor pruefen.",
    )

    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert "Kontext:" in messages[1]["content"]
    assert "Frage:" in messages[1]["content"]
    assert "Chunk-ID: 12" in messages[1]["content"]

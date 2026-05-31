"""Tests for shared AI question normalization helpers."""

from app.extensions import db
from app.models import Department
from app.services.ai_question_normalizer import (
    detect_department,
    detect_severity,
    detect_status,
    detect_time_range,
    is_structured_follow_up,
    mentions_my_area,
    normalize_text,
)


def test_ai_question_normalizer_folds_umlauts_and_punctuation():
    """Verify assistant question text normalization stays deterministic."""
    assert normalize_text("  St\u00f6rungen, heute?  ") == "stoerungen heute"
    assert normalize_text("F\u00e4llige Pr\u00fcfung!") == "faellige pruefung"


def test_ai_question_normalizer_detects_structured_terms():
    """Verify shared structured terms cover status, severity, time and follow-ups."""
    assert detect_status("Welche offenen Tasks gibt es?") == "open"
    assert detect_status("Was ist in Bearbeitung?") == "in_progress"
    assert detect_status("Gestern geschlossen") == "done"
    assert detect_severity("kritische St\u00f6rungen") == "critical"
    assert detect_time_range("Was wurde heute gemeldet?") == "today"
    assert detect_time_range("Was wurde gestern gemeldet?") == "yesterday"
    assert is_structured_follow_up("Und welche davon sind kritisch?")
    assert mentions_my_area("St\u00f6rungen in meinem Bereich")


def test_ai_question_normalizer_detects_department_with_word_boundaries(app):
    """Verify department matching avoids substring matches in German questions."""
    with app.app_context():
        db.session.add(Department(name="QA"))
        db.session.commit()

        assert detect_department("Welche Tasks hat QA?") == "QA"
        assert detect_department("Welche St\u00f6rungen sind kritisch?") == ""

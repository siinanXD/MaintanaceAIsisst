"""Shared normalization helpers for AI maintenance questions."""

from __future__ import annotations

import re

from flask import has_app_context

from app.models import Department

FOLLOW_UP_PATTERNS = (
    "und welche",
    "welche davon",
    "wie viele davon",
    "nur die offenen",
    "nur die dringenden",
    "die von gestern",
    "die kritischen",
    "davon",
    "noch offen",
)
STATUS_TERMS = {
    "open": (
        "offen",
        "offene",
        "offenen",
        "open",
        "ausstehend",
        "ausstehende",
        "steht aus",
        "stehen aus",
        "unerledigt",
    ),
    "in_progress": ("in bearbeitung", "in arbeit", "aktive", "aktiv"),
    "done": ("beendet", "geschlossen", "erledigt", "abgeschlossen", "closed", "done"),
}
TASK_STATUS_TERMS = {
    "in_progress": ("in bearbeitung", "in arbeit"),
    "done": ("beendet", "geschlossen", "erledigt", "abgeschlossen"),
    "open": (
        "offen",
        "ausstehend",
        "ausstehende",
        "steht aus",
        "stehen aus",
        "unerledigt",
    ),
}
SEVERITY_TERMS = {
    "critical": ("kritisch", "kritische", "critical"),
}
MY_AREA_TERMS = (
    "mein bereich",
    "meinem bereich",
    "meine abteilung",
    "meiner abteilung",
    "unserem bereich",
)


def contains_lookup_term(text, term):
    """Return whether normalized text contains one lookup term as a word or phrase."""
    normalized_text = normalize_text(text)
    normalized_term = normalize_text(term)
    if not normalized_term:
        return False
    if " " in normalized_term or "-" in normalized_term:
        return normalized_term in normalized_text
    return bool(
        re.search(rf"(?<!\w){re.escape(normalized_term)}(?!\w)", normalized_text)
    )


def contains_any_lookup_term(text, terms):
    """Return whether normalized text contains any lookup term as a word or phrase."""
    return any(contains_lookup_term(text, term) for term in terms)


def normalize_text(value, strip_punctuation=True):
    """Return lowercase lookup text normalized for German maintenance questions."""
    text = " ".join(str(value or "").lower().split())
    replacements = {
        "\u00e4": "ae",
        "\u00f6": "oe",
        "\u00fc": "ue",
        "\u00df": "ss",
        "\u00c3\u00a4": "ae",
        "\u00c3\u00b6": "oe",
        "\u00c3\u00bc": "ue",
        "\u00c3\u009f": "ss",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    if strip_punctuation:
        text = re.sub(r"[^\w\s-]+", " ", text)
        return " ".join(text.split())
    return text


def detect_status(value, terms=None):
    """Return a normalized lifecycle status mentioned in a question."""
    text = normalize_text(value)
    status_terms = terms or STATUS_TERMS
    for status, aliases in status_terms.items():
        if any(alias in text for alias in aliases):
            return status
    return ""


def detect_severity(value):
    """Return a normalized severity mentioned in a question."""
    text = normalize_text(value)
    for severity, aliases in SEVERITY_TERMS.items():
        if any(alias in text for alias in aliases):
            return severity
    return ""


def detect_time_range(value):
    """Return the supported relative time range mentioned in a question."""
    text = normalize_text(value)
    if "gestern" in text:
        return "yesterday"
    if "heute" in text:
        return "today"
    return ""


def detect_department(value):
    """Return a department name mentioned in a question."""
    if not has_app_context():
        return ""
    text = normalize_text(value)
    for department in Department.query.order_by(Department.name.asc()).all():
        normalized_name = normalize_text(department.name)
        if re.search(rf"(?<!\w){re.escape(normalized_name)}(?!\w)", text):
            return department.name
    return ""


def mentions_my_area(value):
    """Return whether a question asks for the user's own department or area."""
    text = normalize_text(value)
    return any(term in text for term in MY_AREA_TERMS)


def is_structured_follow_up(value):
    """Return whether a question asks to refine the previous structured scope."""
    text = normalize_text(value)
    return any(pattern in text for pattern in FOLLOW_UP_PATTERNS)

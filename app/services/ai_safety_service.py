"""Local safety validation for AI maintenance answers."""

from __future__ import annotations

from dataclasses import dataclass, field

CRITICAL_KEYWORDS = (
    "arbeiten unter spannung",
    "unter spannung",
    "not-aus ueberbruecken",
    "notaus ueberbruecken",
    "schutzschalter ueberbruecken",
    "sicherheitsschalter ueberbruecken",
    "sensor deaktivieren",
    "schutz entfernen",
)

SAFETY_KEYWORDS = {
    "electrical_hazard": (
        "strom",
        "spannung",
        "elektrisch",
        "schaltschrank",
        "kabel",
        "lichtbogen",
    ),
    "emergency_stop": ("not-aus", "notaus", "emergency stop"),
    "safety_shutdown": (
        "abschaltung",
        "sicherheitsabschaltung",
        "schutzschalter",
        "verriegelung",
    ),
    "live_work": ("unter spannung", "arbeiten unter spannung"),
    "critical_machine_state": (
        "rauch",
        "brand",
        "ueberhitzt",
        "überhitzt",
        "stillstand",
        "blockiert",
        "leckage",
    ),
    "dangerous_action": (
        "ueberbruecken",
        "überbrücken",
        "deaktivieren",
        "abschalten umgehen",
        "schutz entfernen",
    ),
}

SAFETY_NOTICE = (
    "## Sicherheitshinweis\n"
    "- **Status:** Sicherheitsrelevante Frage erkannt.\n"
    "- **Regel:** Keine Arbeiten unter Spannung, keine Schutzfunktionen umgehen "
    "und bei Gefahr Maschine sichern sowie qualifizierte Fachkraft hinzuziehen.\n\n"
)


@dataclass(frozen=True)
class SafetyAssessment:
    """Safety classification result for one AI answer."""

    safety_relevant: bool
    risk_level: str = "none"
    categories: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    blocked_actions: tuple[str, ...] = ()
    prompt_rules: tuple[str, ...] = ()
    signals: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self):
        """Return a JSON-serializable safety payload."""
        return {
            "safety_relevant": self.safety_relevant,
            "risk_level": self.risk_level,
            "categories": list(self.categories),
            "warnings": list(self.warnings),
            "blocked_actions": list(self.blocked_actions),
            "prompt_rules": list(self.prompt_rules),
            "signals": list(self.signals),
        }


def assess_ai_safety(message, query_understanding=None, sources=None):
    """Return a local safety assessment for the question and retrieval metadata."""
    text = _normalized_text(message)
    categories = [
        category
        for category, keywords in SAFETY_KEYWORDS.items()
        if any(_normalized_text(keyword) in text for keyword in keywords)
    ]
    blocked_actions = [
        keyword
        for keyword in CRITICAL_KEYWORDS
        if _normalized_text(keyword) in text
    ]
    if query_understanding and getattr(query_understanding, "is_safety", False):
        if "query_understanding" not in categories:
            categories.append("query_understanding")
    source_safety = _source_safety_signal(sources)
    if source_safety and "retrieval_source" not in categories:
        categories.append("retrieval_source")
    risk_level = _risk_level(categories, blocked_actions)
    warnings = _warnings(risk_level, categories)
    prompt_rules = _prompt_rules(risk_level, categories, blocked_actions)
    return SafetyAssessment(
        safety_relevant=bool(categories or blocked_actions),
        risk_level=risk_level,
        categories=tuple(categories),
        warnings=tuple(warnings),
        blocked_actions=tuple(blocked_actions),
        prompt_rules=tuple(prompt_rules),
        signals=tuple(categories + [f"blocked:{item}" for item in blocked_actions]),
    )


def apply_safety_warning(answer, assessment):
    """Return an answer prefixed with a safety warning when needed."""
    if not assessment or not assessment.safety_relevant:
        return answer
    answer_text = str(answer or "").strip()
    if answer_text.startswith(SAFETY_NOTICE.strip()):
        return answer_text
    return f"{SAFETY_NOTICE}{answer_text}".strip()


def apply_safety_payload_warning(answer, safety_payload):
    """Return an answer prefixed when a serialized safety payload is relevant."""
    if not isinstance(safety_payload, dict) or not safety_payload.get("safety_relevant"):
        return answer
    answer_text = str(answer or "").strip()
    if answer_text.startswith(SAFETY_NOTICE.strip()):
        return answer_text
    return f"{SAFETY_NOTICE}{answer_text}".strip()


def safety_context_block(assessment):
    """Return a compact prompt context block for safety-relevant answers."""
    if not assessment or not assessment.safety_relevant:
        return ""
    lines = [
        "Sicherheitskontext:",
        f"- Risikostufe: {assessment.risk_level}",
        "- Keine gefaehrlichen Handlungsanweisungen erfinden.",
        "- Nur sichere, organisatorische und pruefende Schritte nennen.",
    ]
    if assessment.categories:
        lines.append(f"- Kategorien: {', '.join(assessment.categories)}")
    if assessment.blocked_actions:
        lines.append("- Gefaehrliche angefragte Aktionen nicht anleiten.")
    return "\n".join(lines)


def _source_safety_signal(sources):
    """Return whether source metadata suggests safety relevance."""
    for source in sources or []:
        if not isinstance(source, dict):
            continue
        title = _normalized_text(source.get("title"))
        reason = _normalized_text(source.get("reason"))
        if any(keyword in f"{title} {reason}" for keyword in ("sicherheit", "not-aus")):
            return True
    return False


def _risk_level(categories, blocked_actions):
    """Return a coarse local safety risk level."""
    if blocked_actions or "live_work" in categories:
        return "critical"
    if {
        "electrical_hazard",
        "emergency_stop",
        "safety_shutdown",
        "dangerous_action",
    } & set(categories):
        return "high"
    if categories:
        return "caution"
    return "none"


def _warnings(risk_level, categories):
    """Return concise safety warnings for diagnostics and UI."""
    if risk_level == "critical":
        return (
            "Keine Anleitung fuer Arbeiten unter Spannung oder Umgehen von Schutzfunktionen.",
            "Maschine sichern und qualifizierte Elektro-/Sicherheitsfachkraft hinzuziehen.",
        )
    if risk_level == "high":
        return (
            "Sicherheitsrelevanten Zustand vorsichtig behandeln.",
            "Nur freigegebene Verfahren und Fachpersonal nutzen.",
        )
    if categories:
        return ("Sicherheitsbezug erkannt; Antwort fachlich pruefen.",)
    return ()


def _prompt_rules(risk_level, categories, blocked_actions):
    """Return safety prompt rules for answer generation."""
    if risk_level == "none":
        return ()
    rules = [
        "Sicherheitsrelevante Antwort: keine riskanten Schritt-fuer-Schritt-Anweisungen.",
        "Bei Unsicherheit Maschine sichern und Fachkraft hinzuziehen.",
    ]
    if blocked_actions:
        rules.append("Anfragen zum Umgehen von Schutzfunktionen ablehnen.")
    if "electrical_hazard" in categories or "live_work" in categories:
        rules.append("Keine Arbeiten unter Spannung anleiten.")
    return tuple(rules)


def _normalized_text(value):
    """Return normalized text for local matching."""
    text = " ".join(str(value or "").strip().lower().split())
    replacements = {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "ß": "ss",
        "Ã¤": "ae",
        "Ã¶": "oe",
        "Ã¼": "ue",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text

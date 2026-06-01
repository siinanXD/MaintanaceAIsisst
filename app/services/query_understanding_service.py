"""Lightweight query understanding for retrieval routing."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from flask import current_app, has_app_context

from app.services.text_normalization_service import normalize_query

QUERY_ERROR_ANALYSIS = "error_analysis"
QUERY_MACHINE = "machine_question"
QUERY_INVENTORY = "inventory_question"
QUERY_TASK = "task_question"
QUERY_DOCUMENT = "document_question"
QUERY_EMPLOYEE = "employee_question"
QUERY_ADMIN_USER = "admin_user_question"
QUERY_SAFETY = "safety_question"
QUERY_GENERAL = "general_question"
QUERY_KNOWLEDGE_GAP = "knowledge_gap"
QUERY_TREND_HISTORY = "trend_history_question"

QUERY_TYPES = {
    QUERY_ERROR_ANALYSIS,
    QUERY_MACHINE,
    QUERY_INVENTORY,
    QUERY_TASK,
    QUERY_DOCUMENT,
    QUERY_EMPLOYEE,
    QUERY_ADMIN_USER,
    QUERY_SAFETY,
    QUERY_GENERAL,
    QUERY_KNOWLEDGE_GAP,
    QUERY_TREND_HISTORY,
}

ERROR_CODE_PATTERN = re.compile(r"\b[A-Z]{1,6}[-_ ]?\d{2,6}\b", re.IGNORECASE)

KEYWORDS = {
    QUERY_ERROR_ANALYSIS: (
        "fehler",
        "stoerung",
        "stoerfall",
        "problem",
        "probleme",
        "störung",
        "ursache",
        "analyse",
        "ausfall",
        "defekt",
        "error",
    ),
    QUERY_MACHINE: (
        "maschine",
        "anlage",
        "linie",
        "presse",
        "roboter",
        "status",
        "maschineninfo",
    ),
    QUERY_INVENTORY: (
        "lager",
        "bestand",
        "ersatzteil",
        "material",
        "inventar",
        "inventory",
        "teil",
    ),
    QUERY_TASK: (
        "task",
        "aufgabe",
        "arbeit",
        "arbeiten",
        "todo",
        "wartung",
        "fällig",
        "faellig",
        "erledigt",
        "ausstehend",
        "unerledigt",
    ),
    QUERY_DOCUMENT: (
        "dokument",
        "handbuch",
        "anleitung",
        "bericht",
        "manual",
        "pdf",
        "datei",
    ),
    QUERY_EMPLOYEE: (
        "mitarbeiter",
        "personal",
        "person",
        "team",
        "qualifikation",
        "qualifikationen",
        "schichtmodell",
        "schicht",
    ),
    QUERY_ADMIN_USER: (
        "user",
        "users",
        "nutzer",
        "benutzer",
        "account",
        "accounts",
        "rolle",
        "rollen",
        "berechtigung",
        "berechtigungen",
        "permissions",
    ),
    QUERY_SAFETY: (
        "sicherheit",
        "not-aus",
        "notaus",
        "abschaltung",
        "spannung",
        "strom",
        "elektrisch",
        "gefährlich",
        "gefaehrlich",
        "schutz",
        "ueberbruecken",
        "überbrücken",
        "deaktivieren",
    ),
    QUERY_KNOWLEDGE_GAP: (
        "wissenslücke",
        "wissensluecke",
        "nicht gefunden",
        "keine quelle",
        "unbekannt",
        "fehlendes wissen",
    ),
    QUERY_TREND_HISTORY: (
        "historie",
        "handover",
        "verlauf",
        "trend",
        "schichtuebergabe",
        "schichtÃ¼bergabe",
        "uebergabe",
        "Ã¼bergabe",
        "wiederkehrend",
        "sequenz",
        "danach",
        "vorher",
        "letzte",
        "letzten",
        "entwicklung",
    ),
}

SCOPE_BY_QUERY_TYPE = {
    QUERY_ERROR_ANALYSIS: ("errors", "machines", "documents"),
    QUERY_MACHINE: ("machines", "errors", "inventory"),
    QUERY_INVENTORY: ("inventory", "machines", "tasks"),
    QUERY_TASK: ("tasks", "machines", "errors"),
    QUERY_DOCUMENT: ("documents",),
    QUERY_EMPLOYEE: ("employees", "shiftplans", "machines"),
    QUERY_ADMIN_USER: ("admin_users",),
    QUERY_SAFETY: ("machines", "errors", "documents"),
    QUERY_KNOWLEDGE_GAP: ("documents", "errors", "machines"),
    QUERY_TREND_HISTORY: ("errors", "machines", "tasks", "shiftplans"),
}

SOURCE_TYPES_BY_QUERY_TYPE = {
    QUERY_ERROR_ANALYSIS: ("error_entry", "machine_manual", "manual_training"),
    QUERY_MACHINE: ("machine", "machine_manual", "maintenance_plan"),
    QUERY_INVENTORY: ("inventory_material", "maintenance_plan"),
    QUERY_TASK: ("task", "maintenance_plan", "shift_handover"),
    QUERY_DOCUMENT: ("upload", "generated_document", "machine_manual"),
    QUERY_EMPLOYEE: ("employee", "shiftplan", "machine"),
    QUERY_ADMIN_USER: ("admin_user", "dashboard_permission"),
    QUERY_SAFETY: ("machine_manual", "error_entry", "upload"),
    QUERY_KNOWLEDGE_GAP: ("manual_training", "upload", "generated_document"),
    QUERY_TREND_HISTORY: ("error_entry", "task", "shift_handover"),
}


@dataclass(frozen=True)
class QueryUnderstandingResult:
    """Classified user query with retrieval routing metadata."""

    query_type: str
    confidence: float
    is_safety: bool = False
    secondary_types: tuple[str, ...] = ()
    signals: tuple[str, ...] = ()
    recommended_scopes: tuple[str, ...] = ()
    retrieval_strategy: dict = field(default_factory=dict)
    provider: str = "local_rules"

    def to_dict(self):
        """Return a JSON-serializable query-understanding payload."""
        return {
            "query_type": self.query_type,
            "confidence": round(float(self.confidence), 3),
            "is_safety": self.is_safety,
            "secondary_types": list(self.secondary_types),
            "signals": list(self.signals),
            "recommended_scopes": list(self.recommended_scopes),
            "retrieval_strategy": dict(self.retrieval_strategy),
            "provider": self.provider,
        }


def classify_query(message, requested_scopes=None):
    """Classify a user question locally and return retrieval routing metadata."""
    text = _normalized_text(message)
    requested_scopes = set(requested_scopes or [])
    scores = _score_query_types(text, requested_scopes)
    query_type = _primary_query_type(scores)
    secondary_types = tuple(
        item_type
        for item_type, score in sorted(scores.items(), key=lambda item: item[1], reverse=True)
        if item_type != query_type and score >= 2
    )[:3]
    is_safety = scores.get(QUERY_SAFETY, 0) > 0
    if is_safety and scores.get(QUERY_SAFETY, 0) >= max(1, scores.get(query_type, 0) - 1):
        query_type = QUERY_SAFETY
    confidence = _confidence(scores, query_type)
    signals = _signals(text, query_type, scores)
    recommended_scopes = _recommended_scopes(query_type, secondary_types, requested_scopes)
    return QueryUnderstandingResult(
        query_type=query_type,
        confidence=confidence,
        is_safety=is_safety,
        secondary_types=secondary_types,
        signals=signals,
        recommended_scopes=recommended_scopes,
        retrieval_strategy=_retrieval_strategy(query_type, is_safety),
        provider=_provider_label(),
    )


def _score_query_types(text, requested_scopes):
    """Return local rule scores for each supported query type."""
    scores = {query_type: 0 for query_type in QUERY_TYPES}
    for query_type, keywords in KEYWORDS.items():
        scores[query_type] += sum(1 for keyword in keywords if keyword in text)
    if ERROR_CODE_PATTERN.search(text.upper()):
        scores[QUERY_ERROR_ANALYSIS] += 3
    for scope in requested_scopes:
        if scope == "errors":
            scores[QUERY_ERROR_ANALYSIS] += 2
        elif scope == "machines":
            scores[QUERY_MACHINE] += 2
        elif scope == "inventory":
            scores[QUERY_INVENTORY] += 2
        elif scope == "tasks":
            scores[QUERY_TASK] += 2
        elif scope == "documents":
            scores[QUERY_DOCUMENT] += 2
        elif scope == "employees":
            scores[QUERY_EMPLOYEE] += 2
        elif scope == "admin_users":
            scores[QUERY_ADMIN_USER] += 2
        elif scope == "shiftplans":
            scores[QUERY_TREND_HISTORY] += 1
    if not any(scores.values()):
        scores[QUERY_GENERAL] = 1
    return scores


def _primary_query_type(scores):
    """Return the highest-scoring query type."""
    ranked = sorted(
        scores.items(),
        key=lambda item: (item[1], _type_priority(item[0])),
        reverse=True,
    )
    return ranked[0][0] if ranked and ranked[0][1] > 0 else QUERY_GENERAL


def _type_priority(query_type):
    """Return a deterministic tie-break priority for query types."""
    priorities = {
        QUERY_SAFETY: 10,
        QUERY_ERROR_ANALYSIS: 9,
        QUERY_TREND_HISTORY: 8,
        QUERY_MACHINE: 7,
        QUERY_TASK: 6,
        QUERY_INVENTORY: 5,
        QUERY_DOCUMENT: 4,
        QUERY_EMPLOYEE: 4,
        QUERY_ADMIN_USER: 4,
        QUERY_KNOWLEDGE_GAP: 3,
        QUERY_GENERAL: 1,
    }
    return priorities.get(query_type, 0)


def _confidence(scores, query_type):
    """Return a simple normalized confidence value."""
    total = sum(max(score, 0) for score in scores.values())
    if total <= 0:
        return 0.35
    primary = max(scores.get(query_type, 0), 0)
    return min(0.95, max(0.35, primary / max(total, 1)))


def _signals(text, query_type, scores):
    """Return concise explainability signals for classification."""
    signals = [f"type:{query_type}"]
    if ERROR_CODE_PATTERN.search(text.upper()):
        signals.append("error_code_pattern")
    for item_type, score in scores.items():
        if score > 0 and item_type != QUERY_GENERAL:
            signals.append(f"{item_type}:{score}")
    return tuple(signals[:8])


def _recommended_scopes(query_type, secondary_types, requested_scopes):
    """Return scopes that should be searched for the query."""
    scopes = list(requested_scopes)
    for item_type in (query_type, *secondary_types):
        for scope in SCOPE_BY_QUERY_TYPE.get(item_type, ()):
            if scope not in scopes:
                scopes.append(scope)
    return tuple(scopes[:6])


def _retrieval_strategy(query_type, is_safety):
    """Return strategy metadata used by retrieval and prompting."""
    top_k = {
        QUERY_ERROR_ANALYSIS: 6,
        QUERY_MACHINE: 5,
        QUERY_INVENTORY: 4,
        QUERY_TASK: 4,
        QUERY_DOCUMENT: 6,
        QUERY_EMPLOYEE: 5,
        QUERY_ADMIN_USER: 5,
        QUERY_SAFETY: 6,
        QUERY_KNOWLEDGE_GAP: 5,
        QUERY_TREND_HISTORY: 7,
        QUERY_GENERAL: 3,
    }.get(query_type, 4)
    if is_safety:
        top_k = max(top_k, 6)
    return {
        "top_k": top_k,
        "source_types": list(SOURCE_TYPES_BY_QUERY_TYPE.get(query_type, ())),
        "scope_weights": _scope_weights(query_type),
        "prompt_rules": _prompt_rules(query_type, is_safety),
        "prefer_structured": query_type
        in {
            QUERY_MACHINE,
            QUERY_INVENTORY,
            QUERY_TASK,
            QUERY_TREND_HISTORY,
            QUERY_EMPLOYEE,
            QUERY_ADMIN_USER,
        },
        "prefer_confirmed": query_type in {QUERY_ERROR_ANALYSIS, QUERY_SAFETY, QUERY_DOCUMENT},
    }


def _scope_weights(query_type):
    """Return explainable retrieval scope weights for a query type."""
    weights = {scope: 1.0 for scope in SCOPE_BY_QUERY_TYPE.get(query_type, ())}
    if query_type == QUERY_ERROR_ANALYSIS:
        weights.update({"errors": 1.6, "machines": 1.25})
    elif query_type == QUERY_SAFETY:
        weights.update({"machines": 1.6, "errors": 1.35, "documents": 1.3})
    elif query_type == QUERY_TREND_HISTORY:
        weights.update({"errors": 1.45, "machines": 1.2, "tasks": 1.15})
    elif query_type == QUERY_EMPLOYEE:
        weights.update({"employees": 1.6, "shiftplans": 1.2, "machines": 1.1})
    elif query_type == QUERY_ADMIN_USER:
        weights.update({"admin_users": 1.7})
    return weights


def _prompt_rules(query_type, is_safety):
    """Return prompt guidance attached to context builder diagnostics."""
    rules_by_query_type = {
        QUERY_TREND_HISTORY: [
            "Zeitliche Reihenfolge, Datenbasis und Unsicherheit explizit nennen.",
        ],
        QUERY_KNOWLEDGE_GAP: [
            "Wenn keine belastbare Quelle vorhanden ist, Wissensluecke klar benennen.",
        ],
        QUERY_ERROR_ANALYSIS: [
            "Ursachen, Pruefschritte und dokumentierte Loesungen klar trennen.",
        ],
        QUERY_EMPLOYEE: [
            "Mitarbeiterdaten nur gemaess freigegebenem Zugriffsniveau verwenden.",
        ],
        QUERY_ADMIN_USER: [
            "Admin-User- und Rollendaten nur fuer berechtigte Admins verwenden.",
        ],
    }

    rules = [
        "Nutze ausschliesslich bereitgestellte und freigegebene Kontextdaten.",
        "Erfinde keine fehlenden Informationen.",
        "Nenne Unsicherheit, wenn Quellenlage unvollstaendig ist.",
    ]

    rules.extend(rules_by_query_type.get(query_type, []))

    if is_safety:
        rules.append(
            "Sicherheitskritisch: keine riskanten Handlungsanweisungen ohne "
            "belastbare Quelle geben und qualifizierte Fachkraft hinzuziehen."
        )

    return rules


def _provider_label():
    """Return the provider label for local or configured optional enhancement."""
    if has_app_context() and current_app.config.get("QUERY_UNDERSTANDING_OPENAI"):
        return "local_rules_openai_optional"
    return "local_rules"


def _normalized_text(value):
    """Return normalized text for local matching."""
    return normalize_query(value)

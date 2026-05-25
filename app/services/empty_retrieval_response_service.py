"""Human-readable empty-retrieval answers for AI chat."""

from app.services.query_classifier_service import classify_ai_query
from app.services.retrieval_debug_service import is_retrieval_debug_visible

SOURCE_LABELS = {
    "errors": "Fehlerkatalog",
    "error": "Fehlerkatalog",
    "error_entry": "Fehlerkatalog",
    "tasks": "Tasks",
    "task": "Tasks",
    "machines": "Maschinen",
    "machine": "Maschinen",
    "inventory": "Lager/Material",
    "inventory_material": "Lager/Material",
    "documents": "Dokumente",
    "document": "Dokumente",
    "generated_document": "Dokumente",
    "knowledge": "Wissensdatenbank",
    "machine_manual": "Handbuecher",
    "manual_training": "Training/Wissensdatenbank",
    "maintenance_plan": "Wartungsplaene",
    "shiftplans": "Schicht-/Uebergaben",
    "shift_handover": "Schicht-/Uebergaben",
}
QUERY_TYPE_DEFAULT_SOURCES = {
    "LIVE_SQL": ("tasks", "machines", "inventory"),
    "KNOWLEDGE_RAG": ("knowledge", "documents"),
    "HYBRID": ("errors", "machines", "knowledge", "documents"),
    "GENERAL": ("tasks", "errors", "documents"),
}
ENTITY_LABELS = {
    "error_codes": "Fehlercode",
    "task_ids": "Task-ID",
    "machine_hints": "Maschinenhinweis",
    "material_hints": "Materialhinweis",
}


def build_empty_retrieval_answer(message, retrieval=None, user=None):
    """Return a grounded answer for an AI chat request without visible sources."""
    retrieval = retrieval or {}
    rag = retrieval.get("rag") or {}
    classification = _classification_payload(message, retrieval, rag)
    checked_sources = _checked_source_labels(retrieval, rag, classification)
    no_match_summary = _no_match_summary(checked_sources)
    recognized_terms = _recognized_terms(classification)
    likely_reason = _likely_no_match_reason(classification, checked_sources, rag)
    lines = [
        "## Keine belastbare Quelle gefunden",
        (
            "- **Status:** Ich habe keine freigegebene Quelle gefunden, "
            "die diese Frage belastbar beantwortet."
        ),
        "- **Gepruefte Datenquellen:** " + _format_list(checked_sources),
        "- **Ergebnis:** " + no_match_summary,
        (
            "- **Erkannte Suchsignale:** "
            + _format_list(recognized_terms, "keine eindeutigen Suchsignale erkannt")
        ),
        "- **Wahrscheinlicher Grund:** " + likely_reason,
        (
            "- **Warum keine Antwort:** Ohne Quelle wuerde eine konkrete "
            "Loesung oder Wartungsanweisung geraten wirken."
        ),
        "- **Was du versuchen kannst:** " + _next_step_text(classification, checked_sources),
    ]
    admin_lines = _admin_diagnostic_lines(rag, user)
    if admin_lines:
        lines.extend(["", "## Diagnose fuer Admins", *admin_lines])
    return "\n".join(lines)


def _classification_payload(message, retrieval, rag):
    """Return the best available high-level query classification payload."""
    payload = retrieval.get("query_classification") or rag.get("query_classification") or {}
    if payload:
        return dict(payload)
    return classify_ai_query(message).to_dict()


def _checked_source_labels(retrieval, rag, classification):
    """Return readable source labels that were relevant for empty retrieval."""
    source_keys = []
    source_keys.extend(classification.get("suggested_sources") or [])
    understanding = retrieval.get("query_understanding") or rag.get("query_understanding") or {}
    source_keys.extend(understanding.get("recommended_scopes") or [])
    source_keys.extend(retrieval.get("requested_scopes") or [])
    source_keys.extend(retrieval.get("allowed_scopes") or [])
    if not source_keys:
        source_keys.extend(
            QUERY_TYPE_DEFAULT_SOURCES.get(
                str(classification.get("query_type") or "GENERAL"),
                QUERY_TYPE_DEFAULT_SOURCES["GENERAL"],
            )
        )
    labels = [_source_label(source_key) for source_key in source_keys]
    return list(dict.fromkeys(label for label in labels if label))[:6]


def _source_label(source_key):
    """Return a display label for a retrieval source or scope key."""
    return SOURCE_LABELS.get(str(source_key or "").strip(), str(source_key or "").strip())


def _no_match_summary(checked_sources):
    """Return a concise no-match statement for the checked source labels."""
    if not checked_sources:
        return "Keine passende freigegebene Datenquelle war sichtbar."
    relevant = [
        label
        for label in checked_sources
        if label in {"Tasks", "Fehlerkatalog", "Dokumente", "Wissensdatenbank", "Handbuecher"}
    ]
    if relevant:
        return "Keine passenden Eintraege sichtbar in: " + _format_list(relevant) + "."
    return "Keine passenden sichtbaren Eintraege in den geprueften Bereichen gefunden."


def _recognized_terms(classification):
    """Return prompt-safe keywords and extracted technical entities."""
    terms = []
    for keyword in classification.get("extracted_keywords") or []:
        safe_keyword = _safe_term(keyword)
        if safe_keyword:
            terms.append(safe_keyword)
    entities = classification.get("possible_entities") or {}
    for entity_key, values in entities.items():
        label = ENTITY_LABELS.get(str(entity_key), str(entity_key))
        for value in _as_list(values):
            safe_value = _safe_term(value)
            if safe_value:
                terms.append(f"{label}: {safe_value}")
    return list(dict.fromkeys(terms))[:10]


def _likely_no_match_reason(classification, checked_sources, rag):
    """Return a user-safe reason for an empty retrieval outcome."""
    debug = rag.get("retrieval_debug") or {}
    filtered_count = (
        _debug_int(debug, "permission_filtered")
        + _debug_int(debug, "quality_filtered")
        + _debug_int(debug, "score_anchor_filtered", fallback_key="score_filtered")
    )
    candidate_count = (
        _debug_int(debug, "sql_candidates_found")
        + _debug_int(debug, "keyword_candidates_found")
        + _debug_int(debug, "vector_candidates_found")
        + _debug_int(debug, "sql_keyword_fallback_candidates_found")
    )
    final_sources = _debug_int(debug, "final_visible_sources")
    if filtered_count > 0 and final_sources == 0:
        return (
            "Es gab Suchkandidaten, aber keine Quelle blieb nach Sichtbarkeits-, "
            "Qualitaets- oder Relevanzpruefung als belastbare Antwortgrundlage uebrig."
        )
    if candidate_count == 0:
        return "In den geprueften Bereichen wurden keine passenden Treffer ermittelt."
    if final_sources == 0:
        return "Kandidaten waren vorhanden, aber keine freigegebene Quelle war sichtbar."
    query_type = str(classification.get("query_type") or "GENERAL")
    if query_type == "GENERAL" and not checked_sources:
        return "Die Frage passt zu keiner konkreten freigegebenen Datenquelle."
    return "Keine gepruefte Quelle passte ausreichend sicher zur Frage."


def _next_step_text(classification, checked_sources):
    """Return concrete next steps without inventing answer content."""
    query_type = str(classification.get("query_type") or "GENERAL")
    suggestions = []
    if "Fehlerkatalog" in checked_sources or query_type == "HYBRID":
        suggestions.append("Fehlercode, Maschinenname und Symptom zusammen nennen")
    if "Tasks" in checked_sources:
        suggestions.append("Task-ID, Status oder Faelligkeit genauer angeben")
    if "Dokumente" in checked_sources or "Wissensdatenbank" in checked_sources:
        suggestions.append("Dokumenttitel, Handbuch oder Abschnitt nennen")
    if "Lager/Material" in checked_sources:
        suggestions.append("Materialname oder Ersatzteilnummer angeben")
    suggestions.append(
        "falls die Quelle existiert, Berechtigung, Abteilung oder Reindex pruefen lassen"
    )
    return "; ".join(dict.fromkeys(suggestions)) + "."


def _admin_diagnostic_lines(rag, user):
    """Return admin-only retrieval debug lines when safe counters are available."""
    debug = rag.get("retrieval_debug") or {}
    if not debug or not _may_show_admin_diagnostics(user):
        return []
    score_filtered = _debug_int(
        debug,
        "score_anchor_filtered",
        fallback_key="score_filtered",
    )
    return [
        "- **Kandidaten gefunden:** "
        f"SQL {_debug_int(debug, 'sql_candidates_found')}, "
        f"Keyword {_debug_int(debug, 'keyword_candidates_found')}, "
        f"Vector {_debug_int(debug, 'vector_candidates_found')}, "
        f"SQL-Fallback {_debug_int(debug, 'sql_keyword_fallback_candidates_found')}",
        "- **Gefiltert:** "
        f"Permission {_debug_int(debug, 'permission_filtered')}, "
        f"Quality {_debug_int(debug, 'quality_filtered')}, "
        f"Score/Anchor {score_filtered}",
        "- **Admin-Counter:** "
        f"SQL candidate count {_debug_int(debug, 'sql_candidates_found')}; "
        f"vector candidate count {_debug_int(debug, 'vector_candidates_found')}; "
        f"filtered by permission {_debug_int(debug, 'permission_filtered')}; "
        f"filtered by quality {_debug_int(debug, 'quality_filtered')}; "
        f"filtered by score {score_filtered}",
        f"- **Final sichtbare Quellen:** {_debug_int(debug, 'final_visible_sources')}",
    ]


def _may_show_admin_diagnostics(user):
    """Return whether the answer body may include admin retrieval counters."""
    return bool(getattr(user, "is_admin", False)) and is_retrieval_debug_visible(user)


def _as_list(value):
    """Return a bounded list for scalar or list-like values."""
    if isinstance(value, list | tuple | set):
        return list(value)[:8]
    if value in (None, ""):
        return []
    return [value]


def _safe_term(value):
    """Return a short prompt-safe term for answer diagnostics."""
    term = " ".join(str(value or "").strip().split())
    if len(term) > 48:
        return ""
    return term


def _debug_int(debug, key, fallback_key=None):
    """Return a non-negative integer debug counter."""
    value = debug.get(key)
    if value in (None, "") and fallback_key:
        value = debug.get(fallback_key)
    try:
        parsed = int(value or 0)
    except (TypeError, ValueError):
        return 0
    return max(parsed, 0)


def _format_list(items, empty_text="keine"):
    """Return a readable comma-separated list with a fallback label."""
    values = [str(item) for item in items or [] if str(item or "").strip()]
    return ", ".join(values) if values else empty_text

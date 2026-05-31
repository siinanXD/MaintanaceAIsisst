"""Shared answer-quality summaries for AI chat, history, and admin logs."""


def answer_quality_from_result(result, diagnostics=None, warnings=None):
    """Return a compact UI-facing answer-quality summary for a live result."""
    safe_result = result or {}
    safe_diagnostics = diagnostics or safe_result.get("diagnostics") or {}
    safe_warnings = warnings or []
    confidence = safe_result.get("confidence") or safe_diagnostics.get("confidence") or {}
    sources = safe_result.get("sources") or []
    source_count = len(sources)
    confidence_level = str(
        confidence.get("level") or safe_diagnostics.get("confidence_level") or ""
    )
    quality_status = answer_quality_status(
        source_count=source_count,
        confidence_level=confidence_level,
        empty_retrieval=bool(safe_diagnostics.get("empty_retrieval")),
        hallucination_warning=bool(safe_diagnostics.get("hallucination_warning")),
        diagnostics=safe_diagnostics,
    )
    return answer_quality_payload(
        status=quality_status,
        confidence_score=confidence.get("score") or safe_diagnostics.get("confidence_score"),
        confidence_level=confidence_level,
        source_count=source_count,
        warning_types=_warning_types(safe_warnings),
        primary_warning_type=_primary_warning_type(safe_warnings),
    )


def answer_quality_from_history_item(item):
    """Return answer-quality metadata reconstructed from stored chat fields."""
    safe_item = item or {}
    diagnostics = safe_item.get("diagnostics") or {}
    source_count = _safe_int(safe_item.get("source_count"))
    confidence_level = str(safe_item.get("confidence_level") or "")
    warning_types = _warning_types(diagnostics.get("quality_warnings") or [])
    quality_status = answer_quality_status(
        source_count=source_count,
        confidence_level=confidence_level,
        empty_retrieval=bool(diagnostics.get("empty_retrieval")),
        hallucination_warning=bool(diagnostics.get("hallucination_warning")),
        diagnostics=diagnostics,
    )
    return answer_quality_payload(
        status=quality_status,
        confidence_score=safe_item.get("confidence_score"),
        confidence_level=confidence_level,
        source_count=source_count,
        warning_types=warning_types,
        primary_warning_type=_primary_warning_type(diagnostics.get("quality_warnings") or []),
    )


def answer_quality_payload(
    status,
    confidence_score=None,
    confidence_level="",
    source_count=0,
    warning_types=None,
    primary_warning_type="",
):
    """Return the normalized answer-quality payload shape."""
    safe_status = str(status or "unverified")
    safe_confidence_level = str(confidence_level or "")
    safe_source_count = _safe_int(source_count)
    safe_warning_types = [str(item) for item in (warning_types or []) if item]
    return {
        "status": safe_status,
        "status_reason": answer_quality_reason(safe_status, safe_warning_types),
        "confidence_score": confidence_score,
        "confidence_level": safe_confidence_level,
        "uncertainty": answer_uncertainty(safe_status, safe_confidence_level),
        "has_sources": safe_source_count > 0,
        "source_count": safe_source_count,
        "no_answer": safe_status == "no_answer",
        "warning_count": len(safe_warning_types),
        "warning_types": safe_warning_types,
        "primary_warning_type": str(primary_warning_type or ""),
        "recommended_user_action": answer_quality_action(safe_status),
        "evidence_visible": True,
    }


def answer_quality_status(
    source_count,
    confidence_level,
    empty_retrieval,
    hallucination_warning,
    diagnostics=None,
):
    """Return a stable answer-quality status label."""
    safe_diagnostics = diagnostics or {}
    if empty_retrieval and hallucination_warning:
        return "no_answer"
    if safe_diagnostics.get("fallback_used"):
        return "fallback"
    if (safe_diagnostics.get("source_conflicts") or {}).get("has_conflicts"):
        return "conflicting_sources"
    if confidence_level == "low":
        return "low_confidence"
    if _safe_int(source_count) > 0:
        return "grounded"
    return "unverified"


def answer_uncertainty(status, confidence_level):
    """Return a coarse uncertainty label for UI display."""
    if status in {"no_answer", "unverified"}:
        return "high"
    if status in {"fallback", "low_confidence", "conflicting_sources"} or (
        confidence_level == "medium"
    ):
        return "medium"
    return "low"


def answer_quality_action(status):
    """Return a short next-action hint for one answer-quality status."""
    actions = {
        "grounded": "Quellen pruefen und bei Bedarf Rueckfrage stellen.",
        "low_confidence": "Antwort fachlich pruefen und weitere Quellen oder Details ergaenzen.",
        "no_answer": "Keine belegte Antwort vorhanden; Dokumentation oder Fehlerdaten ergaenzen.",
        "fallback": "Provider-Konfiguration pruefen oder lokale Antwort als Orientierung nutzen.",
        "conflicting_sources": (
            "Widerspruechliche Quellen pruefen und bestaetigte Fassung dokumentieren."
        ),
        "unverified": "Antwort nur als Orientierung nutzen und Quellenlage pruefen.",
    }
    return actions.get(status, actions["unverified"])


def answer_quality_reason(status, warning_types=None):
    """Return a stable machine-readable reason for one answer-quality status."""
    warnings = set(str(item) for item in (warning_types or []) if item)
    if status == "no_answer" and "hallucination_risk" in warnings:
        return "empty_retrieval_hallucination_guard"
    if status == "no_answer":
        return "no_grounded_source"
    if status == "conflicting_sources":
        return "source_conflict_detected"
    if status == "low_confidence":
        return "low_confidence_score"
    if status == "fallback":
        return "provider_or_retrieval_fallback"
    if status == "grounded":
        return "sources_available"
    return "unverified_answer"


def redacted_answer_quality(answer_quality):
    """Return answer quality without source or confidence details."""
    quality = answer_quality if isinstance(answer_quality, dict) else {}
    status = str(quality.get("status") or "unverified")
    return {
        "status": status,
        "status_reason": quality.get("status_reason") or answer_quality_reason(status),
        "confidence_score": None,
        "confidence_level": "",
        "uncertainty": quality.get("uncertainty") or answer_uncertainty(status, ""),
        "has_sources": False,
        "source_count": 0,
        "no_answer": status == "no_answer" or bool(quality.get("no_answer")),
        "warning_count": 0,
        "warning_types": [],
        "primary_warning_type": "",
        "recommended_user_action": quality.get("recommended_user_action")
        or answer_quality_action(status),
        "evidence_visible": False,
    }


def _warning_types(warnings):
    """Return stable warning type labels from warning dictionaries or strings."""
    types = []
    for warning in warnings or []:
        if isinstance(warning, dict):
            warning_type = warning.get("type")
        else:
            warning_type = warning
        if warning_type:
            types.append(str(warning_type))
    return types


def _primary_warning_type(warnings):
    """Return the highest-priority warning type for compact UI badges."""
    warning_types = set(_warning_types(warnings))
    for warning_type in (
        "hallucination_risk",
        "source_conflict",
        "empty_retrieval",
        "stale_source",
        "low_confidence",
    ):
        if warning_type in warning_types:
            return warning_type
    return next(iter(warning_types), "")


def _safe_int(value):
    """Return an integer value or zero for malformed input."""
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0

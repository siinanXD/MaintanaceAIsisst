"""Trend analysis for recurring maintenance faults."""

from collections import Counter
from datetime import UTC, datetime, timedelta

from app.models import ErrorEntry
from app.security import has_dashboard_permission
from app.services.error_service import tokenize_similarity_text, visible_errors_query

DEFAULT_WINDOW_DAYS = 30
DEFAULT_MIN_OCCURRENCES = 2
DEFAULT_LIMIT = 5
SIMILARITY_THRESHOLD = 45


def analyze_recurring_issues(user, days=None, min_occurrences=None, limit=None):
    """Return recurring visible error trends for a user."""
    if not has_dashboard_permission(user, "errors", "view"):
        return _empty_result(days, min_occurrences, limit, status="permission_denied")

    window_days = _bounded_int(days, DEFAULT_WINDOW_DAYS, minimum=1, maximum=365)
    minimum = _bounded_int(min_occurrences, DEFAULT_MIN_OCCURRENCES, minimum=2, maximum=50)
    limit_value = _bounded_int(limit, DEFAULT_LIMIT, minimum=1, maximum=20)
    since = datetime.now(UTC) - timedelta(days=window_days)

    entries = (
        visible_errors_query(user)
        .filter(ErrorEntry.created_at >= since)
        .order_by(ErrorEntry.created_at.desc(), ErrorEntry.id.desc())
        .limit(500)
        .all()
    )
    clusters = _cluster_entries(entries)
    trends = [
        _trend_payload(cluster, window_days)
        for cluster in clusters
        if _occurrence_count(cluster) >= minimum
    ]
    trends.sort(
        key=lambda item: (
            item["occurrence_count"],
            item["confidence"],
            item["period"]["to"],
        ),
        reverse=True,
    )
    return {
        "items": trends[:limit_value],
        "count": min(len(trends), limit_value),
        "total_candidates": len(trends),
        "window_days": window_days,
        "min_occurrences": minimum,
        "summary": _summary_text(trends[:limit_value]),
        "diagnostics": {
            "status": "local_answer",
            "provider": "local_trend_analysis",
            "entries_scanned": len(entries),
        },
    }


def _empty_result(days, min_occurrences, limit, status="local_answer"):
    """Return an empty recurring-issue payload."""
    return {
        "items": [],
        "count": 0,
        "total_candidates": 0,
        "window_days": _bounded_int(days, DEFAULT_WINDOW_DAYS, minimum=1, maximum=365),
        "min_occurrences": _bounded_int(
            min_occurrences,
            DEFAULT_MIN_OCCURRENCES,
            minimum=2,
            maximum=50,
        ),
        "summary": "Keine wiederkehrenden Fehler erkannt.",
        "diagnostics": {
            "status": status,
            "provider": "local_trend_analysis",
            "entries_scanned": 0,
        },
    }


def _bounded_int(value, default, minimum, maximum):
    """Return an integer clamped to the provided inclusive bounds."""
    try:
        parsed = int(value if value not in (None, "") else default)
    except (TypeError, ValueError):
        parsed = default
    return min(max(parsed, minimum), maximum)


def _cluster_entries(entries):
    """Group visible error entries into recurring issue clusters."""
    clusters = []
    for entry in entries:
        best_cluster = None
        best_score = 0
        for cluster in clusters:
            score = max(_entry_similarity(entry, candidate) for candidate in cluster)
            if score > best_score:
                best_cluster = cluster
                best_score = score
        if best_cluster is not None and best_score >= SIMILARITY_THRESHOLD:
            best_cluster.append(entry)
        else:
            clusters.append([entry])
    return clusters


def _entry_similarity(left, right):
    """Return a local similarity score for two error entries."""
    if left.department_id and right.department_id and left.department_id != right.department_id:
        return 0

    score = 0
    left_machine = _machine_key(left)
    right_machine = _machine_key(right)
    if left.machine_id and left.machine_id == right.machine_id:
        score += 35
    elif left_machine and right_machine and left_machine == right_machine:
        score += 35
    elif left_machine and right_machine and (
        left_machine in right_machine or right_machine in left_machine
    ):
        score += 20

    left_code = _code_key(left.error_code)
    right_code = _code_key(right.error_code)
    if left_code and right_code and left_code == right_code:
        score += 35

    shared_tokens = _entry_tokens(left) & _entry_tokens(right)
    if shared_tokens:
        score += min(30, len(shared_tokens) * 8)
    return min(score, 100)


def _trend_payload(cluster, window_days):
    """Return a public recurring-issue trend payload for one cluster."""
    entries = sorted(cluster, key=lambda entry: entry.created_at)
    first = entries[0].created_at
    last = entries[-1].created_at
    common_solution = _common_solution(entries)
    machine = _common_machine(entries)
    error_code = _common_error_code(entries)
    occurrence_count = _occurrence_count(entries)
    return {
        "occurrence_count": occurrence_count,
        "entry_count": len(entries),
        "affected_machine": machine,
        "machine_id": _common_machine_id(entries),
        "error_code": error_code,
        "department": entries[0].department.to_dict() if entries[0].department else None,
        "common_solution": common_solution,
        "period": {
            "from": first.isoformat(),
            "to": last.isoformat(),
            "days": max(1, (last.date() - first.date()).days + 1),
            "window_days": window_days,
        },
        "risk_level": _risk_level(occurrence_count),
        "confidence": _confidence(entries),
        "recommendation": _recommendation(machine, error_code, occurrence_count, common_solution),
        "evidence": [_evidence_item(entry) for entry in entries[-5:]],
    }


def _occurrence_count(entries):
    """Return total occurrences represented by entries and repeat counters."""
    return sum(1 + max(entry.repeat_count or 0, 0) for entry in entries)


def _machine_key(entry):
    """Return a normalized machine key for an error entry."""
    machine = entry.machine_rel.name if entry.machine_rel else entry.machine
    return " ".join(str(machine or "").strip().lower().split())


def _code_key(value):
    """Return a normalized error-code key."""
    return "".join(character for character in str(value or "").upper() if character.isalnum())


def _entry_tokens(entry):
    """Return normalized text tokens for recurrence matching."""
    return tokenize_similarity_text(
        " ".join(
            [
                entry.title,
                entry.description,
                entry.possible_causes,
                entry.solution,
            ]
        )
    )


def _common_solution(entries):
    """Return the most frequent documented solution in a cluster."""
    solutions = [
        " ".join(str(entry.solution or "").strip().split())
        for entry in entries
        if str(entry.solution or "").strip()
    ]
    if not solutions:
        return "Noch keine Loesung dokumentiert."
    return Counter(solutions).most_common(1)[0][0]


def _common_machine(entries):
    """Return the most common machine label in a cluster."""
    machines = [
        entry.machine_rel.name if entry.machine_rel else str(entry.machine or "").strip()
        for entry in entries
    ]
    machines = [machine for machine in machines if machine]
    return Counter(machines).most_common(1)[0][0] if machines else "Unbekannte Maschine"


def _common_machine_id(entries):
    """Return the most common machine id in a cluster, if available."""
    machine_ids = [entry.machine_id for entry in entries if entry.machine_id]
    if not machine_ids:
        return None
    return Counter(machine_ids).most_common(1)[0][0]


def _common_error_code(entries):
    """Return the most common error code in a cluster."""
    codes = [str(entry.error_code or "").strip().upper() for entry in entries if entry.error_code]
    return Counter(codes).most_common(1)[0][0] if codes else ""


def _risk_level(occurrence_count):
    """Return a risk level for a recurring issue."""
    if occurrence_count >= 5:
        return "critical"
    if occurrence_count >= 3:
        return "high"
    return "medium"


def _confidence(entries):
    """Return a confidence score for the recurrence cluster."""
    if len(entries) < 2:
        return 0.0
    pair_scores = []
    for index, entry in enumerate(entries):
        for other in entries[index + 1 :]:
            pair_scores.append(_entry_similarity(entry, other))
    if not pair_scores:
        return 0.0
    return round(min(1.0, sum(pair_scores) / len(pair_scores) / 100), 2)


def _recommendation(machine, error_code, occurrence_count, common_solution):
    """Return a practical local recommendation for a recurring issue."""
    code_text = f" Fehlercode {error_code}" if error_code else ""
    if common_solution and common_solution != "Noch keine Loesung dokumentiert.":
        return (
            f"{machine}{code_text} trat {occurrence_count} Mal auf. "
            f"Hauefige Loesung pruefen: {common_solution}. "
            "Ursache buendeln, Wartungsintervall bewerten und Eintrag im "
            "Knowledge-Base-Workflow aktualisieren."
        )
    return (
        f"{machine}{code_text} trat {occurrence_count} Mal auf. "
        "Ursachenanalyse und dokumentierte Loesung ergaenzen; bei Bedarf Wartungstask anlegen."
    )


def _evidence_item(entry):
    """Return compact evidence for one trend source entry."""
    return {
        "id": entry.id,
        "title": f"{entry.error_code} - {entry.title}",
        "machine": entry.machine,
        "description": entry.description,
        "solution": entry.solution,
        "repeat_count": entry.repeat_count,
        "created_at": entry.created_at.isoformat(),
    }


def _summary_text(items):
    """Return a concise local summary for recurring issue trends."""
    if not items:
        return "Keine wiederkehrenden Fehler erkannt."
    top = items[0]
    return (
        f"{len(items)} wiederkehrende Fehlermuster erkannt. "
        f"Top-Thema: {top['affected_machine']} {top['error_code']} "
        f"mit {top['occurrence_count']} Vorkommen."
    )

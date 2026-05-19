"""Detect prompt-safe conflicts between retrieved maintenance sources."""

from __future__ import annotations

import hashlib
from collections import defaultdict


def detect_source_conflicts(sources=None, data=None):
    """Return conflict metadata for retrieved sources and structured data."""
    safe_sources = [source for source in sources or [] if isinstance(source, dict)]
    data = data or {}
    conflicts = []
    conflicts.extend(_error_solution_conflicts(data.get("errors") or []))
    conflicts.extend(_quality_conflicts(safe_sources))
    conflicts.extend(_score_conflicts(safe_sources))
    conflicts = conflicts[:8]
    return {
        "has_conflicts": bool(conflicts),
        "count": len(conflicts),
        "conflicts": conflicts,
        "summary": _summary(conflicts),
        "prompt_rules": _prompt_rules(conflicts),
        "privacy": {
            "stores_source_text": False,
            "stores_solution_text": False,
            "method": "metadata_and_hash_signals",
        },
    }


def cautious_context_block(conflicts):
    """Return a prompt context block instructing cautious wording."""
    if not conflicts or not conflicts.get("has_conflicts"):
        return ""
    lines = [
        "Quellenkonflikte:",
        "- Mehrere Quellen widersprechen sich oder haben unterschiedliche Qualitaet.",
        "- Antwort vorsichtig formulieren und Konflikt transparent benennen.",
    ]
    for conflict in conflicts.get("conflicts", [])[:4]:
        lines.append(
            f"- {conflict['type']}: {conflict['reason']} "
            f"({len(conflict.get('sources') or [])} Quellen)"
        )
    return "\n".join(lines)


def _error_solution_conflicts(errors):
    """Return conflicts for differing error solutions or causes."""
    grouped = defaultdict(list)
    for entry in errors:
        if not isinstance(entry, dict):
            continue
        key = (
            str(entry.get("machine_id") or entry.get("machine") or "").lower(),
            str(entry.get("error_code") or "").upper(),
        )
        if not any(key):
            continue
        grouped[key].append(entry)

    conflicts = []
    for key, entries in grouped.items():
        solution_hashes = _field_hashes(entries, "solution")
        cause_hashes = _field_hashes(entries, "possible_causes")
        if len(solution_hashes) > 1:
            conflicts.append(
                _conflict_payload(
                    "different_solutions",
                    "Unterschiedliche dokumentierte Loesungen fuer gleiche Maschine/Fehlercode.",
                    key,
                    entries,
                    solution_hashes,
                )
            )
        if len(cause_hashes) > 1:
            conflicts.append(
                _conflict_payload(
                    "different_causes",
                    "Unterschiedliche dokumentierte Ursachen fuer gleiche Maschine/Fehlercode.",
                    key,
                    entries,
                    cause_hashes,
                )
            )
    return conflicts


def _quality_conflicts(sources):
    """Return conflicts for mixed source quality statuses."""
    grouped = defaultdict(list)
    for source in sources:
        key = (source.get("type"), source.get("id"))
        if not key[0] or key[1] in (None, ""):
            continue
        grouped[key].append(source)
    conflicts = []
    for key, items in grouped.items():
        statuses = {
            str(item.get("quality_status") or "").strip()
            for item in items
            if item.get("quality_status")
        }
        if {"admin_approved", "outdated"} <= statuses or {"rejected", "admin_approved"} <= statuses:
            conflicts.append(
                {
                    "type": "quality_status_conflict",
                    "reason": "Quellenreferenzen enthalten widerspruechliche Qualitaetsstatus.",
                    "key": _key_payload(key),
                    "signals": sorted(statuses),
                    "sources": [_source_ref(item) for item in items[:5]],
                }
            )
    return conflicts


def _score_conflicts(sources):
    """Return a weak conflict signal for similarly scored mixed source types."""
    if len(sources) < 3:
        return []
    scores = [float(source.get("score") or 0) for source in sources]
    if not scores or max(scores) - min(scores) > 25:
        return []
    source_types = {source.get("type") for source in sources if source.get("type")}
    if len(source_types) < 3:
        return []
    return [
        {
            "type": "mixed_source_evidence",
            "reason": (
                "Mehrere Quellentypen haben aehnliche Scores; "
                "Antwort sollte Quellenlage nennen."
            ),
            "key": {"source_types": sorted(source_types)},
            "signals": ["similar_scores", "mixed_source_types"],
            "sources": [_source_ref(source) for source in sources[:5]],
        }
    ]


def _field_hashes(entries, field_name):
    """Return unique hashes for a non-empty structured text field."""
    values = {}
    for entry in entries:
        normalized = " ".join(str(entry.get(field_name) or "").strip().lower().split())
        if not normalized:
            continue
        values[_hash_text(normalized)] = True
    return sorted(values)


def _conflict_payload(conflict_type, reason, key, entries, signals):
    """Return one prompt-safe conflict payload."""
    return {
        "type": conflict_type,
        "reason": reason,
        "key": {"machine": key[0], "error_code": key[1]},
        "signals": list(signals)[:6],
        "sources": [
            {
                "type": "error",
                "id": entry.get("id"),
                "machine": entry.get("machine"),
                "machine_id": entry.get("machine_id"),
                "error_code": entry.get("error_code"),
                "severity": entry.get("severity"),
            }
            for entry in entries[:5]
        ],
    }


def _source_ref(source):
    """Return a prompt-safe source reference."""
    return {
        "type": source.get("type"),
        "id": source.get("id"),
        "chunk_id": source.get("chunk_id"),
        "score": source.get("score"),
        "quality_status": source.get("quality_status"),
    }


def _key_payload(key):
    """Return a JSON-safe conflict key."""
    return {"type": key[0], "id": key[1]}


def _summary(conflicts):
    """Return a concise conflict summary."""
    if not conflicts:
        return "Keine Konflikte erkannt."
    return f"{len(conflicts)} potenzielle Quellenkonflikte erkannt."


def _prompt_rules(conflicts):
    """Return prompt rules for conflicting sources."""
    if not conflicts:
        return []
    return [
        "Bei widerspruechlichen Quellen keine eindeutige Loesung behaupten.",
        "Konflikt kurz benennen und sichere Pruefung empfehlen.",
    ]


def _hash_text(value):
    """Return a short stable hash for conflict text comparison."""
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()[:12]

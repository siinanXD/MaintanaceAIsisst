"""Weighted deterministic candidate scoring for shift planning."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from unicodedata import normalize

from app.shiftplans.rules import is_work_entry, normalize_rule_entry, shift_hours
from app.shiftplans.templates import ShiftTemplate

QUALIFICATION_WEIGHTS = {
    "basic": 4,
    "trained": 8,
    "expert": 12,
    "trainer": 14,
}


@dataclass(frozen=True)
class CandidateScore:
    """Weighted score result with human-readable reasons."""

    total_score: int
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable score payload."""
        return {
            "total_score": self.total_score,
            "reasons": list(self.reasons),
        }


def score_candidate(
    employee: object,
    machine: object | None,
    work_date: date,
    shift_key: str,
    entries: list[dict[str, object]],
    qualification_map: dict[tuple[int, int], object],
    template: ShiftTemplate,
    preferences: str = "",
) -> CandidateScore:
    """Return a weighted, deterministic score for one valid candidate."""
    employee_id = int(employee.id)
    employee_entries = [
        normalize_rule_entry(entry)
        for entry in entries
        if normalize_rule_entry(entry).get("employee_id") == employee_id
        and is_work_entry(normalize_rule_entry(entry))
    ]
    score = 100
    reasons: list[str] = []

    workload_delta, workload_reason = workload_score(employee_entries)
    score += workload_delta
    reasons.append(workload_reason)

    night_delta, night_reason = night_distribution_score(employee_entries, shift_key)
    score += night_delta
    reasons.append(night_reason)

    weekend_delta, weekend_reason = weekend_distribution_score(employee_entries, work_date)
    score += weekend_delta
    reasons.append(weekend_reason)

    if machine and not qualification_map:
        qualification_delta, qualification_reason = legacy_qualification_score(
            employee,
            machine,
        )
    else:
        qualification_delta, qualification_reason = qualification_score(
            employee_id,
            getattr(machine, "id", None),
            work_date,
            qualification_map,
        )
    score += qualification_delta
    reasons.append(qualification_reason)

    favorite_delta, favorite_reason = favorite_machine_score(employee, machine)
    score += favorite_delta
    if favorite_reason:
        reasons.append(favorite_reason)

    rotation_delta, rotation_reason = forward_rotation_score(
        employee_entries,
        shift_key,
        template,
    )
    score += rotation_delta
    if rotation_reason:
        reasons.append(rotation_reason)

    continuity_delta, continuity_reason = previous_shift_continuity_score(
        employee_entries,
        shift_key,
    )
    score += continuity_delta
    if continuity_reason:
        reasons.append(continuity_reason)

    preference_delta, preference_reason = preference_score(employee, preferences)
    score += preference_delta
    if preference_reason:
        reasons.append(preference_reason)

    return CandidateScore(total_score=score, reasons=tuple(reasons))


def workload_score(entries: list[dict[str, object]]) -> tuple[int, str]:
    """Return workload balancing score based on assigned hours."""
    hours = sum(shift_hours(str(entry["start_time"]), str(entry["end_time"])) for entry in entries)
    penalty = int(hours // 8) * 4
    return -penalty, f"-{penalty} Arbeitslast {hours:.0f}h"


def night_distribution_score(
    entries: list[dict[str, object]],
    shift_key: str,
) -> tuple[int, str]:
    """Return a score that favors fair night shift distribution."""
    night_count = sum(1 for entry in entries if entry.get("shift") == "Nacht")
    if shift_key != "Nacht":
        return 2, "+2 keine zusaetzliche Nacht"
    penalty = night_count * 15
    return -penalty, f"-{penalty} Nachtlast {night_count} bisher"


def weekend_distribution_score(
    entries: list[dict[str, object]],
    work_date: date,
) -> tuple[int, str]:
    """Return a score that favors fair weekend distribution."""
    weekend_count = sum(1 for entry in entries if entry["work_date"].weekday() >= 5)
    if work_date.weekday() < 5:
        return 0, "+0 Werktag"
    penalty = weekend_count * 10
    return -penalty, f"-{penalty} Wochenendlast {weekend_count} bisher"


def qualification_score(
    employee_id: int,
    machine_id: int | None,
    work_date: date,
    qualification_map: dict[tuple[int, int], object],
) -> tuple[int, str]:
    """Return score contribution for the candidate's machine qualification."""
    if not machine_id:
        return 0, "+0 keine Maschinenbindung"
    qualification = qualification_map.get((employee_id, machine_id))
    if not qualification or not qualification.is_valid_for(work_date):
        return -1000, "-1000 keine gueltige Qualifikation"
    level = str(qualification.level or "trained").lower()
    points = QUALIFICATION_WEIGHTS.get(level, QUALIFICATION_WEIGHTS["trained"])
    return points, f"+{points} Qualifikation {level}"


def legacy_qualification_score(employee: object, machine: object) -> tuple[int, str]:
    """Return a compatibility score when no structured matrix exists yet."""
    favorite_machine = normalize_match_text(getattr(employee, "favorite_machine", ""))
    machine_name = normalize_match_text(getattr(machine, "name", ""))
    produced_item = normalize_match_text(getattr(machine, "produced_item", ""))
    qualifications = normalize_match_text(getattr(employee, "qualifications", ""))
    if favorite_machine and favorite_machine == machine_name:
        return 8, "+8 Legacy-Lieblingsmaschine"
    if qualifications and machine_name and machine_name in qualifications:
        return 6, "+6 Legacy-Qualifikation"
    if qualifications and produced_item and produced_item in qualifications:
        return 5, "+5 Legacy-Produktqualifikation"
    if qualifications:
        return 2, "+2 Legacy-Qualifikationshinweis"
    return 0, "+0 Legacy-Modus ohne Qualifikationshinweis"


def normalize_match_text(value: object) -> str:
    """Return lowercase ASCII text for legacy machine and qualification matching."""
    text = str(value or "").strip().lower()
    text = normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return " ".join(text.replace("-", " ").replace("_", " ").split())


def favorite_machine_score(employee: object, machine: object | None) -> tuple[int, str]:
    """Return bonus for favorite machine match."""
    if not machine:
        return 0, ""
    favorite_machine_id = getattr(employee, "favorite_machine_id", None)
    if favorite_machine_id and favorite_machine_id == machine.id:
        return 10, "+10 Lieblingsmaschine"
    favorite_machine = str(getattr(employee, "favorite_machine", "") or "").strip().lower()
    if favorite_machine and favorite_machine == str(machine.name or "").strip().lower():
        return 10, "+10 Lieblingsmaschine"
    return 0, ""


def forward_rotation_score(
    entries: list[dict[str, object]],
    shift_key: str,
    template: ShiftTemplate,
) -> tuple[int, str]:
    """Return score contribution for German forward rotation."""
    previous_shift = previous_work_shift(entries)
    if not previous_shift or template.rotation_direction != "forward":
        return 0, ""
    if is_forward_rotation(previous_shift, shift_key, template.rotation):
        return 8, "+8 Vorwaertsrotation"
    if is_backward_rotation(previous_shift, shift_key, template.rotation):
        return -20, "-20 Rueckwaertsrotation"
    return 1, "+1 Rotation neutral"


def previous_shift_continuity_score(
    entries: list[dict[str, object]],
    shift_key: str,
) -> tuple[int, str]:
    """Return a small bonus for continuity across same shift blocks."""
    previous_shift = previous_work_shift(entries)
    if previous_shift and previous_shift == shift_key:
        return 3, "+3 Schichtkontinuitaet"
    return 0, ""


def preference_score(employee: object, preferences: str) -> tuple[int, str]:
    """Return a simple preference score based on free-text mentions."""
    if not preferences:
        return 0, ""
    name = str(getattr(employee, "name", "") or "").lower()
    if name and name in preferences.lower():
        return 4, "+4 Praeferenzhinweis"
    return 0, ""


def previous_work_shift(entries: list[dict[str, object]]) -> str:
    """Return the most recent shift key from entries."""
    if not entries:
        return ""
    previous = max(entries, key=lambda entry: (entry["work_date"], str(entry["start_time"])))
    return str(previous.get("shift") or "")


def is_forward_rotation(
    previous_shift: str,
    next_shift: str,
    rotation: tuple[str, ...] = ("Frueh", "Spaet", "Nacht"),
) -> bool:
    """Return whether the transition follows Frueh -> Spaet -> Nacht."""
    if previous_shift not in rotation or next_shift not in rotation:
        return False
    previous_index = rotation.index(previous_shift)
    next_index = rotation.index(next_shift)
    return next_index >= previous_index


def is_backward_rotation(
    previous_shift: str,
    next_shift: str,
    rotation: tuple[str, ...] = ("Frueh", "Spaet", "Nacht"),
) -> bool:
    """Return whether the transition goes against forward rotation."""
    if previous_shift not in rotation or next_shift not in rotation:
        return False
    return rotation.index(next_shift) < rotation.index(previous_shift)


def explain_selection(score: CandidateScore) -> str:
    """Return a bounded human-readable selection explanation."""
    reasons = "; ".join(score.reasons[:4])
    return f"Auswahl: Score {score.total_score}; {reasons}."[:500]

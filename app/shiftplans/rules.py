"""Hard rule engine for deterministic shift planning."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from app.shiftplans.templates import ShiftTemplate

MAX_DAILY_HOURS = 10.0
MAX_WEEKLY_HOURS = 48.0
CRITICAL = "critical"
WARNING = "warning"


@dataclass(frozen=True)
class RuleViolation:
    """Structured rule violation emitted by shift planning checks."""

    type: str
    severity: str
    message: str
    employee_id: int | None = None
    machine_id: int | None = None
    work_date: date | None = None

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable violation payload."""
        return {
            "type": self.type,
            "severity": self.severity,
            "employee_id": self.employee_id,
            "machine_id": self.machine_id,
            "work_date": self.work_date.isoformat() if self.work_date else None,
            "message": self.message,
        }


def parse_shift_time(value: str) -> datetime.time:
    """Parse a HH:MM shift time string."""
    return datetime.strptime(value, "%H:%M").time()


def shift_datetimes(work_date: date, start_time: str, end_time: str) -> tuple[datetime, datetime]:
    """Return start and end datetimes for a shift, including overnight windows."""
    start_dt = datetime.combine(work_date, parse_shift_time(start_time))
    end_dt = datetime.combine(work_date, parse_shift_time(end_time))
    if end_dt <= start_dt:
        end_dt += timedelta(days=1)
    return start_dt, end_dt


def shift_hours(start_time: str, end_time: str) -> float:
    """Return shift duration in hours for a time window."""
    start_dt, end_dt = shift_datetimes(date.today(), start_time, end_time)
    return (end_dt - start_dt).total_seconds() / 3600


def is_work_entry(entry: dict[str, object]) -> bool:
    """Return whether a normalized entry represents work."""
    shift = str(entry.get("shift") or "")
    return bool(
        shift not in {"", "Frei", "Urlaub"}
        and entry.get("start_time")
        and entry.get("end_time")
    )


def normalize_rule_entry(entry: object) -> dict[str, object]:
    """Return a dict entry for rule evaluation."""
    if isinstance(entry, dict):
        item = dict(entry)
    else:
        item = {
            "employee_id": getattr(entry, "employee_id", None),
            "machine_id": getattr(entry, "machine_id", None),
            "work_date": getattr(entry, "work_date", None),
            "shift": getattr(entry, "shift", None),
            "start_time": getattr(entry, "start_time", None),
            "end_time": getattr(entry, "end_time", None),
        }
    if isinstance(item.get("work_date"), str):
        item["work_date"] = date.fromisoformat(str(item["work_date"]))
    return item


def validate_rest_time(
    candidate: dict[str, object],
    existing_entries: list[dict[str, object]],
    min_rest_hours: float = 11.0,
) -> list[RuleViolation]:
    """Return rest-time violations for a candidate assignment."""
    if not is_work_entry(candidate):
        return []
    employee_id = int(candidate["employee_id"])
    employee_entries = [
        normalize_rule_entry(entry)
        for entry in existing_entries
        if normalize_rule_entry(entry).get("employee_id") == employee_id
        and is_work_entry(normalize_rule_entry(entry))
    ]
    candidate_start, candidate_end = shift_datetimes(
        candidate["work_date"],
        str(candidate["start_time"]),
        str(candidate["end_time"]),
    )
    violations = []
    for entry in employee_entries:
        entry_start, entry_end = shift_datetimes(
            entry["work_date"],
            str(entry["start_time"]),
            str(entry["end_time"]),
        )
        rest_before = (candidate_start - entry_end).total_seconds() / 3600
        rest_after = (entry_start - candidate_end).total_seconds() / 3600
        if 0 <= rest_before < min_rest_hours or 0 <= rest_after < min_rest_hours:
            violations.append(
                RuleViolation(
                    type="rest_time",
                    severity=CRITICAL,
                    employee_id=employee_id,
                    work_date=candidate["work_date"],
                    message=(
                        f"Mitarbeiter {employee_id} unterschreitet "
                        f"{min_rest_hours:.0f}h Ruhezeit."
                    ),
                )
            )
    return violations


def validate_max_daily_hours(
    candidate: dict[str, object],
    existing_entries: list[dict[str, object]] | None = None,
    max_daily_hours: float = MAX_DAILY_HOURS,
) -> list[RuleViolation]:
    """Return violations when daily working hours exceed the configured maximum."""
    if not is_work_entry(candidate):
        return []
    existing_entries = existing_entries or []
    employee_id = int(candidate["employee_id"])
    work_date = candidate["work_date"]
    total_hours = shift_hours(str(candidate["start_time"]), str(candidate["end_time"]))
    for entry in existing_entries:
        item = normalize_rule_entry(entry)
        if (
            item.get("employee_id") == employee_id
            and item.get("work_date") == work_date
            and is_work_entry(item)
        ):
            total_hours += shift_hours(str(item["start_time"]), str(item["end_time"]))
    if total_hours <= max_daily_hours:
        return []
    return [
        RuleViolation(
            type="daily_hours",
            severity=CRITICAL,
            employee_id=employee_id,
            work_date=work_date,
            message=(
                f"Mitarbeiter {employee_id} waere am {work_date.isoformat()} "
                f"mit {total_hours:.1f}h geplant."
            ),
        )
    ]


def validate_duplicate_assignment(
    candidate: dict[str, object],
    existing_entries: list[dict[str, object]],
) -> list[RuleViolation]:
    """Return violations when a worker is already assigned on the same date."""
    if not is_work_entry(candidate):
        return []
    employee_id = int(candidate["employee_id"])
    work_date = candidate["work_date"]
    for entry in existing_entries:
        item = normalize_rule_entry(entry)
        if (
            item.get("employee_id") == employee_id
            and item.get("work_date") == work_date
            and is_work_entry(item)
        ):
            return [
                RuleViolation(
                    type="duplicate_assignment",
                    severity=CRITICAL,
                    employee_id=employee_id,
                    work_date=work_date,
                    message=(
                        f"Mitarbeiter {employee_id} ist am "
                        f"{work_date.isoformat()} bereits geplant."
                    ),
                )
            ]
    return []


def validate_vacation_conflict(
    candidate: dict[str, object],
    vacation_days: set[tuple[int, date]],
) -> list[RuleViolation]:
    """Return violations when a candidate is absent on the work date."""
    if not is_work_entry(candidate):
        return []
    employee_id = int(candidate["employee_id"])
    work_date = candidate["work_date"]
    if (employee_id, work_date) not in vacation_days:
        return []
    return [
        RuleViolation(
            type="vacation_conflict",
            severity=CRITICAL,
            employee_id=employee_id,
            work_date=work_date,
            message=f"Mitarbeiter {employee_id} ist am {work_date.isoformat()} abwesend.",
        )
    ]


def validate_machine_qualification(
    candidate: dict[str, object],
    qualification_map: dict[tuple[int, int], object],
) -> list[RuleViolation]:
    """Return violations when a worker lacks a valid machine qualification."""
    if not is_work_entry(candidate) or not candidate.get("machine_id"):
        return []
    if not qualification_map:
        return []
    employee_id = int(candidate["employee_id"])
    machine_id = int(candidate["machine_id"])
    work_date = candidate["work_date"]
    qualification = qualification_map.get((employee_id, machine_id))
    if qualification and qualification.is_valid_for(work_date):
        return []
    return [
        RuleViolation(
            type="missing_qualification",
            severity=CRITICAL,
            employee_id=employee_id,
            machine_id=machine_id,
            work_date=work_date,
            message=(
                f"Mitarbeiter {employee_id} hat keine gueltige "
                f"Maschinenfreigabe fuer Maschine {machine_id}."
            ),
        )
    ]


def validate_weekly_hours(
    candidate: dict[str, object],
    existing_entries: list[dict[str, object]],
    max_weekly_hours: float = MAX_WEEKLY_HOURS,
) -> list[RuleViolation]:
    """Return violations when weekly working hours exceed the hard maximum."""
    if not is_work_entry(candidate):
        return []
    employee_id = int(candidate["employee_id"])
    week_key = candidate["work_date"].isocalendar()[:2]
    total_hours = shift_hours(str(candidate["start_time"]), str(candidate["end_time"]))
    for entry in existing_entries:
        item = normalize_rule_entry(entry)
        if (
            item.get("employee_id") == employee_id
            and item.get("work_date").isocalendar()[:2] == week_key
            and is_work_entry(item)
        ):
            total_hours += shift_hours(str(item["start_time"]), str(item["end_time"]))
    if total_hours <= max_weekly_hours:
        return []
    return [
        RuleViolation(
            type="weekly_hours",
            severity=CRITICAL,
            employee_id=employee_id,
            work_date=candidate["work_date"],
            message=(
                f"Mitarbeiter {employee_id} waere in KW {week_key[1]} "
                f"mit {total_hours:.1f}h geplant."
            ),
        )
    ]


def validate_shift_model_rules(
    candidate: dict[str, object],
    existing_entries: list[dict[str, object]],
    template: ShiftTemplate,
    enforce_active_weekdays: bool = True,
) -> list[RuleViolation]:
    """Return violations for template-specific hard rules."""
    if not is_work_entry(candidate):
        return []
    work_date = candidate["work_date"]
    shift_key = str(candidate["shift"])
    violations = []
    if enforce_active_weekdays and not template.is_active_on(work_date):
        violations.append(
            RuleViolation(
                type="shift_model",
                severity=CRITICAL,
                employee_id=int(candidate["employee_id"]),
                work_date=work_date,
                message=f"{template.display_name} plant keinen Dienst an diesem Tag.",
            )
        )
    if shift_key not in template.shift_times:
        violations.append(
            RuleViolation(
                type="shift_model",
                severity=CRITICAL,
                employee_id=int(candidate["employee_id"]),
                work_date=work_date,
                message=f"Schicht {shift_key} gehoert nicht zum Modell {template.key}.",
            )
        )
    if shift_key == "Nacht" and exceeds_max_consecutive_nights(
        candidate,
        existing_entries,
        template.max_consecutive_nights,
    ):
        violations.append(
            RuleViolation(
                type="consecutive_nights",
                severity=CRITICAL,
                employee_id=int(candidate["employee_id"]),
                work_date=work_date,
                message=(
                    f"Mehr als {template.max_consecutive_nights} "
                    "aufeinanderfolgende Nachtschichten."
                ),
            )
        )
    return violations


def exceeds_max_consecutive_nights(
    candidate: dict[str, object],
    existing_entries: list[dict[str, object]],
    max_consecutive_nights: int,
) -> bool:
    """Return whether a candidate would exceed consecutive night limits."""
    if max_consecutive_nights <= 0:
        return str(candidate.get("shift")) == "Nacht"
    employee_id = int(candidate["employee_id"])
    night_dates = {
        normalize_rule_entry(entry)["work_date"]
        for entry in existing_entries
        if normalize_rule_entry(entry).get("employee_id") == employee_id
        and normalize_rule_entry(entry).get("shift") == "Nacht"
    }
    night_dates.add(candidate["work_date"])
    consecutive = 0
    previous_date = None
    for night_date in sorted(night_dates):
        if previous_date and (night_date - previous_date).days == 1:
            consecutive += 1
        else:
            consecutive = 1
        if consecutive > max_consecutive_nights:
            return True
        previous_date = night_date
    return False


def validate_candidate_assignment(
    candidate: dict[str, object],
    existing_entries: list[dict[str, object]],
    vacation_days: set[tuple[int, date]],
    qualification_map: dict[tuple[int, int], object],
    template: ShiftTemplate,
    enforce_active_weekdays: bool = True,
) -> list[RuleViolation]:
    """Return all hard-rule violations for one candidate assignment."""
    normalized_candidate = normalize_rule_entry(candidate)
    normalized_entries = [normalize_rule_entry(entry) for entry in existing_entries]
    violations = []
    violations.extend(validate_duplicate_assignment(normalized_candidate, normalized_entries))
    violations.extend(validate_vacation_conflict(normalized_candidate, vacation_days))
    violations.extend(validate_machine_qualification(normalized_candidate, qualification_map))
    violations.extend(
        validate_max_daily_hours(normalized_candidate, normalized_entries)
    )
    violations.extend(
        validate_rest_time(
            normalized_candidate,
            normalized_entries,
            min_rest_hours=template.recommended_rest_hours,
        )
    )
    violations.extend(validate_weekly_hours(normalized_candidate, normalized_entries))
    violations.extend(
        validate_shift_model_rules(
            normalized_candidate,
            normalized_entries,
            template,
            enforce_active_weekdays=enforce_active_weekdays,
        )
    )
    return violations

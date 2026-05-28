import { todayIsoDate } from "../utils/date";
import { type DashboardPayload, type DashboardShiftCalendar } from "./dashboardApi";
import { peopleText } from "./dashboardPeopleModel";

export type DashboardShiftRow = {
  readonly active: boolean;
  readonly entry: DashboardPayload | null;
  readonly fallbackEnd: string;
  readonly fallbackStart: string;
  readonly label: string;
  readonly shiftKey: string;
  readonly variant: string;
};

export type TimelineGeometry = {
  readonly left: string;
  readonly width: string;
};

const SHIFT_ROWS: readonly Omit<DashboardShiftRow, "active" | "entry">[] = [
  { fallbackEnd: "14:00", fallbackStart: "06:00", label: "Frühschicht", shiftKey: "Frueh", variant: "is-green" },
  { fallbackEnd: "22:00", fallbackStart: "14:00", label: "Spätschicht", shiftKey: "Spaet", variant: "is-blue" },
  { fallbackEnd: "06:00", fallbackStart: "22:00", label: "Nachtschicht", shiftKey: "Nacht", variant: "is-violet" }
];

/**
 * Return a local shift-calendar fallback from employee shift labels.
 */
export function employeesToShiftCalendar(employees: readonly DashboardPayload[]): DashboardShiftCalendar {
  const shifts = [
    { color: "green", end: "14:00", key: "Frueh", start: "06:00" },
    { color: "blue", end: "22:00", key: "Spaet", start: "14:00" },
    { color: "violet", end: "06:00", key: "Nacht", start: "22:00" }
  ] as const;
  const counts = employees.reduce<Map<string, number>>((currentCounts, employee) => {
    const shift = peopleText(employee, "current_shift", "Frei");
    currentCounts.set(shift, (currentCounts.get(shift) ?? 0) + 1);
    return currentCounts;
  }, new Map());

  return {
    employee: null,
    entries: shifts.map((shift) => ({
      color: shift.color,
      end_time: shift.end,
      id: null,
      machine: null,
      notes: `${String(counts.get(shift.key) || 0)} Mitarbeiter`,
      plan_id: null,
      shift: shift.key,
      start_time: shift.start,
      work_date: todayIsoDate()
    })),
    message: employees.length ? "Live aus Mitarbeiter-Schichten" : "Keine Mitarbeiterdaten für die Schichtübersicht."
  };
}

/**
 * Convert a time string into minutes after midnight.
 */
function timeToMinutes(value: unknown): number {
  const [hourPart, minutePart] = String(value || "00:00").split(":");
  const hours = Math.max(0, Math.min(23, Number.parseInt(hourPart || "0", 10) || 0));
  const minutes = Math.max(0, Math.min(59, Number.parseInt(minutePart || "0", 10) || 0));
  return hours * 60 + minutes;
}

/**
 * Return visual geometry for one shift bar.
 */
export function timelineGeometry(start: unknown, end: unknown): TimelineGeometry {
  const startMinutes = timeToMinutes(start);
  let endMinutes = timeToMinutes(end);
  if (endMinutes <= startMinutes) endMinutes += 24 * 60;
  const visibleStart = Math.max(0, Math.min(startMinutes, 24 * 60));
  const visibleEnd = Math.max(0, Math.min(endMinutes, 24 * 60));

  return {
    left: `${((visibleStart / (24 * 60)) * 100).toFixed(2)}%`,
    width: `${Math.max(((visibleEnd - visibleStart) / (24 * 60)) * 100, 2).toFixed(2)}%`
  };
}

/**
 * Return the active shift key for a date.
 */
export function currentShiftKey(date = new Date()): string {
  const minutes = date.getHours() * 60 + date.getMinutes();
  if (minutes >= 6 * 60 && minutes < 14 * 60) return "Frueh";
  if (minutes >= 14 * 60 && minutes < 22 * 60) return "Spaet";
  return "Nacht";
}

/**
 * Return the current time marker position.
 */
export function currentTimelinePercent(date = new Date()): string {
  const minutes = date.getHours() * 60 + date.getMinutes();
  return `${((minutes / (24 * 60)) * 100).toFixed(2)}%`;
}

/**
 * Return the best label for one timeline bar.
 */
export function timelineBarText(entry: DashboardPayload | null): string {
  if (!entry) return "Plan offen";
  const machine = entry.machine;
  if (typeof machine === "object" && machine !== null && !Array.isArray(machine)) {
    const machineName = (machine as Record<string, unknown>).name;
    if (typeof machineName === "string" && machineName.trim()) return machineName;
  }

  return peopleText(entry, "notes", "Geplant");
}

/**
 * Return dashboard timeline rows from a shift calendar payload.
 */
export function dashboardShiftRows(calendar: DashboardShiftCalendar | null): readonly DashboardShiftRow[] {
  const entries = Array.isArray(calendar?.entries) ? calendar.entries : [];
  const todayEntries = entries.filter(
    (entry) => peopleText(entry, "work_date") === todayIsoDate() && peopleText(entry, "shift") !== "Frei"
  );
  const byShift = new Map(todayEntries.map((entry) => [peopleText(entry, "shift"), entry]));
  const activeShift = currentShiftKey();

  return SHIFT_ROWS.map((row) => ({
    ...row,
    active: row.shiftKey === activeShift,
    entry: byShift.get(row.shiftKey) ?? null
  }));
}

/**
 * Return a status message for the shift calendar panel.
 */
export function shiftCalendarMessage(calendar: DashboardShiftCalendar | null, isLoading: boolean): string {
  if (isLoading) return "Schichtkalender wird geladen.";
  if (calendar?.employee && typeof calendar.employee === "object") {
    return `Kalender für ${peopleText(calendar.employee, "name", "Mitarbeiter")}`;
  }

  return calendar?.message || "Schichtkalender live aktualisiert";
}

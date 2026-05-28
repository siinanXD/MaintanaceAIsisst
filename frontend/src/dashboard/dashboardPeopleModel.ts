import { formatGermanDate } from "../utils/date";
import { type DashboardPayload, type DashboardRuntimeData } from "./dashboardApi";

/**
 * Return a normalized text field from a dashboard payload.
 */
export function peopleText(payload: DashboardPayload | null | undefined, key: string, fallback = ""): string {
  const value = payload?.[key];
  return typeof value === "string" && value.trim() ? value : fallback;
}

/**
 * Return initials for the compact employee avatar.
 */
export function employeeInitials(name: unknown): string {
  return (
    String(name || "?")
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase())
      .join("") || "?"
  );
}

/**
 * Return the first visible qualification or role text for an employee.
 */
export function employeeRole(employee: DashboardPayload): string {
  return (
    peopleText(employee, "qualifications")
      .split(/[,\n;]/)
      .map((part) => part.trim())
      .filter(Boolean)[0] ||
    peopleText(employee, "department") ||
    "Mitarbeiter"
  );
}

/**
 * Return the dashboard attendance status for an employee.
 */
export function employeeStatus(employee: DashboardPayload): string {
  const shift = peopleText(employee, "current_shift", peopleText(employee, "shift_model")).toLowerCase();
  if (shift.includes("urlaub") || shift.includes("frei")) return "Abwesend";
  if (!shift) return "Geplant";
  return "Anwesend";
}

/**
 * Return open or relevant vacation requests for people hints.
 */
export function relevantVacations(vacations: readonly DashboardPayload[]): readonly DashboardPayload[] {
  return vacations.filter((vacation) => peopleText(vacation, "status").toLowerCase() !== "rejected");
}

/**
 * Return absent employees for people hints.
 */
export function absentEmployees(employees: readonly DashboardPayload[]): readonly DashboardPayload[] {
  return employees.filter((employee) => employeeStatus(employee) === "Abwesend");
}

/**
 * Return a short handover title.
 */
export function handoverTitle(handover: DashboardPayload): string {
  return `${peopleText(handover, "shift_type", "Schicht")} · ${peopleText(handover, "department", "Bereich")}`;
}

/**
 * Return a short handover meta line.
 */
export function handoverMeta(handover: DashboardPayload): string {
  return [
    formatGermanDate(peopleText(handover, "shift_date"), {
      day: "2-digit",
      fallback: "-",
      month: "2-digit"
    }),
    handover.open_tasks ? "offene Punkte vorhanden" : "keine offenen Punkte erfasst",
    handover.machine_notes ? "Maschinenhinweise" : ""
  ]
    .filter(Boolean)
    .join(" · ");
}

/**
 * Return a dashboard people KPI value.
 */
export function peopleStatusValue(data: DashboardRuntimeData): string {
  const vacations = relevantVacations(data.vacations);
  const absent = absentEmployees(data.employees);
  return String(vacations.length || absent.length || data.employees.length || "--");
}

/**
 * Return a dashboard people KPI meta label.
 */
export function peopleStatusMeta(data: DashboardRuntimeData): string {
  const vacations = relevantVacations(data.vacations);
  const absent = absentEmployees(data.employees);
  if (vacations.length) return `${vacations.length} offene Urlaubsanträge`;
  if (absent.length) return `${absent.length} abwesend`;
  return "Keine offenen Personalwarnungen";
}

/**
 * Return a dashboard shift KPI value based on loaded handovers.
 */
export function handoverStatusValue(data: DashboardRuntimeData): string {
  return data.handovers.length ? String(data.handovers.length) : "--";
}

/**
 * Return a dashboard shift KPI meta label based on loaded handovers.
 */
export function handoverStatusMeta(data: DashboardRuntimeData): string {
  return data.handovers.length ? `${data.handovers.length} Übergaben heute` : "Keine Übergabe heute";
}

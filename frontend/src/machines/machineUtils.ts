import { formatGermanDate } from "../utils/date";
import { safeErrorMessage } from "../utils/errors";
import type { Machine, MachineDraft, MachineProfileRecord } from "./machineTypes";

export const EMPTY_MACHINE_DRAFT: MachineDraft = {
  name: "",
  produced_item: "",
  required_employees: "1"
};

/**
 * Convert unknown API errors into a safe UI message.
 */
export function machineErrorMessage(error: unknown): string {
  return safeErrorMessage(error, "Die Anfrage konnte nicht verarbeitet werden.");
}

/**
 * Return the edit or create draft for one machine.
 */
export function draftFromMachine(machine?: Machine | null): MachineDraft {
  if (!machine) {
    return { ...EMPTY_MACHINE_DRAFT };
  }

  return {
    name: machine.name || "",
    produced_item: machine.produced_item || "",
    required_employees: String(machine.required_employees || 1)
  };
}

/**
 * Return normalized searchable text.
 */
export function searchText(value: unknown): string {
  return String(value || "").toLowerCase().trim();
}

/**
 * Return a German date label.
 */
export function dateLabel(value: unknown): string {
  if (!value) return "-";
  const raw = String(value);
  const label = formatGermanDate(raw.includes("T") ? raw : `${raw}T00:00:00`, {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    fallback: raw
  });
  return label;
}

/**
 * Return a German minutes label.
 */
export function minutesLabel(value: unknown): string {
  const minutes = Number(value || 0);
  if (!minutes) return "0 min";
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest ? `${hours} h ${rest} min` : `${hours} h`;
}

/**
 * Return a stable value text.
 */
export function valueText(value: unknown): string {
  if (value === 0) return "0";
  return value ? String(value) : "-";
}

/**
 * Return the German machine status label.
 */
export function machineStatusLabel(status: unknown): string {
  const labels: Record<string, string> = {
    running: "Läuft",
    stopped: "Stillstand",
    maintenance: "Wartung",
    warning: "Warnung",
    offline: "Offline"
  };
  return labels[String(status || "")] || String(status || "-");
}

/**
 * Return the German criticality label.
 */
export function criticalityLabel(criticality: unknown): string {
  const labels: Record<string, string> = {
    critical: "Kritisch",
    high: "Hoch",
    normal: "Normal",
    low: "Niedrig"
  };
  return labels[String(criticality || "")] || String(criticality || "Normal");
}

/**
 * Return generic status badge classes.
 */
export function genericStatusBadgeClass(status: unknown): string {
  const value = String(status || "");
  if (["open", "warning", "stopped", "critical", "high"].includes(value)) return "badge badge-status is-open";
  if (["in_progress", "maintenance", "medium"].includes(value)) return "badge badge-status is-progress";
  return "badge badge-status is-done";
}

/**
 * Return criticality badge classes.
 */
export function criticalityBadgeClass(criticality: unknown): string {
  const value = String(criticality || "");
  if (value === "critical" || value === "high") return "badge badge-priority is-urgent";
  if (value === "low") return "badge badge-priority is-normal";
  return "badge badge-status is-done";
}

/**
 * Return priority badge classes.
 */
export function priorityBadgeClass(priority: unknown): string {
  if (priority === "urgent") return "badge priority-badge is-urgent";
  if (priority === "soon") return "badge priority-badge is-soon";
  return "badge priority-badge is-normal";
}

/**
 * Return German priority labels.
 */
export function priorityLabel(priority: unknown): string {
  const labels: Record<string, string> = {
    urgent: "Kritisch",
    soon: "Bald",
    normal: "Normal"
  };
  return labels[String(priority || "")] || String(priority || "-");
}

/**
 * Return German status labels.
 */
export function statusLabel(status: unknown): string {
  const labels: Record<string, string> = {
    open: "Offen",
    in_progress: "In Arbeit",
    done: "Erledigt",
    cancelled: "Abgebrochen",
    closed: "Geschlossen"
  };
  return labels[String(status || "")] || String(status || "-");
}

/**
 * Return task status badge classes.
 */
export function statusBadgeClass(status: unknown): string {
  if (status === "in_progress") return "badge status-badge is-progress";
  if (status === "done" || status === "cancelled" || status === "closed") return "badge status-badge is-done";
  return "badge status-badge is-open";
}

/**
 * Read a string property from an unknown profile record.
 */
export function recordString(record: MachineProfileRecord, key: string): string {
  const value = record[key];
  return typeof value === "string" ? value : "";
}

/**
 * Read a numeric property from an unknown profile record.
 */
export function recordNumber(record: MachineProfileRecord, key: string): number {
  const value = record[key];
  return typeof value === "number" ? value : Number(value || 0);
}

/**
 * Read an object property from an unknown profile record.
 */
export function recordObject(record: MachineProfileRecord, key: string): Record<string, unknown> | null {
  const value = record[key];
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
}

import { formatGermanDate } from "../utils/date";
import { type DashboardPayload } from "./dashboardApi";

export type DashboardSignal = "critical" | "good" | "muted" | "warning";

/**
 * Return a normalized text field from a dashboard payload.
 */
export function assetText(payload: DashboardPayload | null | undefined, key: string, fallback = ""): string {
  const value = payload?.[key];
  return typeof value === "string" && value.trim() ? value : fallback;
}

/**
 * Return a nested machine name from an incident payload.
 */
export function incidentMachineName(entry: DashboardPayload): string {
  const machine = entry.machine_obj;
  if (typeof machine === "object" && machine !== null && !Array.isArray(machine)) {
    const name = (machine as Record<string, unknown>).name;
    if (typeof name === "string" && name.trim()) {
      return name;
    }
  }

  return assetText(entry, "machine", "-");
}

/**
 * Return active dashboard incidents sorted by severity and recency.
 */
export function activeDashboardIncidents(errors: readonly DashboardPayload[]): readonly DashboardPayload[] {
  const severityRank: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };

  return errors
    .filter((entry) => assetText(entry, "status").toLowerCase() !== "closed")
    .slice()
    .sort((first, second) => {
      const firstRank = severityRank[assetText(first, "severity").toLowerCase()] ?? 4;
      const secondRank = severityRank[assetText(second, "severity").toLowerCase()] ?? 4;
      if (firstRank !== secondRank) return firstRank - secondRank;
      return assetText(second, "last_seen_at", assetText(second, "created_at")).localeCompare(
        assetText(first, "last_seen_at", assetText(first, "created_at"))
      );
    });
}

/**
 * Return frequent incident codes and counts for the dashboard strip.
 */
export function frequentIncidentCodes(errors: readonly DashboardPayload[]): readonly (readonly [string, number])[] {
  const counts = new Map<string, number>();

  errors.forEach((entry) => {
    const code = assetText(entry, "error_code", assetText(entry, "code", "ohne Code"));
    counts.set(code, (counts.get(code) ?? 0) + 1);
  });

  return [...counts.entries()].sort((first, second) => second[1] - first[1]).slice(0, 5);
}

/**
 * Return a badge class for one incident.
 */
export function incidentBadgeClass(entry: DashboardPayload): string {
  const severity = assetText(entry, "severity").toLowerCase();
  return severity === "critical" || severity === "high"
    ? "badge badge-priority is-urgent"
    : "badge badge-priority is-soon";
}

/**
 * Return a localized incident status label.
 */
export function incidentStatusLabel(status: unknown): string {
  const value = String(status || "open").toLowerCase();
  if (value === "closed") return "Geschlossen";
  if (value === "in_progress") return "In Arbeit";
  if (value === "open") return "Offen";
  return value;
}

/**
 * Return a compact date label for an incident timestamp.
 */
export function incidentDateLabel(entry: DashboardPayload): string {
  return formatGermanDate(assetText(entry, "last_seen_at", assetText(entry, "created_at")), {
    day: "2-digit",
    fallback: "-",
    month: "2-digit"
  });
}

/**
 * Return a dashboard severity class from a signal name.
 */
export function dashboardSignalClass(signal: DashboardSignal): string {
  if (signal === "critical") return "is-critical";
  if (signal === "warning") return "is-warning";
  if (signal === "good") return "is-good";
  return "is-muted";
}

/**
 * Return a machine severity from its status text.
 */
export function machineStatusSeverity(machine: DashboardPayload): DashboardSignal {
  const status = assetText(machine, "status").toLowerCase();
  if (status.includes("down") || status.includes("stör") || status.includes("stoer") || status.includes("error")) {
    return "critical";
  }

  if (status.includes("wart") || status.includes("maintenance") || status.includes("pause") || status.includes("prüf")) {
    return "warning";
  }

  if (status.includes("run") || status.includes("aktiv") || status.includes("ok") || status.includes("bereit")) {
    return "good";
  }

  return "muted";
}

/**
 * Return a localized machine status label.
 */
export function machineStatusText(machine: DashboardPayload): string {
  const status = assetText(machine, "status", "unbekannt");
  if (status === "running") return "Läuft";
  if (status === "down") return "Stillstand";
  if (status === "maintenance") return "Wartung";
  return status;
}

/**
 * Return a badge class from a dashboard signal.
 */
export function signalBadgeClass(signal: DashboardSignal): string {
  if (signal === "critical") return "badge badge-status is-open";
  if (signal === "warning") return "badge badge-status is-progress";
  if (signal === "good") return "badge badge-status is-done";
  return "badge badge-status is-neutral";
}

import { type DashboardPayload, type DashboardRuntimeData } from "./dashboardApi";
import type { DashboardSeverity, DashboardSignalItem } from "./dashboardTechnicalTypes";

/**
 * Return a nested object payload.
 */
export function objectValue(payload: DashboardPayload | null | undefined, key: string): DashboardPayload {
  const value = payload?.[key];
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as DashboardPayload)
    : {};
}

/**
 * Return a numeric field from a payload.
 */
export function numberValue(payload: DashboardPayload | null | undefined, key: string): number {
  const value = payload?.[key];
  const parsed = typeof value === "number" ? value : Number(value || 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

/**
 * Return the last retrieval SLO values from telemetry.
 */
export function retrievalSloValues(data: DashboardRuntimeData): DashboardPayload {
  return objectValue(objectValue(data.retrievalTelemetry, "retrieval_slo"), "last_values");
}

/**
 * Format a rate as percentage.
 */
export function formatRatePercent(value: unknown): string {
  return `${Math.round(Number(value || 0) * 100)}%`;
}

/**
 * Format a millisecond value.
 */
export function formatMilliseconds(value: unknown): string {
  return `${Math.round(Number(value || 0))} ms`;
}

/**
 * Return the dashboard severity CSS class.
 */
export function dashboardSignalClass(severity: DashboardSeverity): string {
  if (severity === "critical") return "is-critical";
  if (severity === "warning") return "is-warning";
  if (severity === "good") return "is-good";
  return "is-muted";
}

/**
 * Return the status label for the worst active dashboard signal.
 */
export function dashboardStatusLabel(signals: readonly DashboardSignalItem[]): string {
  if (signals.some((signal) => signal.severity === "critical")) return "Kritische Lage";
  if (signals.some((signal) => signal.severity === "warning")) return "Prüfen";
  if (signals.length) return "Stabil";
  return "Noch keine Daten";
}

/**
 * Return open knowledge gap count from the current dashboard data.
 */
export function knowledgeGapCount(data: DashboardRuntimeData): number {
  return (
    data.knowledgeGaps.length ||
    numberValue(data.knowledgeStatus, "open_count") ||
    numberValue(data.knowledgeStatus, "open_gap_count")
  );
}

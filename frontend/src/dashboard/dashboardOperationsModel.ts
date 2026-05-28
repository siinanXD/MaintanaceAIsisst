import { type DashboardPayload, type DashboardRuntimeData } from "./dashboardApi";

export type OperationCard = {
  readonly detail: string;
  readonly label: string;
  readonly value: string;
  readonly variant?: string;
};

export type DrilldownRow = {
  readonly label: string;
  readonly meta: string;
  readonly value: string;
};

/**
 * Return a nested object payload.
 */
function objectValue(payload: DashboardPayload | null | undefined, key: string): DashboardPayload {
  const value = payload?.[key];
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as DashboardPayload)
    : {};
}

/**
 * Return a numeric field from a payload.
 */
function numberValue(payload: DashboardPayload | null | undefined, key: string): number {
  const value = payload?.[key];
  const parsed = typeof value === "number" ? value : Number(value || 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

/**
 * Return an array field from a payload.
 */
function arrayValue(payload: DashboardPayload | null | undefined, key: string): readonly DashboardPayload[] {
  const value = payload?.[key];
  return Array.isArray(value) ? (value as DashboardPayload[]) : [];
}

/**
 * Format minutes for compact dashboard operations cards.
 */
export function formatOperationMinutes(value: unknown): string {
  const minutes = Number(value || 0);
  if (minutes >= 60) return `${(minutes / 60).toFixed(1).replace(".", ",")} h`;
  return `${Math.round(minutes)} min`;
}

/**
 * Format a percentage value for compact dashboard cards.
 */
export function formatOperationPercent(value: unknown): string {
  return `${Math.round(Number(value || 0))}%`;
}

/**
 * Format a compact number with German separators.
 */
export function formatOperationNumber(value: unknown): string {
  return new Intl.NumberFormat("de-DE", { maximumFractionDigits: 1 }).format(Number(value || 0));
}

/**
 * Format a USD amount for existing AI-cost dashboard labels.
 */
export function formatOperationUsd(value: unknown): string {
  return new Intl.NumberFormat("de-DE", { currency: "USD", style: "currency" }).format(Number(value || 0));
}

/**
 * Build dashboard operations cards from an operations summary.
 */
export function operationCards(data: DashboardRuntimeData): readonly OperationCard[] {
  const summary = data.operationsSummary ?? {};
  const tasks = objectValue(summary, "tasks");
  const machines = objectValue(summary, "machines");
  const inventory = objectValue(summary, "inventory");
  const workforce = objectValue(summary, "workforce");
  const documents = objectValue(summary, "documents");
  const aiQuality = objectValue(summary, "ai_quality");
  const events = objectValue(summary, "events");

  return [
    {
      detail: `${numberValue(tasks, "overdue")} überfällig`,
      label: "Offene Aufgaben",
      value: String(numberValue(tasks, "open")),
      variant: numberValue(tasks, "overdue") ? "is-risk" : ""
    },
    {
      detail: `${numberValue(machines, "downtime_minutes")} min Ausfall`,
      label: "MTTR",
      value: formatOperationMinutes(machines.mttr_minutes),
      variant: numberValue(machines, "mttr_minutes") ? "is-warning" : ""
    },
    {
      detail: `${numberValue(machines, "faults")} Störungen`,
      label: "Wiederholstörungen",
      value: String(numberValue(machines, "repeat_faults")),
      variant: numberValue(machines, "repeat_faults") ? "is-risk" : ""
    },
    {
      detail: `${numberValue(inventory, "low_stock_count")} unter Mindestbestand`,
      label: "Materialengpässe",
      value: String(numberValue(inventory, "critical_shortage_count")),
      variant: numberValue(inventory, "critical_shortage_count") ? "is-risk" : ""
    },
    {
      detail: `${numberValue(workforce, "critical_conflicts")} kritische Konflikte`,
      label: "Schichtdeckung",
      value: formatOperationPercent(workforce.avg_coverage_percent),
      variant: numberValue(workforce, "critical_conflicts") ? "is-warning" : ""
    },
    {
      detail: `${numberValue(documents, "quality_checked")} geprüft`,
      label: "Dokumentqualität",
      value: formatOperationNumber(documents.avg_quality_score),
      variant: numberValue(documents, "avg_quality_score") < 70 && numberValue(documents, "quality_checked") ? "is-warning" : ""
    },
    {
      detail: `${formatOperationUsd(aiQuality.estimated_cost_usd)} geschätzt`,
      label: "KI-Feedback",
      value: String(numberValue(aiQuality, "feedback_count"))
    },
    {
      detail: "pseudonymisiert erfasst",
      label: "Events",
      value: String(numberValue(events, "total"))
    }
  ];
}

/**
 * Build operations drilldown rows from an operations summary.
 */
export function operationDrilldownRows(data: DashboardRuntimeData): readonly DrilldownRow[] {
  const summary = data.operationsSummary ?? {};
  const inventory = objectValue(summary, "inventory");
  const machines = objectValue(summary, "machines");
  const events = objectValue(summary, "events");
  const rows: DrilldownRow[] = [];

  arrayValue(inventory, "top_shortages").slice(0, 4).forEach((item) => {
    rows.push({
      label: String(item.name || "Material"),
      meta: String(item.criticality || "normal"),
      value: `${String(item.quantity || 0)} / ${String(item.min_quantity || 0)}`
    });
  });

  Object.entries(objectValue(machines, "top_cause_categories")).slice(0, 4).forEach(([cause, count]) => {
    rows.push({
      label: cause === "unknown" ? "Ursache offen" : cause,
      meta: "Störungskategorie",
      value: String(count)
    });
  });

  Object.entries(objectValue(events, "by_feature")).slice(0, 4).forEach(([feature, count]) => {
    rows.push({ label: feature, meta: "Events im Zeitraum", value: String(count) });
  });

  return rows;
}

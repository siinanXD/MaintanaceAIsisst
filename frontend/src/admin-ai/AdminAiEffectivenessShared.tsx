import { type ReactNode } from "react";

import type { AdminAiBarRow, AdminAiMetricRow } from "./adminAiEffectivenessModel";

/**
 * Render existing mini-bar rows with an empty fallback.
 */
export function MiniBarList({
  emptyDetail,
  emptyLabel,
  rows,
  target
}: {
  readonly emptyDetail: string;
  readonly emptyLabel: string;
  readonly rows: readonly AdminAiBarRow[];
  readonly target: "langfuse-models" | "langfuse-workflows" | "workflow-costs";
}): ReactNode {
  const dataAttributes = {
    "data-ai-workflow-cost-chart": target === "workflow-costs" ? true : undefined,
    "data-langfuse-model-costs": target === "langfuse-models" ? true : undefined,
    "data-langfuse-workflow-costs": target === "langfuse-workflows" ? true : undefined
  };

  return (
    <div className="mini-bar-list" {...dataAttributes}>
      {rows.length ? (
        rows.map((row) => (
          <div className="mini-bar-row" key={`${row.label}:${row.value}`}>
            <span>{row.label}</span>
            <i style={{ width: row.width }} />
            <strong>{row.value}</strong>
          </div>
        ))
      ) : (
        <div className="stat-row">
          <span>{emptyLabel}</span>
          <strong>{emptyDetail}</strong>
        </div>
      )}
    </div>
  );
}

/**
 * Render a stats-list with existing stat-row markup.
 */
export function StatsList({
  rows,
  target
}: {
  readonly rows: readonly AdminAiMetricRow[];
  readonly target: "risks";
}): ReactNode {
  return (
    <div className="stats-list" data-ai-effectiveness-risks={target === "risks" ? true : undefined}>
      {rows.map((row) => (
        <div className="stat-row" key={row.label}>
          <span>{row.label}</span>
          <strong>{row.value}</strong>
        </div>
      ))}
    </div>
  );
}

/**
 * Return the visible title for one capability group.
 */
export function capabilityTitle(key: string): string {
  if (key === "supported") return "Unterstützt";
  if (key === "partial") return "Teilweise unterstützt";
  return "Nicht unterstützt";
}

/**
 * Return the visible status for one capability group.
 */
export function capabilityStatus(key: string): string {
  if (key === "supported") return "aktiv";
  if (key === "partial") return "abhängig von Daten";
  return "bewusst gesperrt";
}

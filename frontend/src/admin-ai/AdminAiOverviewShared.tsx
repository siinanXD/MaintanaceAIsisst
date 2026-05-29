import { type ReactNode } from "react";

import type { AdminAiHealthCard, AdminAiStatRow } from "./adminAiOverviewModel";

/**
 * Return a safe display string for Admin-AI overview cells.
 */
export function displayText(value: unknown, fallback = "-"): string {
  if (typeof value === "string" && value.trim()) return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return fallback;
}

/**
 * Format numeric Admin-AI overview values.
 */
export function numberText(value: unknown): string {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed.toLocaleString("de-DE") : displayText(value);
}

/**
 * Return a prompt-safe record reference label.
 */
export function recordReference(prefix: string, id: unknown): string {
  const value = displayText(id, "");
  return value ? `${prefix} #${value}` : prefix;
}

/**
 * Return a health card by key with the legacy loading fallback.
 */
export function healthCard(cards: readonly AdminAiHealthCard[], key: string): AdminAiHealthCard {
  return (
    cards.find((card) => card.key === key) ?? {
      key,
      label: "--",
      detail: "Noch nicht geladen",
      tone: "is-muted"
    }
  );
}

/**
 * Render one existing health metric card.
 */
export function HealthMetricCard({
  card,
  title
}: {
  readonly card: AdminAiHealthCard;
  readonly title: string;
}): ReactNode {
  return (
    <article className={`metric-card ai-status-card ${card.tone}`} data-ai-health={card.key}>
      <span>{title}</span>
      <strong data-ai-health-label>{card.label}</strong>
      <small data-ai-health-detail>{card.detail}</small>
    </article>
  );
}

/**
 * Render Admin-AI stat rows into the existing stats-list markup.
 */
export function StatRows({
  rows,
  target
}: {
  readonly rows: readonly AdminAiStatRow[];
  readonly target: "actions" | "details";
}): ReactNode {
  return (
    <div
      className="stats-list"
      data-ai-provider-actions={target === "actions" ? true : undefined}
      data-ai-provider-details={target === "details" ? true : undefined}
    >
      {rows.map((row) => (
        <div className="stat-row" key={`${row.label}:${row.value}`}>
          <span>{row.label}</span>
          <strong>{row.value}</strong>
        </div>
      ))}
    </div>
  );
}

import { type ReactNode } from "react";

import type { HandoverStats as HandoverStatsData } from "./HandoverTypes";

type HandoverStat = {
  readonly className: string;
  readonly hookName: string;
  readonly keyName: keyof HandoverStatsData;
  readonly label: string;
  readonly meta: string;
};

const HANDOVER_STATS: readonly HandoverStat[] = [
  {
    className: "is-open",
    hookName: "data-ho-open-count",
    keyName: "open",
    label: "Offen",
    meta: "nicht bestätigte Übergaben",
  },
  {
    className: "is-done",
    hookName: "data-ho-completed-count",
    keyName: "completed",
    label: "Bestätigt",
    meta: "abgeschlossene Protokolle",
  },
  {
    className: "is-risk",
    hookName: "data-ho-safety-count",
    keyName: "safety",
    label: "Sicherheit",
    meta: "Hinweise mit Sicherheitsbezug",
  },
  {
    className: "is-followup",
    hookName: "data-ho-followup-count",
    keyName: "followup",
    label: "Folgepunkte",
    meta: "offene Aufgaben für nächste Schicht",
  },
];

/**
 * Convert a data attribute name into a JSX-compatible prop object.
 */
function createDataHook(hookName: string): Record<string, string> {
  return { [hookName]: "" };
}

/**
 * Render the handover KPI strip.
 */
export function HandoverStats({ stats }: { readonly stats: HandoverStatsData }): ReactNode {
  return (
    <section className="handover-control-strip" aria-label="Schichtübergabe Kennzahlen">
      {HANDOVER_STATS.map((stat) => (
        <article key={stat.hookName} className={`handover-control-stat ${stat.className}`}>
          <span>{stat.label}</span>
          <strong {...createDataHook(stat.hookName)}>{stats[stat.keyName]}</strong>
          <small>{stat.meta}</small>
        </article>
      ))}
    </section>
  );
}

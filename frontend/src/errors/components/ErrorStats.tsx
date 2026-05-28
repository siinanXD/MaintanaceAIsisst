import type { ReactNode } from "react";

import type { ErrorEntry } from "../errorTypes";
import { categoriesFromErrors, formatIncidentMinutes } from "../errorUtils";

type ErrorStatsProps = {
  readonly errors: readonly ErrorEntry[];
};

/**
 * Render error catalog KPI cards.
 */
export function ErrorStats({ errors }: ErrorStatsProps): ReactNode {
  const openCount = errors.filter((entry) => (entry.status || "open") !== "closed").length;
  const criticalCount = errors.filter((entry) => entry.severity === "critical" || entry.severity === "high").length;
  const downtime = errors.reduce((sum, entry) => sum + Number(entry.downtime_minutes || 0), 0);
  const categoryCount = categoriesFromErrors(errors).length;

  return (
    <section className="incident-control-strip" aria-label="Störungskennzahlen">
      <article className="incident-control-stat is-total">
        <span>Katalog</span>
        <strong data-error-count>{errors.length} Einträge</strong>
        <small>gesamt erfasst</small>
      </article>
      <article className="incident-control-stat is-open">
        <span>Offen</span>
        <strong data-error-open-count>{openCount}</strong>
        <small>aktive Störungen</small>
      </article>
      <article className="incident-control-stat is-critical">
        <span>Kritisch</span>
        <strong data-error-critical-count>{criticalCount}</strong>
        <small>hohe Schwere</small>
      </article>
      <article className="incident-control-stat is-downtime">
        <span>Stillstand</span>
        <strong data-error-downtime-count>{formatIncidentMinutes(downtime)}</strong>
        <small>erfasste Dauer</small>
      </article>
      <article className="incident-control-stat is-category">
        <span>Kategorien</span>
        <strong data-error-category-count>{categoryCount}</strong>
        <small>strukturierte Ursachen</small>
      </article>
    </section>
  );
}

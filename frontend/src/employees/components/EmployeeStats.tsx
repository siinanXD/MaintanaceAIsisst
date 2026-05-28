import type { ReactNode } from "react";

import type { Employee } from "../employeeTypes";

type EmployeeStatsProps = {
  readonly employees: readonly Employee[];
};

/**
 * Render employee KPI cards.
 */
export function EmployeeStats({ employees }: EmployeeStatsProps): ReactNode {
  return (
    <section className="surface-stat-grid ux-ops-summary-grid" aria-label="Personalstatus">
      <article className="surface-stat-card is-primary">
        <span>Mitarbeitende</span>
        <strong data-employee-count>{employees.length} Mitarbeitende</strong>
        <small>Personen, Teams, Schichtmodell und Zuständigkeiten.</small>
      </article>
      <article className="surface-stat-card is-ai">
        <span>Qualifikationen</span>
        <strong>sichtbar</strong>
        <small>Fähigkeiten und Maschinenbezug direkt an der Person.</small>
      </article>
      <article className="surface-stat-card is-warning">
        <span>Schichtbezug</span>
        <strong>Teams</strong>
        <small>Team, Rhythmus und aktuelle Schicht für Planung.</small>
      </article>
      <article className="surface-stat-card is-neutral">
        <span>Dokumente</span>
        <strong>Personenakte</strong>
        <small>Freigegebene Dokumente bleiben pro Mitarbeiter abrufbar.</small>
      </article>
    </section>
  );
}

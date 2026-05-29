import { type ReactNode } from "react";

import { type DashboardViewState } from "./dashboardModel";
import { dashboardHeroStatus } from "./dashboardTechnicalModel";

type DashboardHeroProps = {
  readonly dashboardState: DashboardViewState;
};

/**
 * Render the dashboard control-center hero with the existing runtime hooks.
 */
export function DashboardHero({ dashboardState }: DashboardHeroProps): ReactNode {
  const status = dashboardHeroStatus(
    dashboardState.data,
    dashboardState.isLoading,
    dashboardState.errorMessage
  );

  return (
    <section
      className="page-hero control-center-hero app-card"
      data-ai-ops-cockpit=""
      aria-label="Maintenance Control Center"
    >
      <div className="control-center-copy">
        <p className="page-kicker">Maintenance Control Center</p>
        <h1 className="page-title">Aktuelle Lage im Werk</h1>
        <p className="page-description">
          Kritische Arbeit, St&ouml;rungen, Maschinen, Schicht und Personalhinweise als operative
          Tageslage.
        </p>
      </div>
      <div className="control-center-status" aria-label="Aktueller Betriebsstatus">
        <span className={`ops-status-pill ${status.className}`} data-ai-ops-status="">
          {status.label}
        </span>
        <span data-ai-ops-updated="">{status.updated}</span>
        <span data-dashboard-system-meta="">{status.meta}</span>
      </div>
      <div className="control-center-actions" aria-label="Schnellzugriff">
        <a className="btn btn-primary btn-sm" data-dashboard-nav="tasks" hidden href="/tasks">
          Aufgabe erstellen
        </a>
        <a className="btn btn-outline btn-sm" data-dashboard-nav="errors" hidden href="/errors">
          St&ouml;rung melden
        </a>
        <a className="btn btn-outline btn-sm" data-dashboard-nav="machines" hidden href="/machines">
          Maschine pr&uuml;fen
        </a>
        <a
          className="btn btn-outline btn-sm"
          data-feature-key="handover"
          data-dashboard-nav="shiftplans"
          hidden
          href="/handover"
        >
          Schicht&uuml;bergabe
        </a>
      </div>
    </section>
  );
}

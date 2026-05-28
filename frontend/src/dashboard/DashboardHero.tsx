import { type ReactNode } from "react";

/**
 * Render the dashboard control-center hero with the existing runtime hooks.
 */
export function DashboardHero(): ReactNode {
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
        <span className="ops-status-pill is-loading" data-ai-ops-status="">
          Daten werden geladen
        </span>
        <span data-ai-ops-updated="">Aktualisierung ausstehend</span>
        <span data-dashboard-system-meta="">Schicht- und Systemdaten werden geladen</span>
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

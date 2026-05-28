import { type ReactNode } from "react";

/**
 * Render the incident overview panel with the existing dashboard runtime hooks.
 */
function IncidentStatusPanel(): ReactNode {
  return (
    <article className="ops-panel app-card">
      <header className="ops-panel-header">
        <div>
          <p className="section-kicker">St&ouml;rungen</p>
          <h2>Aktive St&ouml;rungen</h2>
          <p className="panel-meta">Neueste Fehler mit Maschine, Code und Tageskontext.</p>
        </div>
        <a data-dashboard-nav="errors" hidden href="/errors">
          Fehlerkatalog
        </a>
      </header>
      <div className="incident-list incident-card-list" data-dashboard-error-stats="">
        <div className="empty-state">St&ouml;rungen werden geladen.</div>
      </div>
      <div
        className="frequent-code-strip"
        aria-label="H&auml;ufige Fehlercodes"
        data-dashboard-frequent-codes=""
      >
        <span>Fehlercodes werden geladen.</span>
      </div>
    </article>
  );
}

/**
 * Render the machine-status panel with the existing dashboard runtime hooks.
 */
function MachineStatusPanel(): ReactNode {
  return (
    <article className="ops-panel app-card">
      <header className="ops-panel-header">
        <div>
          <p className="section-kicker">Anlagen</p>
          <h2>Maschinenstatus</h2>
          <p className="panel-meta">
            Status, Ausf&auml;lle, Wiederholungen und Materialrisiken.
          </p>
        </div>
        <a data-dashboard-nav="machines" hidden href="/machines">
          Maschinen
        </a>
      </header>
      <div className="machine-status-strip" data-dashboard-machine-strip="">
        <div className="empty-state">Maschinenlage wird geladen.</div>
      </div>
      <div className="machine-status-card-list" data-dashboard-machine-cards="">
        <div className="empty-state">Maschinen werden geladen.</div>
      </div>
    </article>
  );
}

/**
 * Render dashboard status panels for incidents and machine health.
 */
export function DashboardAssetStatus(): ReactNode {
  return (
    <>
      <IncidentStatusPanel />
      <MachineStatusPanel />
    </>
  );
}

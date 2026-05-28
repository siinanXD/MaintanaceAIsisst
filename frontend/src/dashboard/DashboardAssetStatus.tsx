import { type ReactNode } from "react";

import { type DashboardPayload } from "./dashboardApi";
import { type DashboardViewState } from "./dashboardModel";
import {
  activeDashboardIncidents,
  assetText,
  dashboardSignalClass,
  frequentIncidentCodes,
  incidentBadgeClass,
  incidentDateLabel,
  incidentMachineName,
  incidentStatusLabel,
  machineStatusSeverity,
  machineStatusText,
  signalBadgeClass
} from "./dashboardAssetModel";

type DashboardAssetStatusProps = {
  readonly dashboardState: DashboardViewState;
};

/**
 * Render a visible empty state.
 */
function EmptyState({ children }: { readonly children: ReactNode }): ReactNode {
  return <div className="empty-state">{children}</div>;
}

/**
 * Render one incident row with the existing dashboard classes.
 */
function IncidentRow({ entry }: { readonly entry: DashboardPayload }): ReactNode {
  return (
    <div className="incident-row">
      <span className={incidentBadgeClass(entry)}>Aktiv</span>
      <strong>{assetText(entry, "title", assetText(entry, "error_code", "Störung"))}</strong>
      <span>{incidentMachineName(entry)}</span>
      <span>{incidentDateLabel(entry)}</span>
      <span className="badge badge-status is-progress">{incidentStatusLabel(entry.status)}</span>
    </div>
  );
}

/**
 * Render the frequent incident code strip.
 */
function FrequentCodeStrip({ incidents }: { readonly incidents: readonly DashboardPayload[] }): ReactNode {
  const codes = frequentIncidentCodes(incidents);

  return (
    <div className="frequent-code-strip" aria-label="H&auml;ufige Fehlercodes" data-dashboard-frequent-codes="">
      {codes.length ? (
        codes.map(([code, count]) => (
          <span key={code}>
            {code}
            <strong>{count}</strong>
          </span>
        ))
      ) : (
        <span>Keine Fehlercodes im aktuellen Fenster.</span>
      )}
    </div>
  );
}

/**
 * Render the incident overview panel from React dashboard state.
 */
function IncidentStatusPanel({ dashboardState }: DashboardAssetStatusProps): ReactNode {
  const incidents = activeDashboardIncidents(dashboardState.data.errors);

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
        {dashboardState.isLoading ? <EmptyState>Störungen werden geladen.</EmptyState> : null}
        {!dashboardState.isLoading && incidents.length === 0 ? (
          <EmptyState>Keine aktiven Störungen im aktuellen Fenster.</EmptyState>
        ) : null}
        {incidents.slice(0, 5).map((entry) => (
          <IncidentRow key={String(entry.id ?? entry.error_code ?? entry.title)} entry={entry} />
        ))}
      </div>
      <FrequentCodeStrip incidents={incidents} />
    </article>
  );
}

/**
 * Render one machine signal badge.
 */
function MachineBadge({
  children,
  signal
}: {
  readonly children: ReactNode;
  readonly signal: ReturnType<typeof machineStatusSeverity>;
}): ReactNode {
  return <span className={signalBadgeClass(signal)}>{children}</span>;
}

/**
 * Render one machine status card.
 */
function MachineStatusCard({ machine }: { readonly machine: DashboardPayload }): ReactNode {
  const severity = machineStatusSeverity(machine);
  const criticality = assetText(machine, "criticality", "normal");

  return (
    <a className={`machine-status-card ${dashboardSignalClass(severity)}`} href="/machines">
      <strong>{assetText(machine, "name", "Maschine")}</strong>
      <small>{assetText(machine, "produced_item", "Produktionsdaten offen")}</small>
      <div>
        <MachineBadge signal={severity}>{machineStatusText(machine)}</MachineBadge>
        <MachineBadge signal={criticality === "critical" ? "critical" : "muted"}>{criticality}</MachineBadge>
      </div>
    </a>
  );
}

/**
 * Render a compact machine severity strip.
 */
function MachineStatusStrip({ machines }: { readonly machines: readonly DashboardPayload[] }): ReactNode {
  const critical = machines.filter((machine) => machineStatusSeverity(machine) === "critical").length;
  const warning = machines.filter((machine) => machineStatusSeverity(machine) === "warning").length;
  const good = machines.filter((machine) => machineStatusSeverity(machine) === "good").length;

  return (
    <div className="machine-status-strip" data-dashboard-machine-strip="">
      <span className="badge badge-status is-open">{critical} kritisch</span>
      <span className="badge badge-status is-progress">{warning} beobachten</span>
      <span className="badge badge-status is-done">{good} stabil</span>
    </div>
  );
}

/**
 * Render the machine-status panel from React dashboard state.
 */
function MachineStatusPanel({ dashboardState }: DashboardAssetStatusProps): ReactNode {
  const machines = dashboardState.data.machines;

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
      {dashboardState.isLoading && machines.length === 0 ? (
        <div className="machine-status-strip" data-dashboard-machine-strip="">
          <EmptyState>Maschinenlage wird geladen.</EmptyState>
        </div>
      ) : (
        <MachineStatusStrip machines={machines} />
      )}
      <div className="machine-status-card-list" data-dashboard-machine-cards="">
        {!dashboardState.isLoading && machines.length === 0 ? (
          <EmptyState>Keine Maschinen im aktuellen Zugriff.</EmptyState>
        ) : null}
        {machines.slice(0, 6).map((machine) => (
          <MachineStatusCard key={String(machine.id ?? machine.name)} machine={machine} />
        ))}
      </div>
    </article>
  );
}

/**
 * Render dashboard status panels for incidents and machine health.
 */
export function DashboardAssetStatus({ dashboardState }: DashboardAssetStatusProps): ReactNode {
  return (
    <>
      <IncidentStatusPanel dashboardState={dashboardState} />
      <MachineStatusPanel dashboardState={dashboardState} />
    </>
  );
}

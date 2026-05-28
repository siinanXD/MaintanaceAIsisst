import { type ReactNode } from "react";

import { type DashboardViewState } from "./dashboardModel";
import { operationCards, operationDrilldownRows, type DrilldownRow, type OperationCard } from "./dashboardOperationsModel";

type DashboardOperationsProps = {
  readonly dashboardState: DashboardViewState;
};

/**
 * Render the operations filter controls with legacy-compatible hooks.
 */
function OperationsFilters(): ReactNode {
  return (
    <div className="ops-insights-controls" aria-label="Betriebsfilter">
      <label className="field field-compact">
        <span>Werk</span>
        <select className="select select-bordered" data-operations-site-filter="">
          <option value="">Alle aktiven Werke</option>
        </select>
      </label>
      <label className="field field-compact">
        <span>Zeitraum</span>
        <select className="select select-bordered" data-operations-range-filter="" defaultValue="30">
          <option value="7">7 Tage</option>
          <option value="30">30 Tage</option>
          <option value="90">90 Tage</option>
        </select>
      </label>
      <button className="btn btn-outline btn-sm" type="button" data-operations-refresh="">
        Aktualisieren
      </button>
    </div>
  );
}

/**
 * Render one operations KPI card.
 */
function OperationsKpiCard({ card }: { readonly card: OperationCard }): ReactNode {
  return (
    <article className={`ops-insight-card ${card.variant || ""}`.trim()}>
      <span>{card.label}</span>
      <strong>{card.value}</strong>
      <small>{card.detail}</small>
    </article>
  );
}

/**
 * Render one operations drilldown row.
 */
function OperationsDrilldownRow({ row }: { readonly row: DrilldownRow }): ReactNode {
  return (
    <div className="ops-drilldown-row">
      <strong>{row.label}</strong>
      <span>{row.value}</span>
      <small>{row.meta}</small>
    </div>
  );
}

/**
 * Render the operations KPI panel as React-owned markup.
 */
export function DashboardOperations({ dashboardState }: DashboardOperationsProps): ReactNode {
  const cards = operationCards(dashboardState.data);
  const rows = operationDrilldownRows(dashboardState.data);

  return (
    <article className="ops-panel app-card operations-status-card">
      <header className="ops-panel-header">
        <div>
          <p className="section-kicker">Kennzahlen</p>
          <h2>Wichtige Kennzahlen</h2>
          <p className="panel-meta" data-operations-insights-status="" role="status" aria-live="polite">
            {dashboardState.isLoading ? "Kennzahlen werden geladen." : "Kennzahlen geladen."}
          </p>
        </div>
        <OperationsFilters />
      </header>
      <section className="ops-insights-shell" data-operations-insights="" aria-label="Operations KPIs">
        <div className="ops-insights-grid" data-operations-kpi-grid="">
          {cards.map((card) => (
            <OperationsKpiCard key={card.label} card={card} />
          ))}
        </div>
        <div className="ops-insights-drilldown" data-operations-drilldown="" aria-label="Operations Drilldowns">
          {rows.length ? (
            rows.map((row) => <OperationsDrilldownRow key={`${row.label}-${row.value}`} row={row} />)
          ) : (
            <div className="empty-state">Noch keine Operations-Events im gewählten Zeitraum.</div>
          )}
        </div>
      </section>
    </article>
  );
}

import { type ReactNode } from "react";

type OperationsKpiCard = {
  readonly label: string;
  readonly value: string;
  readonly meta: ReactNode;
};

const OPERATIONS_KPI_CARDS: readonly OperationsKpiCard[] = [
  {
    label: "Aufgaben",
    value: "--",
    meta: "Offene Arbeit"
  },
  {
    label: "Reparaturzeit",
    value: "--",
    meta: "Ausfallzeit"
  },
  {
    label: "Lager",
    value: "--",
    meta: <>Engp&auml;sse</>
  },
  {
    label: "Events",
    value: "--",
    meta: "Prozesssignale"
  }
];

/**
 * Render the operations filter controls with the existing runtime hooks.
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
 * Render one placeholder operations KPI card.
 */
function OperationsKpiCard({ card }: { readonly card: OperationsKpiCard }): ReactNode {
  return (
    <article className="ops-insight-card is-loading">
      <span>{card.label}</span>
      <strong>{card.value}</strong>
      <small>{card.meta}</small>
    </article>
  );
}

/**
 * Render the operations KPI panel as React-owned markup.
 */
export function DashboardOperations(): ReactNode {
  return (
    <article className="ops-panel app-card operations-status-card">
      <header className="ops-panel-header">
        <div>
          <p className="section-kicker">Kennzahlen</p>
          <h2>Wichtige Kennzahlen</h2>
          <p
            className="panel-meta"
            data-operations-insights-status=""
            role="status"
            aria-live="polite"
          >
            Kennzahlen werden geladen.
          </p>
        </div>
        <OperationsFilters />
      </header>
      <section className="ops-insights-shell" data-operations-insights="" aria-label="Operations KPIs">
        <div className="ops-insights-grid" data-operations-kpi-grid="">
          {OPERATIONS_KPI_CARDS.map((card) => (
            <OperationsKpiCard key={card.label} card={card} />
          ))}
        </div>
        <div
          className="ops-insights-drilldown"
          data-operations-drilldown=""
          aria-label="Operations Drilldowns"
        >
          <div className="empty-state">Drilldowns erscheinen nach dem Laden der Kennzahlen.</div>
        </div>
      </section>
    </article>
  );
}

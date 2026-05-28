import { type ReactNode } from "react";

type DashboardKpi = {
  readonly colorClass: string;
  readonly label: ReactNode;
  readonly value: string;
  readonly valueHook: string;
  readonly meta: ReactNode;
  readonly metaHook?: string;
  readonly progressHook: string;
  readonly progressWidth: string;
};

const DASHBOARD_KPIS: readonly DashboardKpi[] = [
  {
    colorClass: "is-red",
    label: "Kritisch heute",
    value: "0",
    valueHook: "data-dashboard-critical-count",
    meta: <>Heute f&auml;llig und &uuml;berf&auml;llig</>,
    metaHook: "data-dashboard-critical-meta",
    progressHook: "data-dashboard-critical-progress",
    progressWidth: "0%"
  },
  {
    colorClass: "is-orange",
    label: <>Aktive St&ouml;rungen</>,
    value: "--",
    valueHook: "data-dashboard-unresolved-errors",
    meta: <>St&ouml;rungen werden geladen</>,
    metaHook: "data-dashboard-machine-status-meta",
    progressHook: "data-dashboard-error-progress",
    progressWidth: "0%"
  },
  {
    colorClass: "is-blue",
    label: "Offene Aufgaben",
    value: "0",
    valueHook: "data-dashboard-open-count",
    meta: "Wird geladen",
    metaHook: "data-dashboard-open-meta",
    progressHook: "data-dashboard-open-progress",
    progressWidth: "12%"
  },
  {
    colorClass: "is-teal",
    label: "Maschinenstatus",
    value: "--",
    valueHook: "data-dashboard-machine-status",
    meta: "Maschinen werden geladen",
    metaHook: "data-dashboard-machine-kpi-meta",
    progressHook: "data-dashboard-machine-progress",
    progressWidth: "0%"
  },
  {
    colorClass: "is-green",
    label: "Erledigte Aufgaben",
    value: "0",
    valueHook: "data-dashboard-done-count",
    meta: "Abgeschlossen im aktuellen Fenster",
    progressHook: "data-dashboard-done-progress",
    progressWidth: "0%"
  },
  {
    colorClass: "is-cyan",
    label: "Schichtlage",
    value: "--",
    valueHook: "data-dashboard-shift-status",
    meta: "Schichtdaten werden geladen",
    metaHook: "data-dashboard-shift-meta",
    progressHook: "data-dashboard-shift-progress",
    progressWidth: "0%"
  },
  {
    colorClass: "is-indigo",
    label: "Personalhinweise",
    value: "--",
    valueHook: "data-dashboard-people-status",
    meta: "Urlaub und Team werden geladen",
    metaHook: "data-dashboard-people-meta",
    progressHook: "data-dashboard-people-progress",
    progressWidth: "0%"
  },
  {
    colorClass: "is-slate",
    label: "Systemstatus",
    value: "--",
    valueHook: "data-dashboard-system-status",
    meta: "Indexstatus wird geladen",
    metaHook: "data-dashboard-index-status-meta",
    progressHook: "data-dashboard-system-progress",
    progressWidth: "0%"
  }
];

/**
 * Build a React data-attribute object for runtime selectors.
 */
function dataHookAttribute(hookName: string): Record<string, string> {
  return { [hookName]: "" };
}

/**
 * Render one dashboard KPI card while preserving selector hooks.
 */
function DashboardKpiCard({ kpi }: { readonly kpi: DashboardKpi }): ReactNode {
  return (
    <article className={`executive-kpi-card ${kpi.colorClass}`}>
      <span>{kpi.label}</span>
      <strong {...dataHookAttribute(kpi.valueHook)}>{kpi.value}</strong>
      <small {...(kpi.metaHook ? dataHookAttribute(kpi.metaHook) : {})}>{kpi.meta}</small>
      <div className="kpi-progress">
        <span {...dataHookAttribute(kpi.progressHook)} style={{ width: kpi.progressWidth }} />
      </div>
    </article>
  );
}

/**
 * Render the dashboard KPI strip as React-owned markup.
 */
export function DashboardKpis(): ReactNode {
  return (
    <section className="executive-kpi-grid control-center-kpis" aria-label="Wichtige Kennzahlen">
      {DASHBOARD_KPIS.map((kpi) => (
        <DashboardKpiCard key={kpi.valueHook} kpi={kpi} />
      ))}
    </section>
  );
}

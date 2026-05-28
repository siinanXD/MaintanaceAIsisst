import { type ReactNode } from "react";

type CockpitColumn = {
  readonly id: string;
  readonly className: string;
  readonly title: ReactNode;
  readonly countKey: string;
  readonly emptyText: ReactNode;
};

const COCKPIT_COLUMNS: readonly CockpitColumn[] = [
  {
    id: "cockpit-urgent-title",
    className: "is-urgent",
    title: "Dringend",
    countKey: "urgent",
    emptyText: "Aufgaben werden geladen."
  },
  {
    id: "cockpit-today-title",
    className: "is-today",
    title: <>Heute f&auml;llig</>,
    countKey: "today",
    emptyText: <>F&auml;lligkeiten werden geladen.</>
  },
  {
    id: "cockpit-progress-title",
    className: "is-progress",
    title: "In Arbeit",
    countKey: "progress",
    emptyText: "Aktive Arbeiten werden geladen."
  }
];

/**
 * Render the critical-today dashboard panel with the existing runtime hooks.
 */
function CriticalTodayPanel(): ReactNode {
  return (
    <article className="ops-panel app-card critical-today-card">
      <header className="ops-panel-header">
        <div>
          <p className="section-kicker">Heute zuerst</p>
          <h2>Kritisch heute</h2>
          <p className="panel-meta">
            Dringende Aufgaben, St&ouml;rungen und Engp&auml;sse mit direkter Aktion.
          </p>
        </div>
        <a data-dashboard-nav="tasks" hidden href="/tasks">
          Alle Aufgaben
        </a>
      </header>
      <div className="critical-today-list" data-dashboard-critical-today="">
        <div className="empty-state">Kritische Lage wird geladen.</div>
      </div>
    </article>
  );
}

/**
 * Render one static cockpit column for the runtime-managed task board.
 */
function CockpitColumnPanel({ column }: { readonly column: CockpitColumn }): ReactNode {
  return (
    <section className={`cockpit-column ${column.className}`} aria-labelledby={column.id}>
      <h3 id={column.id} className="cockpit-column-title">
        {column.title} <span data-cockpit-count={column.countKey}>0</span>
      </h3>
      <div className="cockpit-task-list" data-cockpit-list={column.countKey}>
        <article className="cockpit-task-card is-empty">
          <p>{column.emptyText}</p>
        </article>
      </div>
    </section>
  );
}

/**
 * Render the dashboard task-priority panel with existing Kanban hooks.
 */
function TaskPriorityPanel(): ReactNode {
  return (
    <article className="ops-panel app-card">
      <header className="ops-panel-header">
        <div>
          <p className="section-kicker">Priorit&auml;t</p>
          <h2>Offene Tasks</h2>
          <p className="panel-meta">
            Nach Dringlichkeit, F&auml;lligkeit und Status gruppiert.
          </p>
        </div>
        <a data-dashboard-nav="tasks" hidden href="/tasks">
          Kanban &ouml;ffnen
        </a>
      </header>
      <div className="priority-task-list" data-dashboard-priority-list="" />
      <div className="cockpit-board compact-cockpit-board" data-dashboard-task-board="">
        {COCKPIT_COLUMNS.map((column) => (
          <CockpitColumnPanel key={column.countKey} column={column} />
        ))}
      </div>
    </article>
  );
}

/**
 * Render the dashboard task overview panels as React-owned markup.
 */
export function DashboardTaskOverview(): ReactNode {
  return (
    <>
      <CriticalTodayPanel />
      <TaskPriorityPanel />
    </>
  );
}

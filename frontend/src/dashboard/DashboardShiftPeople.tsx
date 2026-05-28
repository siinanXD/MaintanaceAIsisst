import { type ReactNode } from "react";

/**
 * Render the shift handover panel with the existing dashboard runtime hooks.
 */
function ShiftHandoverPanel(): ReactNode {
  return (
    <article className="ops-panel app-card">
      <header className="ops-panel-header">
        <div>
          <p className="section-kicker">Schicht</p>
          <h2>Schicht&uuml;bergaben</h2>
          <p className="panel-meta">Aktuelle Schichtbelegung und letzte &Uuml;bergaben.</p>
        </div>
        <a data-feature-key="handover" data-dashboard-nav="shiftplans" hidden href="/handover">
          Zur &Uuml;bergabe
        </a>
      </header>
      <p className="sr-only" data-dashboard-calendar-message="">
        Schichtplan heute
      </p>
      <select className="select select-bordered" data-dashboard-calendar-employee="" hidden>
        <option value="">Mein Kalender</option>
      </select>
      <div
        className="shift-timeline"
        aria-label="Schichtbelegung heute"
        data-dashboard-shift-timeline=""
      >
        <div className="timeline-axis">
          <span>00</span>
          <span>04</span>
          <span>08</span>
          <span>12</span>
          <span>16</span>
          <span>20</span>
          <span>24</span>
        </div>
      </div>
      <div className="dashboard-calendar-data" data-dashboard-shift-calendar="" hidden />
      <div className="handover-card-list" data-dashboard-handover-list="">
        <div className="empty-state">&Uuml;bergaben werden geladen.</div>
      </div>
    </article>
  );
}

/**
 * Render the people hint panel with the existing dashboard runtime hooks.
 */
function PeopleHintsPanel(): ReactNode {
  return (
    <article className="ops-panel app-card">
      <header className="ops-panel-header">
        <div>
          <p className="section-kicker">Personal</p>
          <h2>Urlaub &amp; Personalhinweise</h2>
          <p className="panel-meta">
            Team&uuml;bersicht, offene Antr&auml;ge und Schichtverf&uuml;gbarkeit.
          </p>
        </div>
        <a data-dashboard-nav="employees" hidden href="/employees">
          Mitarbeiter
        </a>
      </header>
      <div className="people-hint-list" data-dashboard-people-hints="">
        <div className="empty-state">Personalhinweise werden geladen.</div>
      </div>
      <div
        className="employee-table control-center-employee-table"
        role="table"
        aria-label="Mitarbeiter heute"
        data-dashboard-employee-overview=""
      >
        <div className="employee-row is-head" role="row">
          <span role="columnheader">Mitarbeiter</span>
          <span role="columnheader">Rolle</span>
          <span role="columnheader">Schicht</span>
          <span role="columnheader">Status</span>
        </div>
      </div>
    </article>
  );
}

/**
 * Render dashboard shift and people panels as React-owned markup.
 */
export function DashboardShiftPeople(): ReactNode {
  return (
    <>
      <ShiftHandoverPanel />
      <PeopleHintsPanel />
    </>
  );
}

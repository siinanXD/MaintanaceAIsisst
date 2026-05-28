import { type ReactNode } from "react";

import { type DashboardPayload, type DashboardShiftCalendar } from "./dashboardApi";
import { type DashboardViewState } from "./dashboardModel";
import {
  absentEmployees,
  employeeInitials,
  employeeRole,
  employeeStatus,
  handoverMeta,
  handoverTitle,
  peopleText,
  relevantVacations
} from "./dashboardPeopleModel";
import {
  currentTimelinePercent,
  dashboardShiftRows,
  shiftCalendarMessage,
  timelineBarText,
  timelineGeometry
} from "./dashboardShiftModel";

type DashboardShiftPeopleProps = {
  readonly dashboardState: DashboardViewState;
  readonly isShiftCalendarLoading: boolean;
  readonly onShiftEmployeeChange: (employeeId: string) => void;
  readonly selectedShiftEmployeeId: string;
  readonly shiftCalendar: DashboardShiftCalendar | null;
};

type DashboardPeopleOnlyProps = {
  readonly dashboardState: DashboardViewState;
};

/**
 * Render a compact empty state.
 */
function EmptyState({ children }: { readonly children: ReactNode }): ReactNode {
  return <div className="empty-state">{children}</div>;
}

/**
 * Render the employee select for the React-owned dashboard shift timeline.
 */
function ShiftEmployeeFilter({
  dashboardState,
  onShiftEmployeeChange,
  selectedShiftEmployeeId
}: DashboardShiftPeopleProps): ReactNode {
  return (
    <select
      className="select select-bordered"
      data-dashboard-calendar-employee=""
      hidden={!dashboardState.data.employees.length}
      value={selectedShiftEmployeeId}
      onChange={(event) => onShiftEmployeeChange(event.target.value)}
    >
      <option value="">Alle Mitarbeiter</option>
      {dashboardState.data.employees.map((employee) => (
        <option key={String(employee.id ?? employee.name)} value={String(employee.id ?? "")}>
          {peopleText(employee, "name", "Mitarbeiter")}
        </option>
      ))}
    </select>
  );
}

/**
 * Render one row in the React-owned dashboard shift timeline.
 */
function ShiftTimelineRow({ row }: { readonly row: ReturnType<typeof dashboardShiftRows>[number] }): ReactNode {
  const start = peopleText(row.entry, "start_time", row.fallbackStart);
  const end = peopleText(row.entry, "end_time", row.fallbackEnd);
  const geometry = timelineGeometry(start, end);

  return (
    <div className={`timeline-row ${row.active ? "is-active" : ""}`.trim()}>
      <strong>
        {row.label}
        <small>{start} - {end}</small>
      </strong>
      <span className="timeline-track">
        <span className={`timeline-bar ${row.variant}`} style={{ left: geometry.left, width: geometry.width }}>
          {timelineBarText(row.entry)}
        </span>
      </span>
    </div>
  );
}

/**
 * Render the dashboard shift timeline from React state.
 */
function ShiftTimeline({
  isShiftCalendarLoading,
  shiftCalendar
}: DashboardShiftPeopleProps): ReactNode {
  const rows = dashboardShiftRows(shiftCalendar);

  return (
    <div className="shift-timeline" aria-label="Schichtbelegung heute" data-dashboard-shift-timeline="">
      <div className="timeline-axis">
        <span>00</span>
        <span>04</span>
        <span>08</span>
        <span>12</span>
        <span>16</span>
        <span>20</span>
        <span>24</span>
      </div>
      {rows.map((row) => (
        <ShiftTimelineRow key={row.shiftKey} row={row} />
      ))}
      <div className="now-marker-track">
        <div className="now-marker" style={{ left: currentTimelinePercent() }} title="Jetzt" />
      </div>
      {shiftCalendar?.message || isShiftCalendarLoading ? (
        <div className="timeline-status">{shiftCalendarMessage(shiftCalendar, isShiftCalendarLoading)}</div>
      ) : null}
    </div>
  );
}

/**
 * Render one handover card in the dashboard shift panel.
 */
function HandoverCard({ handover }: { readonly handover: DashboardPayload }): ReactNode {
  const completed = peopleText(handover, "status") === "completed";

  return (
    <a className={`handover-card ${completed ? "is-good" : "is-warning"}`} href="/handover">
      <strong>{handoverTitle(handover)}</strong>
      <small>{handoverMeta(handover)}</small>
      <span className={`badge badge-status ${completed ? "is-done" : "is-progress"}`}>
        {completed ? "Bestätigt" : "Offen"}
      </span>
    </a>
  );
}

/**
 * Render the shift handover panel with React-owned handover cards.
 */
function ShiftHandoverPanel(props: DashboardShiftPeopleProps): ReactNode {
  const { dashboardState, isShiftCalendarLoading, shiftCalendar } = props;
  const handovers = dashboardState.data.handovers;

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
        {shiftCalendarMessage(shiftCalendar, isShiftCalendarLoading)}
      </p>
      <ShiftEmployeeFilter {...props} />
      <ShiftTimeline {...props} />
      <div className="dashboard-calendar-data" data-dashboard-shift-calendar="" hidden>
        {JSON.stringify(shiftCalendar ?? { entries: [] })}
      </div>
      <div className="handover-card-list" data-dashboard-handover-list="">
        {dashboardState.isLoading ? <EmptyState>Übergaben werden geladen.</EmptyState> : null}
        {!dashboardState.isLoading && handovers.length === 0 ? (
          <EmptyState>Heute gibt es noch keine gespeicherte Schichtübergabe.</EmptyState>
        ) : null}
        {handovers.slice(0, 4).map((handover) => (
          <HandoverCard key={String(handover.id ?? `${handover.shift_type}-${handover.department}`)} handover={handover} />
        ))}
      </div>
    </article>
  );
}

/**
 * Render one people hint card.
 */
function PeopleHintCard({
  actionLabel,
  href,
  marker,
  meta,
  signal,
  title
}: {
  readonly actionLabel: string;
  readonly href: string;
  readonly marker: string;
  readonly meta: string;
  readonly signal: "good" | "warning";
  readonly title: string;
}): ReactNode {
  return (
    <a className={`control-center-item ${signal === "good" ? "is-good" : "is-warning"}`} href={href}>
      <span className="control-center-item-marker">{marker}</span>
      <div>
        <strong>{title}</strong>
        <small>{meta}</small>
      </div>
      <span className="control-center-item-action">{actionLabel}</span>
    </a>
  );
}

/**
 * Render the people hint list from React dashboard state.
 */
function PeopleHints({ dashboardState }: DashboardPeopleOnlyProps): ReactNode {
  const vacations = relevantVacations(dashboardState.data.vacations);
  const absent = absentEmployees(dashboardState.data.employees);
  const employees = dashboardState.data.employees;

  return (
    <div className="people-hint-list" data-dashboard-people-hints="">
      {dashboardState.isLoading ? <EmptyState>Personalhinweise werden geladen.</EmptyState> : null}
      {!dashboardState.isLoading && vacations.length ? (
        <PeopleHintCard
          actionLabel="Urlaub"
          href="/vacations"
          marker="UR"
          meta="Genehmigen oder ablehnen"
          signal="warning"
          title={`${vacations.length} offene Urlaubsanträge`}
        />
      ) : null}
      {!dashboardState.isLoading && absent.length ? (
        <PeopleHintCard
          actionLabel="Team"
          href="/employees"
          marker="AB"
          meta={absent.slice(0, 2).map((employee) => peopleText(employee, "name")).join(", ")}
          signal="warning"
          title={`${absent.length} abwesend markiert`}
        />
      ) : null}
      {!dashboardState.isLoading && employees.length > 0 && vacations.length === 0 && absent.length === 0 ? (
        <PeopleHintCard
          actionLabel="Personal"
          href="/employees"
          marker="PE"
          meta="Keine offenen Personalwarnungen"
          signal="good"
          title={`${employees.length} Mitarbeitende sichtbar`}
        />
      ) : null}
      {!dashboardState.isLoading && employees.length === 0 && vacations.length === 0 ? (
        <EmptyState>Keine Personalhinweise im aktuellen Zugriff.</EmptyState>
      ) : null}
    </div>
  );
}

/**
 * Render one employee overview row.
 */
function EmployeeRow({ employee }: { readonly employee: DashboardPayload }): ReactNode {
  const status = employeeStatus(employee);

  return (
    <div className="employee-row" role="row">
      <span>
        <span className="mini-avatar">{employeeInitials(employee.name)}</span>
        {peopleText(employee, "name", "Unbekannt")}
      </span>
      <span>{employeeRole(employee)}</span>
      <span>{peopleText(employee, "current_shift", peopleText(employee, "shift_model", "-"))}</span>
      <strong className={status !== "Anwesend" ? "is-warning" : ""}>{status}</strong>
    </div>
  );
}

/**
 * Render the employee overview table from React dashboard state.
 */
function EmployeeOverview({ dashboardState }: DashboardPeopleOnlyProps): ReactNode {
  const employees = dashboardState.data.employees;

  return (
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
      {dashboardState.isLoading ? <EmptyState>Mitarbeiterdaten werden geladen.</EmptyState> : null}
      {!dashboardState.isLoading && employees.length === 0 ? (
        <div className="guided-empty-state">Keine Mitarbeiterdaten verfügbar.</div>
      ) : null}
      {employees.slice(0, 5).map((employee) => (
        <EmployeeRow key={String(employee.id ?? employee.name)} employee={employee} />
      ))}
    </div>
  );
}

/**
 * Render the people hint panel with React-owned people data.
 */
function PeopleHintsPanel({ dashboardState }: DashboardShiftPeopleProps): ReactNode {
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
      <PeopleHints dashboardState={dashboardState} />
      <EmployeeOverview dashboardState={dashboardState} />
    </article>
  );
}

/**
 * Render dashboard shift and people panels as React-owned markup.
 */
export function DashboardShiftPeople(props: DashboardShiftPeopleProps): ReactNode {
  return (
    <>
      <ShiftHandoverPanel {...props} />
      <PeopleHintsPanel {...props} />
    </>
  );
}

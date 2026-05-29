import { type ReactNode } from "react";

import { type DashboardPayload } from "./dashboardApi";
import { EmptyState } from "./DashboardEmptyState";
import { handoverMeta, handoverTitle, peopleText } from "./dashboardPeopleModel";
import {
  currentTimelinePercent,
  dashboardShiftRows,
  shiftCalendarMessage,
  timelineBarText,
  timelineGeometry
} from "./dashboardShiftModel";
import { type DashboardShiftPeopleProps } from "./DashboardShiftPeopleTypes";

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
export function ShiftHandoverPanel(props: DashboardShiftPeopleProps): ReactNode {
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

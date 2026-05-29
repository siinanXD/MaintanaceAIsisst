import { type ReactNode } from "react";

import { EmptyState } from "./DashboardEmptyState";
import {
  absentEmployees,
  employeeInitials,
  employeeRole,
  employeeStatus,
  peopleText,
  relevantVacations
} from "./dashboardPeopleModel";
import { type DashboardPayload } from "./dashboardApi";
import { type DashboardPeopleOnlyProps, type DashboardShiftPeopleProps } from "./DashboardShiftPeopleTypes";

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
export function PeopleHintsPanel({ dashboardState }: DashboardShiftPeopleProps): ReactNode {
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

import { type ReactNode } from "react";

import { DEPARTMENT_OPTIONS, SHIFT_OPTIONS } from "./HandoverOptions";
import {
  handoverDateLabel,
  handoverDateTimeLabel,
  machineName,
  machineStatusLabel,
  productionStatusLabel,
  shiftLabel,
} from "./handoverUtils";
import type { HandoverFilters, HandoverMessage, HandoverRecord, Machine } from "./HandoverTypes";

type HandoverListProps = {
  readonly filters: HandoverFilters;
  readonly handovers: readonly HandoverRecord[];
  readonly loadedCount: number;
  readonly machines: readonly Machine[];
  readonly message: HandoverMessage;
  readonly onComplete: (handover: HandoverRecord) => void;
  readonly onEdit: (handover: HandoverRecord) => void;
  readonly onFilter: () => void;
  readonly onFilterChange: (filters: HandoverFilters) => void;
  readonly onResetFilters: () => void;
  readonly writable: boolean;
};

/**
 * Render a filter field wrapper.
 */
function FilterField({
  children,
  htmlFor,
  label,
}: {
  readonly children: ReactNode;
  readonly htmlFor: string;
  readonly label: string;
}): ReactNode {
  return (
    <label className="handover-filter-field" htmlFor={htmlFor}>
      <span>{label}</span>
      {children}
    </label>
  );
}

/**
 * Render one compact handover metric.
 */
function Metric({ label, value }: { readonly label: string; readonly value: ReactNode }): ReactNode {
  return (
    <span>
      <small>{label}</small>
      <strong>{value || "-"}</strong>
    </span>
  );
}

/**
 * Render one optional handover detail block.
 */
function DetailBlock({
  label,
  value,
  variant,
}: {
  readonly label: string;
  readonly value?: string;
  readonly variant: string;
}): ReactNode {
  if (!value) return null;
  return (
    <section className={`handover-block ${variant}`}>
      <span>{label}</span>
      <p>{value}</p>
    </section>
  );
}

/**
 * Render the list filter controls.
 */
function HandoverFilters({
  filters,
  machines,
  onFilter,
  onFilterChange,
  onResetFilters,
}: Pick<HandoverListProps, "filters" | "machines" | "onFilter" | "onFilterChange" | "onResetFilters">): ReactNode {
  return (
    <section className="handover-filter-bar" aria-label="Schichtübergaben filtern">
      <FilterField htmlFor="filter-search" label="Suche">
        <input
          className="input input-bordered input-sm"
          id="filter-search"
          data-handover-search=""
          placeholder="Maschine, Ursache, Folgeaufgabe"
          value={filters.search}
          onChange={(event) => onFilterChange({ ...filters, search: event.currentTarget.value })}
        />
      </FilterField>
      <FilterField htmlFor="filter-dept" label="Bereich">
        <select
          className="select select-bordered select-sm"
          id="filter-dept"
          value={filters.department}
          onChange={(event) => onFilterChange({ ...filters, department: event.currentTarget.value })}
        >
          <option value="">Alle Bereiche</option>
          {DEPARTMENT_OPTIONS.map((department) => (
            <option key={department.value} value={department.value}>
              {department.label}
            </option>
          ))}
        </select>
      </FilterField>
      <FilterField htmlFor="filter-date" label="Datum">
        <input
          className="input input-bordered input-sm"
          type="date"
          id="filter-date"
          value={filters.date}
          onChange={(event) => onFilterChange({ ...filters, date: event.currentTarget.value })}
        />
      </FilterField>
      <FilterField htmlFor="filter-shift" label="Schicht">
        <select
          className="select select-bordered select-sm"
          id="filter-shift"
          value={filters.shiftType}
          onChange={(event) => onFilterChange({ ...filters, shiftType: event.currentTarget.value })}
        >
          <option value="">Alle Schichten</option>
          {SHIFT_OPTIONS.map((shift) => (
            <option key={shift.value} value={shift.value}>
              {shift.label}
            </option>
          ))}
        </select>
      </FilterField>
      <FilterField htmlFor="filter-status" label="Status">
        <select
          className="select select-bordered select-sm"
          id="filter-status"
          value={filters.status}
          onChange={(event) => onFilterChange({ ...filters, status: event.currentTarget.value })}
        >
          <option value="">Alle</option>
          <option value="open">Offen</option>
          <option value="completed">Bestätigt</option>
        </select>
      </FilterField>
      <FilterField htmlFor="filter-machine" label="Maschine">
        <select
          className="select select-bordered select-sm"
          id="filter-machine"
          data-ho-filter-machine=""
          value={filters.machineId}
          onChange={(event) => onFilterChange({ ...filters, machineId: event.currentTarget.value })}
        >
          <option value="">Alle Maschinen</option>
          {machines.map((machine) => (
            <option key={machine.id} value={machine.id}>
              {machine.name}
            </option>
          ))}
        </select>
      </FilterField>
      <button className="btn btn-outline btn-sm" id="ho-filter-btn" type="button" onClick={onFilter}>
        Filtern
      </button>
      <button className="btn btn-ghost btn-sm" id="ho-filter-reset" type="button" onClick={onResetFilters}>
        Zurücksetzen
      </button>
    </section>
  );
}

/**
 * Render one handover record card.
 */
function HandoverCard({
  handover,
  onComplete,
  onEdit,
  writable,
}: {
  readonly handover: HandoverRecord;
  readonly onComplete: (handover: HandoverRecord) => void;
  readonly onEdit: (handover: HandoverRecord) => void;
  readonly writable: boolean;
}): ReactNode {
  const completed = handover.status === "completed";
  const critical = Boolean(handover.safety_notes || handover.machine_status === "fault" || handover.production_status === "stopped");
  const cardClassName = [
    "handover-record-card",
    completed ? "is-completed" : "is-open",
    critical ? "is-critical" : "",
  ].filter(Boolean).join(" ");

  return (
    <article className={cardClassName} data-handover-card={handover.id}>
      <header className="handover-record-header">
        <div>
          <h3>{handoverDateLabel(handover.shift_date)} · {shiftLabel(handover.shift_type)}</h3>
          <p>
            {handover.department || "Bereich offen"}
            {handover.area ? ` · ${handover.area}` : ""}
            {machineName(handover) ? ` · ${machineName(handover)}` : ""}
          </p>
        </div>
        <div className="handover-record-badges">
          <span className={`badge status-badge ${completed ? "is-done" : "is-open"}`}>
            {completed ? "Bestätigt" : "Offen"}
          </span>
          {handover.problem_category ? (
            <span className="badge priority-badge is-normal">{handover.problem_category}</span>
          ) : null}
        </div>
      </header>
      <div className="handover-shift-flow" aria-label="Schichtfolge">
        <Metric label="Vorherige Schicht" value={shiftLabel(handover.previous_shift)} />
        <Metric label="Aktuelle Schicht" value={shiftLabel(handover.shift_type)} />
        <Metric label="Nächste Schicht" value={shiftLabel(handover.next_shift)} />
      </div>
      <div className="handover-record-metrics">
        <Metric label="Produktion" value={productionStatusLabel(handover.production_status)} />
        <Metric label="Maschine" value={machineStatusLabel(handover.machine_status)} />
        <Metric label="Dauer" value={`${Number(handover.duration_minutes || 0)} min`} />
        <Metric label="Verantwortlich" value={handover.responsible_employee || handover.handed_over_by || "-"} />
      </div>
      <div className="handover-record-blocks">
        <DetailBlock label="Schichtlage" value={handover.content} variant="is-status" />
        <DetailBlock label="Maschinenhinweis" value={handover.machine_notes} variant="is-machine" />
        <DetailBlock label="Ursache" value={handover.cause} variant="is-cause" />
        <DetailBlock label="Maßnahme" value={handover.action_taken} variant="is-action" />
        <DetailBlock label="Sicherheit" value={handover.safety_notes} variant="is-safety" />
        <DetailBlock label="Material / Ersatzteile" value={handover.material_notes} variant="is-material" />
        <DetailBlock label="Offene Tasks" value={handover.open_tasks} variant="is-open-items" />
        <DetailBlock label="Folgeaufgabe" value={handover.follow_up_task} variant="is-open-items" />
        <DetailBlock label="Nächste Schicht" value={handover.next_notes} variant="is-next" />
      </div>
      <footer className="handover-record-footer">
        <span>
          {handover.handed_over_at
            ? `Bestätigt am ${handoverDateTimeLabel(handover.handed_over_at)}`
            : "Noch nicht bestätigt"}
        </span>
        <div className="toolbar">
          {!completed && writable ? (
            <button className="btn btn-outline btn-sm" type="button" data-edit={handover.id} onClick={() => onEdit(handover)}>
              Bearbeiten
            </button>
          ) : null}
          {!completed && writable ? (
            <button className="btn btn-primary btn-sm" type="button" data-complete={handover.id} onClick={() => onComplete(handover)}>
              Bestätigen
            </button>
          ) : null}
        </div>
      </footer>
    </article>
  );
}

/**
 * Render the handover list and filters.
 */
export function HandoverList({
  filters,
  handovers,
  loadedCount,
  machines,
  message,
  onComplete,
  onEdit,
  onFilter,
  onFilterChange,
  onResetFilters,
  writable,
}: HandoverListProps): ReactNode {
  const summaryText = message.text || `${handovers.length} von ${loadedCount} Übergaben sichtbar`;

  return (
    <article className="handover-list-shell app-card" id="handover-list">
      <header className="handover-list-header">
        <div>
          <h2>Übergabe-Verlauf</h2>
          <p className="panel-meta">Nach Bereich, Datum, Schicht, Maschine oder Status filtern.</p>
        </div>
      </header>
      <HandoverFilters
        filters={filters}
        machines={machines}
        onFilter={onFilter}
        onFilterChange={onFilterChange}
        onResetFilters={onResetFilters}
      />
      <span className={`handover-filter-summary${message.isError ? " is-error" : ""}`} id="ho-filter-summary">
        {summaryText}
      </span>
      <div className="handover-card-grid" id="ho-list-wrap">
        {handovers.length ? (
          handovers.map((handover) => (
            <HandoverCard
              handover={handover}
              key={handover.id}
              onComplete={onComplete}
              onEdit={onEdit}
              writable={writable}
            />
          ))
        ) : (
          <p className="guided-empty-state" id="ho-empty">
            Keine Übergaben gefunden.
          </p>
        )}
      </div>
    </article>
  );
}

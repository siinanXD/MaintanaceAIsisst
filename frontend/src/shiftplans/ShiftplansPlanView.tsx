import { type DragEvent, type ReactNode } from "react";

import type {
  ShiftPlan,
  ShiftplanCalendarSlot,
  ShiftplanChangeLog,
  ShiftplanEntry,
  ShiftplanWarning,
} from "./ShiftplansTypes";
import {
  DAYS_DE,
  SHIFT_LABEL,
  activePlanShifts,
  calendarIndex,
  fairnessRows,
  isUnassignedSlot,
  localIsoDate,
  planDates,
  slotEmployeeName,
  slotMachineName,
} from "./shiftplansUtils";

type ShiftplansPlanViewProps = {
  readonly changelog: readonly ShiftplanChangeLog[];
  readonly currentPlan: ShiftPlan | null;
  readonly isAdmin: boolean;
  readonly onDeleteEntry: (entry: ShiftplanEntry) => void;
  readonly onDeletePlan: () => void;
  readonly onDownload: () => void;
  readonly onEditEntry: (entry: ShiftplanEntry) => void;
  readonly onMoveEntryToEntry: (entryId: number, targetEntryId: number) => void;
  readonly onMoveEntryToSlot: (entryId: number, targetDate: string, targetShift: string) => void;
  readonly onPlanSelect: (index: number) => void;
  readonly onPrint: () => void;
  readonly onPublish: () => void;
  readonly plans: readonly ShiftPlan[];
  readonly selectedPlanIndex: number;
  readonly warnings: readonly ShiftplanWarning[];
  readonly writable: boolean;
};

/**
 * Render the plan action buttons.
 */
function ShiftplansPlanActions({ currentPlan, isAdmin, onDownload, onPrint, onPublish }: Pick<ShiftplansPlanViewProps, "currentPlan" | "isAdmin" | "onDownload" | "onPrint" | "onPublish">): ReactNode {
  const published = currentPlan?.status === "published";
  return (
    <div className="toolbar">
      <button
        className={`btn btn-sm no-print ${published ? "btn-warning" : "btn-success"}`}
        id="sp-publish-btn"
        hidden={!isAdmin || !currentPlan?.id}
        data-hr-only=""
        aria-label="Plan veröffentlichen"
        type="button"
        onClick={onPublish}
      >
        {published ? "↩ Zurück zu Entwurf" : "✓ Veröffentlichen"}
      </button>
      <button className="btn btn-ghost btn-sm no-print" id="sp-print-btn" hidden={!currentPlan} aria-label="Plan drucken" type="button" onClick={onPrint}>
        Drucken
      </button>
      <button className="btn btn-ghost btn-sm no-print" id="sp-csv-btn" hidden={!currentPlan?.id} aria-label="Als Excel exportieren" type="button" onClick={onDownload}>
        XLSX
      </button>
    </div>
  );
}

/**
 * Render the plan selector row.
 */
function ShiftplansSelector({ onPlanSelect, plans, selectedPlanIndex }: Pick<ShiftplansPlanViewProps, "onPlanSelect" | "plans" | "selectedPlanIndex">): ReactNode {
  return (
    <div className="toolbar mb-3 no-print" id="sp-selector" hidden={!plans.length}>
      <label htmlFor="sp-plan-select" className="stat-label">
        Plan:
      </label>
      <select
        className="select select-bordered select-sm"
        id="sp-plan-select"
        aria-label="Schichtplan wählen"
        value={selectedPlanIndex}
        onChange={(event) => onPlanSelect(Number.parseInt(event.currentTarget.value, 10))}
      >
        {plans.map((plan, index) => (
          <option key={`${plan.id || "preview"}-${index}`} value={index}>
            {plan.title}
            {plan.department ? ` [${plan.department}]` : ""}
            {plan.status === "published" ? " ✓" : " [Entwurf]"}
          </option>
        ))}
      </select>
      <span id="sp-status-badge" className={currentStatusBadgeClass(plans[selectedPlanIndex])} hidden={!plans.length}>
        {currentStatusBadgeLabel(plans[selectedPlanIndex])}
      </span>
    </div>
  );
}

/**
 * Return the status badge class for one plan.
 */
function currentStatusBadgeClass(plan: ShiftPlan | undefined): string {
  if (plan?.status === "preview") return "badge badge-info";
  if (plan?.status === "published") return "badge badge-success";
  return "badge badge-ghost";
}

/**
 * Return the status badge label for one plan.
 */
function currentStatusBadgeLabel(plan: ShiftPlan | undefined): string {
  if (plan?.status === "preview") return "Vorschau";
  if (plan?.status === "published") return "✓ Veröffentlicht";
  return "Entwurf";
}

/**
 * Return one rendered shiftplan chip.
 */
function ShiftplanChip({
  canEdit,
  entry,
  onDeleteEntry,
  onEditEntry,
  onMoveEntryToEntry,
}: {
  readonly canEdit: boolean;
  readonly entry: ShiftplanCalendarSlot;
  readonly onDeleteEntry: (entry: ShiftplanEntry) => void;
  readonly onEditEntry: (entry: ShiftplanEntry) => void;
  readonly onMoveEntryToEntry: (entryId: number, targetEntryId: number) => void;
}): ReactNode {
  const machineName = slotMachineName(entry);
  const employeeName = slotEmployeeName(entry);
  const className = `sp-chip${isUnassignedSlot(entry) ? " sp-unassigned" : ""}`;
  const body = (
    <>
      {machineName ? <span className="sp-machine">{machineName}</span> : null}
      <span className="sp-emp">{employeeName}</span>
    </>
  );

  if (!canEdit || isUnassignedSlot(entry)) {
    return <div className={className}>{body}</div>;
  }
  const editableEntry = entry as ShiftplanEntry;

  /**
   * Move a dragged entry onto this existing entry.
   */
  function handleDrop(event: DragEvent<HTMLButtonElement>): void {
    event.preventDefault();
    event.stopPropagation();
    const draggedEntryId = Number.parseInt(event.dataTransfer.getData("entry_id"), 10);
    if (Number.isInteger(draggedEntryId) && draggedEntryId !== editableEntry.id) {
      onMoveEntryToEntry(draggedEntryId, editableEntry.id);
    }
  }

  return (
    <button
      aria-label={`Bearbeiten: ${employeeName}`}
      className={className}
      data-entry-id={editableEntry.id}
      draggable
      type="button"
      onClick={() => onEditEntry(editableEntry)}
      onContextMenu={(event) => {
        event.preventDefault();
        onDeleteEntry(editableEntry);
      }}
      onDragStart={(event) => {
        event.dataTransfer.setData("entry_id", String(editableEntry.id));
        event.dataTransfer.effectAllowed = "move";
      }}
      onDragOver={(event) => {
        event.preventDefault();
        event.stopPropagation();
      }}
      onDrop={handleDrop}
    >
      {body}
    </button>
  );
}

/**
 * Render the calendar grid for the current plan.
 */
function ShiftplansCalendar({
  currentPlan,
  onDeleteEntry,
  onEditEntry,
  onMoveEntryToEntry,
  onMoveEntryToSlot,
  writable,
}: Pick<ShiftplansPlanViewProps, "currentPlan" | "onDeleteEntry" | "onEditEntry" | "onMoveEntryToEntry" | "onMoveEntryToSlot" | "writable">): ReactNode {
  const dates = currentPlan ? planDates(currentPlan) : [];
  const entriesByShift = currentPlan ? calendarIndex(currentPlan) : new Map<string, Map<string, ShiftplanCalendarSlot[]>>();
  const activeShifts = currentPlan ? activePlanShifts(currentPlan) : [];
  const canEdit = Boolean(writable && currentPlan && !currentPlan.is_preview);

  return (
    <div id="sp-table-wrap" data-shiftplan-calendar="" hidden={!currentPlan}>
      <div className="print-only" style={{ marginBottom: "12px" }}>
        <strong id="print-title" style={{ fontSize: "14pt" }}>
          {currentPlan?.title || "Schichtplan"}
        </strong>
        <span id="print-meta" style={{ marginLeft: "16px", fontSize: "10pt", color: "#555" }}>
          {currentPlan ? `Abteilung: ${currentPlan.department || "-"} | ${currentPlan.start_date} | ${currentPlan.days} Tage${currentPlan.status === "published" ? " | ✓ Veröffentlicht" : " | Entwurf"}` : ""}
        </span>
      </div>
      <div className="overflow-x-auto">
        <table id="sp-grid" className="sp-excel-table">
          <caption>Schichtplan-Kalender mit Mitarbeitern, Tagen und Schichten</caption>
          <thead id="sp-thead">
            <tr>
              <th className="sp-col-shift" scope="col">Schicht</th>
              {dates.map((date) => (
                <th className="sp-col-day" key={localIsoDate(date)} scope="col">
                  <span className="sp-dow">{DAYS_DE[date.getDay()]}</span>
                  <br />
                  <span className="sp-date">{String(date.getDate()).padStart(2, "0")}.{String(date.getMonth() + 1).padStart(2, "0")}.</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody id="sp-tbody">
            {!activeShifts.length ? (
              <tr>
                <td className="text-center" colSpan={dates.length + 1} style={{ opacity: 0.5 }}>
                  Keine Einträge im Plan.
                </td>
              </tr>
            ) : activeShifts.map((shiftKey) => (
              <tr key={shiftKey}>
                <th className={`sp-col-shift sp-shift-label sp-shift-${String(shiftKey).toLowerCase()}`} scope="row">
                  {SHIFT_LABEL[String(shiftKey)] || shiftKey}
                </th>
                {dates.map((date) => {
                  const dateString = localIsoDate(date);
                  const dayEntries = entriesByShift.get(String(shiftKey))?.get(dateString) || [];
                  return (
                    <td
                      className={`sp-day-cell sp-cell-${String(shiftKey).toLowerCase()}`}
                      key={`${shiftKey}-${dateString}`}
                      onDragOver={(event) => {
                        if (canEdit) event.preventDefault();
                      }}
                      onDrop={(event) => {
                        if (!canEdit) return;
                        event.preventDefault();
                        const draggedEntryId = Number.parseInt(event.dataTransfer.getData("entry_id"), 10);
                        if (Number.isInteger(draggedEntryId)) onMoveEntryToSlot(draggedEntryId, dateString, String(shiftKey));
                      }}
                    >
                      {dayEntries.length ? dayEntries.map((entry) => (
                        <ShiftplanChip
                          canEdit={canEdit}
                          entry={entry}
                          key={isUnassignedSlot(entry) ? `${entry.shift}-${entry.work_date}-${slotMachineName(entry)}` : entry.id}
                          onDeleteEntry={onDeleteEntry}
                          onEditEntry={onEditEntry}
                          onMoveEntryToEntry={onMoveEntryToEntry}
                        />
                      )) : <span className="sp-empty">-</span>}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="toolbar mt-3 no-print" style={{ gap: "12px", flexWrap: "wrap" }}>
        <span className="badge badge-success badge-outline">F = Frühschicht 06-14</span>
        <span className="badge badge-info badge-outline">S = Spätschicht 14-22</span>
        <span className="badge badge-secondary badge-outline">N = Nachtschicht 22-06</span>
        <span className="badge badge-warning badge-outline">U = Urlaub</span>
        <span className="badge badge-ghost badge-outline">- = Frei</span>
      </div>
    </div>
  );
}

/**
 * Render the fairness statistics panel.
 */
function ShiftplansStats({ currentPlan }: Pick<ShiftplansPlanViewProps, "currentPlan">): ReactNode {
  const rows = currentPlan ? fairnessRows(currentPlan) : [];
  return (
    <details className="mt-5 no-print" id="sp-stats" hidden={!currentPlan}>
      <summary className="stat-label cursor-pointer select-none mb-2">Fairness-Statistik</summary>
      <div className="overflow-x-auto">
        <table className="table table-xs">
          <caption>Fairness-Statistik des aktuellen Schichtplans</caption>
          <thead>
            <tr>
              <th scope="col">Mitarbeiter</th>
              <th scope="col">Früh</th>
              <th scope="col">Spät</th>
              <th scope="col">Nacht</th>
              <th scope="col">Urlaub</th>
              <th scope="col">Stunden</th>
            </tr>
          </thead>
          <tbody id="sp-stats-body">
            {rows.map((row) => (
              <tr key={row.employee.id || row.employee.name}>
                <th scope="row">{row.employee.name || "-"}</th>
                <td>{row.frueh}</td>
                <td>{row.spaet}</td>
                <td>{row.nacht}</td>
                <td>{row.urlaub}</td>
                <td>{row.hours.toFixed(1)}h</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

/**
 * Render warning, changelog, and deletion shells.
 */
function ShiftplansAdminDetails({ changelog, currentPlan, isAdmin, onDeletePlan, warnings }: Pick<ShiftplansPlanViewProps, "changelog" | "currentPlan" | "isAdmin" | "onDeletePlan" | "warnings">): ReactNode {
  return (
    <>
      <details className="mt-4 no-print" id="sp-warnings" hidden={!warnings.length}>
        <summary className="stat-label cursor-pointer select-none mb-2" id="sp-warn-summary">
          Warnungen anzeigen ({warnings.length})
        </summary>
        <ul id="sp-warn-list" className="space-y-1 mt-2" role="list">
          {warnings.map((warning, index) => (
            <li className={`panel-meta ${warning.severity === "critical" ? "text-error" : "text-warning"}`} key={`${warning.message}-${index}`}>
              {warning.severity === "critical" ? "⛔ " : "⚠ "}
              {warning.message}
            </li>
          ))}
        </ul>
      </details>
      <details className="mt-5 no-print" id="sp-changelog" data-hr-only="" hidden={!isAdmin || !currentPlan?.id}>
        <summary className="stat-label cursor-pointer select-none mb-2">Änderungsprotokoll</summary>
        <div className="overflow-x-auto">
          <table className="table table-xs">
            <caption>Änderungsprotokoll des aktuellen Schichtplans</caption>
            <thead>
              <tr>
                <th scope="col">Zeitpunkt</th>
                <th scope="col">Benutzer</th>
                <th scope="col">Aktion</th>
                <th scope="col">Feld</th>
                <th scope="col">Alt</th>
                <th scope="col">Neu</th>
              </tr>
            </thead>
            <tbody id="sp-changelog-body">
              {changelog.map((log, index) => (
                <tr key={`${log.changed_at}-${index}`}>
                  <td>{log.changed_at ? new Date(log.changed_at).toLocaleString("de-DE") : "-"}</td>
                  <td>{log.user || "-"}</td>
                  <td>{log.action || "-"}</td>
                  <td>{log.field_name || "-"}</td>
                  <td>{log.old_value || "-"}</td>
                  <td>{log.new_value || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
      <div className="toolbar mt-5 no-print" id="sp-delete-wrap" data-hr-only="" hidden={!isAdmin || !currentPlan?.id}>
        <button className="btn btn-error btn-sm" id="sp-delete-btn" type="button" onClick={onDeletePlan}>
          Plan löschen
        </button>
      </div>
    </>
  );
}

/**
 * Render the shiftplan view card and all runtime-controlled child containers.
 */
export function ShiftplansPlanView(props: ShiftplansPlanViewProps): ReactNode {
  return (
    <article className="card app-card lg:col-span-12" id="sp-view-card">
      <div className="card-body">
        <div className="panel-header no-print">
          <div>
            <h2 className="panel-title" id="sp-view-title">
              Schichtpläne
            </h2>
            <p className="panel-meta" id="sp-view-meta">
              Zuletzt generierte Pläne
            </p>
          </div>
          <ShiftplansPlanActions currentPlan={props.currentPlan} isAdmin={props.isAdmin} onDownload={props.onDownload} onPrint={props.onPrint} onPublish={props.onPublish} />
        </div>
        <ShiftplansSelector onPlanSelect={props.onPlanSelect} plans={props.plans} selectedPlanIndex={props.selectedPlanIndex} />
        <p className="panel-meta" id="sp-empty-msg" hidden={props.plans.length > 0}>
          Noch keine Schichtpläne vorhanden. Plan generieren um zu starten.
        </p>
        <ShiftplansCalendar
          currentPlan={props.currentPlan}
          onDeleteEntry={props.onDeleteEntry}
          onEditEntry={props.onEditEntry}
          onMoveEntryToEntry={props.onMoveEntryToEntry}
          onMoveEntryToSlot={props.onMoveEntryToSlot}
          writable={props.writable}
        />
        <ShiftplansStats currentPlan={props.currentPlan} />
        <ShiftplansAdminDetails changelog={props.changelog} currentPlan={props.currentPlan} isAdmin={props.isAdmin} onDeletePlan={props.onDeletePlan} warnings={props.warnings} />
      </div>
    </article>
  );
}

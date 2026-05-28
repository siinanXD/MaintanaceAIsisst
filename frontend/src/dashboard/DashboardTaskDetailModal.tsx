import { useEffect, useState, type FormEvent, type ReactNode } from "react";

import { canWriteDashboard } from "../auth/permissions";
import { type DashboardPayload, type DashboardTaskMutation, type DashboardTaskReportPayload } from "./dashboardApi";
import {
  dashboardTaskDetailValue,
  taskDepartmentName,
  taskText
} from "./dashboardTaskModel";

type DashboardTaskDetailModalProps = {
  readonly activeTask: DashboardPayload | null;
  readonly isBusy: boolean;
  readonly message: string;
  readonly onClose: () => void;
  readonly onComplete: (payload: DashboardTaskReportPayload) => void;
  readonly onStart: () => void;
  readonly onUpdate: (payload: DashboardTaskMutation) => void;
};

type ReportState = {
  readonly action: string;
  readonly cause: string;
  readonly generate_report: boolean;
  readonly machine: string;
  readonly result: string;
};

type ReportTextFieldName = Exclude<keyof ReportState, "generate_report">;

type ReportFieldConfig = {
  readonly fieldName: ReportTextFieldName;
  readonly id: string;
  readonly isTextArea: boolean;
  readonly label: string;
};

type EditState = {
  readonly department: string;
  readonly description: string;
  readonly due_date: string;
  readonly priority: string;
  readonly status: string;
  readonly title: string;
};

const REPORT_FIELDS: readonly ReportFieldConfig[] = [
  { id: "report-machine", label: "Maschine", fieldName: "machine", isTextArea: false },
  { id: "report-result", label: "Ergebnis", fieldName: "result", isTextArea: false },
  { id: "report-cause", label: "Ursache", fieldName: "cause", isTextArea: false },
  {
    id: "report-action",
    label: "Maßnahme / Notizen",
    fieldName: "action",
    isTextArea: true
  }
] as const;

const TASK_DETAIL_ROWS = [
  ["Titel", "title"],
  ["Beschreibung", "description"],
  ["Priorität", "priority"],
  ["Status", "status"],
  ["Bereich", "department"],
  ["Ersteller", "creator"],
  ["Erstellt am", "created_at"],
  ["Aktuell bearbeitet von", "current_worker"],
  ["Gestartet am", "started_at"],
  ["Erledigt von", "completed_by_user"],
  ["Erledigt am", "completed_at"]
] as const;

/**
 * Build the initial report state for the controlled completion form.
 */
function initialReportState(): ReportState {
  return {
    action: "",
    cause: "",
    generate_report: false,
    machine: "",
    result: ""
  };
}

/**
 * Build an edit form state from the active task.
 */
function editStateFromTask(task: DashboardPayload | null): EditState {
  return {
    department: taskDepartmentName(task),
    description: taskText(task, "description"),
    due_date: taskText(task, "due_date"),
    priority: taskText(task, "priority", "normal"),
    status: taskText(task, "status", "open"),
    title: taskText(task, "title")
  };
}

/**
 * Render one detail row in the dashboard task modal.
 */
function DetailRow({
  label,
  value
}: {
  readonly label: string;
  readonly value: string;
}): ReactNode {
  return (
    <div className="task-detail-row">
      <span>{label}</span>
      <strong>{value || "-"}</strong>
    </div>
  );
}

/**
 * Render one report input while preserving the dashboard runtime hook.
 */
function ReportField({
  field,
  onChange,
  value
}: {
  readonly field: ReportFieldConfig;
  readonly onChange: (fieldName: ReportTextFieldName, value: string) => void;
  readonly value: string;
}): ReactNode {
  const fieldClassName = field.isTextArea ? "field is-full" : "field";

  return (
    <div className={fieldClassName}>
      <label htmlFor={field.id}>{field.label}</label>
      {field.isTextArea ? (
        <textarea
          className="textarea textarea-bordered"
          id={field.id}
          data-report-field={field.fieldName}
          value={value}
          onChange={(event) => onChange(field.fieldName, event.target.value)}
        />
      ) : (
        <input
          className="input input-bordered"
          id={field.id}
          data-report-field={field.fieldName}
          value={value}
          onChange={(event) => onChange(field.fieldName, event.target.value)}
        />
      )}
    </div>
  );
}

/**
 * Render the editable task detail form.
 */
function TaskEditForm({
  editState,
  isBusy,
  onChange,
  onSubmit
}: {
  readonly editState: EditState;
  readonly isBusy: boolean;
  readonly onChange: (key: keyof EditState, value: string) => void;
  readonly onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}): ReactNode {
  return (
    <form className="task-detail-row md:col-span-2" data-task-edit-form="true" onSubmit={onSubmit}>
      <div className="form-grid">
        <label className="field">
          <span>Titel</span>
          <input
            className="input input-bordered"
            name="title"
            required
            value={editState.title}
            onChange={(event) => onChange("title", event.target.value)}
          />
        </label>
        <label className="field">
          <span>Bereich</span>
          <input
            className="input input-bordered"
            name="department"
            required
            value={editState.department}
            onChange={(event) => onChange("department", event.target.value)}
          />
        </label>
        <label className="field">
          <span>Priorität</span>
          <select
            className="select select-bordered"
            name="priority"
            value={editState.priority}
            onChange={(event) => onChange("priority", event.target.value)}
          >
            <option value="urgent">urgent</option>
            <option value="soon">soon</option>
            <option value="normal">normal</option>
            <option value="low">low</option>
          </select>
        </label>
        <label className="field">
          <span>Status</span>
          <select
            className="select select-bordered"
            name="status"
            value={editState.status}
            onChange={(event) => onChange("status", event.target.value)}
          >
            <option value="open">open</option>
            <option value="in_progress">in_progress</option>
            <option value="done">done</option>
            <option value="cancelled">cancelled</option>
          </select>
        </label>
        <label className="field">
          <span>Fällig am</span>
          <input
            className="input input-bordered"
            name="due_date"
            type="date"
            value={editState.due_date}
            onChange={(event) => onChange("due_date", event.target.value)}
          />
        </label>
        <label className="field is-full">
          <span>Beschreibung</span>
          <textarea
            className="textarea textarea-bordered"
            name="description"
            value={editState.description}
            onChange={(event) => onChange("description", event.target.value)}
          />
        </label>
      </div>
      <div className="toolbar form-actions">
        <button className="btn btn-primary" disabled={isBusy} type="submit">
          Änderungen speichern
        </button>
      </div>
    </form>
  );
}

/**
 * Render the task detail modal controlled by the React dashboard runtime.
 */
export function DashboardTaskDetailModal({
  activeTask,
  isBusy,
  message,
  onClose,
  onComplete,
  onStart,
  onUpdate
}: DashboardTaskDetailModalProps): ReactNode {
  const [reportState, setReportState] = useState<ReportState>(initialReportState);
  const [editState, setEditState] = useState<EditState>(() => editStateFromTask(activeTask));
  const canWriteTasks = canWriteDashboard("tasks");
  const status = taskText(activeTask, "status", "open");

  useEffect(() => {
    setReportState(initialReportState());
    setEditState(editStateFromTask(activeTask));
  }, [activeTask]);

  /**
   * Update one report field.
   */
  function updateReportField(fieldName: ReportTextFieldName, value: string): void {
    setReportState((currentState) => ({ ...currentState, [fieldName]: value }));
  }

  /**
   * Update one edit field.
   */
  function updateEditField(fieldName: keyof EditState, value: string): void {
    setEditState((currentState) => ({ ...currentState, [fieldName]: value }));
  }

  /**
   * Submit the edit form through the React dashboard action handler.
   */
  function submitEditForm(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    onUpdate(editState);
  }

  /**
   * Submit the completion action with optional report data.
   */
  function completeTask(): void {
    onComplete(
      reportState.generate_report
        ? {
            ...reportState,
            notes: reportState.action
          }
        : {}
    );
  }

  return (
    <div className="modal task-detail-modal" data-task-detail-modal="" hidden={!activeTask}>
      <div className="modal-box max-w-4xl">
        <div className="panel-header">
          <div>
            <h2 className="panel-title" id="task-detail-title" data-task-detail-title="">
              {taskText(activeTask, "title", "Aufgabe")}
            </h2>
            <p className="panel-meta" data-task-detail-subtitle="">
              {activeTask ? taskDepartmentName(activeTask) : "Details und Workflow"}
            </p>
          </div>
          <button className="btn btn-ghost btn-sm" type="button" data-task-detail-close="" onClick={onClose}>
            Schließen
          </button>
        </div>
        <div className="task-detail-body" data-task-detail-body="">
          {activeTask
            ? TASK_DETAIL_ROWS.map(([label, key]) => (
                <DetailRow key={key} label={label} value={dashboardTaskDetailValue(activeTask, key)} />
              ))
            : null}
          {activeTask && canWriteTasks ? (
            <TaskEditForm
              editState={editState}
              isBusy={isBusy}
              onChange={updateEditField}
              onSubmit={submitEditForm}
            />
          ) : null}
        </div>
        <div className="form-grid mt-6" data-report-options="">
          <label className="field cursor-pointer">
            <span>Wartungsbericht erzeugen</span>
            <input
              className="checkbox checkbox-primary"
              type="checkbox"
              checked={reportState.generate_report}
              data-report-generate=""
              onChange={(event) =>
                setReportState((currentState) => ({
                  ...currentState,
                  generate_report: event.target.checked
                }))
              }
            />
          </label>
          {REPORT_FIELDS.map((field) => (
            <ReportField
              key={field.id}
              field={field}
          value={String(reportState[field.fieldName] || "")}
              onChange={updateReportField}
            />
          ))}
        </div>
        <div className="toolbar form-actions">
          <button
            className="btn btn-primary"
            disabled={isBusy || !canWriteTasks || status !== "open"}
            type="button"
            data-task-start-button=""
            onClick={onStart}
          >
            Aufgabe starten
          </button>
          <button
            className="btn btn-success text-white"
            disabled={isBusy || !canWriteTasks || status === "done" || status === "cancelled"}
            type="button"
            data-task-complete-button=""
            onClick={completeTask}
          >
            Aufgabe abschließen
          </button>
          <span className="panel-meta" data-task-detail-message="" role="status" aria-live="polite">
            {message}
          </span>
        </div>
      </div>
    </div>
  );
}

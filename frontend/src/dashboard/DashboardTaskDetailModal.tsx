import { type ReactNode } from "react";

const REPORT_FIELDS = [
  { id: "report-machine", label: "Maschine", fieldName: "machine", isTextArea: false },
  { id: "report-result", label: "Ergebnis", fieldName: "result", isTextArea: false },
  { id: "report-cause", label: "Ursache", fieldName: "cause", isTextArea: false },
  {
    id: "report-action",
    label: "Maßnahme / Notizen",
    fieldName: "action",
    isTextArea: true,
  },
] as const;

/**
 * Render one report input while preserving the dashboard runtime hook.
 */
function ReportField({
  fieldName,
  id,
  isTextArea,
  label,
}: (typeof REPORT_FIELDS)[number]): ReactNode {
  const fieldClassName = isTextArea ? "field is-full" : "field";

  return (
    <div className={fieldClassName}>
      <label htmlFor={id}>{label}</label>
      {isTextArea ? (
        <textarea className="textarea textarea-bordered" id={id} data-report-field={fieldName} />
      ) : (
        <input className="input input-bordered" id={id} data-report-field={fieldName} />
      )}
    </div>
  );
}

/**
 * Render the hidden task detail modal controlled by the existing dashboard runtime.
 */
export function DashboardTaskDetailModal(): ReactNode {
  return (
    <div className="modal task-detail-modal" data-task-detail-modal="" hidden>
      <div className="modal-box max-w-4xl">
        <div className="panel-header">
          <div>
            <h2 className="panel-title" id="task-detail-title" data-task-detail-title="">
              Aufgabe
            </h2>
            <p className="panel-meta" data-task-detail-subtitle="">
              Details und Workflow
            </p>
          </div>
          <button className="btn btn-ghost btn-sm" type="button" data-task-detail-close="">
            Schließen
          </button>
        </div>
        <div className="task-detail-body" data-task-detail-body="" />
        <div className="form-grid mt-6" data-report-options="">
          <label className="field cursor-pointer">
            <span>Wartungsbericht erzeugen</span>
            <input className="checkbox checkbox-primary" type="checkbox" data-report-generate="" />
          </label>
          {REPORT_FIELDS.map((field) => (
            <ReportField key={field.id} {...field} />
          ))}
        </div>
        <div className="toolbar form-actions">
          <button className="btn btn-primary" type="button" data-task-start-button="">
            Aufgabe starten
          </button>
          <button className="btn btn-success text-white" type="button" data-task-complete-button="">
            Aufgabe abschließen
          </button>
          <span
            className="panel-meta"
            data-task-detail-message=""
            role="status"
            aria-live="polite"
          />
        </div>
      </div>
    </div>
  );
}

import { useState, type FormEvent, type ReactNode } from "react";

import { createEmployee } from "../employeeApi";
import type { EmployeeDraft, MessageState } from "../employeeTypes";
import { EMPTY_EMPLOYEE_DRAFT, employeeErrorMessage } from "../employeeUtils";
import { EmployeeFormFields } from "./EmployeeFormFields";

type EmployeeCreatePanelProps = {
  readonly hidden: boolean;
  readonly onCreated: () => Promise<void>;
};

/**
 * Render the employee creation form.
 */
export function EmployeeCreatePanel({ hidden, onCreated }: EmployeeCreatePanelProps): ReactNode {
  const [draft, setDraft] = useState<EmployeeDraft>({ ...EMPTY_EMPLOYEE_DRAFT });
  const [message, setMessage] = useState<MessageState>({ text: "", error: false });

  /**
   * Save one employee.
   */
  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setMessage({ text: "Mitarbeiter wird gespeichert...", error: false });
    try {
      await createEmployee(draft);
      setDraft({ ...EMPTY_EMPLOYEE_DRAFT });
      await onCreated();
      setMessage({ text: "Mitarbeiter gespeichert.", error: false });
    } catch (error) {
      setMessage({ text: employeeErrorMessage(error), error: true });
    }
  }

  return (
    <details className="card app-card mobile-action-section lg:col-span-12" data-mobile-collapsible data-permission-write="employees" hidden={hidden} open>
      <summary className="mobile-action-summary">
        <span>
          <span className="mobile-action-title">Mitarbeiter anlegen</span>
          <span className="mobile-action-meta">Stammdaten und Qualifikationen erfassen</span>
        </span>
      </summary>
      <form data-employee-form onSubmit={handleSubmit}>
        <div className="card-body">
          <div className="panel-header">
            <div>
              <h2 className="panel-title">Mitarbeiter anlegen</h2>
              <p className="panel-meta">Personalnummer, Stammdaten, Schicht, Team, Qualifikationen und Lieblingsmaschine</p>
            </div>
          </div>
          <EmployeeFormFields draft={draft} onDraftChange={setDraft} />
          <div className="toolbar form-actions">
            <button className="btn btn-primary" type="submit">Mitarbeiter speichern</button>
            <span className={`panel-meta${message.error ? " is-error" : ""}`} data-employee-message>{message.text}</span>
          </div>
        </div>
      </form>
    </details>
  );
}

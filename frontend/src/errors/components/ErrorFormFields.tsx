import type { ChangeEvent, ReactNode } from "react";

import type { Department, ErrorDraft } from "../errorTypes";
import { ERROR_CATEGORIES } from "../errorUtils";

type ErrorFormFieldsProps = {
  readonly departments: readonly Department[];
  readonly draft: ErrorDraft;
  readonly idPrefix: string;
  readonly onDraftChange: (draft: ErrorDraft) => void;
};

/**
 * Return the selected string value from a form field event.
 */
function fieldValue(event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>): string {
  return event.currentTarget.value;
}

/**
 * Render shared create/edit error fields.
 */
export function ErrorFormFields({ departments, draft, idPrefix, onDraftChange }: ErrorFormFieldsProps): ReactNode {
  /**
   * Update one field in the controlled error draft.
   */
  function updateField(field: keyof ErrorDraft, value: string): void {
    onDraftChange({ ...draft, [field]: value });
  }

  return (
    <div className="form-grid">
      <div className="field">
        <label htmlFor={`${idPrefix}-department`}>Bereich</label>
        <select className="select select-bordered" id={`${idPrefix}-department`} name="department" value={draft.department} onChange={(event) => updateField("department", fieldValue(event))}>
          <option value="">Bereich wählen</option>
          {departments.map((department) => <option key={department.name} value={department.name}>{department.name}</option>)}
        </select>
      </div>
      <div className="field">
        <label htmlFor={`${idPrefix}-machine`}>Maschine</label>
        <input className="input input-bordered" id={`${idPrefix}-machine`} name="machine" required value={draft.machine} onChange={(event) => updateField("machine", fieldValue(event))} />
      </div>
      <div className="field">
        <label htmlFor={`${idPrefix}-code`}>Fehlercode</label>
        <input className="input input-bordered" id={`${idPrefix}-code`} name="error_code" placeholder="E104" required value={draft.error_code} onChange={(event) => updateField("error_code", fieldValue(event))} />
      </div>
      <div className="field">
        <label htmlFor={`${idPrefix}-status`}>Status</label>
        <select className="select select-bordered" id={`${idPrefix}-status`} name="status" value={draft.status} onChange={(event) => updateField("status", fieldValue(event))}>
          <option value="open">Offen</option>
          <option value="in_progress">In Bearbeitung</option>
          <option value="closed">Geschlossen</option>
        </select>
      </div>
      <div className="field">
        <label htmlFor={`${idPrefix}-severity`}>Schweregrad</label>
        <select className="select select-bordered" id={`${idPrefix}-severity`} name="severity" value={draft.severity} onChange={(event) => updateField("severity", fieldValue(event))}>
          <option value="critical">Kritisch</option>
          <option value="high">Hoch</option>
          <option value="medium">Mittel</option>
          <option value="low">Niedrig</option>
        </select>
      </div>
      <div className="field">
        <label htmlFor={`${idPrefix}-category`}>Kategorie</label>
        <select className="select select-bordered" id={`${idPrefix}-category`} name="cause_category" value={draft.cause_category} onChange={(event) => updateField("cause_category", fieldValue(event))}>
          <option value="">Noch offen</option>
          {ERROR_CATEGORIES.map((category) => <option key={category} value={category}>{category}</option>)}
        </select>
      </div>
      <div className="field is-full">
        <label htmlFor={`${idPrefix}-title`}>Kurzbeschreibung</label>
        <input className="input input-bordered" id={`${idPrefix}-title`} name="title" required value={draft.title} onChange={(event) => updateField("title", fieldValue(event))} />
      </div>
      <div className="field is-full">
        <label htmlFor={`${idPrefix}-symptoms`}>Symptome</label>
        <textarea className="textarea textarea-bordered" id={`${idPrefix}-symptoms`} name="symptoms" placeholder="Was war sichtbar, hörbar oder messbar?" value={draft.symptoms} onChange={(event) => updateField("symptoms", fieldValue(event))} />
      </div>
      <div className="field">
        <label htmlFor={`${idPrefix}-causes`}>Ursache</label>
        <textarea className="textarea textarea-bordered" id={`${idPrefix}-causes`} name="possible_causes" value={draft.possible_causes} onChange={(event) => updateField("possible_causes", fieldValue(event))} />
      </div>
      <div className="field">
        <label htmlFor={`${idPrefix}-solution`}>Lösung</label>
        <textarea className="textarea textarea-bordered" id={`${idPrefix}-solution`} name="solution" value={draft.solution} onChange={(event) => updateField("solution", fieldValue(event))} />
      </div>
      <div className="field is-full">
        <label htmlFor={`${idPrefix}-impact`}>Auswirkung auf Produktion</label>
        <input className="input input-bordered" id={`${idPrefix}-impact`} name="impact" placeholder="z. B. Linie 2 stand, Ausschuss erhöht, Taktzeit reduziert" value={draft.impact} onChange={(event) => updateField("impact", fieldValue(event))} />
      </div>
      <div className="field">
        <label htmlFor={`${idPrefix}-downtime`}>Stillstandszeit in Minuten</label>
        <input className="input input-bordered" id={`${idPrefix}-downtime`} min="0" name="downtime_minutes" step="1" type="number" value={draft.downtime_minutes} onChange={(event) => updateField("downtime_minutes", fieldValue(event))} />
      </div>
      <div className="field">
        <label htmlFor={`${idPrefix}-production-loss`}>Produktionsverlust in Minuten</label>
        <input className="input input-bordered" id={`${idPrefix}-production-loss`} min="0" name="production_loss_minutes" step="1" type="number" value={draft.production_loss_minutes} onChange={(event) => updateField("production_loss_minutes", fieldValue(event))} />
      </div>
      <div className="field">
        <label htmlFor={`${idPrefix}-repeat-count`}>Wiederholungen</label>
        <input className="input input-bordered" id={`${idPrefix}-repeat-count`} min="0" name="repeat_count" step="1" type="number" value={draft.repeat_count} onChange={(event) => updateField("repeat_count", fieldValue(event))} />
      </div>
    </div>
  );
}

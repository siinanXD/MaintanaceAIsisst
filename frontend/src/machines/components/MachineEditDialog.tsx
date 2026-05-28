import { useEffect, useRef, useState, type ReactNode } from "react";

import { updateMachine } from "../machineApi";
import type { Machine, MachineDraft, MessageState } from "../machineTypes";
import { draftFromMachine, machineErrorMessage } from "../machineUtils";

type MachineEditDialogProps = {
  readonly machine: Machine | null;
  readonly onClose: () => void;
  readonly onSaved: () => Promise<void>;
};

/**
 * Render the machine edit modal.
 */
export function MachineEditDialog({ machine, onClose, onSaved }: MachineEditDialogProps): ReactNode {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState<MachineDraft>(draftFromMachine(machine));
  const [message, setMessage] = useState<MessageState>({ text: "", error: false });

  /**
   * Open and sync the dialog when a machine is selected.
   */
  useEffect(() => {
    setDraft(draftFromMachine(machine));
    setMessage({ text: "", error: false });
    if (machine && dialogRef.current && !dialogRef.current.open) {
      dialogRef.current.showModal();
    }
    if (!machine && dialogRef.current?.open) {
      dialogRef.current.close();
    }
  }, [machine]);

  /**
   * Update one edit field.
   */
  function updateField(fieldName: keyof MachineDraft, value: string): void {
    setDraft((currentDraft) => ({ ...currentDraft, [fieldName]: value }));
  }

  /**
   * Save the machine edit.
   */
  async function handleSave(): Promise<void> {
    if (!machine) return;
    setBusy(true);
    setMessage({ text: "Wird gespeichert...", error: false });

    try {
      await updateMachine(machine.id, draft);
      await onSaved();
      onClose();
    } catch (error) {
      setMessage({ text: machineErrorMessage(error), error: true });
    } finally {
      setBusy(false);
    }
  }

  return (
    <dialog id="machine-edit-dialog" aria-modal="true" aria-labelledby="med-title" onClose={onClose} ref={dialogRef}>
      <div className="card app-card" style={{ minWidth: 300, maxWidth: 420, padding: "1.5rem" }}>
        <h3 className="panel-title mb-4" id="med-title">Maschine bearbeiten</h3>
        <input id="med-id" type="hidden" value={machine?.id || ""} readOnly />
        <div className="form-grid">
          <div className="field">
            <label htmlFor="med-name">Name</label>
            <input className="input input-bordered" disabled={busy} id="med-name" onChange={(event) => updateField("name", event.target.value)} required value={draft.name} />
          </div>
          <div className="field">
            <label htmlFor="med-produced">Was wird produziert?</label>
            <input className="input input-bordered" disabled={busy} id="med-produced" onChange={(event) => updateField("produced_item", event.target.value)} value={draft.produced_item} />
          </div>
          <div className="field">
            <label htmlFor="med-employees">Mitarbeiter pro Maschine</label>
            <input className="input input-bordered" disabled={busy} id="med-employees" min="1" onChange={(event) => updateField("required_employees", event.target.value)} type="number" value={draft.required_employees} />
          </div>
        </div>
        <div className="toolbar mt-4">
          <button className="btn btn-primary btn-sm" disabled={busy} id="med-save" onClick={handleSave} type="button">
            {busy ? "Speichert..." : "Speichern"}
          </button>
          <button className="btn btn-ghost btn-sm" disabled={busy} id="med-cancel" onClick={onClose} type="button">
            Abbrechen
          </button>
        </div>
        <p className={`panel-meta mt-2${message.error ? " is-error" : ""}`} id="med-msg" role="status" aria-live="polite">
          {message.text}
        </p>
      </div>
    </dialog>
  );
}

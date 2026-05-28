import { useEffect, useState, type ReactNode } from "react";

import { updateErrorEntry } from "../errorApi";
import type { Department, ErrorEntry, ErrorDraft, MessageState } from "../errorTypes";
import { draftFromError, errorMessage } from "../errorUtils";
import { ErrorFormFields } from "./ErrorFormFields";

type ErrorEditDialogProps = {
  readonly departments: readonly Department[];
  readonly entry: ErrorEntry | null;
  readonly onClose: () => void;
  readonly onMessageChange: (message: MessageState) => void;
  readonly onSaved: () => Promise<void>;
};

/**
 * Render the error edit dialog.
 */
export function ErrorEditDialog({ departments, entry, onClose, onMessageChange, onSaved }: ErrorEditDialogProps): ReactNode {
  const [draft, setDraft] = useState<ErrorDraft | null>(null);
  const [message, setMessage] = useState("");

  useEffect(() => {
    setDraft(entry ? draftFromError(entry) : null);
    setMessage("");
  }, [entry]);

  /**
   * Save the dialog draft.
   */
  async function save(): Promise<void> {
    if (!entry || !draft) return;
    setMessage("Wird gespeichert...");
    try {
      await updateErrorEntry(entry.id, draft);
      await onSaved();
      onMessageChange({ text: "Störung gespeichert.", error: false });
      onClose();
    } catch (error) {
      setMessage(errorMessage(error));
    }
  }

  return (
    <dialog className="incident-edit-dialog" id="error-edit-dialog" aria-modal="true" aria-labelledby="eed-title" open={Boolean(entry)}>
      <form className="incident-edit-card app-card" method="dialog">
        <header className="panel-header">
          <div>
            <h3 className="panel-title" id="eed-title">Störung bearbeiten</h3>
            <p className="panel-meta">Katalogdaten, Status und Auswirkungen aktualisieren.</p>
          </div>
          <button className="btn btn-ghost btn-sm" id="eed-cancel" type="button" onClick={onClose}>Schließen</button>
        </header>
        <input id="eed-id" type="hidden" value={entry?.id || ""} readOnly />
        {draft ? <ErrorFormFields departments={departments} draft={draft} idPrefix="eed" onDraftChange={setDraft} /> : null}
        <div className="toolbar form-actions">
          <button className="btn btn-primary btn-sm" id="eed-save" type="button" onClick={save}>Speichern</button>
          <span className="panel-meta" id="eed-msg" role="status" aria-live="polite">{message}</span>
        </div>
      </form>
    </dialog>
  );
}

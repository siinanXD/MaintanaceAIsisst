import { type ReactNode } from "react";

import { type AdminAiRagBoardProps } from "./AdminAiRagBoardTypes";

/**
 * Render RAG reindex and queue maintenance controls.
 */
export function ReindexJobsPanel({ onQueueStale, onReindexStale, ragBoardState }: AdminAiRagBoardProps): ReactNode {
  return (
    <section className="panel mt-4">
      <div className="panel-header">
        <div>
          <h3>RAG-Pflegeaktionen</h3>
          <p className="panel-meta" data-ai-reindex-message>
            {ragBoardState.statusMessage || "Quelle -> Textabschnitte -> Vektoren -> Suchbar -> Getestet"}
          </p>
        </div>
        <div className="toolbar">
          <button
            className="btn btn-secondary btn-sm"
            disabled={ragBoardState.isSaving}
            type="button"
            data-ai-queue-stale
            onClick={onQueueStale}
          >
            Job planen
          </button>
          <button
            className="btn btn-primary btn-sm"
            disabled={ragBoardState.isSaving}
            type="button"
            data-ai-reindex-stale
            onClick={onReindexStale}
          >
            Reindex
          </button>
        </div>
      </div>
      {ragBoardState.errorMessage ? <p className="panel-meta text-error">{ragBoardState.errorMessage}</p> : null}
    </section>
  );
}

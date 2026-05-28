import type { ReactNode } from "react";

type TaskHeaderProps = {
  readonly writable: boolean;
  readonly onRefreshPriorities: () => Promise<void>;
  readonly priorityBusy: boolean;
};

/**
 * Render the task page hero and command actions.
 */
export function TaskHeader({
  writable,
  onRefreshPriorities,
  priorityBusy
}: TaskHeaderProps): ReactNode {
  return (
    <section className="page-hero task-workboard-hero">
      <div>
        <h1 className="page-title">Maintenance Workboard</h1>
        <p className="page-description">Wartungs-, Reparatur- und Prüfaufgaben nach Priorität, Status, Bereich und Fälligkeit steuern.</p>
      </div>
      <div className="task-hero-actions">
        {writable ? (
          <a className="btn btn-primary btn-sm" data-permission-write="tasks" href="#task-create">Aufgabe anlegen</a>
        ) : null}
        <button
          className="btn btn-outline btn-sm"
          data-task-priority-refresh
          disabled={priorityBusy}
          onClick={onRefreshPriorities}
          type="button"
        >
          {priorityBusy ? "Wird geladen..." : "Priorität aktualisieren"}
        </button>
        <a className="btn btn-ghost btn-sm" href="/">Cockpit</a>
      </div>
    </section>
  );
}

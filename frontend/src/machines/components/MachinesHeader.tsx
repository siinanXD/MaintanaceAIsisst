import type { ReactNode } from "react";

type MachinesHeaderProps = {
  readonly issueCount: number;
  readonly onAssistantFocus: () => void;
};

/**
 * Render machine overview hero and quick actions.
 */
export function MachinesHeader({ issueCount, onAssistantFocus }: MachinesHeaderProps): ReactNode {
  return (
    <>
      <section className="page-hero">
        <div>
          <h1 className="page-title">Maschinen</h1>
          <p className="page-description">Anlagenstatus, offene Arbeit und Wartungshinweise an einem Ort prüfen.</p>
        </div>
      </section>

      <nav className="page-command-bar" aria-label="Maschinen Schnellzugriff">
        <a className="quick-action-row" href="#machine-list">
          <span>Maschinenübersicht öffnen</span>
          <strong>Anlagen</strong>
        </a>
        <button className="quick-action-row is-button" data-machine-assistant-focus onClick={onAssistantFocus} type="button">
          <span>Maschine prüfen</span>
          <strong>Assist</strong>
        </button>
        <a className="quick-action-row" data-dashboard-nav="errors" href="/errors" hidden>
          <span>Störungen prüfen</span>
          <strong data-dashboard-machine-issue-count>{issueCount}</strong>
        </a>
      </nav>

      <section className="ai-action-grid" aria-label="Maschinen Aktionen">
        <button className="ai-action-card is-button" data-machine-assistant-focus onClick={onAssistantFocus} type="button">
          <strong>Maschine prüfen</strong>
          <span>Anlagenakte, Forecast und Historie in einem Schritt ansehen</span>
        </button>
      </section>
    </>
  );
}

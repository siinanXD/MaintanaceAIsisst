import type { ReactNode } from "react";

import { canViewDashboard } from "../../auth/permissions";

/**
 * Render the inventory hero and command bar.
 */
export function InventoryHeader(): ReactNode {
  const canOpenMachines = canViewDashboard("machines");

  return (
    <>
      <section className="page-hero">
        <div>
          <p className="page-kicker">Material</p>
          <h1 className="page-title">Lager</h1>
          <p className="page-description">Materialien mit Kosten, Anzahl, Hersteller und verbauter Maschine verwalten.</p>
        </div>
      </section>

      <nav className="page-command-bar" aria-label="Lager Schnellzugriff">
        <a className="quick-action-row" href="#inventory-list">
          <span>Lagerbestand prüfen</span>
          <strong>Bestand</strong>
        </a>
        <button className="quick-action-row is-button" type="submit" form="inventory-forecast-command-form">
          <span>Ersatzteil-Prognose berechnen</span>
          <strong>AI</strong>
        </button>
        <a className="quick-action-row" href="/machines" data-dashboard-nav="machines" hidden={!canOpenMachines}>
          <span>Maschinenbezug öffnen</span>
          <strong>Anlagen</strong>
        </a>
      </nav>
    </>
  );
}

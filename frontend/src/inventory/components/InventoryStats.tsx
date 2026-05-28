import type { ReactNode } from "react";

import type { InventoryMaterial } from "../inventoryTypes";
import { inventoryStats } from "../inventoryUtils";

type InventoryStatsProps = {
  readonly materials: readonly InventoryMaterial[];
  readonly threshold: number;
};

/**
 * Render inventory KPI cards.
 */
export function InventoryStats({ materials, threshold }: InventoryStatsProps): ReactNode {
  const stats = inventoryStats(materials, threshold);

  return (
    <section className="surface-stat-grid ux-ops-summary-grid" aria-label="Lagerstatus">
      <article className="surface-stat-card is-primary">
        <span>Positionen</span>
        <strong data-inventory-count>{stats.count}</strong>
        <small>Materialien, Hersteller und Maschinenzuordnung.</small>
      </article>
      <article className="surface-stat-card is-warning">
        <span>Mindestbestand</span>
        <strong data-inventory-low-count>{stats.lowStock}</strong>
        <small>Artikel unter oder gleich aktueller Warnschwelle.</small>
      </article>
      <article className="surface-stat-card is-ai">
        <span>Lagerwert</span>
        <strong data-inventory-total-value>{stats.totalValue}</strong>
        <small>Summierter Wert aus Bestand und Einzelkosten.</small>
      </article>
      <article className="surface-stat-card is-neutral">
        <span>Maschinenbezug</span>
        <strong data-inventory-linked-count>{stats.linked}</strong>
        <small>Ersatzteile mit direkter Anlagenverknüpfung.</small>
      </article>
    </section>
  );
}

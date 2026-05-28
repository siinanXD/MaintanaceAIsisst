import { useMemo, useState, type ReactNode } from "react";

import { deleteInventoryMaterial } from "../inventoryApi";
import type { InventoryMaterial } from "../inventoryTypes";
import { formatMoney } from "../../formatters/number";
import { materialSearchText, searchText } from "../inventoryUtils";

type InventoryListProps = {
  readonly materials: readonly InventoryMaterial[];
  readonly writable: boolean;
  readonly onRefresh: () => Promise<void>;
};

/**
 * Render one inventory material card.
 */
function MaterialCard({
  material,
  writable,
  onDeleted
}: {
  readonly material: InventoryMaterial;
  readonly writable: boolean;
  readonly onDeleted: () => Promise<void>;
}): ReactNode {
  const [busy, setBusy] = useState(false);
  const quantity = Number(material.quantity || 0);
  const machineName = material.machine?.name || "Keine Maschine";

  /**
   * Delete a material after user confirmation.
   */
  async function handleDelete(): Promise<void> {
    if (!window.confirm(`${material.name} wirklich löschen?`)) {
      return;
    }

    setBusy(true);
    try {
      await deleteInventoryMaterial(material.id);
      await onDeleted();
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className={`record-card inventory-card${quantity <= 5 ? " is-low-stock" : ""}`} data-search-text={searchText(materialSearchText(material))}>
      <div className="record-card-header">
        <div>
          <h3 className="record-card-title">{material.name || "Material"}</h3>
          <p className="record-card-subtitle">{[material.manufacturer || "Hersteller offen", machineName].join(" · ")}</p>
        </div>
        <span className={quantity <= 5 ? "badge badge-priority is-soon" : "badge badge-status is-done"}>
          {quantity <= 5 ? "niedrig" : "verfügbar"}
        </span>
      </div>
      <div className="record-card-meta inventory-card-meta">
        {[
          ["Bestand", String(quantity)],
          ["Einzelkosten", formatMoney(material.unit_cost)],
          ["Gesamtwert", formatMoney(material.total_value)],
          ["Maschine", machineName]
        ].map(([label, value]) => (
          <span key={label}>
            <small>{label}</small>
            <strong>{value || "-"}</strong>
          </span>
        ))}
      </div>
      <div className="record-card-actions">
        {material.machine?.id ? (
          <a className="btn btn-outline btn-sm" href={`/machines/${material.machine.id}`}>Maschinenprofil</a>
        ) : null}
        {writable ? (
          <button className="btn btn-ghost btn-sm" disabled={busy} onClick={handleDelete} type="button">
            Löschen
          </button>
        ) : null}
      </div>
    </article>
  );
}

/**
 * Render the inventory list and local search.
 */
export function InventoryList({ materials, writable, onRefresh }: InventoryListProps): ReactNode {
  const [query, setQuery] = useState("");
  const filteredMaterials = useMemo(() => {
    const normalizedQuery = searchText(query);
    if (!normalizedQuery) {
      return materials;
    }

    return materials.filter((material) => searchText(materialSearchText(material)).includes(normalizedQuery));
  }, [materials, query]);

  return (
    <article className="card app-card mobile-primary-card lg:order-1 lg:col-span-12" id="inventory-list">
      <div className="card-body">
        <div className="panel-header">
          <div>
            <h2 className="panel-title">Lagerbestand</h2>
            <p className="panel-meta">Materialien, Mengen und Gesamtwert je Position</p>
          </div>
        </div>
        <div className="list-toolbar">
          <label className="compact-search-field" htmlFor="react-inventory-list-search">
            <span>Material suchen</span>
            <input className="input input-bordered input-sm" data-list-search data-list-search-target="[data-inventory-list]" id="react-inventory-list-search" onChange={(event) => setQuery(event.target.value)} placeholder="Name, Maschine, Hersteller" value={query} />
          </label>
        </div>
        <div className="record-card-grid inventory-card-grid bounded-list-scroll" data-inventory-list data-list-search-items=".inventory-card">
          {filteredMaterials.length ? (
            filteredMaterials.map((material) => (
              <MaterialCard key={material.id} material={material} onDeleted={onRefresh} writable={writable} />
            ))
          ) : (
            <div className="empty-state">
              <strong>Noch kein Material angelegt.</strong>
              <span>Lege die ersten Ersatzteile an, damit Lagerwert und Maschinenbezug sichtbar werden.</span>
            </div>
          )}
        </div>
      </div>
    </article>
  );
}

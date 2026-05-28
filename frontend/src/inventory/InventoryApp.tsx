import { useEffect, useLayoutEffect, useState, type ReactNode } from "react";

import { markIslandMounted } from "../app/islandMount";
import { canWriteDashboard } from "../auth/permissions";
import { InventoryForecastPanel } from "./components/InventoryForecastPanel";
import { InventoryHeader } from "./components/InventoryHeader";
import { InventoryList } from "./components/InventoryList";
import { InventoryStats } from "./components/InventoryStats";
import { MaterialForm } from "./components/MaterialForm";
import {
  calculateInventoryForecast,
  loadInventoryMaterials,
  loadMachines
} from "./inventoryApi";
import type { InventoryForecast, InventoryMaterial, Machine } from "./inventoryTypes";
import { inventoryErrorMessage } from "./inventoryUtils";

const INVENTORY_ISLAND = {
  fallbackSelector: "[data-react-inventory-fallback]",
  mountedFlag: "maintenanceInventoryReactMounted",
  mountEvent: "maintenance-inventory-react-mounted"
};

/**
 * Render the React inventory workflow island.
 */
export function InventoryApp(): ReactNode {
  const writable = canWriteDashboard("inventory");
  const [materials, setMaterials] = useState<InventoryMaterial[]>([]);
  const [machines, setMachines] = useState<Machine[]>([]);
  const [forecast, setForecast] = useState<InventoryForecast | null>(null);
  const [threshold, setThreshold] = useState(5);
  const [loadError, setLoadError] = useState("");

  /**
   * Refresh inventory and machine data in parallel.
   */
  async function refreshInventory(): Promise<void> {
    const [loadedMaterials, loadedMachines] = await Promise.all([
      loadInventoryMaterials(),
      loadMachines()
    ]);
    setMaterials(loadedMaterials);
    setMachines(loadedMachines);
  }

  /**
   * Run the inventory forecast request.
   */
  async function runForecast(nextThreshold: number): Promise<void> {
    const result = await calculateInventoryForecast({
      low_stock_threshold: nextThreshold,
      status: "open",
      limit: 20
    });
    setForecast(result);
  }

  useLayoutEffect(() => {
    markIslandMounted(INVENTORY_ISLAND);
  }, []);

  useEffect(() => {
    refreshInventory().catch((error: unknown) => {
      setLoadError(inventoryErrorMessage(error));
    });
  }, []);

  return (
    <>
      <InventoryHeader />
      {loadError ? (
        <section className="card app-card" role="alert">
          <div className="card-body">
            <p className="panel-meta is-error">{loadError}</p>
          </div>
        </section>
      ) : null}
      <InventoryStats materials={materials} threshold={threshold} />
      <section className="dashboard-grid">
        {writable ? <MaterialForm machines={machines} onCreated={refreshInventory} /> : null}
        <InventoryForecastPanel
          forecast={forecast}
          onForecast={runForecast}
          onThresholdChange={setThreshold}
          threshold={threshold}
        />
        <InventoryList materials={materials} onRefresh={refreshInventory} writable={writable} />
      </section>
    </>
  );
}

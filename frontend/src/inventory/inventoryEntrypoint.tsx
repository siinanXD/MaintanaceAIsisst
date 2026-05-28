import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { InventoryApp } from "./InventoryApp";

const INVENTORY_ROOT_ID = "maintenance-inventory-root";

declare global {
  interface Window {
    maintenanceInventoryReactMounted?: boolean;
  }
}

/**
 * Mount the inventory React island only on the explicit inventory root.
 */
function bootstrapInventoryIsland(): void {
  const rootElement = document.getElementById(INVENTORY_ROOT_ID);

  if (!rootElement) {
    return;
  }

  createRoot(rootElement).render(
    <StrictMode>
      <InventoryApp />
    </StrictMode>
  );
}

bootstrapInventoryIsland();

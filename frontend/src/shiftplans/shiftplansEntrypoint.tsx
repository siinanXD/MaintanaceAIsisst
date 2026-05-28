import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { ShiftplansApp } from "./ShiftplansApp";

const SHIFTPLANS_ROOT_ID = "maintenance-shiftplans-root";

/**
 * Mount the shift planning React shell only on the shift planning route.
 */
function bootstrapShiftplansIsland(): void {
  const rootElement = document.getElementById(SHIFTPLANS_ROOT_ID);

  if (!rootElement) {
    return;
  }

  createRoot(rootElement).render(
    <StrictMode>
      <ShiftplansApp />
    </StrictMode>
  );
}

bootstrapShiftplansIsland();

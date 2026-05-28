import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { HandoverApp } from "./HandoverApp";

const HANDOVER_ROOT_ID = "maintenance-handover-root";

/**
 * Mount the handover React shell only on the handover route.
 */
function bootstrapHandoverIsland(): void {
  const rootElement = document.getElementById(HANDOVER_ROOT_ID);

  if (!rootElement) {
    return;
  }

  createRoot(rootElement).render(
    <StrictMode>
      <HandoverApp />
    </StrictMode>
  );
}

bootstrapHandoverIsland();

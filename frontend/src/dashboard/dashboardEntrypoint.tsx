import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { DashboardApp } from "./DashboardApp";

const DASHBOARD_ROOT_ID = "maintenance-dashboard-root";

/**
 * Mount the dashboard React shell only on the cockpit route.
 */
function bootstrapDashboardIsland(): void {
  const rootElement = document.getElementById(DASHBOARD_ROOT_ID);

  if (!rootElement) {
    return;
  }

  createRoot(rootElement).render(
    <StrictMode>
      <DashboardApp />
    </StrictMode>
  );
}

bootstrapDashboardIsland();

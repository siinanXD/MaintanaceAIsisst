import { useEffect, type ReactNode } from "react";

import { markIslandMounted } from "../app/islandMount";
import { DashboardMarkup } from "./DashboardMarkup";

const DASHBOARD_ISLAND = {
  fallbackSelector: "[data-react-dashboard-fallback]",
  mountedFlag: "maintenanceDashboardReactMounted",
  mountEvent: "maintenance-dashboard-react-mounted"
} as const;

/**
 * Render the dashboard with React-owned markup while preserving runtime hooks.
 */
export function DashboardApp(): ReactNode {
  useEffect(() => {
    markIslandMounted(DASHBOARD_ISLAND);
  }, []);

  return (
    <div data-dashboard-react-shell>
      <DashboardMarkup />
    </div>
  );
}

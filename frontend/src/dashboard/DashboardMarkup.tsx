import { type ReactNode } from "react";

import { DashboardAssetStatus } from "./DashboardAssetStatus";
import { DashboardHiddenForms } from "./DashboardHiddenForms";
import { DashboardHero } from "./DashboardHero";
import { DashboardKpis } from "./DashboardKpis";
import { DashboardOperations } from "./DashboardOperations";
import { DashboardShiftPeople } from "./DashboardShiftPeople";
import { DashboardSideColumn } from "./DashboardSideColumn";
import { DashboardTaskDetailModal } from "./DashboardTaskDetailModal";
import { DashboardTaskOverview } from "./DashboardTaskOverview";
import { DashboardTechnicalDetails } from "./DashboardTechnicalDetails";

/**
 * Render the dashboard shell that the existing dashboard runtime hydrates.
 */
export function DashboardMarkup(): ReactNode {
  return (
    <div data-dashboard-static-shell>
      <DashboardHero />
      <DashboardKpis />
      <section className="control-center-grid" aria-label="Maintenance Control Center">
        <DashboardTaskOverview />
        <DashboardAssetStatus />
        <DashboardShiftPeople />
        <DashboardOperations />
        <DashboardSideColumn />
        <DashboardTechnicalDetails />
        <DashboardHiddenForms />
        <DashboardTaskDetailModal />
      </section>
    </div>
  );
}

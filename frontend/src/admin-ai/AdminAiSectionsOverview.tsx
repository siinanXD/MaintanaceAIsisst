import { type ReactNode } from "react";

import type { AdminAiOverviewLoadState } from "./adminAiOverviewModel";
import { AdminAiOverviewActivity } from "./AdminAiOverviewActivity";
import { AdminAiOverviewStatus } from "./AdminAiOverviewStatus";

type AdminAiOverviewProps = {
  readonly overviewState: AdminAiOverviewLoadState;
};

/**
 * Render the compact Admin-AI overview cockpit.
 */
export function AdminAiOverview({ overviewState }: AdminAiOverviewProps): ReactNode {
  return (
    <section className="ai-admin-area" id="ai-models" data-ai-admin-area="overview">
      <AdminAiOverviewStatus overviewState={overviewState} />
      <AdminAiOverviewActivity overviewState={overviewState} />
    </section>
  );
}

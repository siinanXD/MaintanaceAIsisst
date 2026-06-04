import { type ReactNode } from "react";

import { AdminAiOperateHub } from "./AdminAiOperateHub";
import type { AdminAiOverviewLoadState } from "./adminAiOverviewModel";

type AdminAiOverviewProps = {
  readonly overviewState: AdminAiOverviewLoadState;
};

/**
 * Render the Admin-AI operations overview (monitoring entry point).
 */
export function AdminAiOverview({ overviewState }: AdminAiOverviewProps): ReactNode {
  return <AdminAiOperateHub overviewState={overviewState} />;
}

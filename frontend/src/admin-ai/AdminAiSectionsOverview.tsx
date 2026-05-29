import { type ReactNode } from "react";

import type { AdminAiOverviewLoadState } from "./adminAiOverviewModel";
import { AdminAiOverviewActivity } from "./AdminAiOverviewActivity";
import { AdminAiOverviewIntro, AdminAiOverviewStatus } from "./AdminAiOverviewStatus";
import { AdminAiOverviewProvider } from "./AdminAiOverviewProvider";

type AdminAiOverviewProps = {
  readonly onChatQueryChange: (value: string) => void;
  readonly onEventErrorChange: (value: string) => void;
  readonly overviewChatQuery: string;
  readonly overviewEventError: string;
  readonly overviewState: AdminAiOverviewLoadState;
};

/**
 * Render the Admin-AI overview cockpit markup.
 */
export function AdminAiOverview({
  onChatQueryChange,
  onEventErrorChange,
  overviewChatQuery,
  overviewEventError,
  overviewState
}: AdminAiOverviewProps): ReactNode {
  return (
    <>
      <AdminAiOverviewIntro />
      <section className="ai-admin-area" id="ai-models" data-ai-admin-area="overview">
        <AdminAiOverviewStatus overviewState={overviewState} />
        <AdminAiOverviewActivity
          onChatQueryChange={onChatQueryChange}
          onEventErrorChange={onEventErrorChange}
          overviewChatQuery={overviewChatQuery}
          overviewEventError={overviewEventError}
          overviewState={overviewState}
        />
        <AdminAiOverviewProvider overviewState={overviewState} />
      </section>
    </>
  );
}

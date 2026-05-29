import { type ReactNode } from "react";

import { AdminAiMarkup, type AdminAiMarkupProps } from "./AdminAiMarkup";

/**
 * Render the selected Admin-AI view with data supplied by React hooks.
 */
export function AdminAiViewRouter(props: AdminAiMarkupProps): ReactNode {
  return <AdminAiMarkup {...props} />;
}

import { type ReactNode } from "react";

/**
 * Render a compact dashboard empty state.
 */
export function EmptyState({ children }: { readonly children: ReactNode }): ReactNode {
  return <div className="empty-state">{children}</div>;
}

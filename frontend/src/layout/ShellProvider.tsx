import { type ReactNode } from "react";

import { ShellRuntimeProvider } from "./ShellRuntimeProvider";

/**
 * Provide the central React shell runtime under the architecture-level ShellProvider name.
 */
export function ShellProvider({ children }: { readonly children: ReactNode }): ReactNode {
  return <ShellRuntimeProvider>{children}</ShellRuntimeProvider>;
}

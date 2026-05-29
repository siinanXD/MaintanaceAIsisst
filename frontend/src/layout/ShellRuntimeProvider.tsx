import { type ReactNode } from "react";

import { DialogProvider } from "../app/DialogProvider";
import { FeatureRegistryProvider } from "../app/FeatureRegistryProvider";
import { ToastProvider } from "../app/ToastProvider";
import { AuthProvider } from "../auth/AuthProvider";
import { PermissionProvider } from "../auth/PermissionProvider";

/**
 * Compose the global providers used by the central React shell runtime.
 */
export function ShellRuntimeProvider({ children }: { readonly children: ReactNode }): ReactNode {
  return (
    <FeatureRegistryProvider>
      <AuthProvider>
        <PermissionProvider>
          <ToastProvider>
            <DialogProvider>{children}</DialogProvider>
          </ToastProvider>
        </PermissionProvider>
      </AuthProvider>
    </FeatureRegistryProvider>
  );
}

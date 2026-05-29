import { createContext, useContext, useMemo, type ReactNode } from "react";

import { legacyFeatureRegistry, type MaintenanceFeatureRegistry } from "./runtimeBridge";

const FeatureRegistryContext = createContext<MaintenanceFeatureRegistry | null>(null);

/**
 * Provide the existing static feature registry to React shell components.
 */
export function FeatureRegistryProvider({ children }: { readonly children: ReactNode }): ReactNode {
  const registry = useMemo(() => legacyFeatureRegistry(), []);
  return <FeatureRegistryContext.Provider value={registry}>{children}</FeatureRegistryContext.Provider>;
}

/**
 * Return the React feature registry context with a stable empty fallback.
 */
export function useFeatureRegistry(): MaintenanceFeatureRegistry {
  return useContext(FeatureRegistryContext) || { all: [] };
}

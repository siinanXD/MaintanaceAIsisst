import { useEffect, useMemo, type ReactNode } from "react";

import { markIslandMounted } from "../app/islandMount";
import { AdminAiViewRouter } from "./AdminAiViewRouter";
import { resolveAdminAiViewFromPathname } from "./AdminAiTypes";
import { useAdminAiData } from "./useAdminAiData";

const ADMIN_AI_ISLAND = {
  mountedFlag: "maintenanceAdminAiReactMounted",
  mountEvent: "maintenance-admin-ai-react-mounted"
} as const;

type AdminAiRuntimeWindow = Window & {
  maintenanceAdminAiReactRuntime?: string;
};

/**
 * Render the Admin-AI page with React-owned markup and data hooks.
 */
export function AdminAiApp(): ReactNode {
  const adminAiView = useMemo(
    () => resolveAdminAiViewFromPathname(window.location.pathname),
    []
  );
  const adminAiData = useAdminAiData(adminAiView);

  useEffect(() => {
    markIslandMounted(ADMIN_AI_ISLAND);
  }, []);

  useEffect(() => {
    (window as AdminAiRuntimeWindow).maintenanceAdminAiReactRuntime = adminAiView;
  }, [adminAiView]);

  return (
    <div data-admin-ai-react-shell>
      <AdminAiViewRouter view={adminAiView} {...adminAiData} />
    </div>
  );
}

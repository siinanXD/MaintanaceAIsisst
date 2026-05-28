import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { AdminAiApp } from "./AdminAiApp";

const ADMIN_AI_ROOT_ID = "maintenance-admin-ai-root";

/**
 * Mount the Admin-AI React shell only on Admin-AI routes.
 */
function bootstrapAdminAiIsland(): void {
  const rootElement = document.getElementById(ADMIN_AI_ROOT_ID);

  if (!rootElement) {
    return;
  }

  createRoot(rootElement).render(
    <StrictMode>
      <AdminAiApp />
    </StrictMode>
  );
}

bootstrapAdminAiIsland();

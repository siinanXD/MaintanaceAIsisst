import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { AdminUsersApp } from "./AdminUsersApp";

const ADMIN_USERS_ROOT_ID = "maintenance-admin-users-root";

/**
 * Mount the admin users React island only on the explicit admin root.
 */
function bootstrapAdminUsersIsland(): void {
  const rootElement = document.getElementById(ADMIN_USERS_ROOT_ID);

  if (!rootElement) {
    return;
  }

  createRoot(rootElement).render(
    <StrictMode>
      <AdminUsersApp />
    </StrictMode>
  );
}

bootstrapAdminUsersIsland();

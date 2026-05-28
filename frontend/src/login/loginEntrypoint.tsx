import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { LoginApp } from "./LoginApp";

const LOGIN_ROOT_ID = "maintenance-login-root";

/**
 * Mount the login island only on the explicit login root.
 */
function bootstrapLoginIsland(): void {
  const rootElement = document.getElementById(LOGIN_ROOT_ID);

  if (!rootElement) {
    return;
  }

  createRoot(rootElement).render(
    <StrictMode>
      <LoginApp />
    </StrictMode>
  );
}

bootstrapLoginIsland();

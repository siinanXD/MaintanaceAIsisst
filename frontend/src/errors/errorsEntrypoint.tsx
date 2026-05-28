import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { ErrorsApp } from "./ErrorsApp";

const ERRORS_ROOT_ID = "maintenance-errors-root";

/**
 * Mount the errors React island only on the explicit errors root.
 */
function bootstrapErrorsIsland(): void {
  const rootElement = document.getElementById(ERRORS_ROOT_ID);

  if (!rootElement) {
    return;
  }

  createRoot(rootElement).render(
    <StrictMode>
      <ErrorsApp />
    </StrictMode>
  );
}

bootstrapErrorsIsland();

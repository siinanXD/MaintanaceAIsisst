import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { VacationsApp } from "./VacationsApp";

const VACATIONS_ROOT_ID = "maintenance-vacations-root";

/**
 * Mount the vacations React island only on the explicit vacations root.
 */
function bootstrapVacationsIsland(): void {
  const rootElement = document.getElementById(VACATIONS_ROOT_ID);

  if (!rootElement) {
    return;
  }

  createRoot(rootElement).render(
    <StrictMode>
      <VacationsApp />
    </StrictMode>
  );
}

bootstrapVacationsIsland();

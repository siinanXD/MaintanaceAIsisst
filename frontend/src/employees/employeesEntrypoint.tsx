import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { EmployeesApp } from "./EmployeesApp";

const EMPLOYEES_ROOT_ID = "maintenance-employees-root";

/**
 * Mount the employees React island only on the explicit employees root.
 */
function bootstrapEmployeesIsland(): void {
  const rootElement = document.getElementById(EMPLOYEES_ROOT_ID);

  if (!rootElement) {
    return;
  }

  createRoot(rootElement).render(
    <StrictMode>
      <EmployeesApp />
    </StrictMode>
  );
}

bootstrapEmployeesIsland();

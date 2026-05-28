import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { TasksApp } from "./TasksApp";

const TASKS_ROOT_ID = "maintenance-tasks-root";

/**
 * Mount the tasks React island only on the explicit tasks root.
 */
function bootstrapTasksIsland(): void {
  const rootElement = document.getElementById(TASKS_ROOT_ID);

  if (!rootElement) {
    return;
  }

  createRoot(rootElement).render(
    <StrictMode>
      <TasksApp />
    </StrictMode>
  );
}

bootstrapTasksIsland();

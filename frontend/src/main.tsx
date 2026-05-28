import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./app/App";

const REACT_ROOT_ID = "maintenance-react-root";

/**
 * Mount the React foundation only when an explicit root element exists.
 */
function bootstrapReactApp(): void {
  const rootElement = document.getElementById(REACT_ROOT_ID);

  if (!rootElement) {
    return;
  }

  createRoot(rootElement).render(
    <StrictMode>
      <App />
    </StrictMode>
  );
}

bootstrapReactApp();

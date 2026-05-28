import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { DocumentsApp } from "./DocumentsApp";

const DOCUMENTS_ROOT_ID = "maintenance-documents-root";

/**
 * Mount the documents React island only on the explicit documents root.
 */
function bootstrapDocumentsIsland(): void {
  const rootElement = document.getElementById(DOCUMENTS_ROOT_ID);

  if (!rootElement) {
    return;
  }

  createRoot(rootElement).render(
    <StrictMode>
      <DocumentsApp />
    </StrictMode>
  );
}

bootstrapDocumentsIsland();

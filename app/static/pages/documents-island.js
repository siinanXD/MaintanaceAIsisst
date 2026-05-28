(async function () {
  "use strict";

  const STATIC_VERSION = window.maintenanceStaticVersion || "dev";
  await import("/static/pages/react-island-loader.js?v=" + STATIC_VERSION);
  const { initializeReactIslandFallback } = window.MaintenanceReactIslandLoader;

  await initializeReactIslandFallback({
    mountedFlag: "maintenanceDocumentsReactMounted",
    mountEvent: "maintenance-documents-react-mounted",
    fallbackSelector: "[data-react-documents-fallback]",
    workflowModules: ["documents.js"],
    initializerNames: ["initDocuments"],
    missingMessage: "Documents fallback initializer is missing."
  });
})();

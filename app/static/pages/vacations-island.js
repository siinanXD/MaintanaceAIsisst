(async function () {
  "use strict";

  const STATIC_VERSION = window.maintenanceStaticVersion || "dev";
  await import("/static/pages/react-island-loader.js?v=" + STATIC_VERSION);
  const { initializeReactIslandFallback } = window.MaintenanceReactIslandLoader;

  await initializeReactIslandFallback({
    mountedFlag: "maintenanceVacationsReactMounted",
    mountEvent: "maintenance-vacations-react-mounted",
    fallbackSelector: "[data-react-vacations-fallback]",
    workflowModules: ["vacations.js"],
    initializerNames: ["initVacations"],
    missingMessage: "Vacations fallback initializer is missing."
  });
})();

(async function () {
  "use strict";

  const STATIC_VERSION = window.maintenanceStaticVersion || "dev";
  await import("/static/pages/react-island-loader.js?v=" + STATIC_VERSION);
  const { initializeReactIslandFallback } = window.MaintenanceReactIslandLoader;

  await initializeReactIslandFallback({
    mountedFlag: "maintenanceErrorsReactMounted",
    mountEvent: "maintenance-errors-react-mounted",
    fallbackSelector: "[data-react-errors-fallback]",
    workflowModules: ["errors.js"],
    initializerNames: ["initDepartments", "initErrors"],
    missingMessage: "Errors fallback initializer is missing."
  });
})();

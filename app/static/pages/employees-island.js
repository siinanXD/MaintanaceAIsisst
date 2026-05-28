(async function () {
  "use strict";

  const STATIC_VERSION = window.maintenanceStaticVersion || "dev";
  await import("/static/pages/react-island-loader.js?v=" + STATIC_VERSION);
  const { initializeReactIslandFallback } = window.MaintenanceReactIslandLoader;

  await initializeReactIslandFallback({
    mountedFlag: "maintenanceEmployeesReactMounted",
    mountEvent: "maintenance-employees-react-mounted",
    fallbackSelector: "[data-react-employees-fallback]",
    workflowModules: ["employees.js"],
    initializerNames: ["initDepartments", "initEmployees"],
    missingMessage: "Employees fallback initializer is missing."
  });
})();

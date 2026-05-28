(async function () {
  "use strict";

  const STATIC_VERSION = window.maintenanceStaticVersion || "dev";
  await import("/static/pages/react-island-loader.js?v=" + STATIC_VERSION);
  const { initializeReactIslandFallback } = window.MaintenanceReactIslandLoader;

  await initializeReactIslandFallback({
    mountedFlag: "maintenanceTasksReactMounted",
    mountEvent: "maintenance-tasks-react-mounted",
    fallbackSelector: "[data-react-tasks-fallback]",
    workflowModules: ["tasks.js"],
    initializerNames: ["initDepartments", "initTasks"],
    missingMessage: "Tasks fallback initializer is missing."
  });
})();

(async function () {
  "use strict";

  const STATIC_VERSION = window.maintenanceStaticVersion || "dev";
  await import("/static/pages/react-island-loader.js?v=" + STATIC_VERSION);
  const { initializeReactIslandFallback } = window.MaintenanceReactIslandLoader;

  await initializeReactIslandFallback({
    mountedFlag: "maintenanceAdminUsersReactMounted",
    mountEvent: "maintenance-admin-users-react-mounted",
    fallbackSelector: "[data-react-admin-users-fallback]",
    workflowModules: ["admin-users.js"],
    initializerNames: ["initUsers"],
    missingMessage: "Admin users fallback initializer is missing."
  });
})();

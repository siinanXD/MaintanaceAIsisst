(async function () {
  "use strict";

  const STATIC_VERSION = window.maintenanceStaticVersion || "dev";
  await import("/static/pages/react-island-loader.js?v=" + STATIC_VERSION);
  const { initializeReactIslandFallback } = window.MaintenanceReactIslandLoader;

  await initializeReactIslandFallback({
    mountedFlag: "maintenanceInventoryReactMounted",
    mountEvent: "maintenance-inventory-react-mounted",
    fallbackSelector: "[data-react-inventory-fallback]",
    workflowModules: ["inventory.js"],
    initializerNames: ["initInventory"],
    missingMessage: "Inventory fallback initializer is missing."
  });
})();

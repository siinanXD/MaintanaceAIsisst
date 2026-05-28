(async function () {
  "use strict";

  const STATIC_VERSION = window.maintenanceStaticVersion || "dev";
  await import("/static/pages/react-island-loader.js?v=" + STATIC_VERSION);
  const { initializeReactIslandFallback } = window.MaintenanceReactIslandLoader;

  /**
   * Return true on the machine profile route.
   *
   * @returns {boolean} Whether the profile fallback should initialize.
   */
  function isMachineProfileRoute() {
    return Boolean(document.querySelector("[data-machine-profile-page]"));
  }

  await initializeReactIslandFallback({
    mountedFlag: "maintenanceMachinesReactMounted",
    mountEvent: "maintenance-machines-react-mounted",
    fallbackSelector: isMachineProfileRoute()
      ? "[data-react-machine-profile-fallback]"
      : "[data-react-machines-fallback]",
    workflowModules: () => (isMachineProfileRoute() ? ["machine-profile.js"] : ["machines.js"]),
    initializerNames: () => (isMachineProfileRoute() ? ["initMachineProfile"] : ["initMachines"]),
    missingMessage: "Machines fallback initializer is missing."
  });
})();

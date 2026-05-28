(async function () {
  "use strict";

  const STATIC_VERSION = window.maintenanceStaticVersion || "dev";
  await import("/static/pages/react-island-loader.js?v=" + STATIC_VERSION);
  const { waitForReactIsland } = window.MaintenanceReactIslandLoader;

  /**
   * Load the existing shift planning runtime against the active page shell.
   *
   * @returns {Promise<void>} Resolves after the shift planning runtime has loaded.
   */
  async function initializeShiftplansRuntime() {
    await import("/static/pages/shiftplans.js?v=" + STATIC_VERSION);
  }

  const reactMounted = await waitForReactIsland({
    mountedFlag: "maintenanceShiftplansReactMounted",
    mountEvent: "maintenance-shiftplans-react-mounted",
    fallbackSelector: "[data-react-shiftplans-fallback]",
    timeoutMs: 900
  });
  if (reactMounted) return;
  await initializeShiftplansRuntime();
})();

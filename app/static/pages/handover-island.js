(async function () {
  "use strict";

  const STATIC_VERSION = window.maintenanceStaticVersion || "dev";
  await import("/static/pages/react-island-loader.js?v=" + STATIC_VERSION);
  const { waitForReactIsland } = window.MaintenanceReactIslandLoader;

  /**
   * Load and run the existing handover runtime against the active page shell.
   *
   * @returns {Promise<void>} Resolves after the handover runtime has initialized.
   */
  async function initializeHandoverRuntime() {
    await import("/static/pages/handover.js?v=" + STATIC_VERSION);
    if (
      window.MaintenanceHandoverRuntime
      && typeof window.MaintenanceHandoverRuntime.initHandover === "function"
    ) {
      await window.MaintenanceHandoverRuntime.initHandover();
    }
  }

  const reactMounted = await waitForReactIsland({
    mountedFlag: "maintenanceHandoverReactMounted",
    mountEvent: "maintenance-handover-react-mounted",
    fallbackSelector: "[data-react-handover-fallback]",
    timeoutMs: 900
  });
  if (reactMounted) return;
  await initializeHandoverRuntime();
})();

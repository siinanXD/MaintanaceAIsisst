(async function () {
  "use strict";

  const STATIC_VERSION = window.maintenanceStaticVersion || "dev";
  await import("/static/pages/react-island-loader.js?v=" + STATIC_VERSION);
  const { initializeReactShellRuntime } = window.MaintenanceReactIslandLoader;

  /**
   * Load and run the existing dashboard runtime against the active dashboard DOM.
   *
   * @returns {Promise<void>} Resolves after the dashboard initializers have run.
   */
  async function initializeDashboardRuntime() {
    const shared = await import("/static/pages/workflows/shared.js?v=" + STATIC_VERSION);
    await shared.loadWorkflowShared();
    await import("/static/pages/workflows/dashboard-shifts.js?v=" + STATIC_VERSION);
    await import("/static/pages/workflows/dashboard.js?v=" + STATIC_VERSION);

    const initializers = [
      shared.resolveWorkflowInitializer("initDashboardShiftRealtime"),
      shared.resolveWorkflowInitializer("initDailyCockpit")
    ];
    if (initializers.some((initializer) => typeof initializer !== "function")) {
      throw new Error("Dashboard runtime initializer is missing.");
    }
    for (const initializer of initializers) {
      await initializer();
    }
  }

  await initializeReactShellRuntime({
    mountedFlag: "maintenanceDashboardReactMounted",
    mountEvent: "maintenance-dashboard-react-mounted",
    fallbackSelector: "[data-react-dashboard-fallback]",
    timeoutMs: 900,
    initializeRuntime: initializeDashboardRuntime
  });
})();

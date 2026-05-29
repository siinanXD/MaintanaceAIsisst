(async function () {
  "use strict";

  const STATIC_VERSION = window.maintenanceStaticVersion || "dev";
  await import("/static/pages/react-island-loader.js?v=" + STATIC_VERSION);
  const { waitForReactIsland } = window.MaintenanceReactIslandLoader;

  /**
   * Report a tasks React mount failure without starting deleted legacy code.
   */
  function reportTasksMountFailure() {
    console.error("Tasks React island did not mount.");
  }

  const mounted = await waitForReactIsland({
    mountedFlag: "maintenanceTasksReactMounted",
    mountEvent: "maintenance-tasks-react-mounted"
  });

  if (!mounted) {
    reportTasksMountFailure();
  }
})();

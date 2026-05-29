(async function () {
  "use strict";

  const STATIC_VERSION = window.maintenanceStaticVersion || "dev";
  await import("/static/pages/react-island-loader.js?v=" + STATIC_VERSION);
  const { waitForReactIsland } = window.MaintenanceReactIslandLoader;

  /**
   * Report a vacations React mount failure without starting deleted legacy code.
   */
  function reportVacationsMountFailure() {
    console.error("Vacations React island did not mount.");
  }

  const mounted = await waitForReactIsland({
    mountedFlag: "maintenanceVacationsReactMounted",
    mountEvent: "maintenance-vacations-react-mounted"
  });

  if (!mounted) {
    reportVacationsMountFailure();
  }
})();

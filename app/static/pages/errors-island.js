(async function () {
  "use strict";

  const STATIC_VERSION = window.maintenanceStaticVersion || "dev";
  await import("/static/pages/react-island-loader.js?v=" + STATIC_VERSION);
  const { waitForReactIsland } = window.MaintenanceReactIslandLoader;

  /**
   * Report an errors React mount failure without starting deleted legacy code.
   */
  function reportErrorsMountFailure() {
    console.error("Errors React island did not mount.");
  }

  const mounted = await waitForReactIsland({
    mountedFlag: "maintenanceErrorsReactMounted",
    mountEvent: "maintenance-errors-react-mounted"
  });

  if (!mounted) {
    reportErrorsMountFailure();
  }
})();

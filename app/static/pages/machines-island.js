(async function () {
  "use strict";

  const STATIC_VERSION = window.maintenanceStaticVersion || "dev";
  await import("/static/pages/react-island-loader.js?v=" + STATIC_VERSION);
  const { waitForReactIsland } = window.MaintenanceReactIslandLoader;

  /**
   * Report a machines React mount failure without starting deleted legacy code.
   */
  function reportMachinesMountFailure() {
    console.error("Machines React island did not mount.");
  }

  const mounted = await waitForReactIsland({
    mountedFlag: "maintenanceMachinesReactMounted",
    mountEvent: "maintenance-machines-react-mounted"
  });

  if (!mounted) {
    reportMachinesMountFailure();
  }
})();

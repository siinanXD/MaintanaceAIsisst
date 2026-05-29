(async function () {
  "use strict";

  const STATIC_VERSION = window.maintenanceStaticVersion || "dev";
  await import("/static/pages/react-island-loader.js?v=" + STATIC_VERSION);
  const { waitForReactIsland } = window.MaintenanceReactIslandLoader;

  /**
   * Report an admin users React mount failure without starting deleted legacy code.
   */
  function reportAdminUsersMountFailure() {
    console.error("Admin users React island did not mount.");
  }

  const mounted = await waitForReactIsland({
    mountedFlag: "maintenanceAdminUsersReactMounted",
    mountEvent: "maintenance-admin-users-react-mounted"
  });

  if (!mounted) {
    reportAdminUsersMountFailure();
  }
})();

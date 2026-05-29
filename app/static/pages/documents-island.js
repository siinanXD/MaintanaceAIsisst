(async function () {
  "use strict";

  const STATIC_VERSION = window.maintenanceStaticVersion || "dev";
  await import("/static/pages/react-island-loader.js?v=" + STATIC_VERSION);
  const { waitForReactIsland } = window.MaintenanceReactIslandLoader;

  /**
   * Report a documents React mount failure without starting deleted legacy code.
   */
  function reportDocumentsMountFailure() {
    console.error("Documents React island did not mount.");
  }

  const mounted = await waitForReactIsland({
    mountedFlag: "maintenanceDocumentsReactMounted",
    mountEvent: "maintenance-documents-react-mounted"
  });

  if (!mounted) {
    reportDocumentsMountFailure();
  }
})();

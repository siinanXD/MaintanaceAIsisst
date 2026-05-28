(async function () {
  "use strict";

  const STATIC_VERSION = window.maintenanceStaticVersion || "dev";
  await import("/static/pages/react-island-loader.js?v=" + STATIC_VERSION);
  const { waitForReactIsland } = window.MaintenanceReactIslandLoader;

  /**
   * Load the existing Admin-AI runtime against the active page shell.
   *
   * @returns {Promise<void>} Resolves after the Admin-AI runtime has loaded.
   */
  async function initializeAdminAiRuntime() {
    await import("/static/pages/admin-ai.js?v=" + STATIC_VERSION);
  }

  /**
   * Return true when React owns the active canonical Admin-AI route.
   *
   * @returns {boolean} Whether the legacy runtime should stay unloaded.
   */
  function reactOwnsRuntimeRoute() {
    const pathname = window.location.pathname;
    return (
      pathname === "/admin/ai"
      || pathname === "/admin/ai/"
      || pathname === "/admin/ai/effectiveness"
      || pathname === "/admin/ai/prompt-faq"
    );
  }

  const reactMounted = await waitForReactIsland({
    mountedFlag: "maintenanceAdminAiReactMounted",
    mountEvent: "maintenance-admin-ai-react-mounted",
    fallbackSelector: "[data-react-admin-ai-fallback]",
    timeoutMs: 900
  });

  if (reactMounted && reactOwnsRuntimeRoute()) return;
  await initializeAdminAiRuntime();
})();

(async function () {
  /**
   * Load and initialize the route-specific workflow bundle.
   *
   * @returns {Promise<void>} Resolves after the current workflow page is initialized.
   */
  async function initializeWorkflowPage() {
    const staticVersion = window.maintenanceStaticVersion || "20260521-task-priority1";
    await import("/static/pages/workflows.js?v=" + encodeURIComponent(staticVersion));
    if (!window.maintenanceWorkflows || !window.maintenanceWorkflows.initCurrentWorkflowPage) {
      throw new Error("Workflow initializers are unavailable.");
    }
    await window.maintenanceWorkflows.initCurrentWorkflowPage();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializeWorkflowPage, { once: true });
    return;
  }
  await initializeWorkflowPage();
})();

(function bootstrapAdminAiPage() {
  const root = document.querySelector("[data-admin-ai-page]");
  if (!root) return;

  const AdminAI = {
    root,
    adminView: (root.dataset.aiAdminView || "overview").toLowerCase(),
    QUALITY_STATUS_OPTIONS: [
      "draft",
      "ai_suggested",
      "technician_confirmed",
      "admin_approved",
      "low_quality",
      "duplicate",
      "outdated",
      "rejected"
    ],
    state: {
      retrievalDebugItems: [],
      selectedRetrievalFlowId: null,
      currentKnowledgeNetworkPayload: null,
      latestAiStatus: null,
      latestAiSummary: null,
      latestKnowledgeStatus: null,
      latestRetrievalTelemetry: null,
      latestAiObservability: null,
      latestOperationsStatus: null,
      latestJobSummary: null,
      latestTrainingSummary: null,
      latestKnowledgeGaps: null
    }
  };
  window.MaintenanceAdminAI = AdminAI;

  const modules = [
    "shared",
    "overview",
    "knowledge",
    "retrieval",
    "observability",
    "operations",
    "actions"
  ];

  function moduleBaseUrl() {
    const currentScript = document.currentScript;
    if (!currentScript || !currentScript.src) return "/static/pages/admin-ai/";
    return currentScript.src.split("/static/pages/admin-ai.js")[0] + "/static/pages/admin-ai/";
  }

  function loadScript(name) {
    return new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = moduleBaseUrl() + name + ".js";
      script.defer = true;
      script.onload = resolve;
      script.onerror = () => reject(new Error("Admin-AI-Modul konnte nicht geladen werden: " + name));
      document.head.appendChild(script);
    });
  }

  async function start() {
    for (const name of modules) {
      await loadScript(name);
    }
    AdminAI.bindAdminAiActions();
    await AdminAI.refreshAll();
  }

  start().catch((error) => {
    if (AdminAI.setAdminMessage && AdminAI.safeErrorMessage) {
      AdminAI.setAdminMessage(
        AdminAI.safeErrorMessage(error, "KI-Administration konnte nicht vollst?ndig geladen werden"),
        true
      );
      return;
    }
    console.warn(error);
  });
})();

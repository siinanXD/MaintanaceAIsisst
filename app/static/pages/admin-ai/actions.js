/**
 * Admin AI actions module.
 * Registers view helpers on the shared MaintenanceAdminAI runtime.
 */
(function registerAdminAiModule(AdminAI) {
  const { root, adminView, state, QUALITY_STATUS_OPTIONS } = AdminAI;
  const api = (...args) => AdminAI.api(...args);
  const bind = (...args) => AdminAI.bind(...args);
  const loadAiStatus = (...args) => AdminAI.loadAiStatus(...args);
  const loadAiObservability = (...args) => AdminAI.loadAiObservability(...args);
  const loadAdminUserCosts = (...args) => AdminAI.loadAdminUserCosts(...args);
  const loadChats = (...args) => AdminAI.loadChats(...args);
  const loadEvents = (...args) => AdminAI.loadEvents(...args);
  const loadFaq = (...args) => AdminAI.loadFaq(...args);
  const loadFaqSuggestions = (...args) => AdminAI.loadFaqSuggestions(...args);
  const loadJobs = (...args) => AdminAI.loadJobs(...args);
  const loadKnowledge = (...args) => AdminAI.loadKnowledge(...args);
  const loadKnowledgeGaps = (...args) => AdminAI.loadKnowledgeGaps(...args);
  const loadKnowledgeNetwork = (...args) => AdminAI.loadKnowledgeNetwork(...args);
  const loadKnowledgeStatus = (...args) => AdminAI.loadKnowledgeStatus(...args);
  const loadOperationsMetrics = (...args) => AdminAI.loadOperationsMetrics(...args);
  const loadPrompts = (...args) => AdminAI.loadPrompts(...args);
  const loadResponseSnippets = (...args) => AdminAI.loadResponseSnippets(...args);
  const loadRetrievalDebug = (...args) => AdminAI.loadRetrievalDebug(...args);
  const loadRetrievalTelemetry = (...args) => AdminAI.loadRetrievalTelemetry(...args);
  const loadSummary = (...args) => AdminAI.loadSummary(...args);
  const loadTraining = (...args) => AdminAI.loadTraining(...args);
  const loadTrainingSummary = (...args) => AdminAI.loadTrainingSummary(...args);
  const qualityStatusLabel = (...args) => AdminAI.qualityStatusLabel(...args);
  const renderAnswerQualityGuide = (...args) => AdminAI.renderAnswerQualityGuide(...args);
  const renderCapabilities = (...args) => AdminAI.renderCapabilities(...args);
  const renderRetrievalFlow = (...args) => AdminAI.renderRetrievalFlow(...args);
  const resetTrainingForm = (...args) => AdminAI.resetTrainingForm(...args);
  const runAdminLoad = (...args) => AdminAI.runAdminLoad(...args);
  const safeErrorMessage = (...args) => AdminAI.safeErrorMessage(...args);
  const selectedRetrievalFlowItem = (...args) => AdminAI.selectedRetrievalFlowItem(...args);
  const setAdminMessage = (...args) => AdminAI.setAdminMessage(...args);
  const setButtonBusy = (...args) => AdminAI.setButtonBusy(...args);
  const setFormBusy = (...args) => AdminAI.setFormBusy(...args);
  const setHealthCard = (...args) => AdminAI.setHealthCard(...args);
  const runSourceTest = (...args) => AdminAI.runSourceTest(...args);
  const submitSourceTestFeedback = (...args) => AdminAI.submitSourceTestFeedback(...args);
  const createFaqFromSourceTest = (...args) => AdminAI.createFaqFromSourceTest(...args);
  const trainingPayload = (...args) => AdminAI.trainingPayload(...args);
  const runPromptDryRun = (...args) => AdminAI.runPromptDryRun(...args);

  function adminLoader(label, loader, statusKey) {
    return { label, loader, statusKey };
  }

  function markAdminLoaderFailure(item, error) {
    if (!item.statusKey) return;
    const status = Number(error && error.status);
    const endpoint = error && error.path ? String(error.path).split("?")[0] : "";
    const detail = [
      status ? "Status " + status : "Ladefehler",
      endpoint
    ].filter(Boolean).join(" - ");
    setHealthCard(item.statusKey, "critical", detail);
  }

  function adminLoadersForView() {
  const loadersByView = {
    overview: [
      adminLoader("AI-Status", loadAiStatus, "ai"),
      adminLoader("AI-Zusammenfassung", loadSummary),
      adminLoader("Wissenslücken", loadKnowledgeGaps),
      adminLoader("RAG-Status", loadKnowledgeStatus, "rag"),
      adminLoader("Betriebsmetriken", loadOperationsMetrics, "queue")
    ],
    rag_board: [
      adminLoader("AI-Status", loadAiStatus, "ai"),
      adminLoader("RAG-Status", loadKnowledgeStatus, "rag"),
      adminLoader("Training-Zusammenfassung", loadTrainingSummary),
      adminLoader("Training", loadTraining),
      adminLoader("Wissensquellen", loadKnowledge),
      adminLoader("Wissensnetz", loadKnowledgeNetwork),
      adminLoader("Wissenslücken", loadKnowledgeGaps),
      adminLoader("AI-Zusammenfassung", loadSummary),
      adminLoader("Index-Jobs", loadJobs, "queue"),
      adminLoader("Betriebsmetriken", loadOperationsMetrics),
      adminLoader("Retrieval-Telemetrie", loadRetrievalTelemetry)
    ],
    source_check: [
      adminLoader("Prompts", loadPrompts, "prompts"),
      adminLoader("RAG-Status", loadKnowledgeStatus, "rag"),
      adminLoader("AI-Zusammenfassung", loadSummary)
    ],
    prompt_faq: [
      adminLoader("Prompts", loadPrompts, "prompts"),
      adminLoader("FAQ", loadFaq),
      adminLoader("FAQ-Vorschläge", loadFaqSuggestions),
      adminLoader("Antwortbausteine", loadResponseSnippets)
    ],
    effectiveness: [
      adminLoader("AI-Zusammenfassung", loadSummary),
      adminLoader("Nutzerkosten", loadAdminUserCosts),
      adminLoader("Retrieval-Telemetrie", loadRetrievalTelemetry),
      adminLoader("Wissenslücken", loadKnowledgeGaps),
      adminLoader("Observability", loadAiObservability, "ai")
    ],
    technical: [
      adminLoader("AI-Status", loadAiStatus, "ai"),
      adminLoader("AI-Zusammenfassung", loadSummary),
      adminLoader("Retrieval-Debug", loadRetrievalDebug),
      adminLoader("Retrieval-Telemetrie", loadRetrievalTelemetry),
      adminLoader("RAG-Status", loadKnowledgeStatus, "rag"),
      adminLoader("Wissenslücken", loadKnowledgeGaps),
      adminLoader("Observability", loadAiObservability),
      adminLoader("Index-Jobs", loadJobs, "queue"),
      adminLoader("Betriebsmetriken", loadOperationsMetrics)
    ]
  };
  return loadersByView[adminView] || loadersByView.overview;
  }

  async function refreshAll() {
  renderCapabilities();
  renderAnswerQualityGuide();
  const loaders = adminLoadersForView();
  const results = await Promise.allSettled(loaders.map((item) => item.loader()));
  const failedResults = results
    .map((result, index) => ({ ...result, item: loaders[index] }))
    .filter((result) => result.status === "rejected");
  if (!failedResults.length) return;
  failedResults.forEach((result) => markAdminLoaderFailure(result.item, result.reason));
  const firstFailure = failedResults[0];
  const context = failedResults.length === 1
    ? firstFailure.item.label + " konnte nicht geladen werden"
    : failedResults.length + " KI-Admin-Bereiche konnten nicht geladen werden";
  const message = safeErrorMessage(
    firstFailure.reason,
    context
  );
  setAdminMessage(message, true);
  if (window.console && window.console.warn) {
    window.console.warn("admin_ai_partial_load", failedResults.map((result) => ({
      area: result.item.label,
      endpoint: result.reason && result.reason.path,
      status: result.reason && result.reason.status
    })));
  }
  }

  function bindAdminAiActions() {
  bind("[data-ai-event-error]", "change", () => {
    runAdminLoad(loadEvents, "AI-Fehler laden");
  });
  bind("[data-ai-chat-search]", "input", () => {
    window.clearTimeout(root._chatTimer);
    root._chatTimer = window.setTimeout(() => runAdminLoad(loadChats, "AI-Anfragen laden"), 250);
  });
  bind("[data-ai-training-search]", "input", () => {
    window.clearTimeout(root._trainingTimer);
    root._trainingTimer = window.setTimeout(() => runAdminLoad(loadTraining, "Training laden"), 250);
  });
  bind("[data-ai-training-active]", "change", () => {
    runAdminLoad(loadTraining, "Training laden");
  });
  bind("[data-ai-lab-form]", "submit", async (event) => {
    event.preventDefault();
    await runAdminLoad(() => runPromptDryRun(event.currentTarget), "Prompt Dry-run");
  });
  bind("[data-ai-source-test-form]", "submit", async (event) => {
    event.preventDefault();
    const submitter = event.submitter;
    const intent = submitter && submitter.value ? submitter.value : undefined;
    await runAdminLoad(() => runSourceTest(event.currentTarget, intent), "Quellenprüfung");
  });
  bind("[data-ai-source-reset]", "click", () => {
    const form = root.querySelector("[data-ai-source-test-form]");
    if (form) form.reset();
    state.latestSourceTest = null;
    const answer = root.querySelector("[data-ai-source-test-answer]");
    const meta = root.querySelector("[data-ai-lab-meta]");
    const actions = root.querySelector("[data-ai-source-test-actions]");
    if (answer) answer.textContent = "Wähle Dry-run für Prompt-/Kontextprüfung oder Live für eine echte Antwort mit Quellen.";
    if (meta) meta.textContent = "Noch kein Test ausgeführt.";
    if (actions) actions.hidden = true;
    root.querySelectorAll("[data-ai-source-test-kpi]").forEach((target) => {
      target.textContent = target.dataset.aiSourceTestKpi === "confidence" ? "-" : "0";
    });
  });
  bind("[data-ai-prompt-version-form]", "submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const payload = Object.fromEntries(new FormData(form).entries());
    const templateId = payload.template_id;
    const status = root.querySelector("[data-ai-prompt-form-status]");
    if (!templateId) return;
    await api("/api/v1/admin/ai/prompts/" + templateId + "/versions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (status) status.textContent = "Entwurf gespeichert";
    form.reset();
    await loadPrompts();
  });
  bind("[data-ai-faq-form]", "submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const payload = Object.fromEntries(new FormData(form).entries());
    payload.status = "draft";
    payload.source = "manual";
    await api("/api/v1/admin/ai/faq", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    form.reset();
    await Promise.all([loadFaq(), loadFaqSuggestions()]);
  });
  bind("[data-ai-training-reset]", "click", resetTrainingForm);
  bind("[data-ai-knowledge-search]", "input", () => {
    window.clearTimeout(root._knowledgeTimer);
    root._knowledgeTimer = window.setTimeout(() => runAdminLoad(loadKnowledge, "Wissen laden"), 250);
  });
  bind("[data-ai-knowledge-source]", "change", () => {
    runAdminLoad(loadKnowledge, "Wissen laden");
  });
  bind("[data-ai-knowledge-status]", "change", () => {
    runAdminLoad(loadKnowledge, "Wissen laden");
  });
  bind("[data-ai-knowledge-quality]", "change", () => {
    runAdminLoad(loadKnowledge, "Wissen laden");
  });
  bind("[data-knowledge-network-search]", "input", () => {
    window.clearTimeout(root._knowledgeNetworkTimer);
    root._knowledgeNetworkTimer = window.setTimeout(() => runAdminLoad(loadKnowledgeNetwork, "Wissensnetz laden"), 250);
  });
  bind("[data-knowledge-network-focus]", "input", () => {
    window.clearTimeout(root._knowledgeNetworkFocusTimer);
    root._knowledgeNetworkFocusTimer = window.setTimeout(() => runAdminLoad(loadKnowledgeNetwork, "Wissensnetz laden"), 250);
  });
  bind("[data-knowledge-network-source]", "change", () => {
    runAdminLoad(loadKnowledgeNetwork, "Wissensnetz laden");
  });
  bind("[data-knowledge-network-quality]", "change", () => {
    runAdminLoad(loadKnowledgeNetwork, "Wissensnetz laden");
  });
  bind("[data-knowledge-network-focus-type]", "change", () => {
    runAdminLoad(loadKnowledgeNetwork, "Wissensnetz laden");
  });
  bind("[data-knowledge-network-refresh]", "click", () => {
    runAdminLoad(loadKnowledgeNetwork, "Wissensnetz laden");
  });
  bind("[data-retrieval-debug-search]", "input", () => {
    window.clearTimeout(root._retrievalDebugTimer);
    root._retrievalDebugTimer = window.setTimeout(() => runAdminLoad(loadRetrievalDebug, "Quellenabruf Debug laden"), 250);
  });
  bind("[data-retrieval-debug-type]", "change", () => {
    runAdminLoad(loadRetrievalDebug, "Quellenabruf Debug laden");
  });
  bind("[data-retrieval-debug-refresh]", "click", () => {
    runAdminLoad(loadRetrievalDebug, "Quellenabruf Debug laden");
  });
  bind("[data-retrieval-evaluation-run]", "click", () => {
    runAdminLoad(runRetrievalEvaluation, "Golden Eval ausfuehren");
  });
  bind("[data-ai-observability-refresh]", "click", () => {
    runAdminLoad(loadAiObservability, "Monitoring aktualisieren");
  });
  bind("[data-ai-debug-request]", "change", (event) => {
    loadAiObservability(event.currentTarget.value)
      .catch((error) => setAdminMessage(safeErrorMessage(error, "Debug laden"), true));
  });
  bind("[data-ai-observability-logs]", "click", (event) => {
    const button = event.target.closest("[data-ai-debug-select]");
    if (!button) return;
    loadAiObservability(button.dataset.aiDebugSelect)
      .catch((error) => setAdminMessage(safeErrorMessage(error, "Debug laden"), true));
  });
  bind("[data-retrieval-debug-rows]", "click", (event) => {
    const button = event.target.closest("[data-retrieval-flow-select]");
    if (!button) return;
    state.selectedRetrievalFlowId = Number(button.dataset.retrievalFlowSelect);
    renderRetrievalFlow(selectedRetrievalFlowItem());
    root.querySelectorAll("[data-retrieval-debug-rows] tr").forEach((row) => {
      const rowButton = row.querySelector("[data-retrieval-flow-select]");
      row.classList.toggle(
        "is-selected",
        Boolean(rowButton) && Number(rowButton.dataset.retrievalFlowSelect) === state.selectedRetrievalFlowId
      );
    });
  });
  bind("[data-ai-training-form]", "submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const entryId = form.elements.id.value;
    const path = entryId
      ? "/api/v1/admin/ai/training/" + entryId
      : "/api/v1/admin/ai/training";
    const method = entryId ? "PUT" : "POST";
    setFormBusy(form, true, "Speichert...");
    setAdminMessage(entryId ? "Training wird aktualisiert..." : "Training wird gespeichert...");
    try {
      await api(path, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(trainingPayload(form))
      });
      resetTrainingForm();
      setAdminMessage("Training gespeichert. Bitte veraltete Quellen indexieren.");
      await Promise.all([
        loadTrainingSummary(),
        loadTraining(),
        loadKnowledge(),
        loadKnowledgeNetwork(),
        loadKnowledgeStatus()
      ]);
    } catch (error) {
      setAdminMessage(safeErrorMessage(error, "Training speichern"), true);
    } finally {
      setFormBusy(form, false);
    }
  });
  async function runReindex(button, path) {
    button.disabled = true;
    setAdminMessage("Index wird neu aufgebaut...");
    try {
      const result = await api(path, { method: "POST" });
      setAdminMessage(
        "Indexiert: " + result.indexed + " Dokumente, " + result.chunks + " Textabschnitte."
      );
      await Promise.all([
        loadKnowledge(),
        loadKnowledgeNetwork(),
        loadKnowledgeStatus(),
        loadJobs(),
        loadOperationsMetrics()
      ]);
    } catch (error) {
      setAdminMessage(safeErrorMessage(error, "Reindex ausführen"), true);
    } finally {
      button.disabled = false;
    }
  }

  bind("[data-ai-reindex]", "click", async () => {
    await runReindex(
      root.querySelector("[data-ai-reindex]"),
      "/api/v1/admin/ai/knowledge/reindex"
    );
  });
  bind("[data-ai-reindex-stale]", "click", async () => {
    await runReindex(
      root.querySelector("[data-ai-reindex-stale]"),
      "/api/v1/admin/ai/knowledge/reindex?mode=stale"
    );
  });
  bind("[data-ai-queue-stale]", "click", async () => {
    const button = root.querySelector("[data-ai-queue-stale]");
    setButtonBusy(button, true, "Plant...");
    setAdminMessage("RAG-Reindex-Job wird eingeplant...");
    try {
      const job = await api("/api/v1/admin/ai/knowledge/reindex/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: "stale" })
      });
      setAdminMessage("Job #" + job.id + " wurde eingeplant.");
      await Promise.all([loadJobs(), loadOperationsMetrics()]);
    } catch (error) {
      setAdminMessage(safeErrorMessage(error, "Reindex-Job einplanen"), true);
    } finally {
      setButtonBusy(button, false);
    }
  });
  bind("[data-ai-knowledge-upload]", "submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    setFormBusy(event.currentTarget, true, "Lädt...");
    setAdminMessage("Dokument wird hochgeladen...");
    try {
      await api("/api/v1/admin/ai/knowledge/upload", { method: "POST", body: formData });
      event.currentTarget.reset();
      setAdminMessage("Dokument hochgeladen und indexiert.");
      await Promise.all([
        loadKnowledge(),
        loadKnowledgeNetwork(),
        loadKnowledgeStatus(),
        loadJobs(),
        loadOperationsMetrics()
      ]);
    } catch (error) {
      setAdminMessage(safeErrorMessage(error, "Dokument hochladen"), true);
    } finally {
      setFormBusy(event.currentTarget, false);
    }
  });
  root.addEventListener("click", async (event) => {
    const approveFaqButton = event.target.closest("[data-approve-faq]");
    if (approveFaqButton) {
      setButtonBusy(approveFaqButton, true, "Freigibt...");
      try {
        await api("/api/v1/admin/ai/faq/" + approveFaqButton.dataset.approveFaq + "/approve", {
          method: "POST"
        });
        setAdminMessage("FAQ freigegeben und fuer den Index vorgemerkt.");
        await Promise.all([loadFaq(), loadKnowledgeStatus()]);
      } catch (error) {
        setAdminMessage(safeErrorMessage(error, "FAQ freigeben"), true);
      } finally {
        setButtonBusy(approveFaqButton, false);
      }
      return;
    }

    const sourceFeedbackButton = event.target.closest("[data-ai-source-feedback]");
    if (sourceFeedbackButton) {
      setButtonBusy(sourceFeedbackButton, true, "Speichert...");
      try {
        await submitSourceTestFeedback(sourceFeedbackButton.dataset.aiSourceFeedback);
        setAdminMessage("Quellenprüfung bewertet.");
        await Promise.all([loadSummary(), loadRetrievalTelemetry()]);
      } catch (error) {
        setAdminMessage(safeErrorMessage(error, "Quellenprüfung bewerten"), true);
      } finally {
        setButtonBusy(sourceFeedbackButton, false);
      }
      return;
    }

    const sourceFaqButton = event.target.closest("[data-ai-source-create-faq]");
    if (sourceFaqButton) {
      setButtonBusy(sourceFaqButton, true, "Erstellt...");
      try {
        await createFaqFromSourceTest();
        setAdminMessage("FAQ-Entwurf aus der Testfrage erstellt.");
        await Promise.all([loadFaq(), loadFaqSuggestions()]);
      } catch (error) {
        setAdminMessage(safeErrorMessage(error, "FAQ aus Quellenprüfung erstellen"), true);
      } finally {
        setButtonBusy(sourceFaqButton, false);
      }
      return;
    }

    const missingSourceButton = event.target.closest("[data-ai-source-missing]");
    if (missingSourceButton) {
      setButtonBusy(missingSourceButton, true, "Markiert...");
      try {
        await submitSourceTestFeedback("not_helpful", "Quelle fehlt laut KI-Admin Quellenprüfung");
        setAdminMessage("Fehlende Quelle als negatives Feedback markiert.");
        await Promise.all([loadSummary(), loadKnowledgeGaps(), loadRetrievalTelemetry()]);
      } catch (error) {
        setAdminMessage(safeErrorMessage(error, "Fehlende Quelle markieren"), true);
      } finally {
        setButtonBusy(missingSourceButton, false);
      }
      return;
    }

    const trainingDeleteButton = event.target.closest("[data-delete-training]");
    if (trainingDeleteButton) {
      setButtonBusy(trainingDeleteButton, true, "Löscht...");
      try {
        await api("/api/v1/admin/ai/training/" + trainingDeleteButton.dataset.deleteTraining, {
          method: "DELETE"
        });
        setAdminMessage("Training gelöscht.");
        await Promise.all([
          loadTrainingSummary(),
          loadTraining(),
          loadKnowledge(),
          loadKnowledgeNetwork(),
          loadKnowledgeStatus()
        ]);
      } catch (error) {
        setAdminMessage(safeErrorMessage(error, "Training löschen"), true);
      } finally {
        setButtonBusy(trainingDeleteButton, false);
      }
      return;
    }

    const qualityButton = event.target.closest("[data-update-knowledge-quality]");
    if (qualityButton) {
      const row = qualityButton.closest("tr");
      const select = row && row.querySelector("[data-knowledge-quality-select]");
      if (!select) return;
      setButtonBusy(qualityButton, true, "Speichert...");
      setAdminMessage("Wissens-Qualitätsstatus wird aktualisiert...");
      try {
        const documentItem = await api(
          "/api/v1/admin/ai/knowledge/"
          + qualityButton.dataset.updateKnowledgeQuality
          + "/quality-status",
          {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ quality_status: select.value })
          }
        );
        setAdminMessage(
          "Wissen #" + documentItem.id + " ist "
          + qualityStatusLabel(documentItem.quality_status) + "."
        );
        await Promise.all([
          loadKnowledge(),
          loadKnowledgeNetwork(),
          loadKnowledgeStatus(),
          loadOperationsMetrics()
        ]);
      } catch (error) {
        setAdminMessage(safeErrorMessage(error, "Qualitätsstatus setzen"), true);
      } finally {
        setButtonBusy(qualityButton, false);
      }
      return;
    }

    const reindexButton = event.target.closest("[data-reindex-knowledge]");
    if (reindexButton) {
      reindexButton.disabled = true;
      setAdminMessage("Dokument wird neu indexiert...");
      try {
        const documentItem = await api(
          "/api/v1/admin/ai/knowledge/" + reindexButton.dataset.reindexKnowledge + "/reindex",
          { method: "POST" }
        );
        setAdminMessage(
          "Dokument " + documentItem.id + " ist " + documentItem.status + "."
        );
        await Promise.all([
          loadKnowledge(),
          loadKnowledgeNetwork(),
          loadKnowledgeStatus(),
          loadJobs(),
          loadOperationsMetrics()
        ]);
      } catch (error) {
        setAdminMessage(safeErrorMessage(error, "Dokument reindexieren"), true);
      } finally {
        reindexButton.disabled = false;
      }
      return;
    }

    const queueButton = event.target.closest("[data-queue-knowledge]");
    if (queueButton) {
      setButtonBusy(queueButton, true, "Plant...");
      setAdminMessage("Dokument-Reindex-Job wird eingeplant...");
      try {
        const job = await api("/api/v1/admin/ai/knowledge/reindex/jobs", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ document_id: Number(queueButton.dataset.queueKnowledge) })
        });
        setAdminMessage("Job #" + job.id + " wurde eingeplant.");
        await Promise.all([loadJobs(), loadOperationsMetrics()]);
      } catch (error) {
        setAdminMessage(safeErrorMessage(error, "Dokument-Job einplanen"), true);
      } finally {
        setButtonBusy(queueButton, false);
      }
      return;
    }

    const button = event.target.closest("[data-delete-knowledge]");
    if (!button) return;
    setButtonBusy(button, true, "Löscht...");
    try {
      await api("/api/v1/admin/ai/knowledge/" + button.dataset.deleteKnowledge, { method: "DELETE" });
      setAdminMessage("Dokument gelöscht.");
      await Promise.all([
        loadKnowledge(),
        loadKnowledgeNetwork(),
        loadKnowledgeStatus(),
        loadJobs(),
        loadOperationsMetrics()
      ]);
    } catch (error) {
      setAdminMessage(safeErrorMessage(error, "Dokument löschen"), true);
    } finally {
      setButtonBusy(button, false);
    }
  });
  }
  Object.assign(AdminAI, { adminLoadersForView, refreshAll, bindAdminAiActions });
})(window.MaintenanceAdminAI);

/**
 * Admin AI overview module.
 * Registers view helpers on the shared MaintenanceAdminAI runtime.
 */
(function registerAdminAiModule(AdminAI) {
  const { root, adminView, state, QUALITY_STATUS_OPTIONS } = AdminAI;
  const dateTimeText = (...args) => AdminAI.dateTimeText(...args);
  const healthClass = (...args) => AdminAI.healthClass(...args);
  const numberText = (...args) => AdminAI.numberText(...args);
  const percentText = (...args) => AdminAI.percentText(...args);
  const readinessLabel = (...args) => AdminAI.readinessLabel(...args);
  const recordReference = (...args) => AdminAI.recordReference(...args);
  const sourceTypeLabel = (...args) => AdminAI.sourceTypeLabel(...args);
  const statusRow = (...args) => AdminAI.statusRow(...args);
  const text = (...args) => AdminAI.text(...args);
  function setOverviewStatus(key, label, detail, status) {
    const card = root.querySelector('[data-ai-status-overview-item="' + key + '"]');
    if (!card) return;
    card.classList.remove("is-active", "is-stale", "is-error", "is-muted");
    card.classList.add(status === "muted" ? "is-muted" : healthClass(status));
    const labelTarget = card.querySelector("[data-ai-status-overview-label]");
    const detailTarget = card.querySelector("[data-ai-status-overview-detail]");
    if (labelTarget) labelTarget.textContent = label;
    if (detailTarget) detailTarget.textContent = detail;
  }

  /**
   * Render the cross-section status line from already loaded AI, RAG, telemetry, and job data.
   */
  function renderStatusOverview() {
    if (!root.querySelector("[data-ai-status-overview]")) return;
    const aiLoaded = Boolean(state.latestAiStatus);
    const aiReady = aiLoaded && state.latestAiStatus.ready !== false;
    const providerName = String((state.latestAiStatus && state.latestAiStatus.provider) || "").toLowerCase();
    const modelName = String((state.latestAiStatus && state.latestAiStatus.model) || "").toLowerCase();
    const openAiConfigured = providerName.includes("openai") || modelName.includes("gpt");
    const fallbackRate = state.latestAiSummary && state.latestAiSummary.fallback_rate != null
      ? Number(state.latestAiSummary.fallback_rate || 0)
      : Number(latestSloValues().fallback_rate || 0);
    const fallbackActive = (aiLoaded && !aiReady) || fallbackRate > 0;
    const knowledgeLoaded = Boolean(state.latestKnowledgeStatus);
    const diagnostics = (state.latestKnowledgeStatus && state.latestKnowledgeStatus.diagnostics) || {};
    const ragScore = Number((state.latestKnowledgeStatus || {}).readiness_score || 0);
    const ragReady = knowledgeLoaded && (
      diagnostics.ready === true
      || (diagnostics.ready == null && ragScore >= 60)
    );
    const latestJob = state.latestJobSummary && state.latestJobSummary.latestJob;
    const latestJobStatus = latestJob && latestJob.status;
    const latestJobTone = latestJobStatus === "failed"
      ? "critical"
      : (latestJobStatus === "queued" || latestJobStatus === "running" ? "warning" : "ok");

    setOverviewStatus(
      "ai",
      aiLoaded ? (aiReady ? "aktiv" : "inaktiv") : "Wird geladen",
      aiLoaded ? "Anbieterstatus aus /api/v1/ai/status" : "Status wird geladen",
      aiLoaded ? (aiReady ? "ok" : "critical") : "muted"
    );
    setOverviewStatus(
      "openai",
      !aiLoaded
        ? "Wird geladen"
        : (openAiConfigured ? (aiReady ? "verfügbar" : "nicht verfügbar") : "nicht konfiguriert"),
      !aiLoaded
        ? "Provider wird geladen"
        : ((state.latestAiStatus.provider || "lokal") + " / " + (state.latestAiStatus.model || "lokal")),
      !aiLoaded ? "muted" : (openAiConfigured ? (aiReady ? "ok" : "critical") : "muted")
    );
    setOverviewStatus(
      "fallback",
      fallbackActive ? "aktiv" : "inaktiv",
      "Fallback-Rate " + percentText(fallbackRate),
      fallbackActive ? "warning" : "ok"
    );
    setOverviewStatus(
      "rag",
      knowledgeLoaded ? (ragReady ? "verfügbar" : "nicht verfügbar") : "Wird geladen",
      knowledgeLoaded ? ("Bereitschaft " + ragScore + "/100") : "RAG-Status wird geladen",
      knowledgeLoaded ? (ragReady ? "ok" : (ragScore >= 40 ? "warning" : "critical")) : "muted"
    );
    setOverviewStatus(
      "reindex",
      latestJob ? text(latestJobStatus) : "kein Job",
      latestJob
        ? ("Job #" + latestJob.id + " - " + dateTimeText(latestJob.updated_at || latestJob.created_at))
        : "Noch kein Reindex-Job vorhanden",
      latestJob ? latestJobTone : "muted"
    );
  }

  /**
   * Update a compact section badge with the shared AI health visual language.
   */
  function setSectionStatus(key, label, status) {
    const target = root.querySelector('[data-ai-section-status="' + key + '"]');
    if (!target) return;
    target.textContent = label;
    target.className = "badge badge-ai " + healthClass(status);
  }

  /**
   * Set text for a single optional target without requiring every section to exist.
   */
  function setOptionalText(selector, value) {
    const target = root.querySelector(selector);
    if (target) target.textContent = text(value);
  }

  /**
   * Return the source-type row from the latest RAG status for one source type.
   */
  function sourceTypeStatus(sourceType) {
    const status = state.latestKnowledgeStatus || {};
    return (status.source_types || []).find((item) => item.source_type === sourceType) || {};
  }

  /**
   * Return a safe integer field from the latest SLO payload.
   */
  function sloCount(key) {
    return Number(latestSloValues()[key] || 0);
  }

  /**
   * Return a display label for one AI feedback rating.
   */
  function feedbackRatingLabel(rating) {
    const labels = {
      helpful: "hilfreich",
      partially_helpful: "teilweise",
      not_helpful: "nicht hilfreich"
    };
    return labels[rating] || text(rating || "unbewertet");
  }

  /**
   * Render one compact card in the KI-Administration overview.
   */
  function renderClarityCard(target, label, value, detail, status) {
    const card = document.createElement("article");
    const labelElement = document.createElement("span");
    const valueElement = document.createElement("strong");
    const detailElement = document.createElement("small");
    card.className = "ai-clarity-card " + (status === "muted" ? "is-muted" : healthClass(status));
    labelElement.textContent = label;
    valueElement.textContent = value;
    detailElement.textContent = detail;
    card.append(labelElement, valueElement, detailElement);
    target.appendChild(card);
  }

  /**
   * Replace one stats-list with a title and privacy-safe rows.
   */
  function renderClarityList(selector, title, rows, emptyText) {
    const target = root.querySelector(selector);
    if (!target) return;
    target.innerHTML = "";
    const heading = document.createElement("div");
    const headingTitle = document.createElement("strong");
    heading.className = "ai-clarity-list-header";
    headingTitle.textContent = title;
    heading.appendChild(headingTitle);
    target.appendChild(heading);
    if (!rows.length) {
      target.appendChild(statusRow(title, emptyText));
      return;
    }
    rows.forEach(([label, value]) => target.appendChild(statusRow(label, value)));
  }

  /**
   * Render the one-screen KI-Administration overview from already loaded API payloads.
   */
  function renderAiClaritySummary() {
    const target = root.querySelector("[data-ai-clarity-summary]");
    if (!target) return;
    const status = state.latestKnowledgeStatus || {};
    const lifecycle = status.lifecycle || {};
    const qualityGate = lifecycle.rag_quality_gate || {};
    const vectorStore = status.vector_store || {};
    const feedback = (state.latestAiSummary && state.latestAiSummary.feedback) || {};
    const trainingItems = (state.latestTrainingSummary && state.latestTrainingSummary.items) || [];
    const activeTraining = trainingItems.filter((item) => item.is_active);
    const manualTrainingQuelle = sourceTypeStatus("manual_training");
    const gaps = state.latestKnowledgeGaps || {};
    const sourceTypes = status.source_types || [];
    const indexed = Number(status.indexed || lifecycle.indexed_documents || 0);
    const searchable = Number(status.searchable_documents || 0);
    const chunks = Number(status.chunks || 0);
    const missingTextabschnitte = Number(vectorStore.missing_chunk_count || 0);
    const chunkMismatches = Number(vectorStore.chunk_mismatch_count || 0);
    const permissionFiltered = sloCount("permission_filtered_candidate_count");
    const qualityBlocked = Number(qualityGate.quality_blocked_indexed_documents || 0);
    const openGaps = Number(gaps.open_count || lifecycle.knowledge_gaps_open || 0);
    const feedbackTotal = Number(feedback.total || 0);
    const negativeFeedback = Number(feedback.not_helpful || 0);
    const clarityState = root.querySelector("[data-ai-clarity-state]");
    const blockedTotal = permissionFiltered + qualityBlocked;
    const hasWarnings = openGaps || blockedTotal || negativeFeedback || missingTextabschnitte || chunkMismatches;
    const hasCritical = openGaps >= 5 || blockedTotal >= 10 || qualityBlocked >= 5;

    target.innerHTML = "";
    renderClarityCard(
      target,
      "Indexierte Quellen",
      numberText(indexed) + " / " + numberText(searchable),
      sourceTypes.length + " Quelltypen mit RAG-Status",
      indexed && searchable ? "ok" : (indexed ? "warning" : "muted")
    );
    renderClarityCard(
      target,
      "Aktive Textabschnitte",
      numberText(chunks),
      missingTextabschnitte + chunkMismatches
        ? numberText(missingTextabschnitte + chunkMismatches) + " Textabschnitt-Probleme"
        : "Textabschnitt-Zaehlung konsistent",
      missingTextabschnitte || chunkMismatches ? "warning" : (chunks ? "ok" : "muted")
    );
    renderClarityCard(
      target,
      "Aktive Trainingsdaten",
      numberText(activeTraining.length),
      numberText(manualTrainingQuelle.chunks || 0) + " Training-Textabschnitte im Index",
      activeTraining.length ? "ok" : "muted"
    );
    renderClarityCard(
      target,
      "Fehlgeschlagene Fragen",
      numberText(openGaps),
      "Offene Wissenslücken aus KI-Fragen",
      openGaps ? "warning" : "ok"
    );
    renderClarityCard(
      target,
      "Geblockte Quelles",
      numberText(blockedTotal),
      "Permission-Filter und Quality-Gate",
      blockedTotal ? "warning" : "ok"
    );
    renderClarityCard(
      target,
      "Letzte Feedbacks",
      numberText(feedbackTotal),
      feedback.helpful_rate == null
        ? "Noch keine Bewertungsrate"
        : "Hilfreich " + percentText(feedback.helpful_rate),
      negativeFeedback ? "warning" : (feedbackTotal ? "ok" : "muted")
    );

    if (clarityState) {
      clarityState.textContent = hasCritical ? "Handlungsbedarf" : (hasWarnings ? "Beobachten" : "klar");
      clarityState.className = "status-pill " + (hasCritical ? "is-error" : (hasWarnings ? "is-stale" : "is-active"));
    }

    renderIndexedQuelleSummary(sourceTypes);
    renderTextabschnittSummary(status, vectorStore);
    renderTrainingSummary(trainingItems, manualTrainingQuelle);
    renderFailureSummary(gaps);
    renderBlockedQuelleSummary(permissionFiltered, qualityBlocked, lifecycle);
    renderFeedbackSummary(feedback);
  }

  /**
   * Render indexed source-type coverage.
   */
  function renderIndexedQuelleSummary(sourceTypes) {
    const rows = (sourceTypes || []).slice(0, 8).map((item) => [
      sourceTypeLabel(item.source_type),
      numberText(item.searchable_documents || 0) + "/"
        + numberText(item.documents || 0) + " suchbar, "
        + numberText(item.chunks || 0) + " Textabschnitte"
    ]);
    renderClarityList(
      "[data-ai-indexed-source-summary]",
      "Indexierte Quellen",
      rows,
      "Noch keine indexierten Quellen vorhanden."
    );
  }

  /**
   * Render active chunk and vector-store consistency information.
   */
  function renderTextabschnittSummary(status, vectorStore) {
    const rows = [
      ["Aktive Textabschnitte", numberText(status.chunks || 0)],
      ["Durchsuchbare Dokumente", numberText(status.searchable_documents || 0)],
      ["Soll Vektoren", numberText(vectorStore.expected_vector_count || 0)],
      ["Ist Vektoren", vectorStore.actual_vector_count == null ? "-" : numberText(vectorStore.actual_vector_count)],
      ["Fehlende Textabschnitte", numberText(vectorStore.missing_chunk_count || 0)],
      ["Textabschnitt-Mismatch", numberText(vectorStore.chunk_mismatch_count || 0)]
    ];
    renderClarityList(
      "[data-ai-active-chunk-summary]",
      "Aktive Textabschnitte",
      rows,
      "Noch keine Textabschnitt-Daten geladen."
    );
  }

  /**
   * Render active manual training coverage.
   */
  function renderTrainingSummary(trainingItems, manualTrainingQuelle) {
    const activeTraining = (trainingItems || []).filter((item) => item.is_active);
    const inactiveTraining = (trainingItems || []).length - activeTraining.length;
    const rows = [
      ["Aktiv", numberText(activeTraining.length)],
      ["Inaktiv", numberText(inactiveTraining)],
      ["Index-Dokumente", numberText(manualTrainingQuelle.documents || 0)],
      ["Suchbar", numberText(manualTrainingQuelle.searchable_documents || 0)],
      ["Training-Textabschnitte", numberText(manualTrainingQuelle.chunks || 0)]
    ];
    activeTraining.slice(0, 3).forEach((entry) => {
      rows.push([
        recordReference("Training", entry.id),
        text(entry.category || "wartung") + " - Prioritaet " + numberText(entry.priority || 0)
      ]);
    });
    renderClarityList(
      "[data-ai-training-summary]",
      "Trainingsdaten",
      rows,
      "Noch keine Trainingsdaten vorhanden."
    );
  }

  /**
   * Render failing AI question signals without exposing raw questions.
   */
  function renderFailureSummary(gaps) {
    const values = latestSloValues();
    const rows = [
      ["Offene Gaps", numberText((gaps && gaps.open_count) || 0)],
      ["Ohne Quellen", percentText(values.no_source_rate)],
      ["Niedrige Konfidenz", percentText(values.low_confidence_rate)],
      ["Fallback-Rate", percentText(values.fallback_rate)]
    ];
    ((gaps && gaps.items) || []).slice(0, 4).forEach((gap) => {
      rows.push([
        recordReference("Gap", gap.id),
        text(gap.department || "-") + " - "
          + text(gap.machine || "ohne Maschine") + " - "
          + numberText(gap.occurrence_count || 0) + "x"
      ]);
    });
    renderClarityList(
      "[data-ai-failure-summary]",
      "Fehlschlagende Fragen",
      rows,
      "Keine fehlgeschlagenen Fragen sichtbar."
    );
  }

  /**
   * Render permission and quality blocking signals.
   */
  function renderBlockedQuelleSummary(permissionFiltered, qualityBlocked, lifecycle) {
    const qualityGate = (lifecycle && lifecycle.rag_quality_gate) || {};
    const rows = [
      ["Permission-gefiltert", numberText(permissionFiltered)],
      ["Quality-geblockt", numberText(qualityBlocked)],
      ["Rejected", numberText((lifecycle && lifecycle.rejected) || 0)],
      ["Low Quality", numberText((lifecycle && lifecycle.low_quality) || 0)],
      ["Duplikate", numberText((lifecycle && lifecycle.duplicate) || 0)],
      ["Nicht freigegeben", numberText(qualityGate.non_approved_indexed_documents || 0)],
      ["Gewichtet statt voll", numberText(qualityGate.quality_weighted_indexed_documents || 0)]
    ];
    renderClarityList(
      "[data-ai-blocked-source-summary]",
      "Geblockte Quelles",
      rows,
      "Keine geblockten Quelles im aktuellen Fenster."
    );
  }

  /**
   * Render latest AI feedback metadata without comments, prompts, or answers.
   */
  function renderFeedbackSummary(feedback) {
    const rows = [
      ["Feedback gesamt", numberText(feedback.total || 0)],
      ["Hilfreich", numberText(feedback.helpful || 0)],
      ["Teilweise", numberText(feedback.partially_helpful || 0)],
      ["Nicht hilfreich", numberText(feedback.not_helpful || 0)]
    ];
    (feedback.latest || []).slice(0, 5).forEach((item) => {
      rows.push([
        recordReference("Feedback", item.id),
        feedbackRatingLabel(item.rating) + " - "
          + text(item.response_type || "-") + " - "
          + numberText(item.source_count || 0) + " Quellen"
      ]);
    });
    renderClarityList(
      "[data-ai-feedback-summary]",
      "Letzte AI-Feedbacks",
      rows,
      "Noch keine AI-Feedbacks vorhanden."
    );
  }

  /**
   * Return the primary SLO metric payload used by safety and section summaries.
   */
  function latestSloValues() {
    const telemetry = state.latestRetrievalTelemetry || {};
    const slo = telemetry.retrieval_slo || {};
    return slo.last_values || {};
  }

  /**
   * Render the read-only provider configuration snapshot from /api/v1/ai/status.
   */
  function renderProviderConfiguration(status) {
    const data = status || {};
    const ready = data.ready !== false;
    const provider = data.provider || "lokal";
    const model = data.model || "lokal";
    const lastError = data.last_error || "";
    const mode = ready ? "Modellbetrieb" : "Fallback / Kontrolle";
    const summary = root.querySelector("[data-ai-provider-summary]");
    setOptionalText('[data-ai-provider-field="provider"]', provider);
    setOptionalText('[data-ai-provider-field="model"]', model);
    setOptionalText('[data-ai-provider-field="mode"]', mode);
    setOptionalText(
      '[data-ai-provider-field="streaming"]',
      data.streaming_enabled ? "aktiv" : "aus"
    );
    if (summary) {
      summary.textContent = ready ? "Provider bereit" : "Provider checken";
      summary.className = "status-pill " + (ready ? "is-active" : "is-stale");
    }

    const details = root.querySelector("[data-ai-provider-details]");
    if (details) {
      details.innerHTML = "";
      details.append(
        statusRow("Provider", provider),
        statusRow("Modell", model),
        statusRow("Streaming", data.streaming_enabled ? "aktiv" : "aus"),
        statusRow("Letzter Fehler", lastError || "kein letzter Fehler")
      );
    }

    const actions = root.querySelector("[data-ai-provider-actions]");
    if (actions) {
      actions.innerHTML = "";
      actions.append(
        statusRow("Ändern", ".env / Runtime-Konfiguration"),
        statusRow("Endpoint", "/api/v1/ai/status"),
        statusRow("Service", "app.ai.services.ai_status"),
        statusRow("Admin-Hinweis", ready ? "Keine Aktion erforderlich" : "Key, Modell und Provider kontrollieren")
      );
    }
  }

  /**
   * Render the safety and fallback snapshot from existing summary and telemetry data.
   */
  function renderSafetyFallbackSummary() {
    const values = latestSloValues();
    const fallbackRate = state.latestAiSummary && state.latestAiSummary.fallback_rate != null
      ? state.latestAiSummary.fallback_rate
      : values.fallback_rate;
    const noQuelleRate = values.no_source_rate;
    const lowConfidenceRate = values.low_confidence_rate;
    const safetyRiskCount = Number(values.safety_risk_count || 0);
    const fieldValues = {
      fallback_rate: percentText(fallbackRate),
      safety_risk_count: numberText(safetyRiskCount),
      no_source_rate: percentText(noQuelleRate),
      low_confidence_rate: percentText(lowConfidenceRate)
    };
    Object.keys(fieldValues).forEach((key) => {
      const target = root.querySelector('[data-ai-safety-field="' + key + '"]');
      if (!target) return;
      target.textContent = fieldValues[key];
      const numberValue = key === "safety_risk_count"
        ? safetyRiskCount
        : Number(key === "fallback_rate" ? fallbackRate : values[key] || 0);
      const warning = key === "safety_risk_count" ? numberValue > 0 : numberValue >= 0.2;
      const critical = key === "safety_risk_count" ? numberValue >= 5 : numberValue >= 0.4;
      const card = target.closest(".ai-safety-card");
      if (card) {
        card.classList.remove("is-active", "is-stale", "is-error");
        card.classList.add(critical ? "is-error" : (warning ? "is-stale" : "is-active"));
      }
    });

    const critical = safetyRiskCount >= 5
      || Number(fallbackRate || 0) >= 0.5
      || Number(noQuelleRate || 0) >= 0.4
      || Number(lowConfidenceRate || 0) >= 0.4;
    const warning = !critical && (
      safetyRiskCount > 0
      || Number(fallbackRate || 0) >= 0.2
      || Number(noQuelleRate || 0) >= 0.2
      || Number(lowConfidenceRate || 0) >= 0.2
    );
    const summaryState = root.querySelector("[data-ai-safety-summary-state]");
    if (summaryState) {
      summaryState.textContent = critical ? "Handlungsbedarf" : (warning ? "Beobachten" : "unauffällig");
      summaryState.className = "status-pill " + (critical ? "is-error" : (warning ? "is-stale" : "is-active"));
    }
  }

  /**
   * Keep the seven section-level status badges aligned with loaded data.
   */
  function renderSectionStatusSummaries() {
    const aiReady = !state.latestAiStatus || state.latestAiStatus.ready !== false;
    const providerReady = state.latestAiStatus && state.latestAiStatus.ready !== false;
    const ragScore = Number((state.latestKnowledgeStatus || {}).readiness_score || 0);
    const sloStatus = (
      state.latestRetrievalTelemetry
      && state.latestRetrievalTelemetry.retrieval_slo
      && state.latestRetrievalTelemetry.retrieval_slo.status
    ) || "ok";
    const jobs = (state.latestOperationsStatus && state.latestOperationsStatus.background_jobs) || {};
    const jobCounts = (state.latestJobSummary && state.latestJobSummary.statusCounts) || {};
    const failedJobs = Number(jobs.failed || jobCounts.failed || 0);
    const queuedJobs = Number(jobs.queue_length || jobCounts.queued || 0);
    const values = latestSloValues();
    const safetyCritical = Number(values.safety_risk_count || 0) >= 5
      || Number(values.no_source_rate || 0) >= 0.4
      || Number(values.low_confidence_rate || 0) >= 0.4;
    const safetyWarning = !safetyCritical && (
      Number(values.safety_risk_count || 0) > 0
      || Number(values.no_source_rate || 0) >= 0.2
      || Number(values.low_confidence_rate || 0) >= 0.2
    );

    setSectionStatus("status", aiReady ? "Betriebsbereit" : "AI checken", aiReady ? "ok" : "critical");
    setSectionStatus("provider", providerReady ? "Provider bereit" : "Provider checken", providerReady ? "ok" : "warning");
    setSectionStatus(
      "knowledge",
      ragScore >= 80 ? "RAG bereit" : (ragScore >= 40 ? "RAG beobachten" : "RAG kritisch"),
      ragScore >= 80 ? "ok" : (ragScore >= 40 ? "warning" : "critical")
    );
    setSectionStatus(
      "jobs",
      failedJobs ? "Jobs kritisch" : (queuedJobs ? "Jobs laufen" : "Queue ruhig"),
      failedJobs ? "critical" : (queuedJobs ? "warning" : "ok")
    );
    setSectionStatus("retrieval", readinessLabel(sloStatus), sloStatus);
    setSectionStatus(
      "safety",
      safetyCritical ? "Sicherheit kritisch" : (safetyWarning ? "Sicherheit beobachten" : "Sicherheit unauffällig"),
      safetyCritical ? "critical" : (safetyWarning ? "warning" : "ok")
    );
    renderStatusOverview();
  }
  Object.assign(AdminAI, { setOverviewStatus, renderStatusOverview, setSectionStatus, setOptionalText, sourceTypeStatus, sloCount, feedbackRatingLabel, renderClarityCard, renderClarityList, renderAiClaritySummary, renderIndexedQuelleSummary, renderTextabschnittSummary, renderTrainingSummary, renderFailureSummary, renderBlockedQuelleSummary, renderFeedbackSummary, latestSloValues, renderProviderConfiguration, renderSafetyFallbackSummary, renderSectionStatusSummaries });
})(window.MaintenanceAdminAI);

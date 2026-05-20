(function () {
  const root = document.querySelector("[data-admin-ai-page]");
  if (!root) return;
  const adminView = (root.dataset.aiAdminView || "overview").toLowerCase();

  const QUALITY_STATUS_OPTIONS = [
    "draft",
    "ai_suggested",
    "technician_confirmed",
    "admin_approved",
    "low_quality",
    "duplicate",
    "outdated",
    "rejected"
  ];
  let retrievalDebugItems = [];
  let selectedRetrievalFlowId = null;
  let currentKnowledgeNetworkPayload = null;
  let latestAiStatus = null;
  let latestAiSummary = null;
  let latestKnowledgeStatus = null;
  let latestRetrievalTelemetry = null;
  let latestAiObservability = null;
  let latestOperationsStatus = null;
  let latestJobSummary = null;
  let latestTrainingSummary = null;
  let latestKnowledgeGaps = null;

  function bind(selector, eventName, handler) {
    const element = root.querySelector(selector);
    if (!element) return;
    element.addEventListener(eventName, handler);
  }

  function token() {
    return window.localStorage.getItem("maintenance_access_token");
  }

  async function api(path, options) {
    const response = await fetch(path, {
      ...options,
      headers: {
        ...(options && options.headers ? options.headers : {}),
        Authorization: "Bearer " + token()
      }
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      const error = new Error("API-Fehler");
      error.status = response.status;
      error.statusText = response.statusText;
      error.path = path;
      throw error;
    }
    return payload.data || payload;
  }

  /**
   * Return a user-facing API error that never exposes tokens, request payloads, or raw backend details.
   */
  function safeErrorMessage(error, context) {
    const status = Number(error && error.status);
    const endpoint = error && error.path ? String(error.path).split("?")[0] : "";
    const messages = {
      400: "Der Request wurde vom Backend abgelehnt.",
      401: "Die Sitzung ist abgelaufen. Bitte neu anmelden.",
      403: "Für diese Aktion fehlt die Berechtigung.",
      404: "Der API-Endpunkt wurde nicht gefunden.",
      409: "Die Aktion kollidiert mit dem aktuellen Datenstand.",
      422: "Die Eingaben passen nicht zum API-Vertrag.",
      429: "Das Rate Limit ist erreicht. Bitte kurz warten.",
      500: "Das Backend konnte die Aktion nicht ausführen.",
      502: "Der AI-Provider oder ein Gateway antwortet nicht.",
      503: "Der Service ist gerade nicht verfügbar.",
      504: "Die Aktion hat zu lange gedauert."
    };
    const summary = messages[status] || "Die Aktion konnte nicht abgeschlossen werden.";
    return [
      context || "AI Admin",
      summary,
      status ? "Status " + status : "",
      endpoint ? "Endpoint " + endpoint : ""
    ].filter(Boolean).join(" - ");
  }

  /**
   * Hide prompt, answer, and free-text question content in admin overview surfaces.
   */
  function redactSensitiveText(value, fallback) {
    if (value == null || value === "") return fallback || "Inhalt ausgeblendet";
    return fallback || "Aus Datenschutz ausgeblendet";
  }

  /**
   * Return a compact privacy-safe reference for persisted AI records.
   */
  function recordReference(prefix, id, fallback) {
    if (id != null && id !== "") return prefix + " #" + id;
    return fallback || prefix + " ohne ID";
  }

  /**
   * Render a consistent empty state into lists and table bodies.
   */
  function renderAdminEmptyState(target, message, hint) {
    if (!target) return;
    target.innerHTML = "";
    const state = document.createElement("div");
    const title = document.createElement("strong");
    state.className = "admin-empty";
    title.textContent = message;
    state.appendChild(title);
    if (hint) {
      const detail = document.createElement("span");
      detail.textContent = hint;
      state.appendChild(detail);
    }
    if (target.tagName === "TBODY") {
      const row = document.createElement("tr");
      const cellElement = document.createElement("td");
      const headerCount = target.closest("table")
        ? target.closest("table").querySelectorAll("thead th").length
        : 1;
      cellElement.colSpan = Math.max(headerCount, 1);
      cellElement.appendChild(state);
      row.appendChild(cellElement);
      target.appendChild(row);
      return;
    }
    target.appendChild(state);
  }

  function text(value) {
    return value == null || value === "" ? "-" : String(value);
  }

  function numberText(value) {
    if (value == null || value === "") return "0";
    const number = Number(value);
    if (!Number.isFinite(number)) return text(value);
    return number.toLocaleString("de-DE");
  }

  function percentText(value) {
    const number = Number(value || 0);
    return Math.round(number * 100) + "%";
  }

  function msText(value) {
    return numberText(value) + " ms";
  }

  function moneyText(value) {
    const number = Number(value || 0);
    return "$" + number.toLocaleString("de-DE", {
      minimumFractionDigits: 0,
      maximumFractionDigits: 6
    });
  }

  function secondsText(value) {
    const number = Number(value || 0);
    return Math.round(number) + " s";
  }

  function cell(value) {
    const item = document.createElement("td");
    item.textContent = text(value);
    return item;
  }

  function statusPill(label, className) {
    const item = document.createElement("span");
    item.className = "status-pill " + (className || "");
    item.textContent = label;
    return item;
  }

  function pillCell(label, className) {
    const item = document.createElement("td");
    item.appendChild(statusPill(label, className));
    return item;
  }

  function statusRow(label, value) {
    const item = document.createElement("div");
    item.className = "stat-row";
    const labelElement = document.createElement("span");
    labelElement.textContent = label;
    const valueElement = document.createElement("strong");
    valueElement.textContent = text(value);
    item.append(labelElement, valueElement);
    return item;
  }

  function readinessLabel(status) {
    const labels = {
      ok: "bereit",
      warning: "Warnung",
      critical: "kritisch"
    };
    return labels[status] || text(status);
  }

  function healthClass(status) {
    if (status === "ok") return "is-active";
    if (status === "critical") return "is-error";
    return "is-stale";
  }

  function setHealthCard(key, status, detail) {
    const card = root.querySelector('[data-ai-health="' + key + '"]');
    if (!card) return;
    card.classList.remove("is-active", "is-stale", "is-error");
    card.classList.add(healthClass(status));
    const label = card.querySelector("[data-ai-health-label]");
    const detailElement = card.querySelector("[data-ai-health-detail]");
    if (label) label.textContent = readinessLabel(status);
    if (detailElement) detailElement.textContent = detail || "-";
  }

  /**
   * Update one card in the top-level AI status overview.
   */
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
    const aiLoaded = Boolean(latestAiStatus);
    const aiReady = aiLoaded && latestAiStatus.ready !== false;
    const providerName = String((latestAiStatus && latestAiStatus.provider) || "").toLowerCase();
    const modelName = String((latestAiStatus && latestAiStatus.model) || "").toLowerCase();
    const openAiConfigured = providerName.includes("openai") || modelName.includes("gpt");
    const fallbackRate = latestAiSummary && latestAiSummary.fallback_rate != null
      ? Number(latestAiSummary.fallback_rate || 0)
      : Number(latestSloValues().fallback_rate || 0);
    const fallbackActive = (aiLoaded && !aiReady) || fallbackRate > 0;
    const knowledgeLoaded = Boolean(latestKnowledgeStatus);
    const diagnostics = (latestKnowledgeStatus && latestKnowledgeStatus.diagnostics) || {};
    const ragScore = Number((latestKnowledgeStatus || {}).readiness_score || 0);
    const ragReady = knowledgeLoaded && (
      diagnostics.ready === true
      || (diagnostics.ready == null && ragScore >= 60)
    );
    const latestJob = latestJobSummary && latestJobSummary.latestJob;
    const latestJobStatus = latestJob && latestJob.status;
    const latestJobTone = latestJobStatus === "failed"
      ? "critical"
      : (latestJobStatus === "queued" || latestJobStatus === "running" ? "warning" : "ok");

    setOverviewStatus(
      "ai",
      aiLoaded ? (aiReady ? "aktiv" : "inaktiv") : "Wird geladen",
      aiLoaded ? "Providerstatus aus /api/v1/ai/status" : "Status wird geladen",
      aiLoaded ? (aiReady ? "ok" : "critical") : "muted"
    );
    setOverviewStatus(
      "openai",
      !aiLoaded
        ? "Wird geladen"
        : (openAiConfigured ? (aiReady ? "verfügbar" : "nicht verfügbar") : "nicht konfiguriert"),
      !aiLoaded
        ? "Provider wird geladen"
        : ((latestAiStatus.provider || "lokal") + " / " + (latestAiStatus.model || "lokal")),
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
      knowledgeLoaded ? ("Readiness " + ragScore + "/100") : "RAG-Status wird geladen",
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
    const status = latestKnowledgeStatus || {};
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
   * Render one compact card in the AI Admin overview.
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
   * Render the one-screen AI Admin overview from already loaded API payloads.
   */
  function renderAiClaritySummary() {
    const target = root.querySelector("[data-ai-clarity-summary]");
    if (!target) return;
    const status = latestKnowledgeStatus || {};
    const lifecycle = status.lifecycle || {};
    const qualityGate = lifecycle.rag_quality_gate || {};
    const vectorStore = status.vector_store || {};
    const feedback = (latestAiSummary && latestAiSummary.feedback) || {};
    const trainingItems = (latestTrainingSummary && latestTrainingSummary.items) || [];
    const activeTraining = trainingItems.filter((item) => item.is_active);
    const manualTrainingSource = sourceTypeStatus("manual_training");
    const gaps = latestKnowledgeGaps || {};
    const sourceTypes = status.source_types || [];
    const indexed = Number(status.indexed || lifecycle.indexed_documents || 0);
    const searchable = Number(status.searchable_documents || 0);
    const chunks = Number(status.chunks || 0);
    const missingChunks = Number(vectorStore.missing_chunk_count || 0);
    const chunkMismatches = Number(vectorStore.chunk_mismatch_count || 0);
    const permissionFiltered = sloCount("permission_filtered_candidate_count");
    const qualityBlocked = Number(qualityGate.quality_blocked_indexed_documents || 0);
    const openGaps = Number(gaps.open_count || lifecycle.knowledge_gaps_open || 0);
    const feedbackTotal = Number(feedback.total || 0);
    const negativeFeedback = Number(feedback.not_helpful || 0);
    const clarityState = root.querySelector("[data-ai-clarity-state]");
    const blockedTotal = permissionFiltered + qualityBlocked;
    const hasWarnings = openGaps || blockedTotal || negativeFeedback || missingChunks || chunkMismatches;
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
      "Aktive Chunks",
      numberText(chunks),
      missingChunks + chunkMismatches
        ? numberText(missingChunks + chunkMismatches) + " Chunk-Probleme"
        : "Chunk-Zaehlung konsistent",
      missingChunks || chunkMismatches ? "warning" : (chunks ? "ok" : "muted")
    );
    renderClarityCard(
      target,
      "Aktive Trainingsdaten",
      numberText(activeTraining.length),
      numberText(manualTrainingSource.chunks || 0) + " Training-Chunks im Index",
      activeTraining.length ? "ok" : "muted"
    );
    renderClarityCard(
      target,
      "Fehlgeschlagene Fragen",
      numberText(openGaps),
      "Offene Knowledge-Gaps aus AI-Fragen",
      openGaps ? "warning" : "ok"
    );
    renderClarityCard(
      target,
      "Geblockte Sources",
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

    renderIndexedSourceSummary(sourceTypes);
    renderChunkSummary(status, vectorStore);
    renderTrainingSummary(trainingItems, manualTrainingSource);
    renderFailureSummary(gaps);
    renderBlockedSourceSummary(permissionFiltered, qualityBlocked, lifecycle);
    renderFeedbackSummary(feedback);
  }

  /**
   * Render indexed source-type coverage.
   */
  function renderIndexedSourceSummary(sourceTypes) {
    const rows = (sourceTypes || []).slice(0, 8).map((item) => [
      sourceTypeLabel(item.source_type),
      numberText(item.searchable_documents || 0) + "/"
        + numberText(item.documents || 0) + " suchbar, "
        + numberText(item.chunks || 0) + " Chunks"
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
  function renderChunkSummary(status, vectorStore) {
    const rows = [
      ["Aktive Chunks", numberText(status.chunks || 0)],
      ["Durchsuchbare Dokumente", numberText(status.searchable_documents || 0)],
      ["Soll Vektoren", numberText(vectorStore.expected_vector_count || 0)],
      ["Ist Vektoren", vectorStore.actual_vector_count == null ? "-" : numberText(vectorStore.actual_vector_count)],
      ["Fehlende Chunks", numberText(vectorStore.missing_chunk_count || 0)],
      ["Chunk-Mismatch", numberText(vectorStore.chunk_mismatch_count || 0)]
    ];
    renderClarityList(
      "[data-ai-active-chunk-summary]",
      "Aktive Chunks",
      rows,
      "Noch keine Chunk-Daten geladen."
    );
  }

  /**
   * Render active manual training coverage.
   */
  function renderTrainingSummary(trainingItems, manualTrainingSource) {
    const activeTraining = (trainingItems || []).filter((item) => item.is_active);
    const inactiveTraining = (trainingItems || []).length - activeTraining.length;
    const rows = [
      ["Aktiv", numberText(activeTraining.length)],
      ["Inaktiv", numberText(inactiveTraining)],
      ["Index-Dokumente", numberText(manualTrainingSource.documents || 0)],
      ["Suchbar", numberText(manualTrainingSource.searchable_documents || 0)],
      ["Training-Chunks", numberText(manualTrainingSource.chunks || 0)]
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
      ["Niedrige Confidence", percentText(values.low_confidence_rate)],
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
  function renderBlockedSourceSummary(permissionFiltered, qualityBlocked, lifecycle) {
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
      "Geblockte Sources",
      rows,
      "Keine geblockten Sources im aktuellen Fenster."
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
    const telemetry = latestRetrievalTelemetry || {};
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
    const fallbackRate = latestAiSummary && latestAiSummary.fallback_rate != null
      ? latestAiSummary.fallback_rate
      : values.fallback_rate;
    const noSourceRate = values.no_source_rate;
    const lowConfidenceRate = values.low_confidence_rate;
    const safetyRiskCount = Number(values.safety_risk_count || 0);
    const fieldValues = {
      fallback_rate: percentText(fallbackRate),
      safety_risk_count: numberText(safetyRiskCount),
      no_source_rate: percentText(noSourceRate),
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
      || Number(noSourceRate || 0) >= 0.4
      || Number(lowConfidenceRate || 0) >= 0.4;
    const warning = !critical && (
      safetyRiskCount > 0
      || Number(fallbackRate || 0) >= 0.2
      || Number(noSourceRate || 0) >= 0.2
      || Number(lowConfidenceRate || 0) >= 0.2
    );
    const state = root.querySelector("[data-ai-safety-summary-state]");
    if (state) {
      state.textContent = critical ? "Handlungsbedarf" : (warning ? "Beobachten" : "unauffällig");
      state.className = "status-pill " + (critical ? "is-error" : (warning ? "is-stale" : "is-active"));
    }
  }

  /**
   * Keep the seven section-level status badges aligned with loaded data.
   */
  function renderSectionStatusSummaries() {
    const aiReady = !latestAiStatus || latestAiStatus.ready !== false;
    const providerReady = latestAiStatus && latestAiStatus.ready !== false;
    const ragScore = Number((latestKnowledgeStatus || {}).readiness_score || 0);
    const sloStatus = (
      latestRetrievalTelemetry
      && latestRetrievalTelemetry.retrieval_slo
      && latestRetrievalTelemetry.retrieval_slo.status
    ) || "ok";
    const jobs = (latestOperationsStatus && latestOperationsStatus.background_jobs) || {};
    const jobCounts = (latestJobSummary && latestJobSummary.statusCounts) || {};
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
      safetyCritical ? "Safety kritisch" : (safetyWarning ? "Safety beobachten" : "Safety unauffällig"),
      safetyCritical ? "critical" : (safetyWarning ? "warning" : "ok")
    );
    renderStatusOverview();
  }

  function sourceTypeLabel(sourceType) {
    const labels = {
      upload: "Uploads",
      generated_document: "Berichte",
      error_entry: "Fehlerkatalog",
      task: "Tasks",
      machine: "Maschinen",
      inventory_material: "Inventar",
      maintenance_plan: "Wartungspläne",
      machine_manual: "Maschineninfos",
      shift_handover: "Schichtübergaben",
      manual_training: "Manuelles Training"
    };
    return labels[sourceType] || sourceType;
  }

  function dataSourceDefinitions() {
    return [
      {
        key: "error_catalog",
        label: "Fehlerkatalog",
        description: "Fehlercodes, Ursachen und L&ouml;sungen",
        types: ["error_entry"]
      },
      {
        key: "documents",
        label: "Dokumente",
        description: "Uploads, Berichte und Maschinenhandb&uuml;cher",
        types: ["upload", "generated_document", "machine_manual", "maintenance_plan"]
      },
      {
        key: "tasks",
        label: "Tasks",
        description: "Wartungs- und Eskalationsaufgaben",
        types: ["task"]
      },
      {
        key: "machines",
        label: "Maschinen",
        description: "Anlagen, Komponenten und Maschinenkontext",
        types: ["machine"]
      },
      {
        key: "shift_data",
        label: "Schichtdaten",
        description: "Schicht&uuml;bergaben und operative Hinweise",
        types: ["shift_handover"]
      },
      {
        key: "training",
        label: "Trainingsdaten",
        description: "Manuelles Assistant-Training",
        types: ["manual_training"]
      }
    ];
  }

  function sourceMetrics(status, types) {
    const sourceTypes = status.source_types || [];
    const matching = sourceTypes.filter((item) => types.includes(item.source_type));
    return matching.reduce((result, item) => ({
      documents: result.documents + Number(item.documents || 0),
      searchable: result.searchable + Number(item.searchable_documents || 0),
      chunks: result.chunks + Number(item.chunks || 0),
      active: result.active || Boolean(item.searchable),
    }), { documents: 0, searchable: 0, chunks: 0, active: false });
  }

  function sourceHealth(metrics, ragEnabled) {
    if (!ragEnabled) {
      return { label: "RAG aus", className: "is-muted", detail: "Strukturierte Daten bleiben nutzbar" };
    }
    if (!metrics.documents) {
      return { label: "leer", className: "is-muted", detail: "noch keine Quelle registriert" };
    }
    if (metrics.active && metrics.searchable === metrics.documents) {
      return { label: "gesund", className: "is-active", detail: "vollst&auml;ndig im Retrieval nutzbar" };
    }
    if (metrics.active) {
      return { label: "teilweise", className: "is-stale", detail: "ein Teil ist suchbar" };
    }
    return { label: "nicht aktiv", className: "is-error", detail: "nicht im RAG-Kontext verf&uuml;gbar" };
  }

  function appendSourceStat(target, label, value) {
    const item = document.createElement("span");
    const key = document.createElement("small");
    const count = document.createElement("strong");
    key.textContent = label;
    count.textContent = text(value);
    item.append(key, count);
    target.appendChild(item);
  }

  function renderSourceHealth(status) {
    const target = root.querySelector("[data-ai-source-health]");
    if (!target) return;
    const data = status || {};
    const ragEnabled = Boolean(data.diagnostics && data.diagnostics.rag_enabled);
    const vectorStatus = data.vector_store || {};
    const lastUpdate = vectorStatus.latest_indexed_at
      || (vectorStatus.last_successful_sync && vectorStatus.last_successful_sync.synced_at)
      || "";
    target.innerHTML = "";
    dataSourceDefinitions().forEach((definition) => {
      const metrics = sourceMetrics(data, definition.types);
      const health = sourceHealth(metrics, ragEnabled);
      const card = document.createElement("article");
      const header = document.createElement("div");
      const title = document.createElement("strong");
      const badge = statusPill(health.label, health.className);
      const description = document.createElement("p");
      const stats = document.createElement("div");
      const meta = document.createElement("small");
      card.className = "ai-source-card " + health.className;
      header.className = "ai-source-card-header";
      title.textContent = definition.label;
      description.innerHTML = definition.description;
      stats.className = "ai-source-stats";
      appendSourceStat(stats, "Einträge", numberText(metrics.documents));
      appendSourceStat(stats, "Chunks", numberText(metrics.chunks));
      appendSourceStat(stats, "Suchbar", numberText(metrics.searchable));
      meta.innerHTML = [
        "Embedding: " + text(data.diagnostics && data.diagnostics.embedding_provider),
        "RAG: " + (metrics.active ? "aktiv genutzt" : "nicht aktiv"),
        "Letzte Aktualisierung: " + (lastUpdate ? dateTimeText(lastUpdate) : "nicht verf&uuml;gbar"),
        "Health: " + health.detail
      ].join(" &middot; ");
      header.append(title, badge);
      card.append(header, description, stats, meta);
      target.appendChild(card);
    });
  }

  function knowledgeOriginKind(documentItem) {
    const sourceType = documentItem.source_type || "";
    const title = String(documentItem.title || "");
    if (sourceType === "manual_training" && title.startsWith("Tag-Bibliothek:")) {
      return "prebuilt";
    }
    if (sourceType === "upload" || sourceType === "manual_training") {
      return "manual";
    }
    return "automatic";
  }

  function knowledgeOriginLabel(origin) {
    const labels = {
      automatic: "Automatisch",
      manual: "Manuell",
      prebuilt: "Vorgefertigt"
    };
    return labels[origin] || "Automatisch";
  }

  function knowledgeOriginClass(origin) {
    const classes = {
      automatic: "is-source-automatic",
      manual: "is-source-manual",
      prebuilt: "is-source-prebuilt"
    };
    return classes[origin] || classes.automatic;
  }

  function knowledgeSourceCell(documentItem) {
    const item = document.createElement("td");
    const origin = knowledgeOriginKind(documentItem);
    item.className = "knowledge-source-cell";
    item.append(
      statusPill(sourceTypeLabel(documentItem.source_type), "is-muted"),
      statusPill(knowledgeOriginLabel(origin), knowledgeOriginClass(origin))
    );
    return item;
  }

  function qualityStatusLabel(status) {
    const labels = {
      draft: "Entwurf",
      ai_suggested: "AI-Vorschlag",
      technician_confirmed: "Techniker bestaetigt",
      admin_approved: "Admin freigegeben",
      low_quality: "Niedrige Qualität",
      duplicate: "Duplikat",
      outdated: "Veraltet",
      rejected: "Abgelehnt"
    };
    return labels[status] || text(status || "draft");
  }

  function qualityStatusClass(status) {
    if (status === "admin_approved" || status === "technician_confirmed") return "is-active";
    if (status === "outdated" || status === "low_quality" || status === "duplicate") {
      return "is-stale";
    }
    if (status === "rejected") return "is-error";
    return "is-muted";
  }

  function networkTypeLabel(type) {
    const labels = {
      machine: "Maschine",
      error: "Fehler",
      solution: "Lösung",
      document: "Dokument",
      task: "Task",
      inventory_part: "Inventar",
      recurring_issue: "Wiederkehrender Fehler",
      knowledge_gap: "Knowledge-Gap",
      component: "Komponente",
      sensor: "Sensor"
    };
    return labels[type] || text(type);
  }

  function queryTypeLabel(type) {
    const labels = {
      error_analysis: "Fehleranalyse",
      machine_question: "Maschinenfrage",
      inventory_question: "Inventarfrage",
      task_question: "Taskfrage",
      document_question: "Dokumentfrage",
      safety_question: "Sicherheitsfrage",
      general_question: "Allgemein",
      knowledge_gap: "Wissenslücke",
      trend_history_question: "Trend/Historie"
    };
    return labels[type] || text(type);
  }

  function scoreText(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return "-";
    if (number > 0 && number <= 1) return Math.round(number * 100) + "%";
    return Math.round(number).toLocaleString("de-DE");
  }

  function flowStatusLabel(status) {
    const labels = {
      ok: "OK",
      warning: "Warnung",
      empty: "Keine Daten",
      critical: "Kritisch"
    };
    return labels[status] || text(status);
  }

  function flowStatusClass(status) {
    if (status === "ok") return "is-active";
    if (status === "warning") return "is-stale";
    if (status === "critical") return "is-error";
    return "is-muted";
  }

  function confidenceLabel(confidence) {
    const score = confidence && confidence.score != null ? confidence.score : "-";
    const level = confidence && confidence.level ? confidence.level : "-";
    return score + " / " + level;
  }

  function sourceReferenceLabel(source) {
    if (!source) return "Quelle";
    if (source.source_label) return source.source_label;
    let label = text(source.type || "knowledge");
    if (source.id != null) label += " #" + source.id;
    if (source.chunk_id != null) label += " / Chunk #" + source.chunk_id;
    if (source.section_title) label += " - " + truncateLabel(source.section_title, 52);
    return label;
  }

  function networkTypeColor(type) {
    const colors = {
      machine: "#2563eb",
      error: "#dc2626",
      solution: "#16a34a",
      document: "#7c3aed",
      task: "#0891b2",
      inventory_part: "#ca8a04",
      recurring_issue: "#ea580c",
      knowledge_gap: "#be123c",
      component: "#0f766e",
      sensor: "#4f46e5"
    };
    return colors[type] || "#475569";
  }

  function truncateLabel(value, maxLength) {
    const label = text(value);
    if (label.length <= maxLength) return label;
    return label.slice(0, maxLength - 3).trim() + "...";
  }

  function networkNodeRadius(node) {
    const weight = Number(node.weight || 0);
    return Math.max(9, Math.min(22, 8 + Math.sqrt(weight) * 3));
  }

  function networkNodeMap(nodes) {
    const map = {};
    (nodes || []).forEach((node) => {
      map[node.id] = node;
    });
    return map;
  }

  function networkPositions(nodes) {
    const width = 920;
    const height = 520;
    const center = { x: width / 2, y: height / 2 };
    const ringByType = {
      document: 0,
      machine: 1,
      error: 1,
      recurring_issue: 1,
      task: 2,
      solution: 2,
      inventory_part: 2,
      knowledge_gap: 2,
      component: 3,
      sensor: 3
    };
    const ringRadii = [72, 154, 218, 252];
    const rings = [[], [], [], []];
    const positions = {};
    nodes.forEach((node) => {
      const ring = ringByType[node.type] == null ? 3 : ringByType[node.type];
      rings[ring].push(node);
    });
    rings.forEach((ringNodes, ringIndex) => {
      if (!ringNodes.length) return;
      ringNodes.sort((left, right) => String(left.id).localeCompare(String(right.id)));
      ringNodes.forEach((node, index) => {
        const angle = (-Math.PI / 2) + (2 * Math.PI * index) / ringNodes.length;
        const radius = ringRadii[ringIndex];
        positions[node.id] = {
          x: center.x + Math.cos(angle) * radius,
          y: center.y + Math.sin(angle) * radius
        };
      });
    });
    return { positions, width, height };
  }

  function metadataValue(value) {
    if (value == null || value === "") return "-";
    if (typeof value === "object") return JSON.stringify(value);
    return String(value);
  }

  function networkEdgeNodeLabels(edge, payload) {
    const nodes = networkNodeMap(payload.nodes || []);
    const source = nodes[edge.source];
    const target = nodes[edge.target];
    return {
      source: source ? source.label : edge.source,
      target: target ? target.label : edge.target
    };
  }

  function networkEdgeDetail(edge) {
    const labels = {
      source_relation: "Direkte Quelle",
      mentions: "Entity-Erwaehnung",
      recurring_pattern: "Wiederkehrendes Muster",
      knowledge_gap: "Knowledge-Gap",
      task_context: "Task-Kontext"
    };
    return labels[edge.type] || text(edge.type);
  }

  function renderKnowledgeNetworkGroups(payload) {
    const target = root.querySelector("[data-knowledge-network-groups]");
    if (!target) return;
    target.innerHTML = "";
    const groups = payload.groups || [];
    if (!groups.length) {
      target.appendChild(statusRow("Gruppen", "Keine gruppierten Nodes vorhanden"));
      return;
    }
    groups.forEach((group) => {
      const card = document.createElement("article");
      const header = document.createElement("div");
      const title = document.createElement("strong");
      const count = document.createElement("span");
      const list = document.createElement("div");
      card.className = "knowledge-network-group-card";
      header.className = "knowledge-network-group-header";
      title.textContent = group.label || networkTypeLabel(group.type);
      count.textContent = numberText(group.count) + " Nodes / " + numberText(group.edge_count) + " Links";
      header.append(title, count);
      list.className = "knowledge-network-group-nodes";
      (group.top_nodes || []).forEach((node) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "knowledge-network-node-chip";
        button.dataset.networkGroupNode = node.id;
        button.textContent = truncateLabel(node.label, 34);
        button.addEventListener("click", () => {
          const nodeDetail = (currentKnowledgeNetworkPayload.nodes || []).find((item) => item.id === node.id);
          renderKnowledgeNetworkDetail(nodeDetail, currentKnowledgeNetworkPayload);
        });
        list.appendChild(button);
      });
      card.append(header, list);
      target.appendChild(card);
    });
  }

  function renderKnowledgeNetworkRelations(payload) {
    const target = root.querySelector("[data-knowledge-network-relations]");
    if (!target) return;
    target.innerHTML = "";
    const edges = (payload.edges || []).slice(0, 16);
    const heading = document.createElement("div");
    const title = document.createElement("strong");
    const meta = document.createElement("span");
    heading.className = "knowledge-network-relations-header";
    title.textContent = "Klickbare Verbindungen";
    meta.textContent = edges.length ? edges.length + " wichtigste Beziehungen" : "Keine sichtbaren Beziehungen";
    heading.append(title, meta);
    target.appendChild(heading);
    if (!edges.length) return;
    edges.forEach((edge) => {
      const labels = networkEdgeNodeLabels(edge, payload);
      const button = document.createElement("button");
      const relation = document.createElement("span");
      const source = document.createElement("strong");
      const score = document.createElement("small");
      button.type = "button";
      button.className = "knowledge-network-relation-card";
      button.dataset.networkRelation = edge.id;
      relation.textContent = networkEdgeDetail(edge);
      source.textContent = truncateLabel(labels.source, 34) + " -> " + truncateLabel(labels.target, 34);
      score.textContent = "Gewicht " + Number(edge.weight || 0).toFixed(1) + " / Evidenz " + numberText(edge.evidence_count || 0);
      button.append(relation, source, score);
      button.addEventListener("click", () => renderKnowledgeNetworkEdgeDetail(edge, payload));
      target.appendChild(button);
    });
  }

  function renderKnowledgeNetworkStats(stats) {
    const target = root.querySelector("[data-knowledge-network-stats]");
    if (!target) return;
    target.innerHTML = "";
    [
      ["Nodes", stats.node_count || 0],
      ["Edges", stats.edge_count || 0],
      ["Roh-Nodes", stats.raw_node_count || 0],
      ["Zeitraum", (stats.window_days || 30) + " Tage"]
    ].forEach(([label, value]) => {
      const card = document.createElement("article");
      const span = document.createElement("span");
      const strong = document.createElement("strong");
      card.className = "metric-card";
      span.textContent = label;
      strong.textContent = numberText(value).replace(" Tage", "") + (label === "Zeitraum" ? " Tage" : "");
      card.append(span, strong);
      target.appendChild(card);
    });
  }

  function renderKnowledgeNetworkLegend(payload) {
    const target = root.querySelector("[data-knowledge-network-legend]");
    if (!target) return;
    target.innerHTML = "";
    const stats = payload.stats || {};
    const nodesByType = stats.nodes_by_type || {};
    Object.keys(nodesByType).sort().forEach((type) => {
      target.appendChild(statusRow(
        networkTypeLabel(type),
        nodesByType[type] + " Nodes"
      ));
    });
    if (!Object.keys(nodesByType).length) {
      target.appendChild(statusRow("Legende", "Keine Netzwerkdaten vorhanden"));
    }
    const privacy = payload.privacy || {};
    target.appendChild(statusRow("Privacy", privacy.mode || "metadata_only"));
  }

  function renderKnowledgeNetworkDetail(node, payload) {
    const target = root.querySelector("[data-knowledge-network-detail]");
    if (!target) return;
    target.innerHTML = "";
    if (!node) {
      target.appendChild(statusRow("Auswahl", "Node anklicken"));
      return;
    }
    const edges = payload.edges || [];
    const nodes = networkNodeMap(payload.nodes || []);
    const connected = edges.filter((edge) => edge.source === node.id || edge.target === node.id);
    target.append(
      statusRow("Titel", node.title || node.label),
      statusRow("Typ", networkTypeLabel(node.type)),
      statusRow("Gewicht", Number(node.weight || 0).toFixed(1)),
      statusRow("Evidenz", node.evidence_count || 0),
      statusRow("Status", node.status || node.quality_status || "-"),
      statusRow("Quelle", node.source_type ? sourceTypeLabel(node.source_type) : "-")
    );
    Object.keys(node.metadata || {}).slice(0, 8).forEach((key) => {
      target.appendChild(statusRow(key, truncateLabel(metadataValue(node.metadata[key]), 80)));
    });
    if (connected.length) {
      connected.slice(0, 8).forEach((edge) => {
        const otherId = edge.source === node.id ? edge.target : edge.source;
        const other = nodes[otherId];
        target.appendChild(statusRow(
          edge.label || edge.type,
          other ? truncateLabel(other.label, 42) : otherId
        ));
      });
    } else {
      target.appendChild(statusRow("Verbindungen", "keine sichtbaren Kanten"));
    }
  }

  function renderKnowledgeNetworkEdgeDetail(edge, payload) {
    const target = root.querySelector("[data-knowledge-network-detail]");
    if (!target) return;
    target.innerHTML = "";
    if (!edge) {
      target.appendChild(statusRow("Auswahl", "Node oder Verbindung anklicken"));
      return;
    }
    const nodes = networkNodeMap(payload.nodes || []);
    const source = nodes[edge.source];
    const targetNode = nodes[edge.target];
    target.append(
      statusRow("Beziehung", networkEdgeDetail(edge)),
      statusRow("Von", source ? truncateLabel(source.label, 80) : edge.source),
      statusRow("Nach", targetNode ? truncateLabel(targetNode.label, 80) : edge.target),
      statusRow("Gewicht", Number(edge.weight || 0).toFixed(1)),
      statusRow("Evidenz", edge.evidence_count || 0),
      statusRow("Typ", edge.type || "-")
    );
    ((edge.explainability || {}).signals || []).slice(0, 8).forEach((signal) => {
      target.appendChild(statusRow("Signal", signal));
    });
  }

  function renderKnowledgeNetworkCanvas(payload) {
    const container = root.querySelector("[data-knowledge-network-canvas]");
    if (!container) return;
    container.innerHTML = "";
    const nodes = payload.nodes || [];
    const edges = payload.edges || [];
    if (!nodes.length) {
      container.appendChild(statusRow("Knowledge Network", "Keine Daten für diesen Filter."));
      renderKnowledgeNetworkDetail(null, payload);
      return;
    }

    const svgNamespace = "http://www.w3.org/2000/svg";
    const layout = networkPositions(nodes);
    const svg = document.createElementNS(svgNamespace, "svg");
    svg.setAttribute("viewBox", "0 0 " + layout.width + " " + layout.height);
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", "Knowledge Network");
    svg.style.width = "100%";
    svg.style.minHeight = "440px";
    svg.style.display = "block";
    svg.style.background = "#f8fafc";
    svg.style.border = "1px solid #e2e8f0";
    svg.style.borderRadius = "8px";

    edges.forEach((edge) => {
      const sourcePosition = layout.positions[edge.source];
      const targetPosition = layout.positions[edge.target];
      if (!sourcePosition || !targetPosition) return;
      const edgeGroup = document.createElementNS(svgNamespace, "g");
      const hitLine = document.createElementNS(svgNamespace, "line");
      const line = document.createElementNS(svgNamespace, "line");
      edgeGroup.setAttribute("tabindex", "0");
      edgeGroup.setAttribute("role", "button");
      edgeGroup.setAttribute("class", "knowledge-network-edge");
      edgeGroup.dataset.networkEdgeId = edge.id;
      hitLine.setAttribute("x1", sourcePosition.x);
      hitLine.setAttribute("y1", sourcePosition.y);
      hitLine.setAttribute("x2", targetPosition.x);
      hitLine.setAttribute("y2", targetPosition.y);
      hitLine.setAttribute("stroke", "transparent");
      hitLine.setAttribute("stroke-width", "14");
      line.setAttribute("x1", sourcePosition.x);
      line.setAttribute("y1", sourcePosition.y);
      line.setAttribute("x2", targetPosition.x);
      line.setAttribute("y2", targetPosition.y);
      line.setAttribute("stroke", edge.type === "source_relation" ? "#64748b" : "#cbd5e1");
      line.setAttribute("stroke-width", Math.max(1, Math.min(5, Number(edge.weight || 1) / 3)));
      line.setAttribute("stroke-opacity", edge.type === "source_relation" ? "0.7" : "0.45");
      const title = document.createElementNS(svgNamespace, "title");
      title.textContent = edge.label + " (" + Number(edge.weight || 0).toFixed(1) + ")";
      edgeGroup.append(hitLine, line, title);
      edgeGroup.addEventListener("click", () => {
        svg.querySelectorAll("[data-network-edge-id]").forEach((item) => {
          item.classList.remove("is-selected");
        });
        svg.querySelectorAll("[data-network-node-id] circle").forEach((item) => {
          item.setAttribute("stroke", "#ffffff");
          item.setAttribute("stroke-width", "2");
        });
        edgeGroup.classList.add("is-selected");
        renderKnowledgeNetworkEdgeDetail(edge, payload);
      });
      edgeGroup.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        edgeGroup.dispatchEvent(new Event("click"));
      });
      svg.appendChild(edgeGroup);
    });

    nodes.forEach((node) => {
      const position = layout.positions[node.id];
      if (!position) return;
      const group = document.createElementNS(svgNamespace, "g");
      const circle = document.createElementNS(svgNamespace, "circle");
      const label = document.createElementNS(svgNamespace, "text");
      const title = document.createElementNS(svgNamespace, "title");
      group.setAttribute("tabindex", "0");
      group.setAttribute("role", "button");
      group.dataset.networkNodeId = node.id;
      circle.setAttribute("cx", position.x);
      circle.setAttribute("cy", position.y);
      circle.setAttribute("r", networkNodeRadius(node));
      circle.setAttribute("fill", networkTypeColor(node.type));
      circle.setAttribute("fill-opacity", "0.88");
      circle.setAttribute("stroke", "#ffffff");
      circle.setAttribute("stroke-width", "2");
      label.setAttribute("x", position.x);
      label.setAttribute("y", position.y + networkNodeRadius(node) + 14);
      label.setAttribute("text-anchor", "middle");
      label.setAttribute("font-size", "11");
      label.setAttribute("fill", "#0f172a");
      label.textContent = truncateLabel(node.label, 22);
      title.textContent = node.title || node.label;
      group.append(circle, label, title);
      group.addEventListener("click", () => {
        svg.querySelectorAll("[data-network-edge-id]").forEach((item) => {
          item.classList.remove("is-selected");
        });
        svg.querySelectorAll("[data-network-node-id] circle").forEach((item) => {
          item.setAttribute("stroke", "#ffffff");
          item.setAttribute("stroke-width", "2");
        });
        circle.setAttribute("stroke", "#020617");
        circle.setAttribute("stroke-width", "4");
        renderKnowledgeNetworkDetail(node, payload);
      });
      group.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        group.dispatchEvent(new Event("click"));
      });
      svg.appendChild(group);
    });
    container.appendChild(svg);
    renderKnowledgeNetworkDetail(nodes[0], payload);
  }

  function renderKnowledgeNetwork(payload) {
    payload = payload || { nodes: [], edges: [], groups: [], stats: {} };
    currentKnowledgeNetworkPayload = payload;
    renderKnowledgeNetworkStats(payload.stats || {});
    renderKnowledgeNetworkGroups(payload);
    renderKnowledgeNetworkLegend(payload);
    renderKnowledgeNetworkCanvas(payload);
    renderKnowledgeNetworkRelations(payload);
  }

  async function loadKnowledgeNetwork() {
    const query = root.querySelector("[data-knowledge-network-search]").value;
    const source = root.querySelector("[data-knowledge-network-source]").value;
    const quality = root.querySelector("[data-knowledge-network-quality]").value;
    const focusType = root.querySelector("[data-knowledge-network-focus-type]").value;
    const focus = root.querySelector("[data-knowledge-network-focus]").value;
    const params = new URLSearchParams({
      limit: "120",
      q: query,
      source_type: source,
      quality_status: quality,
      focus,
      focus_type: focusType
    });
    const data = await api("/api/v1/admin/ai/knowledge-network?" + params.toString());
    renderKnowledgeNetwork(data);
  }

  function renderRetrievalDebug(data) {
    const tbody = root.querySelector("[data-retrieval-debug-rows]");
    if (!tbody) return;
    tbody.innerHTML = "";
    retrievalDebugItems = data.items || [];
    if (
      retrievalDebugItems.length
      && !retrievalDebugItems.some((item) => item.chat_message_id === selectedRetrievalFlowId)
    ) {
      selectedRetrievalFlowId = retrievalDebugItems[0].chat_message_id;
    }
    if (!retrievalDebugItems.length) {
      selectedRetrievalFlowId = null;
    }
    renderRetrievalFlow(selectedRetrievalFlowItem());
    renderAiClaritySummary();
    const items = data.items || [];
    if (!items.length) {
      renderAdminEmptyState(
        tbody,
        "Keine Retrieval-Debug-Daten für diesen Filter.",
        "Passe Zeitraum, Suchbegriff oder Query-Typ an."
      );
      return;
    }
    items.forEach((item) => {
      const row = document.createElement("tr");
      const action = document.createElement("td");
      const button = document.createElement("button");
      const conflicts = item.conflicts || {};
      const safety = item.safety || {};
      const sourceText = (item.used_sources || []).length + " Quellen";
      const conflictText = conflicts.has_conflicts
        ? conflicts.count + " Konflikte"
        : (safety.safety_relevant ? "Safety " + safety.risk_level : "-");
      row.className = selectedRetrievalFlowId === item.chat_message_id ? "is-selected" : "";
      button.type = "button";
      button.className = "btn btn-ghost btn-sm";
      button.dataset.retrievalFlowSelect = item.chat_message_id;
      button.textContent = "Ansehen";
      action.appendChild(button);
      row.append(
        cell(dateTimeText(item.created_at)),
        cell(recordReference("Chat", item.chat_message_id)),
        cell(queryTypeLabel(item.query_type)),
        cell(sourceText),
        cell(text(item.confidence && item.confidence.score) + " / " + text(item.confidence && item.confidence.level)),
        cell(conflictText),
        cell(text(item.retrieval_duration_ms) + " ms"),
        action
      );
      tbody.appendChild(row);
    });
  }

  function selectedRetrievalFlowItem() {
    if (!retrievalDebugItems.length) return null;
    return (
      retrievalDebugItems.find((item) => item.chat_message_id === selectedRetrievalFlowId)
      || retrievalDebugItems[0]
    );
  }

  function renderRetrievalFlow(item) {
    const statusTarget = root.querySelector("[data-retrieval-flow-status]");
    const durationTarget = root.querySelector("[data-retrieval-flow-duration]");
    const summaryTarget = root.querySelector("[data-retrieval-flow-summary]");
    const timelineTarget = root.querySelector("[data-retrieval-flow-timeline]");
    const sourceMapTarget = root.querySelector("[data-retrieval-flow-source-map]");
    const answerTarget = root.querySelector("[data-retrieval-flow-answer]");
    if (!summaryTarget || !timelineTarget || !sourceMapTarget || !answerTarget) return;
    summaryTarget.innerHTML = "";
    timelineTarget.innerHTML = "";
    sourceMapTarget.innerHTML = "";
    answerTarget.innerHTML = "";
    if (!item) {
      if (statusTarget) {
        statusTarget.textContent = "Keine Daten";
        statusTarget.className = "badge badge-ai is-muted";
      }
      if (durationTarget) durationTarget.textContent = "-";
      summaryTarget.appendChild(statusRow("Flow", "Noch keine Retrieval-Debug-Daten vorhanden."));
      renderRetrievalAnalysis(null);
      return;
    }
    const worstStatus = retrievalFlowWorstStatus(item.flow_steps || []);
    if (statusTarget) {
      statusTarget.textContent = flowStatusLabel(worstStatus);
      statusTarget.className = "badge badge-ai " + flowStatusClass(worstStatus);
    }
    if (durationTarget) durationTarget.textContent = msText(item.retrieval_duration_ms || 0);
    renderRetrievalFlowSummary(summaryTarget, item);
    renderRetrievalFlowTimeline(timelineTarget, item);
    renderRetrievalFlowSources(sourceMapTarget, item);
    renderRetrievalFlowAnswer(answerTarget, item);
    renderRetrievalAnalysis(item);
  }

  function renderRetrievalAnalysis(item) {
    const target = root.querySelector("[data-retrieval-analysis]");
    if (!target) return;
    target.innerHTML = "";
    const empty = !item;
    const reranking = empty ? {} : (item.reranking || {});
    const metrics = [
      {
        label: "Gefundene Chunks",
        value: empty ? "0" : numberText((item.rag_chunks || []).length),
        detail: "RAG-Kontext"
      },
      {
        label: "Hybrid Treffer",
        value: empty ? "0" : numberText((item.used_sources || []).length),
        detail: "Strukturiert + RAG"
      },
      {
        label: "Re-Ranking",
        value: numberText(reranking.reranked_count || 0),
        detail: "sichtbar neu sortiert"
      },
      {
        label: "Top Score",
        value: scoreText(reranking.top_score),
        detail: "bestbewertete Quelle"
      },
      {
        label: "Permission Status",
        value: empty ? "-" : "gefiltert",
        detail: "nur erlaubte Quellen im Flow"
      },
      {
        label: "Suchdauer",
        value: empty ? "0 ms" : msText(item.retrieval_duration_ms || 0),
        detail: "bis Context Building"
      },
      {
        label: "Tokens",
        value: "-",
        detail: "prompt-sicher nicht persistiert"
      },
      {
        label: "Chunk IDs",
        value: empty ? "-" : (item.rag_chunks || []).map((chunk) => chunk.chunk_id).filter(Boolean).slice(0, 3).join(", ") || "-",
        detail: "Top sichtbare Chunks"
      }
    ];
    metrics.forEach((metric) => {
      const card = document.createElement("article");
      const label = document.createElement("span");
      const value = document.createElement("strong");
      const detail = document.createElement("small");
      card.className = "ai-retrieval-metric";
      label.textContent = metric.label;
      value.textContent = metric.value;
      detail.textContent = metric.detail;
      card.append(label, value, detail);
      target.appendChild(card);
    });
  }

  function retrievalFlowWorstStatus(steps) {
    const order = { ok: 0, empty: 1, warning: 2, critical: 3 };
    return (steps || []).reduce((worst, step) => (
      order[step.status] > order[worst] ? step.status : worst
    ), "ok");
  }

  function renderRetrievalFlowSummary(target, item) {
    const question = document.createElement("article");
    const meta = document.createElement("div");
    question.className = "retrieval-flow-question";
    meta.className = "retrieval-flow-meta";
    const title = document.createElement("span");
    const textNode = document.createElement("strong");
    title.textContent = "Chat-Referenz";
    textNode.textContent = recordReference("Chat", item.chat_message_id);
    question.append(title, textNode);
    [
      ["Query-Typ", queryTypeLabel(item.query_type)],
      ["Strukturierte Quellen", numberText((item.structured_sources || []).length)],
      ["RAG-Chunks", numberText((item.rag_chunks || []).length)],
      ["Confidence", confidenceLabel(item.confidence)]
    ].forEach(([label, value]) => {
      meta.appendChild(statusRow(label, value));
    });
    target.append(question, meta);
  }

  function renderRetrievalFlowTimeline(target, item) {
    const steps = item.flow_steps || [];
    if (!steps.length) {
      target.appendChild(statusRow("Timeline", "Keine Flow-Schritte gespeichert."));
      return;
    }
    steps.forEach((step, index) => {
      const details = document.createElement("details");
      const summary = document.createElement("summary");
      const marker = document.createElement("span");
      const body = document.createElement("div");
      const title = document.createElement("strong");
      const badge = statusPill(flowStatusLabel(step.status), flowStatusClass(step.status));
      const subtitle = document.createElement("small");
      details.className = "retrieval-flow-step " + flowStatusClass(step.status);
      details.open = index < 3 || step.status === "warning" || step.status === "critical";
      marker.className = "retrieval-flow-step-marker";
      marker.textContent = String(index + 1);
      body.className = "retrieval-flow-step-body";
      title.textContent = step.label;
      subtitle.textContent = step.summary || "-";
      body.append(title, subtitle);
      summary.append(marker, body, badge);
      details.appendChild(summary);
      details.appendChild(retrievalFlowMetrics(step.metrics));
      target.appendChild(details);
    });
  }

  function retrievalFlowMetrics(metrics) {
    const grid = document.createElement("div");
    grid.className = "retrieval-flow-metrics";
    const safeMetrics = metrics && typeof metrics === "object" ? metrics : {};
    const entries = Object.entries(safeMetrics)
      .filter(([, value]) => value != null && value !== "" && typeof value !== "object")
      .slice(0, 8);
    if (!entries.length) {
      grid.appendChild(statusRow("Details", "Keine zusätzlichen Metriken."));
      return grid;
    }
    entries.forEach(([key, value]) => {
      grid.appendChild(statusRow(flowMetricLabel(key), flowMetricValue(key, value)));
    });
    return grid;
  }

  function flowMetricLabel(key) {
    const labels = {
      query_type: "Query-Typ",
      query_confidence: "Query Confidence",
      source_count: "Quellen",
      chunk_count: "Chunks",
      candidate_count: "Kandidaten",
      shown_count: "Sichtbar",
      reranked_count: "Re-Ranked",
      top_score: "Top Score",
      section_count: "Sections",
      used_chars: "Kontext",
      max_chars: "Budget",
      answer_preview_chars: "Antwortvorschau"
    };
    return labels[key] || key.replaceAll("_", " ");
  }

  function flowMetricValue(key, value) {
    if (key.includes("score") || key.includes("confidence")) return scoreText(value);
    if (key.includes("chars")) return numberText(value);
    return text(value);
  }

  function renderRetrievalFlowSources(target, item) {
    const heading = document.createElement("div");
    const title = document.createElement("strong");
    const meta = document.createElement("span");
    const list = document.createElement("div");
    heading.className = "retrieval-flow-card-header";
    title.textContent = "Quelle → Antwort";
    meta.textContent = (item.source_answer_links || []).length + " Links";
    list.className = "retrieval-flow-source-list";
    heading.append(title, meta);
    target.appendChild(heading);
    if (!(item.source_answer_links || []).length) {
      target.appendChild(statusRow("Quellen", "Keine Quellen im Flow."));
      return;
    }
    (item.source_answer_links || []).slice(0, 8).forEach((link) => {
      const source = link.source || {};
      const card = document.createElement("article");
      const cardTitle = document.createElement("strong");
      const cardMeta = document.createElement("small");
      const reasons = document.createElement("div");
      card.className = "retrieval-flow-source";
      cardTitle.textContent = sourceReferenceLabel(source);
      cardMeta.textContent = [
        "Rank " + text(source.rank),
        "Score " + scoreText(source.final_score != null ? source.final_score : source.score),
        source.quality_status ? "Quality " + source.quality_status : ""
      ].filter(Boolean).join(" · ");
      reasons.className = "retrieval-flow-badges";
      (link.reasons || []).forEach((reason) => {
        reasons.appendChild(statusPill(flowReasonLabel(reason), "is-muted"));
      });
      card.append(cardTitle, cardMeta, reasons);
      list.appendChild(card);
    });
    target.appendChild(list);
  }

  function flowReasonLabel(reason) {
    const labels = {
      score_signal: "Score",
      quality_gate: "Quality Gate",
      machine_context: "Maschinenkontext",
      section_context: "Abschnitt",
      retrieved_context: "Retrieval",
      used_as_answer_context: "Antwortkontext"
    };
    return labels[reason] || text(reason);
  }

  function renderRetrievalFlowAnswer(target, item) {
    const heading = document.createElement("div");
    const title = document.createElement("strong");
    const meta = document.createElement("span");
    const answer = document.createElement("p");
    const checks = document.createElement("div");
    heading.className = "retrieval-flow-card-header";
    title.textContent = "Finale Antwort und Safety";
    meta.textContent = confidenceLabel(item.confidence);
    answer.className = "retrieval-flow-answer-preview";
    answer.textContent = redactSensitiveText(
      item.answer_preview,
      "Antwortvorschau aus Datenschutz ausgeblendet."
    );
    checks.className = "retrieval-flow-checks";
    (item.safety_checks || []).forEach((check) => {
      checks.appendChild(statusRow(
        check.label,
        check.safety_relevant
          ? "relevant · " + text(check.risk_level || check.action || "-")
          : "nicht relevant"
      ));
    });
    heading.append(title, meta);
    target.append(heading, answer, checks);
  }

  async function loadRetrievalDebug() {
    const query = root.querySelector("[data-retrieval-debug-search]").value;
    const queryType = root.querySelector("[data-retrieval-debug-type]").value;
    const params = new URLSearchParams({
      limit: "20",
      q: query,
      query_type: queryType
    });
    const data = await api("/api/v1/admin/ai/retrieval-debug?" + params.toString());
    renderRetrievalDebug(data);
  }

  function lifecycleStepStatusLabel(status) {
    const labels = {
      available: "vorhanden",
      partial: "teilweise",
      missing: "offen"
    };
    return labels[status] || text(status);
  }

  function dateTimeText(value) {
    if (!value) return "-";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return text(value);
    return date.toLocaleString("de-DE");
  }

  function setAdminMessage(message, isError) {
    const target = root.querySelector("[data-ai-reindex-message]");
    if (!target) return;
    target.textContent = message || "";
    target.classList.toggle("is-error", Boolean(isError));
    if (message && window.maintenanceFrontend && window.maintenanceFrontend.showInterfaceToast) {
      window.maintenanceFrontend.showInterfaceToast(message, isError ? "error" : "info");
    }
  }

  /**
   * Run an admin data refresh and surface API failures without leaking backend details.
   */
  function runAdminLoad(loader, context) {
    loader().catch((error) => {
      setAdminMessage(safeErrorMessage(error, context), true);
    });
  }

  function setButtonBusy(button, busy, busyText) {
    if (window.maintenanceFrontend && window.maintenanceFrontend.setButtonBusy) {
      window.maintenanceFrontend.setButtonBusy(button, busy, busyText);
      return;
    }
    if (!button) return;
    if (busy) {
      if (!button.dataset.originalText) button.dataset.originalText = button.textContent;
      button.disabled = true;
      button.setAttribute("aria-busy", "true");
      if (busyText) {
        button.dataset.busyText = busyText;
        button.textContent = busyText;
      }
      return;
    }
    button.disabled = false;
    button.removeAttribute("aria-busy");
    if (button.dataset.originalText) {
      if (!button.dataset.busyText || button.textContent === button.dataset.busyText) {
        button.textContent = button.dataset.originalText;
      }
      delete button.dataset.originalText;
      delete button.dataset.busyText;
    }
  }

  function setFormBusy(form, busy, busyText) {
    if (window.maintenanceFrontend && window.maintenanceFrontend.setFormBusy) {
      window.maintenanceFrontend.setFormBusy(form, busy, busyText);
      return;
    }
    if (!form) return;
    setButtonBusy(form.querySelector("button[type='submit']"), busy, busyText);
    form.setAttribute("aria-busy", String(Boolean(busy)));
  }

  async function loadSummary() {
    const summary = await api("/api/v1/admin/ai/summary?days=7");
    latestAiSummary = summary || {};
    const formatters = {
      events_total: numberText,
      fallback_rate: percentText,
      error_rate: percentText,
      average_latency_ms: (value) => numberText(value) + " ms",
      total_tokens: numberText,
      estimated_cost_usd: moneyText,
      cache_rate: percentText,
      cost_per_1k_tokens: moneyText
    };
    Object.keys(formatters).forEach((key) => {
      const target = root.querySelector('[data-ai-kpi="' + key + '"]');
      if (target) target.textContent = formatters[key](summary[key]);
    });
    renderWorkflowMetrics(summary.top_workflows || []);
    renderTopErrors(summary.top_errors || []);
    const readiness = summary.readiness || {};
    setHealthCard("ai", readiness.status || "warning", (readiness.reasons || []).join(" "));
    renderSafetyFallbackSummary();
    renderSectionStatusSummaries();
    renderAiClaritySummary();
  }

  function retrievalSloLabel(metric) {
    const labels = {
      retrieval_p95_ms: "P95 Suchzeit",
      no_source_rate: "Ohne Quellen",
      low_confidence_rate: "Niedrige Sicherheit",
      permission_filtered_candidate_count: "Berechtigungsfilter",
      negative_feedback_rate: "Negatives Feedback",
      safety_risk_count: "Safety Risiken",
      fallback_rate: "Ausweichantworten",
      vector_sync_failure_count: "Index-Sync-Fehler",
      stale_index_count: "Veralteter Index"
    };
    return labels[metric] || text(metric);
  }

  function retrievalSloValue(metric, value) {
    if (metric === "retrieval_p95_ms") return msText(value);
    if (
      metric === "no_source_rate"
      || metric === "low_confidence_rate"
      || metric === "negative_feedback_rate"
      || metric === "fallback_rate"
    ) {
      return percentText(value);
    }
    return numberText(value);
  }

  function renderRetrievalSlo(payload) {
    const slo = (payload && payload.retrieval_slo) || {};
    const values = slo.last_values || {};
    const status = slo.status || "ok";
    const statusTarget = root.querySelector("[data-retrieval-slo-status]");
    if (statusTarget) {
      statusTarget.textContent = readinessLabel(status);
      statusTarget.className = "badge badge-ai " + healthClass(status);
    }
    root.querySelectorAll("[data-retrieval-slo-kpi]").forEach((target) => {
      const key = target.dataset.retrievalSloKpi;
      if (key === "index_sync_risks") {
        target.textContent = numberText(
          Number(values.vector_sync_failure_count || 0) + Number(values.stale_index_count || 0)
        );
        return;
      }
      target.textContent = retrievalSloValue(key, values[key]);
    });

    const trendList = root.querySelector("[data-retrieval-slo-trends]");
    if (trendList) {
      trendList.innerHTML = "";
      const trends = slo.trends || {};
      Object.keys(trends).slice(0, 9).forEach((metric) => {
        const item = trends[metric] || {};
        const delta = item.delta || 0;
        const sign = delta > 0 ? "+" : "";
        trendList.appendChild(statusRow(
          retrievalSloLabel(metric),
          retrievalSloValue(metric, item.current) + " (" + sign + retrievalSloValue(metric, delta) + ")"
        ));
      });
      if (!Object.keys(trends).length) {
        trendList.appendChild(statusRow("Trend", "noch keine Messwerte"));
      }
    }

    const warningList = root.querySelector("[data-retrieval-slo-warnings]");
    if (warningList) {
      warningList.innerHTML = "";
      const warnings = slo.warnings || [];
      if (!warnings.length) {
        warningList.appendChild(statusRow("SLO Status", "keine Warnungen"));
      } else {
        warnings.forEach((warning) => {
          warningList.appendChild(statusRow(
            retrievalSloLabel(warning.metric),
            readinessLabel(warning.status) + " ab " + retrievalSloValue(warning.metric, warning.threshold)
          ));
        });
      }
    }
    renderOverviewState();
    renderSafetyFallbackSummary();
    renderSectionStatusSummaries();
    renderAiClaritySummary();
  }

  function monitoringStatus(metrics, qualityMetrics) {
    const errorRate = Number((metrics && metrics.error_rate) || 0);
    const emptyRate = Number((metrics && metrics.empty_retrieval_rate) || 0);
    const warnings = Number((metrics && metrics.hallucination_warning_count) || 0);
    const hitRate = Number((qualityMetrics && qualityMetrics.retrieval_hit_rate) || 0);
    if (errorRate >= 0.25 || emptyRate >= 0.35 || warnings >= 5 || hitRate < 0.5) {
      return "critical";
    }
    if (errorRate > 0 || emptyRate >= 0.15 || warnings > 0 || hitRate < 0.75) {
      return "warning";
    }
    return "ok";
  }

  function monitoringKpiValue(key, metrics, qualityMetrics) {
    const source = key in qualityMetrics ? qualityMetrics : metrics;
    const value = source[key];
    if (key.includes("rate") || key.includes("similarity")) return percentText(value);
    if (key.includes("_ms")) return msText(Math.round(Number(value || 0)));
    return numberText(value);
  }

  function renderMiniBar(target, label, value, maxValue) {
    const row = document.createElement("div");
    const header = document.createElement("div");
    const bar = document.createElement("span");
    const fill = document.createElement("i");
    const safeMax = Math.max(Number(maxValue || 0), Number(value || 0), 1);
    row.className = "ai-mini-bar";
    header.append(statusPill(label, "is-muted"), document.createElement("strong"));
    header.querySelector("strong").textContent = numberText(value);
    fill.style.width = Math.max(4, Math.round((Number(value || 0) / safeMax) * 100)) + "%";
    bar.appendChild(fill);
    row.append(header, bar);
    target.appendChild(row);
  }

  function renderMonitoringList(target, title, rows, emptyText, rowRenderer) {
    if (!target) return;
    target.innerHTML = "";
    const heading = document.createElement("div");
    const headingTitle = document.createElement("strong");
    heading.className = "ai-monitor-list-header";
    headingTitle.textContent = title;
    heading.appendChild(headingTitle);
    target.appendChild(heading);
    if (!rows || !rows.length) {
      target.appendChild(statusRow(title, emptyText));
      return;
    }
    rows.forEach((row, index) => target.appendChild(rowRenderer(row, index)));
  }

  function monitoringRow(label, value, meta, className) {
    const row = document.createElement("article");
    const title = document.createElement("strong");
    const detail = document.createElement("span");
    const foot = document.createElement("small");
    row.className = "ai-monitor-row " + (className || "");
    title.textContent = label;
    detail.textContent = value;
    foot.textContent = meta || "";
    row.append(title, detail, foot);
    return row;
  }

  function renderAiObservability(payload) {
    latestAiObservability = payload || {};
    const metrics = latestAiObservability.metrics || {};
    const quality = latestAiObservability.quality_metrics || {};
    const retrieval = latestAiObservability.retrieval_monitoring || {};
    const status = monitoringStatus(metrics, quality);
    const statusTarget = root.querySelector("[data-ai-observability-status]");
    if (statusTarget) {
      statusTarget.textContent = readinessLabel(status);
      statusTarget.className = "badge badge-ai " + healthClass(status);
    }
    root.querySelectorAll("[data-ai-monitoring-kpi]").forEach((target) => {
      const key = target.dataset.aiMonitoringKpi;
      target.textContent = monitoringKpiValue(key, metrics, quality);
    });
    renderTopQuestions(metrics.top_questions || []);
    renderSourceDistribution(metrics.source_distribution_rows || []);
    renderRetrievalHits(retrieval);
    renderQualityMetrics(quality, retrieval.score_summary || {});
    renderAiObservabilityLogs(latestAiObservability.ai_logs || []);
    renderDebugTools(latestAiObservability.debug_tools || {});
    renderSafetyFallbackSummary();
    renderSectionStatusSummaries();
    renderAiClaritySummary();
  }

  function renderTopQuestions(rows) {
    renderMonitoringList(
      root.querySelector("[data-ai-top-questions]"),
      "Häufigste Fragen",
      rows,
      "noch keine Fragen",
      (row, index) => monitoringRow(
        "Fragegruppe " + (index + 1),
        numberText(row.count) + "x",
        "Ø Confidence " + text(row.average_confidence) + " - Inhalt ausgeblendet"
      )
    );
  }

  function renderSourceDistribution(rows) {
    const target = root.querySelector("[data-ai-source-distribution]");
    if (!target) return;
    target.innerHTML = "";
    const heading = document.createElement("div");
    heading.className = "ai-monitor-list-header";
    heading.appendChild(document.createElement("strong"));
    heading.querySelector("strong").textContent = "Quellenverteilung";
    target.appendChild(heading);
    if (!rows.length) {
      target.appendChild(statusRow("Quellen", "noch keine Quellen genutzt"));
      return;
    }
    const maxValue = Math.max(...rows.map((row) => Number(row.count || 0)), 1);
    rows.forEach((row) => renderMiniBar(target, sourceTypeLabel(row.key), row.count, maxValue));
  }

  function renderRetrievalHits(retrieval) {
    renderMonitoringList(
      root.querySelector("[data-ai-top-hits]"),
      "Top Treffer",
      retrieval.top_hits || [],
      "noch keine Treffer",
      (row) => monitoringRow(
        truncateLabel(row.label, 120),
        "Score " + scoreText(row.score),
        "Rank " + text(row.rank) + " · Similarity " + scoreText(row.similarity)
      )
    );
    renderMonitoringList(
      root.querySelector("[data-ai-poor-hits]"),
      "Schlechte Treffer",
      retrieval.poor_hits || [],
      "keine auffälligen Treffer",
      (row) => monitoringRow(
        truncateLabel(row.label, 120),
        "Score " + scoreText(row.score),
        "Similarity " + scoreText(row.similarity),
        "is-warning"
      )
    );
    renderMonitoringList(
      root.querySelector("[data-ai-chunk-usage]"),
      "Chunk-Nutzung",
      retrieval.chunk_usage || [],
      "noch keine Chunk-Nutzung",
      (row) => monitoringRow(
        truncateLabel(row.label || row.source_type + " #" + row.source_id, 120),
        numberText(row.uses) + " Nutzungen",
        row.chunk_id ? "Chunk #" + row.chunk_id : "ohne Chunk"
      )
    );
  }

  function renderQualityMetrics(quality, scoreSummary) {
    const rows = [
      ["Recall@K", quality.recall_at_k == null ? "-" : percentText(quality.recall_at_k)],
      ["Trefferquote", percentText(quality.retrieval_hit_rate)],
      ["Leere Suchläufe", percentText(quality.empty_retrieval_rate)],
      ["Similarity Ø", percentText(quality.average_similarity_score)],
      ["Score Ø", scoreText(scoreSummary.average_score)],
      ["Niedrige Ähnlichkeit", numberText(quality.low_similarity_count)]
    ];
    renderMonitoringList(
      root.querySelector("[data-ai-quality-metrics]"),
      "Qualitätsmetriken",
      rows,
      "noch keine Metriken",
      (row) => monitoringRow(row[0], row[1], "")
    );
  }

  function renderAiObservabilityLogs(logs) {
    const tbody = root.querySelector("[data-ai-observability-logs]");
    if (!tbody) return;
    tbody.innerHTML = "";
    if (!logs.length) {
      renderAdminEmptyState(
        tbody,
        "Noch keine AI-Logs im Zeitraum.",
        "Monitoring-Daten erscheinen, sobald AI-Anfragen verarbeitet wurden."
      );
      return;
    }
    logs.forEach((item) => {
      const row = document.createElement("tr");
      const action = document.createElement("td");
      const button = document.createElement("button");
      button.type = "button";
      button.className = "btn btn-ghost btn-sm";
      button.dataset.aiDebugSelect = item.chat_message_id;
      button.textContent = "Analysieren";
      action.appendChild(button);
      row.append(
        cell(dateTimeText(item.created_at)),
        cell(recordReference("Chat", item.chat_message_id)),
        pillCell(answerQualityLabel(item.answer_quality), answerQualityClass(item.answer_quality)),
        cell(confidenceLabel(item.confidence)),
        cell(numberText(item.source_count)),
        cell(msText(item.response_duration_ms || item.retrieval_duration_ms || 0)),
        action
      );
      tbody.appendChild(row);
    });
  }

  function answerQualityLabel(value) {
    const labels = {
      good: "gut",
      ok: "ok",
      warning: "prüfen",
      risk: "Risiko"
    };
    return labels[value] || text(value);
  }

  function answerQualityClass(value) {
    if (value === "good") return "is-active";
    if (value === "risk") return "is-error";
    if (value === "warning") return "is-stale";
    return "is-muted";
  }

  function renderDebugTools(debugTools) {
    const select = root.querySelector("[data-ai-debug-request]");
    const analysisTarget = root.querySelector("[data-ai-debug-analysis]");
    const promptTarget = root.querySelector("[data-ai-debug-prompt]");
    if (!select || !analysisTarget || !promptTarget) return;
    const selectedId = String(debugTools.selected_chat_message_id || "");
    select.innerHTML = "";
    (debugTools.available_requests || []).forEach((item) => {
      const option = document.createElement("option");
      option.value = item.chat_message_id;
      option.textContent = recordReference("Chat", item.chat_message_id);
      option.selected = String(item.chat_message_id) === selectedId;
      select.appendChild(option);
    });
    if (!select.options.length) {
      const option = document.createElement("option");
      option.value = "";
      option.textContent = "Keine Anfrage vorhanden";
      select.appendChild(option);
    }
    renderDebugAnalysis(analysisTarget, debugTools.request_analysis);
    promptTarget.textContent = promptDebugText(debugTools.prompt_blueprint);
  }

  function renderDebugAnalysis(target, analysis) {
    target.innerHTML = "";
    if (!analysis) {
      target.appendChild(statusRow("Analyse", "noch keine Anfrage vorhanden"));
      return;
    }
    const retrieval = analysis.retrieval || {};
    const contextBuilder = analysis.context_builder || {};
    const stats = contextBuilder.stats || {};
    target.appendChild(statusRow("Frage", redactSensitiveText(analysis.question, "Inhalt ausgeblendet")));
    target.appendChild(statusRow("Query-Typ", queryTypeLabel((analysis.query_understanding || {}).query_type)));
    target.appendChild(statusRow("Quellen", numberText(retrieval.source_count)));
    target.appendChild(statusRow("Suchdauer", msText(retrieval.retrieval_duration_ms || 0)));
    target.appendChild(statusRow("Context Sections", numberText((contextBuilder.sections || []).length)));
    target.appendChild(statusRow("Kontextbudget", numberText(stats.used_chars) + " / " + numberText(stats.max_chars)));
    target.appendChild(statusRow("Confidence", confidenceLabel(analysis.confidence)));
    target.appendChild(statusRow("Warnungen", numberText((analysis.quality_warnings || []).length)));
  }

  function promptDebugText(prompt) {
    if (!prompt) return "Kein Prompt-Blueprint geladen.";
    return [
      "System Prompt:",
      redactSensitiveText(prompt.system_prompt, "ausgeblendet"),
      "",
      "Kontextsicht:",
      prompt.context_visibility || "-",
      "",
      "Prompt Preview:",
      redactSensitiveText(prompt.prompt_preview, "ausgeblendet"),
      "",
      "Quellen:",
      (prompt.source_references || []).map((source) => "- " + sourceReferenceLabel(source)).join("\n") || "-",
      "",
      "Hinweis:",
      "Rohprompts, Chatfragen und Antworttexte werden in dieser Admin-Ansicht nicht angezeigt."
    ].join("\n");
  }

  async function loadAiObservability(chatMessageId) {
    const params = new URLSearchParams({ days: "30", limit: "10" });
    if (chatMessageId) params.set("chat_message_id", chatMessageId);
    const payload = await api("/api/v1/admin/ai/observability?" + params.toString());
    renderAiObservability(payload);
  }

  function retrievalEvaluationValue(metric, value) {
    if (metric === "recall_at_k" || metric === "mrr" || metric === "ndcg_at_k") {
      return percentText(value);
    }
    return numberText(value);
  }

  function retrievalEvaluationLabel(metric) {
    const labels = {
      recall_at_k: "Recall@K",
      mrr: "MRR",
      ndcg_at_k: "nDCG@K",
      permission_leak_count: "Permission Leaks",
      forbidden_source_hit_count: "Verbotene Quellen",
      no_result_count: "Keine Treffer"
    };
    return labels[metric] || text(metric);
  }

  function renderRetrievalEvaluationHistory(payload) {
    const history = (payload && payload.retrieval_evaluation_history) || {};
    const latest = history.latest || {};
    const regression = history.regression || {};
    const status = history.unavailable ? "warning" : (regression.regressed ? "warning" : "ok");
    const statusTarget = root.querySelector("[data-retrieval-evaluation-status]");
    if (statusTarget) {
      statusTarget.textContent = history.unavailable ? "Nicht verfügbar" : readinessLabel(status);
      statusTarget.className = "badge badge-ai " + healthClass(status);
    }

    root.querySelectorAll("[data-retrieval-evaluation-kpi]").forEach((target) => {
      const key = target.dataset.retrievalEvaluationKpi;
      target.textContent = retrievalEvaluationValue(key, latest[key]);
    });

    const regressionList = root.querySelector("[data-retrieval-evaluation-regression]");
    if (regressionList) {
      regressionList.innerHTML = "";
      const signals = regression.signals || [];
      if (!latest.id) {
        regressionList.appendChild(statusRow("Golden Eval", "noch keine Runs gespeichert"));
      } else if (!signals.length) {
        regressionList.appendChild(statusRow("Regression", "keine Regression erkannt"));
      } else {
        signals.forEach((signal) => {
          const delta = signal.delta > 0 ? "+" + signal.delta : signal.delta;
          regressionList.appendChild(statusRow(
            retrievalEvaluationLabel(signal.metric),
            retrievalEvaluationValue(signal.metric, signal.current) + " (" + delta + ")"
          ));
        });
      }
    }

    const runList = root.querySelector("[data-retrieval-evaluation-runs]");
    if (runList) {
      runList.innerHTML = "";
      const runs = history.runs || [];
      if (!runs.length) {
        runList.appendChild(statusRow("Historie", "keine gespeicherten Runs"));
      } else {
        runs.slice(0, 5).forEach((run) => {
          runList.appendChild(statusRow(
            dateTimeText(run.created_at),
            retrievalEvaluationValue("recall_at_k", run.recall_at_k)
              + " / "
              + retrievalEvaluationValue("mrr", run.mrr)
              + " / "
              + retrievalEvaluationValue("ndcg_at_k", run.ndcg_at_k)
          ));
        });
      }
    }
  }

  async function loadRetrievalTelemetry() {
    const telemetry = await api("/api/v1/admin/ai/retrieval-telemetry?days=30&limit=5");
    latestRetrievalTelemetry = telemetry;
    renderRetrievalSlo(telemetry);
    renderRetrievalEvaluationHistory(telemetry);
  }

  function renderAiStatus(status) {
    latestAiStatus = status || {};
    const card = root.querySelector("[data-ai-model-card]");
    const label = root.querySelector("[data-ai-model-status]");
    const detail = root.querySelector("[data-ai-model-detail]");
    if (!card || !label || !detail) return;
    card.classList.remove("is-active", "is-stale", "is-error");
    card.classList.add(latestAiStatus.ready ? "is-active" : "is-stale");
    label.textContent = latestAiStatus.model || "lokal";
    detail.textContent = [
      latestAiStatus.provider || "provider offen",
      latestAiStatus.streaming_enabled ? "Streaming aktiv" : "Streaming aus",
      latestAiStatus.last_error ? "Fehler: " + latestAiStatus.last_error : "kein letzter Fehler"
    ].join(" - ");
    renderProviderConfiguration(latestAiStatus);
    renderCapabilities();
    renderOverviewState();
    renderSafetyFallbackSummary();
    renderSectionStatusSummaries();
    renderAiClaritySummary();
  }

  async function loadAiStatus() {
    const status = await api("/api/v1/ai/status");
    renderAiStatus(status);
  }

  function renderOverviewState() {
    const target = root.querySelector("[data-ai-overview-state]");
    if (!target) return;
    const aiReady = !latestAiStatus || latestAiStatus.ready !== false;
    const ragScore = Number((latestKnowledgeStatus || {}).readiness_score || 0);
    const sloStatus = (
      latestRetrievalTelemetry
      && latestRetrievalTelemetry.retrieval_slo
      && latestRetrievalTelemetry.retrieval_slo.status
    ) || "ok";
    const critical = !aiReady || ragScore < 40 || sloStatus === "critical";
    const warning = !critical && (ragScore < 80 || sloStatus === "warning");
    target.textContent = critical ? "Handlungsbedarf" : (warning ? "Beobachten" : "Betriebsbereit");
    target.className = "badge badge-ai " + (critical ? "is-error" : (warning ? "is-stale" : "is-active"));
  }

  function capabilityGroups() {
    const ragReady = Number((latestKnowledgeStatus || {}).readiness_score || 0) >= 60;
    const modelReady = !latestAiStatus || latestAiStatus.ready !== false;
    return {
      supported: [
        ["Permission-aware Retrieval", "Quellen werden rollen- und berechtigungsbewusst gefiltert."],
        ["Fehlerkatalog-Assistenz", "Fehlercodes, Ursachen und L&ouml;sungen bleiben strukturiert nutzbar."],
        ["Confidence & Explainability", "Antworten zeigen Score, Begr&uuml;ndung und verwendete Quellen."],
        ["Safety Checks", "Riskante Wartungshinweise werden vor und nach der Generierung gepr&uuml;ft."]
      ],
      partial: [
        [
          "RAG & Dokumentwissen",
          ragReady
            ? "Aktiv, aber abh&auml;ngig von Indexfrische und Quellenqualit&auml;t."
            : "Nur eingeschr&auml;nkt, solange Readiness oder Chunks fehlen."
        ],
        ["Golden Retrieval Evaluation", "Historie ist vorhanden, ben&ouml;tigt regelm&auml;&szlig;ige Runs f&uuml;r Trends."],
        [
          "OpenAI-Anbindung",
          modelReady ? "Konfiguriert; Fallbacks bleiben m&ouml;glich." : "Nicht voll bereit; lokale/strukturierte Antworten bleiben m&ouml;glich."
        ],
        ["Knowledge Network", "Read-only Analyse verf&uuml;gbar; keine GraphDB erforderlich."]
      ],
      unsupported: [
        ["Autonome Maschinenfreigaben", "Die KI darf keine sicherheitskritischen Freigaben erteilen."],
        ["Arbeiten unter Spannung", "Gef&auml;hrliche Schritt-f&uuml;r-Schritt-Anleitungen werden entsch&auml;rft."],
        ["Ungefilterte Prompt-/Chunk-Einsicht", "Admin-Debug bleibt prompt-sicher und zeigt keine sensiblen Rohtexte."]
      ]
    };
  }

  function renderCapabilityCard(target, title, detail, tone) {
    const card = document.createElement("article");
    const heading = document.createElement("strong");
    const textNode = document.createElement("p");
    card.className = "ai-capability-card " + tone;
    heading.innerHTML = title;
    textNode.innerHTML = detail;
    card.append(heading, textNode);
    target.appendChild(card);
  }

  function renderCapabilities() {
    const groups = capabilityGroups();
    Object.keys(groups).forEach((key) => {
      const target = root.querySelector('[data-ai-capabilities="' + key + '"]');
      if (!target) return;
      target.innerHTML = "";
      const tone = key === "supported" ? "is-active" : (key === "unsupported" ? "is-muted" : "is-stale");
      groups[key].forEach(([title, detail]) => renderCapabilityCard(target, title, detail, tone));
    });
  }

  function renderAnswerQualityGuide() {
    const target = root.querySelector("[data-ai-answer-quality-guide]");
    if (!target) return;
    target.innerHTML = "";
    [
      ["Quellen", "Verwendete Quellen und Dokumente werden als Chips angezeigt.", "is-active"],
      ["Confidence Score", "Hoch, mittel oder niedrig mit visueller Skala.", "is-active"],
      ["Antwortqualit&auml;t", "SLOs, Feedback und Golden Eval zeigen Qualit&auml;t &uuml;ber Zeit.", "is-stale"],
        ["Unsicherheit", "Niedrige Sicherheit, Konflikte und fehlende Quellen werden sichtbar markiert.", "is-stale"],
      ["Safety", "Sicherheitsrelevante Inhalte erhalten klare Warnhinweise.", "is-error"],
      ["Dokumentbezug", "Abschnitte, Chunks und Quelle-zu-Antwort-Bezug bleiben nachvollziehbar.", "is-active"]
    ].forEach(([title, detail, tone]) => {
      renderCapabilityCard(target, title, detail, tone);
    });
  }

  function renderWorkflowMetrics(workflows) {
    const tbody = root.querySelector("[data-ai-workflows]");
    if (!tbody) return;
    tbody.innerHTML = "";
    if (!workflows.length) {
      const row = document.createElement("tr");
      const empty = document.createElement("td");
      empty.colSpan = 7;
      empty.textContent = "Noch keine AI-Workflow-Metriken vorhanden.";
      row.appendChild(empty);
      tbody.appendChild(row);
      return;
    }
    workflows.slice(0, 8).forEach((workflow) => {
      const row = document.createElement("tr");
      row.append(
        cell(workflow.workflow),
        cell(numberText(workflow.events)),
        cell(percentText(workflow.fallback_rate)),
        cell(numberText(workflow.errors)),
        cell(numberText(workflow.total_tokens)),
        cell(moneyText(workflow.estimated_cost_usd)),
        cell(numberText(workflow.average_latency_ms) + " ms")
      );
      tbody.appendChild(row);
    });
  }

  function renderTopErrors(errors) {
    const list = root.querySelector("[data-ai-top-errors]");
    if (!list) return;
    list.innerHTML = "";
    if (!errors.length) {
      list.appendChild(statusRow("AI Fehler", "keine Fehler im Zeitraum"));
      return;
    }
    errors.slice(0, 6).forEach((item) => {
      list.appendChild(statusRow(item.error_category, numberText(item.count)));
    });
  }

  function lifecycleKpiValue(lifecycle, key) {
    const reviewQueue = lifecycle.review_queue || {};
    const qualityGate = lifecycle.rag_quality_gate || {};
    if (key === "needs_admin_approval") return reviewQueue.needs_admin_approval || 0;
    if (key === "non_approved_indexed_documents") {
      return qualityGate.non_approved_indexed_documents || 0;
    }
    return lifecycle[key] || 0;
  }

  function renderLifecycle(lifecycle) {
    const data = lifecycle || {};
    root.querySelectorAll("[data-lifecycle-kpi]").forEach((target) => {
      target.textContent = numberText(lifecycleKpiValue(data, target.dataset.lifecycleKpi));
    });

    const state = root.querySelector("[data-knowledge-lifecycle-state]");
    if (state) {
      const hasProblems = Number(data.problem_documents || 0) > 0;
      const reviewQueue = data.review_queue || {};
      const hasReview = Number(reviewQueue.needs_technician_review || 0) > 0
        || Number(reviewQueue.needs_admin_approval || 0) > 0
        || Number(reviewQueue.needs_quality_review || 0) > 0
        || Number(reviewQueue.needs_refresh || 0) > 0;
      state.textContent = hasProblems ? "kritisch" : (hasReview ? "Review offen" : "bereit");
      state.className = "badge badge-ai "
        + (hasProblems ? "is-error" : (hasReview ? "is-stale" : "is-active"));
    }

    renderLifecycleReview(data.review_queue || {});
    renderLifecycleGate(data.rag_quality_gate || {});
    renderLifecycleActions(data.next_actions || []);
    renderLifecycleSteps(data.steps || []);
  }

  function renderLifecycleReview(reviewQueue) {
    const list = root.querySelector("[data-knowledge-lifecycle-review]");
    if (!list) return;
    list.innerHTML = "";
    list.append(
      statusRow("Techniker-Review", numberText(reviewQueue.needs_technician_review || 0)),
      statusRow("Admin-Freigabe", numberText(reviewQueue.needs_admin_approval || 0)),
      statusRow("Quality-Review", numberText(reviewQueue.needs_quality_review || 0)),
      statusRow("Low Quality", numberText(reviewQueue.low_quality || 0)),
      statusRow("Duplikate", numberText(reviewQueue.duplicate || 0)),
      statusRow("Refresh", numberText(reviewQueue.needs_refresh || 0)),
      statusRow("Abgelehnt", numberText(reviewQueue.rejected || 0))
    );
  }

  function renderLifecycleGate(qualityGate) {
    const list = root.querySelector("[data-knowledge-lifecycle-gate]");
    if (!list) return;
    list.innerHTML = "";
    list.append(
      statusRow("Quality Gate", qualityGate.enabled ? "aktiv" : "diagnostisch"),
      statusRow(
        "Freigegeben indexiert",
        numberText(qualityGate.approved_indexed_documents || 0)
      ),
      statusRow(
        "Nicht freigegeben indexiert",
        numberText(qualityGate.non_approved_indexed_documents || 0)
      ),
      statusRow("Hinweis", qualityGate.reason || "-")
    );
  }

  function renderLifecycleActions(actions) {
    const list = root.querySelector("[data-knowledge-lifecycle-actions]");
    if (!list) return;
    list.innerHTML = "";
    const items = actions.length ? actions : ["Keine offenen Lifecycle-Aktionen."];
    items.slice(0, 6).forEach((action, index) => {
      list.appendChild(statusRow("Aktion " + (index + 1), action));
    });
  }

  function renderLifecycleSteps(steps) {
    const list = root.querySelector("[data-knowledge-lifecycle-steps]");
    if (!list) return;
    list.innerHTML = "";
    if (!steps.length) {
      list.appendChild(statusRow("Lifecycle", "keine Diagnostik vorhanden"));
      return;
    }
    steps.slice(0, 9).forEach((step) => {
      list.appendChild(statusRow(step.label, lifecycleStepStatusLabel(step.status)));
    });
  }

  function vectorSyncEventText(event) {
    if (!event) return "-";
    const timestamp = event.synced_at || event.failed_at;
    return "#" + text(event.document_id) + " " + dateTimeText(timestamp);
  }

  function renderVectorStoreStatus(vectorStatus) {
    const syncList = root.querySelector("[data-rag-vector-sync]");
    const issueList = root.querySelector("[data-rag-vector-issues]");
    const data = vectorStatus || {};
    if (syncList) {
      syncList.innerHTML = "";
      syncList.append(
        statusRow("Suchindex Backend", data.store || "-"),
        statusRow("Konfiguriert", data.configured_store || "-"),
        statusRow("Ausweichbetrieb", data.fallback_active ? "aktiv" : "nein"),
        statusRow("Soll Vektoren", numberText(data.expected_vector_count || 0)),
        statusRow("Ist Vektoren", data.actual_vector_count == null ? "-" : numberText(data.actual_vector_count)),
        statusRow("Letzter Index", dateTimeText(data.latest_indexed_at)),
        statusRow("Letzter Sync", vectorSyncEventText(data.last_successful_sync)),
        statusRow("Letzter Fehler", vectorSyncEventText(data.last_failed_sync))
      );
    }
    if (issueList) {
      issueList.innerHTML = "";
      issueList.append(
        statusRow("Reindex empfohlen", data.reindex_recommended ? "ja" : "nein"),
        statusRow("Stale Dokumente", numberText(data.stale_document_count || 0)),
        statusRow("Fehlende Chunks", numberText(data.missing_chunk_count || 0)),
        statusRow("Chunk Mismatch", numberText(data.chunk_mismatch_count || 0)),
        statusRow("Sync-Fehler", numberText(data.vector_sync_failure_count || 0))
      );
      const reasons = data.reindex_reasons || [];
      if (reasons.length) {
        issueList.appendChild(statusRow("Grund", reasons.join(", ")));
      }
    }
  }

  function renderKnowledgeStatus(status) {
    latestKnowledgeStatus = status || {};
    ["documents", "indexed", "stale", "pending", "searchable_documents", "chunks"].forEach((key) => {
      const target = root.querySelector('[data-rag-kpi="' + key + '"]');
      if (target) target.textContent = text(status[key]);
    });

    const readiness = root.querySelector("[data-rag-readiness]");
    if (readiness) {
      readiness.textContent = status.diagnostics && status.diagnostics.ready
        ? "bereit"
        : "nicht bereit";
    }
    const score = Number(status.readiness_score || 0);
    const scoreTarget = root.querySelector("[data-rag-readiness-score]");
    if (scoreTarget) scoreTarget.textContent = score + "/100";
    const ragHealth = score >= 80 ? "ok" : (score >= 40 ? "warning" : "critical");
    setHealthCard(
      "rag",
      ragHealth,
      score + "/100 - " + (status.readiness_reasons || []).join(" ")
    );

    const sourceList = root.querySelector("[data-rag-source-status]");
    if (sourceList) {
      sourceList.innerHTML = "";
      const sourceTypes = status.source_types || [];
      if (!sourceTypes.length) {
        sourceList.appendChild(statusRow("Quellen", "Noch keine Daten indexiert"));
      } else {
        sourceTypes.forEach((item) => {
          sourceList.appendChild(statusRow(
            sourceTypeLabel(item.source_type),
            item.searchable_documents + "/" + item.documents + " durchsuchbar, " + item.chunks + " Chunks"
          ));
        });
      }
    }

    const diagnostics = status.diagnostics || {};
    const diagnosticList = root.querySelector("[data-rag-diagnostics]");
    if (diagnosticList) {
      diagnosticList.innerHTML = "";
      diagnosticList.append(
        statusRow("RAG aktiv", diagnostics.rag_enabled ? "ja" : "nein"),
        statusRow("Suchindex", diagnostics.vector_store),
        statusRow("Embedding-Anbieter", diagnostics.embedding_provider),
        statusRow("Chunking", diagnostics.chunk_size + " / " + diagnostics.chunk_overlap),
        statusRow("Top K", diagnostics.top_k),
        statusRow("Scan Limit", diagnostics.scan_limit)
      );
    }

    const reasonList = root.querySelector("[data-rag-readiness-reasons]");
    if (reasonList) {
      reasonList.innerHTML = "";
      (status.readiness_reasons || ["Keine Readiness-Daten vorhanden."]).forEach((reason) => {
        reasonList.appendChild(statusRow("Readiness", reason));
      });
    }

    const problemList = root.querySelector("[data-rag-problem-documents]");
    if (problemList) {
      problemList.innerHTML = "";
      const problemDocuments = status.problem_documents || [];
      if (!problemDocuments.length) {
        problemList.appendChild(statusRow("Problemdokumente", "keine offenen Quellen"));
      } else {
        problemDocuments.forEach((documentItem) => {
          problemList.appendChild(statusRow(
            "#" + documentItem.id + " " + sourceTypeLabel(documentItem.source_type),
            documentItem.status + " - " + documentItem.title
          ));
        });
      }
    }

    renderLifecycle(status.lifecycle || {});
    renderVectorStoreStatus(status.vector_store || {});
    renderSourceHealth(status);
    renderCapabilities();
    renderOverviewState();
    renderSafetyFallbackSummary();
    renderSectionStatusSummaries();
  }

  async function loadKnowledgeStatus() {
    const status = await api("/api/v1/admin/ai/knowledge/status");
    renderKnowledgeStatus(status);
  }

  async function loadJobs() {
    const data = await api("/api/v1/admin/jobs?job_type=rag_reindex&limit=10");
    const tbody = root.querySelector("[data-ai-jobs]");
    const count = root.querySelector("[data-ai-job-count]");
    const statusList = root.querySelector("[data-ai-job-status]");
    tbody.innerHTML = "";
    if (count) count.textContent = data.pagination.total + " Jobs";
    const statusCounts = {};
    let oldestQueued = null;
    data.items.forEach((job) => {
      statusCounts[job.status] = (statusCounts[job.status] || 0) + 1;
      if (job.status === "queued" && !oldestQueued) oldestQueued = job;
      const row = document.createElement("tr");
      row.dataset.jobStatus = job.status;
      row.append(
        cell(job.id),
        cell(job.job_type),
        cell(job.status),
        cell(job.attempts + "/" + job.max_attempts),
        cell(safeJobResultText(job))
      );
      tbody.appendChild(row);
    });
    if (!data.items.length) {
      renderAdminEmptyState(
        tbody,
        "Keine RAG-Reindex-Jobs vorhanden.",
        "Plane einen Job ein, wenn neue oder veraltete Quellen indexiert werden sollen."
      );
    }
    if (statusList) {
      statusList.innerHTML = "";
      statusList.append(
        statusRow("Queued", statusCounts.queued || 0),
        statusRow("Running", statusCounts.running || 0),
        statusRow("Failed", statusCounts.failed || 0),
        statusRow("Done", statusCounts.done || 0),
        statusRow("Ältester queued Job", oldestQueued ? "#" + oldestQueued.id : "-")
      );
    }
    latestJobSummary = {
      total: data.pagination.total,
      statusCounts,
      latestJob: data.items[0] || null
    };
    renderSectionStatusSummaries();
  }

  /**
   * Return a prompt-safe job result summary without raw exception or payload data.
   */
  function safeJobResultText(job) {
    if (!job) return "-";
    if (job.status === "failed") return "Fehlerdetails ausgeblendet";
    const result = job.result || {};
    if (result.indexed != null || result.chunks != null) {
      return "Indexiert: " + numberText(result.indexed || 0) + " / Chunks: " + numberText(result.chunks || 0);
    }
    if (job.status === "done") return "abgeschlossen";
    if (job.status === "running") return "läuft";
    if (job.status === "queued") return "wartet";
    return "-";
  }

  function renderOperationsMetrics(data) {
    latestOperationsStatus = data || {};
    const database = data.database || {};
    const jobs = data.background_jobs || {};
    const ai = data.ai || {};
    const rag = data.rag || {};
    const generated = root.querySelector("[data-ops-generated]");
    const dbLatency = root.querySelector('[data-ops-kpi="database_latency_ms"]');
    const queueLength = root.querySelector('[data-ops-kpi="queue_length"]');
    const runningJobs = root.querySelector('[data-ops-kpi="running_jobs"]');
    const failedJobs = root.querySelector('[data-ops-kpi="failed_jobs"]');
    const aiLatency = root.querySelector('[data-ops-kpi="ai_latency_ms"]');
    const ragStale = root.querySelector('[data-ops-kpi="rag_stale_ratio"]');
    const oldestQueuedAge = root.querySelector('[data-ops-kpi="oldest_queued_age"]');
    const jobAvgDuration = root.querySelector('[data-ops-kpi="job_avg_duration"]');
    if (generated) generated.textContent = data.generated_at ? new Date(data.generated_at).toLocaleTimeString("de-DE") : "-";
    if (dbLatency) dbLatency.textContent = text(database.latency_ms) + " ms";
    if (queueLength) queueLength.textContent = text(jobs.queue_length);
    if (runningJobs) runningJobs.textContent = text(jobs.running);
    if (failedJobs) failedJobs.textContent = text(jobs.failed);
    if (aiLatency) aiLatency.textContent = text(ai.avg_latency_ms) + " ms";
    if (ragStale) ragStale.textContent = Math.round((rag.stale_ratio || 0) * 100) + "%";
    if (oldestQueuedAge) oldestQueuedAge.textContent = secondsText(jobs.oldest_queued_age_seconds);
    if (jobAvgDuration) jobAvgDuration.textContent = secondsText(jobs.recent_avg_duration_seconds);
    const queueStatus = jobs.failed ? "critical" : (jobs.queue_length || jobs.running ? "warning" : "ok");
    setHealthCard(
      "queue",
      queueStatus,
      (jobs.queue_length || 0) + " queued, " + (jobs.running || 0) + " running, "
      + (jobs.failed || 0) + " failed"
    );
    renderSectionStatusSummaries();

    const slowList = root.querySelector("[data-ops-slow-endpoints]");
    if (!slowList) return;
    slowList.innerHTML = "";
    const slowEndpoints = (data.requests && data.requests.slow_endpoints) || [];
    if (!slowEndpoints.length) {
      slowList.appendChild(statusRow("Slow Endpoints", "noch keine Messwerte"));
      return;
    }
    slowEndpoints.slice(0, 5).forEach((item) => {
      slowList.appendChild(
        statusRow(
          item.endpoint,
          item.avg_duration_ms + " ms avg / " + item.slow_count + " slow"
        )
      );
    });
  }

  async function loadOperationsMetrics() {
    const data = await api("/api/v1/health/operations");
    renderOperationsMetrics(data);
  }

  function isFailedAiEvent(event) {
    const status = String((event && event.status) || "").toLowerCase();
    return Boolean(
      event
      && (
        event.error_category
        || status.includes("error")
        || status.includes("failed")
        || status.includes("timeout")
      )
    );
  }

  function renderFailedQueries(events) {
    const target = root.querySelector("[data-ai-failed-queries]");
    if (!target) return;
    target.innerHTML = "";
    const failedEvents = (events || []).filter(isFailedAiEvent).slice(0, 6);
    if (!failedEvents.length) {
      renderAdminEmptyState(
        target,
        "Keine fehlgeschlagenen AI-Queries im aktuellen Filter.",
        "Provider-, Modell-, Timeout- und Retrieval-Fehler erscheinen hier metadata-only."
      );
      return;
    }
    failedEvents.forEach((event) => {
      const item = document.createElement("article");
      const title = document.createElement("strong");
      const detail = document.createElement("small");
      const badge = statusPill(event.error_category || event.status || "failed", "is-error");
      item.className = "list-card ai-failed-query-card";
      title.textContent = recordReference("Audit", event.id);
      detail.textContent = [
        dateTimeText(event.created_at),
        "Workflow " + text(event.workflow),
        "Status " + text(event.status),
        "Tokens " + numberText(event.total_tokens || 0)
      ].join(" - ");
      item.append(title, badge, detail);
      target.appendChild(item);
    });
  }

  async function loadEvents() {
    const errorInput = root.querySelector("[data-ai-event-error]");
    const error = errorInput ? errorInput.value : "";
    const data = await api("/api/v1/admin/ai/events?limit=20&error=" + encodeURIComponent(error));
    const tbody = root.querySelector("[data-ai-events]");
    renderFailedQueries(data.items || []);
    if (!tbody) return;
    tbody.innerHTML = "";
    if (!data.items.length) {
      renderAdminEmptyState(
        tbody,
        "Keine AI-Fehler für diesen Filter.",
        "Der Zeitraum enthält keine passenden Provider-, Modell- oder Timeout-Ereignisse."
      );
      return;
    }
    data.items.forEach((event) => {
      const row = document.createElement("tr");
      row.append(
        cell(event.created_at),
        cell(event.workflow),
        cell(event.status),
        cell(event.error_category),
        cell(event.total_tokens)
      );
      tbody.appendChild(row);
    });
  }

  async function loadChats() {
    const query = root.querySelector("[data-ai-chat-search]").value;
    const data = await api("/api/v1/admin/ai/chats?limit=20&q=" + encodeURIComponent(query));
    const list = root.querySelector("[data-ai-chats]");
    list.innerHTML = "";
    if (!data.items.length) {
      renderAdminEmptyState(
        list,
        "Keine AI-Anfragen für diese Suche.",
        "Chat-Inhalte werden in dieser Admin-Übersicht nicht direkt angezeigt."
      );
      return;
    }
    data.items.forEach((chat) => {
      const item = document.createElement("article");
      item.className = "list-card";
      const reference = document.createElement("strong");
      const privacyNote = document.createElement("p");
      const meta = document.createElement("small");
      reference.textContent = recordReference("Chat", chat.id);
      privacyNote.textContent = redactSensitiveText(
        chat.message,
        "Frage und Antwort sind in dieser Übersicht ausgeblendet."
      );
      meta.textContent = [
        "Typ " + text(chat.response_type),
        "Quellen " + numberText(chat.source_count || 0),
        "Confidence " + confidenceLabel({
          score: chat.confidence_score,
          level: chat.confidence_level
        }),
        dateTimeText(chat.created_at)
      ].join(" - ");
      item.append(reference, privacyNote, meta);
      list.appendChild(item);
    });
  }

  async function loadKnowledgeGaps() {
    const data = await api("/api/v1/admin/ai/knowledge-gaps?status=open&limit=10");
    latestKnowledgeGaps = data || {};
    const tbody = root.querySelector("[data-ai-knowledge-gaps]");
    const count = root.querySelector("[data-ai-knowledge-gap-count]");
    if (count) count.textContent = numberText(data.open_count || 0) + " offen";
    if (!tbody) return;
    tbody.innerHTML = "";
    if (!data.items.length) {
      renderAdminEmptyState(
        tbody,
        "Keine offenen Knowledge Gaps.",
        "Die KI hat aktuell keine unbeantworteten Fragen mit Pflegebedarf gemeldet."
      );
      renderAiClaritySummary();
      return;
    }
    data.items.forEach((gap) => {
      const row = document.createElement("tr");
      row.append(
        cell(recordReference("Gap", gap.id)),
        cell(gap.department),
        cell(gap.machine),
        cell(gap.status),
        cell(gap.occurrence_count),
        cell(dateTimeText(gap.last_seen_at))
      );
      tbody.appendChild(row);
    });
    renderAiClaritySummary();
  }

  function trainingPayload(form) {
    return {
      title: form.elements.title.value.trim(),
      category: form.elements.category.value.trim() || "wartung",
      department: form.elements.department.value.trim(),
      keywords: form.elements.keywords.value.trim(),
      question: form.elements.question.value.trim(),
      answer: form.elements.answer.value.trim(),
      is_active: form.elements.is_active.checked,
      priority: Number(form.elements.priority.value || 50)
    };
  }

  function resetTrainingForm() {
    const form = root.querySelector("[data-ai-training-form]");
    if (!form) return;
    form.reset();
    form.elements.id.value = "";
    form.elements.is_active.checked = true;
    form.elements.priority.value = "50";
    const title = root.querySelector("[data-ai-training-editor-title]");
    const status = root.querySelector("[data-ai-training-editor-status]");
    if (title) title.textContent = "Neuer Trainingseintrag";
    if (status) {
      status.textContent = "Nach dem Speichern neu indexieren";
      status.className = "status-pill is-stale";
    }
    root.querySelectorAll(".training-card.is-selected").forEach((item) => {
      item.classList.remove("is-selected");
    });
  }

  function fillTrainingForm(entry) {
    const form = root.querySelector("[data-ai-training-form]");
    if (!form) return;
    form.elements.id.value = entry.id;
    form.elements.title.value = entry.title || "";
    form.elements.category.value = entry.category || "";
    form.elements.department.value = entry.department || "";
    form.elements.keywords.value = entry.keywords || "";
    form.elements.question.value = entry.question || "";
    form.elements.answer.value = entry.answer || "";
    form.elements.is_active.checked = Boolean(entry.is_active);
    form.elements.priority.value = entry.priority || 50;
    const title = root.querySelector("[data-ai-training-editor-title]");
    const status = root.querySelector("[data-ai-training-editor-status]");
    if (title) title.textContent = "Training bearbeiten";
    if (status) {
      status.textContent = entry.is_active ? "Aktiv im RAG-Index" : "Inaktiv, wird nicht genutzt";
      status.className = "status-pill " + (entry.is_active ? "is-active" : "is-muted");
    }
    root.querySelectorAll(".training-card").forEach((item) => {
      item.classList.toggle("is-selected", item.dataset.trainingId === String(entry.id));
    });
    form.elements.title.focus();
  }

  async function loadTraining() {
    const query = root.querySelector("[data-ai-training-search]").value;
    const active = root.querySelector("[data-ai-training-active]").value;
    const data = await api(
      "/api/v1/admin/ai/training?limit=50&q="
      + encodeURIComponent(query)
      + "&active="
      + encodeURIComponent(active)
    );
    const list = root.querySelector("[data-ai-training]");
    const selectedId = root.querySelector("[data-ai-training-form]").elements.id.value;
    list.innerHTML = "";
    if (!data.items.length) {
      renderAdminEmptyState(
        list,
        "Keine passenden Trainingseinträge gefunden.",
        "Passe Suche oder Statusfilter an oder lege einen neuen Trainingseintrag an."
      );
      return;
    }
    data.items.forEach((entry) => {
      const item = document.createElement("article");
      item.className = "training-card";
      item.dataset.trainingId = entry.id;
      item.classList.toggle("is-selected", selectedId === String(entry.id));
      const title = document.createElement("strong");
      const question = document.createElement("p");
      const meta = document.createElement("div");
      const actions = document.createElement("div");
      const editButton = document.createElement("button");
      const deleteButton = document.createElement("button");
      title.textContent = text(entry.title);
      question.textContent = text(entry.question);
      meta.className = "training-card-meta";
      meta.append(
        statusPill(entry.is_active ? "aktiv" : "inaktiv", entry.is_active ? "is-active" : "is-muted"),
        statusPill("Priorität " + text(entry.priority), ""),
        statusPill(text(entry.category), ""),
        statusPill(text(entry.department || "alle Abteilungen"), "")
      );
      actions.className = "training-card-actions";
      editButton.type = "button";
      editButton.className = "btn btn-secondary btn-sm";
      editButton.textContent = "Bearbeiten";
      editButton.addEventListener("click", () => fillTrainingForm(entry));
      deleteButton.type = "button";
      deleteButton.className = "btn btn-ghost btn-sm";
      deleteButton.dataset.deleteTraining = entry.id;
      deleteButton.textContent = "Löschen";
      actions.append(editButton, deleteButton);
      item.append(title, question, meta, actions);
      list.appendChild(item);
    });
  }

  /**
   * Load an unfiltered training snapshot for the AI Admin clarity overview.
   */
  async function loadTrainingSummary() {
    const data = await api("/api/v1/admin/ai/training?limit=100&active=");
    latestTrainingSummary = data || {};
    renderAiClaritySummary();
  }

  async function loadKnowledge() {
    const query = root.querySelector("[data-ai-knowledge-search]").value;
    const source = root.querySelector("[data-ai-knowledge-source]").value;
    const status = root.querySelector("[data-ai-knowledge-status]").value;
    const quality = root.querySelector("[data-ai-knowledge-quality]").value;
    const data = await api(
      "/api/v1/admin/ai/knowledge?limit=50&q="
      + encodeURIComponent(query)
      + "&source_type="
      + encodeURIComponent(source)
      + "&status="
      + encodeURIComponent(status)
      + "&quality_status="
      + encodeURIComponent(quality)
    );
    const tbody = root.querySelector("[data-ai-knowledge]");
    tbody.innerHTML = "";
    if (!data.items.length) {
      renderAdminEmptyState(
        tbody,
        "Keine Wissensquellen für diesen Filter.",
        "Passe Quelle, Indexstatus oder Qualitätsstatus an."
      );
      return;
    }
    data.items.forEach((documentItem) => {
      const row = document.createElement("tr");
      const actions = document.createElement("td");
      const reindexButton = document.createElement("button");
      const queueButton = document.createElement("button");
      const qualitySelect = knowledgeQualitySelect(documentItem);
      const qualityButton = document.createElement("button");
      reindexButton.type = "button";
      reindexButton.className = "btn btn-secondary btn-sm";
      reindexButton.dataset.reindexKnowledge = documentItem.id;
      reindexButton.textContent = "Indexieren";
      queueButton.type = "button";
      queueButton.className = "btn btn-ghost btn-sm";
      queueButton.dataset.queueKnowledge = documentItem.id;
      queueButton.textContent = "Job planen";
      qualityButton.type = "button";
      qualityButton.className = "btn btn-secondary btn-sm";
      qualityButton.dataset.updateKnowledgeQuality = documentItem.id;
      qualityButton.textContent = "Status setzen";
      const button = document.createElement("button");
      button.type = "button";
      button.className = "btn btn-ghost btn-sm";
      button.dataset.deleteKnowledge = documentItem.id;
      button.textContent = "Löschen";
      actions.className = "table-actions";
      actions.append(reindexButton, queueButton, qualitySelect, qualityButton, button);
      row.dataset.knowledgeStatus = documentItem.status;
      row.dataset.knowledgeQualityStatus = documentItem.quality_status || "draft";
      row.setAttribute("data-knowledge-origin", knowledgeOriginKind(documentItem));
      row.append(
        cell(documentItem.title),
        knowledgeSourceCell(documentItem),
        cell(documentItem.status),
        pillCell(
          qualityStatusLabel(documentItem.quality_status),
          qualityStatusClass(documentItem.quality_status)
        ),
        cell(documentItem.chunk_count),
        cell(documentItem.department),
        actions
      );
      tbody.appendChild(row);
    });
  }

  function knowledgeQualitySelect(documentItem) {
    const select = document.createElement("select");
    select.className = "input input-bordered";
    select.dataset.knowledgeQualitySelect = documentItem.id;
    select.setAttribute("aria-label", "Knowledge-Qualitätsstatus setzen");
    QUALITY_STATUS_OPTIONS.forEach((status) => {
      const option = document.createElement("option");
      option.value = status;
      option.textContent = qualityStatusLabel(status);
      option.selected = status === (documentItem.quality_status || "draft");
      select.appendChild(option);
    });
    return select;
  }

  function adminLoadersForView() {
    const loadersByView = {
      overview: [
        loadAiStatus,
        loadSummary,
        loadKnowledgeGaps,
        loadKnowledgeStatus,
        loadOperationsMetrics
      ],
      models: [
        loadAiStatus,
        loadSummary,
        loadEvents,
        loadChats,
        loadOperationsMetrics
      ],
      retrieval: [
        loadRetrievalDebug,
        loadRetrievalTelemetry,
        loadSummary
      ],
      knowledge: [
        loadKnowledgeStatus,
        loadTrainingSummary,
        loadKnowledge,
        loadKnowledgeNetwork,
        loadKnowledgeGaps,
        loadOperationsMetrics
      ],
      training: [
        loadTrainingSummary,
        loadTraining,
        loadKnowledgeStatus
      ],
      diagnostics: [
        loadSummary,
        loadEvents,
        loadKnowledgeGaps,
        loadAiObservability
      ],
      feedback: [
        loadSummary,
        loadKnowledgeGaps,
        loadRetrievalTelemetry,
        loadAiObservability
      ],
      indexing: [
        loadKnowledgeStatus,
        loadJobs,
        loadOperationsMetrics
      ]
    };
    return loadersByView[adminView] || loadersByView.overview;
  }

  async function refreshAll() {
    renderCapabilities();
    renderAnswerQualityGuide();
    await Promise.all(adminLoadersForView().map((loader) => loader()));
  }

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
    root._knowledgeNetworkTimer = window.setTimeout(() => runAdminLoad(loadKnowledgeNetwork, "Knowledge Network laden"), 250);
  });
  bind("[data-knowledge-network-focus]", "input", () => {
    window.clearTimeout(root._knowledgeNetworkFocusTimer);
    root._knowledgeNetworkFocusTimer = window.setTimeout(() => runAdminLoad(loadKnowledgeNetwork, "Knowledge Network laden"), 250);
  });
  bind("[data-knowledge-network-source]", "change", () => {
    runAdminLoad(loadKnowledgeNetwork, "Knowledge Network laden");
  });
  bind("[data-knowledge-network-quality]", "change", () => {
    runAdminLoad(loadKnowledgeNetwork, "Knowledge Network laden");
  });
  bind("[data-knowledge-network-focus-type]", "change", () => {
    runAdminLoad(loadKnowledgeNetwork, "Knowledge Network laden");
  });
  bind("[data-knowledge-network-refresh]", "click", () => {
    runAdminLoad(loadKnowledgeNetwork, "Knowledge Network laden");
  });
  bind("[data-retrieval-debug-search]", "input", () => {
    window.clearTimeout(root._retrievalDebugTimer);
    root._retrievalDebugTimer = window.setTimeout(() => runAdminLoad(loadRetrievalDebug, "Retrieval Debug laden"), 250);
  });
  bind("[data-retrieval-debug-type]", "change", () => {
    runAdminLoad(loadRetrievalDebug, "Retrieval Debug laden");
  });
  bind("[data-retrieval-debug-refresh]", "click", () => {
    runAdminLoad(loadRetrievalDebug, "Retrieval Debug laden");
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
    selectedRetrievalFlowId = Number(button.dataset.retrievalFlowSelect);
    renderRetrievalFlow(selectedRetrievalFlowItem());
    root.querySelectorAll("[data-retrieval-debug-rows] tr").forEach((row) => {
      const rowButton = row.querySelector("[data-retrieval-flow-select]");
      row.classList.toggle(
        "is-selected",
        Boolean(rowButton) && Number(rowButton.dataset.retrievalFlowSelect) === selectedRetrievalFlowId
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
        "Indexiert: " + result.indexed + " Dokumente, " + result.chunks + " Chunks."
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
      setAdminMessage("Knowledge-Qualitätsstatus wird aktualisiert...");
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
          "Knowledge #" + documentItem.id + " ist "
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

  refreshAll().catch((error) => {
    setAdminMessage(safeErrorMessage(error, "AI Admin konnte nicht vollständig geladen werden"), true);
  });
})();

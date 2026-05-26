/**
 * Admin AI operations module.
 * Registers view helpers on the shared MaintenanceAdminAI runtime.
 */
(function registerAdminAiModule(AdminAI) {
  const { root, adminView, state, QUALITY_STATUS_OPTIONS } = AdminAI;
  const api = (...args) => AdminAI.api(...args);
  const cell = (...args) => AdminAI.cell(...args);
  const confidenceLabel = (...args) => AdminAI.confidenceLabel(...args);
  const dateTimeText = (...args) => AdminAI.dateTimeText(...args);
  const knowledgeOriginKind = (...args) => AdminAI.knowledgeOriginKind(...args);
  const knowledgeSourceCell = (...args) => AdminAI.knowledgeSourceCell(...args);
  const lifecycleStepStatusLabel = (...args) => AdminAI.lifecycleStepStatusLabel(...args);
  const moneyText = (...args) => AdminAI.moneyText(...args);
  const numberText = (...args) => AdminAI.numberText(...args);
  const percentText = (...args) => AdminAI.percentText(...args);
  const pillCell = (...args) => AdminAI.pillCell(...args);
  const qualityStatusClass = (...args) => AdminAI.qualityStatusClass(...args);
  const qualityStatusLabel = (...args) => AdminAI.qualityStatusLabel(...args);
  const recordReference = (...args) => AdminAI.recordReference(...args);
  const redactSensitiveText = (...args) => AdminAI.redactSensitiveText(...args);
  const renderAdminEmptyState = (...args) => AdminAI.renderAdminEmptyState(...args);
  const renderAiClaritySummary = (...args) => AdminAI.renderAiClaritySummary(...args);
  const renderCapabilities = (...args) => AdminAI.renderCapabilities(...args);
  const renderOverviewState = (...args) => AdminAI.renderOverviewState(...args);
  const renderQuelleHealth = (...args) => AdminAI.renderQuelleHealth(...args);
  const renderSafetyFallbackSummary = (...args) => AdminAI.renderSafetyFallbackSummary(...args);
  const renderSectionStatusSummaries = (...args) => AdminAI.renderSectionStatusSummaries(...args);
  const secondsText = (...args) => AdminAI.secondsText(...args);
  const setHealthCard = (...args) => AdminAI.setHealthCard(...args);
  const sourceTypeLabel = (...args) => AdminAI.sourceTypeLabel(...args);
  const statusPill = (...args) => AdminAI.statusPill(...args);
  const statusRow = (...args) => AdminAI.statusRow(...args);
  const text = (...args) => AdminAI.text(...args);
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
        statusRow("Fehlende Textabschnitte", numberText(data.missing_chunk_count || 0)),
        statusRow("Textabschnitt Mismatch", numberText(data.chunk_mismatch_count || 0)),
        statusRow("Sync-Fehler", numberText(data.vector_sync_failure_count || 0))
      );
      const reasons = data.reindex_reasons || [];
      if (reasons.length) {
        issueList.appendChild(statusRow("Grund", reasons.join(", ")));
      }
    }
  }

  function renderKnowledgeStatus(status) {
    state.latestKnowledgeStatus = status || {};
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
            item.searchable_documents + "/" + item.documents + " durchsuchbar, " + item.chunks + " Textabschnitte"
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
        statusRow("Textabschnitting", diagnostics.chunk_size + " / " + diagnostics.chunk_overlap),
        statusRow("Top K", diagnostics.top_k),
        statusRow("Scan Limit", diagnostics.scan_limit)
      );
    }

    const reasonList = root.querySelector("[data-rag-readiness-reasons]");
    if (reasonList) {
      reasonList.innerHTML = "";
      (status.readiness_reasons || ["Keine Bereitschaft-Daten vorhanden."]).forEach((reason) => {
        reasonList.appendChild(statusRow("Bereitschaft", reason));
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
    renderQuelleHealth(status);
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
    state.latestJobSummary = {
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
      return "Indexiert: " + numberText(result.indexed || 0) + " / Textabschnitte: " + numberText(result.chunks || 0);
    }
    if (job.status === "done") return "abgeschlossen";
    if (job.status === "running") return "läuft";
    if (job.status === "queued") return "wartet";
    return "-";
  }

  function renderOperationsMetrics(data) {
    state.latestOperationsStatus = data || {};
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
        "Provider-, Modell-, Timeout- und Quellenabruf-Fehler erscheinen hier metadata-only."
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
        "Konfidenz " + confidenceLabel({
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
    state.latestKnowledgeGaps = data || {};
    const tbody = root.querySelector("[data-ai-knowledge-gaps]");
    const count = root.querySelector("[data-ai-knowledge-gap-count]");
    if (count) count.textContent = numberText(data.open_count || 0) + " offen";
    if (!tbody) return;
    tbody.innerHTML = "";
    if (!data.items.length) {
      renderAdminEmptyState(
        tbody,
        "Keine offenen Wissenslücken.",
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
   * Load an unfiltered training snapshot for the KI-Administration clarity overview.
   */
  async function loadTrainingSummary() {
    const data = await api("/api/v1/admin/ai/training?limit=100&active=");
    state.latestTrainingSummary = data || {};
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
    select.setAttribute("aria-label", "Wissens-Qualitätsstatus setzen");
    QUALITY_STATUS_OPTIONS.forEach((status) => {
      const option = document.createElement("option");
      option.value = status;
      option.textContent = qualityStatusLabel(status);
      option.selected = status === (documentItem.quality_status || "draft");
      select.appendChild(option);
    });
    return select;
  }
  Object.assign(AdminAI, { renderWorkflowMetrics, renderTopErrors, lifecycleKpiValue, renderLifecycle, renderLifecycleReview, renderLifecycleGate, renderLifecycleActions, renderLifecycleSteps, vectorSyncEventText, renderVectorStoreStatus, renderKnowledgeStatus, loadKnowledgeStatus, loadJobs, safeJobResultText, renderOperationsMetrics, loadOperationsMetrics, isFailedAiEvent, renderFailedQueries, loadEvents, loadChats, loadKnowledgeGaps, trainingPayload, resetTrainingForm, fillTrainingForm, loadTraining, loadTrainingSummary, loadKnowledge, knowledgeQualitySelect });
})(window.MaintenanceAdminAI);

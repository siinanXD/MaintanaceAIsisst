(function () {
  const root = document.querySelector("[data-admin-ai-page]");
  if (!root) return;

  const QUALITY_STATUS_OPTIONS = [
    "draft",
    "ai_suggested",
    "technician_confirmed",
    "admin_approved",
    "outdated",
    "rejected"
  ];

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
    if (!response.ok) throw new Error(payload.message || payload.error || "API error");
    return payload.data || payload;
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
      outdated: "Veraltet",
      rejected: "Abgelehnt"
    };
    return labels[status] || text(status || "draft");
  }

  function qualityStatusClass(status) {
    if (status === "admin_approved" || status === "technician_confirmed") return "is-active";
    if (status === "outdated") return "is-stale";
    if (status === "rejected") return "is-error";
    return "is-muted";
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

  function renderKnowledgeStatus(status) {
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

    const diagnostics = status.diagnostics || {};
    const diagnosticList = root.querySelector("[data-rag-diagnostics]");
    diagnosticList.innerHTML = "";
    diagnosticList.append(
      statusRow("RAG aktiv", diagnostics.rag_enabled ? "ja" : "nein"),
      statusRow("Vector Store", diagnostics.vector_store),
      statusRow("Embedding", diagnostics.embedding_provider),
      statusRow("Chunking", diagnostics.chunk_size + " / " + diagnostics.chunk_overlap),
      statusRow("Top K", diagnostics.top_k),
      statusRow("Scan Limit", diagnostics.scan_limit)
    );

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
        cell(job.error_message || JSON.stringify(job.result || {}))
      );
      tbody.appendChild(row);
    });
    if (!data.items.length) {
      const row = document.createElement("tr");
      const empty = document.createElement("td");
      empty.colSpan = 5;
      empty.textContent = "Keine RAG-Reindex-Jobs vorhanden.";
      row.appendChild(empty);
      tbody.appendChild(row);
    }
    if (statusList) {
      statusList.innerHTML = "";
      statusList.append(
        statusRow("Queued", statusCounts.queued || 0),
        statusRow("Running", statusCounts.running || 0),
        statusRow("Failed", statusCounts.failed || 0),
        statusRow("Done", statusCounts.done || 0),
        statusRow("Aeltester queued Job", oldestQueued ? "#" + oldestQueued.id : "-")
      );
    }
  }

  function renderOperationsMetrics(data) {
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

  async function loadEvents() {
    const error = root.querySelector("[data-ai-event-error]").value;
    const data = await api("/api/v1/admin/ai/events?limit=20&error=" + encodeURIComponent(error));
    const tbody = root.querySelector("[data-ai-events]");
    tbody.innerHTML = "";
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
    data.items.forEach((chat) => {
      const item = document.createElement("article");
      item.className = "list-card";
      const user = document.createElement("strong");
      const prompt = document.createElement("p");
      const meta = document.createElement("small");
      user.textContent = text(chat.user && chat.user.username);
      prompt.textContent = text(chat.message);
      meta.textContent = text(chat.response_type) + " - " + text(chat.created_at);
      item.append(user, prompt, meta);
      list.appendChild(item);
    });
  }

  async function loadKnowledgeGaps() {
    const data = await api("/api/v1/admin/ai/knowledge-gaps?status=open&limit=10");
    const tbody = root.querySelector("[data-ai-knowledge-gaps]");
    const count = root.querySelector("[data-ai-knowledge-gap-count]");
    if (count) count.textContent = numberText(data.open_count || 0) + " offen";
    if (!tbody) return;
    tbody.innerHTML = "";
    if (!data.items.length) {
      const row = document.createElement("tr");
      const empty = document.createElement("td");
      empty.colSpan = 7;
      empty.textContent = "Keine offenen Knowledge Gaps.";
      row.appendChild(empty);
      tbody.appendChild(row);
      return;
    }
    data.items.forEach((gap) => {
      const row = document.createElement("tr");
      row.append(
        cell(gap.question),
        cell(gap.department),
        cell(gap.machine),
        cell(gap.status),
        cell(gap.occurrence_count),
        cell(dateTimeText(gap.last_seen_at))
      );
      tbody.appendChild(row);
    });
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
      const empty = document.createElement("div");
      empty.className = "admin-empty";
      empty.textContent = "Keine passenden Trainingseinträge gefunden.";
      list.appendChild(empty);
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
      const row = document.createElement("tr");
      const empty = document.createElement("td");
      empty.colSpan = 7;
      empty.textContent = "Keine Wissensquellen für diesen Filter.";
      row.appendChild(empty);
      tbody.appendChild(row);
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

  async function refreshAll() {
    await Promise.all([
      loadSummary(),
      loadEvents(),
      loadChats(),
      loadKnowledgeGaps(),
      loadTraining(),
      loadKnowledge(),
      loadKnowledgeStatus(),
      loadJobs(),
      loadOperationsMetrics()
    ]);
  }

  root.querySelector("[data-ai-event-error]").addEventListener("change", loadEvents);
  root.querySelector("[data-ai-chat-search]").addEventListener("input", () => {
    window.clearTimeout(root._chatTimer);
    root._chatTimer = window.setTimeout(loadChats, 250);
  });
  root.querySelector("[data-ai-training-search]").addEventListener("input", () => {
    window.clearTimeout(root._trainingTimer);
    root._trainingTimer = window.setTimeout(loadTraining, 250);
  });
  root.querySelector("[data-ai-training-active]").addEventListener("change", loadTraining);
  root.querySelector("[data-ai-training-reset]").addEventListener("click", resetTrainingForm);
  root.querySelector("[data-ai-knowledge-search]").addEventListener("input", () => {
    window.clearTimeout(root._knowledgeTimer);
    root._knowledgeTimer = window.setTimeout(loadKnowledge, 250);
  });
  root.querySelector("[data-ai-knowledge-source]").addEventListener("change", loadKnowledge);
  root.querySelector("[data-ai-knowledge-status]").addEventListener("change", loadKnowledge);
  root.querySelector("[data-ai-knowledge-quality]").addEventListener("change", loadKnowledge);
  root.querySelector("[data-ai-training-form]").addEventListener("submit", async (event) => {
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
      await Promise.all([loadTraining(), loadKnowledge(), loadKnowledgeStatus()]);
    } catch (error) {
      setAdminMessage(error.message, true);
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
      await Promise.all([loadKnowledge(), loadKnowledgeStatus(), loadJobs(), loadOperationsMetrics()]);
    } catch (error) {
      setAdminMessage(error.message, true);
    } finally {
      button.disabled = false;
    }
  }

  root.querySelector("[data-ai-reindex]").addEventListener("click", async () => {
    await runReindex(
      root.querySelector("[data-ai-reindex]"),
      "/api/v1/admin/ai/knowledge/reindex"
    );
  });
  root.querySelector("[data-ai-reindex-stale]").addEventListener("click", async () => {
    await runReindex(
      root.querySelector("[data-ai-reindex-stale]"),
      "/api/v1/admin/ai/knowledge/reindex?mode=stale"
    );
  });
  root.querySelector("[data-ai-queue-stale]").addEventListener("click", async () => {
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
      setAdminMessage(error.message, true);
    } finally {
      setButtonBusy(button, false);
    }
  });
  root.querySelector("[data-ai-knowledge-upload]").addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    setFormBusy(event.currentTarget, true, "Lädt...");
    setAdminMessage("Dokument wird hochgeladen...");
    try {
      await api("/api/v1/admin/ai/knowledge/upload", { method: "POST", body: formData });
      event.currentTarget.reset();
      setAdminMessage("Dokument hochgeladen und indexiert.");
      await Promise.all([loadKnowledge(), loadKnowledgeStatus(), loadJobs(), loadOperationsMetrics()]);
    } catch (error) {
      setAdminMessage(error.message, true);
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
        await Promise.all([loadTraining(), loadKnowledge(), loadKnowledgeStatus()]);
      } catch (error) {
        setAdminMessage(error.message, true);
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
        await Promise.all([loadKnowledge(), loadKnowledgeStatus(), loadOperationsMetrics()]);
      } catch (error) {
        setAdminMessage(error.message, true);
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
        await Promise.all([loadKnowledge(), loadKnowledgeStatus(), loadJobs(), loadOperationsMetrics()]);
      } catch (error) {
        setAdminMessage(error.message, true);
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
        setAdminMessage(error.message, true);
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
      await Promise.all([loadKnowledge(), loadKnowledgeStatus(), loadJobs(), loadOperationsMetrics()]);
    } catch (error) {
      setAdminMessage(error.message, true);
    } finally {
      setButtonBusy(button, false);
    }
  });

  refreshAll().catch((error) => {
    setAdminMessage("AI Admin konnte nicht vollständig geladen werden: " + error.message, true);
  });
})();

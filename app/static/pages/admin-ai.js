(function () {
  const root = document.querySelector("[data-admin-ai-page]");
  if (!root) return;

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
    ["events_total", "fallback_count", "total_tokens", "estimated_cost_usd"].forEach((key) => {
      const target = root.querySelector('[data-ai-kpi="' + key + '"]');
      if (target) target.textContent = text(summary[key]);
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
  }

  async function loadKnowledgeStatus() {
    const status = await api("/api/v1/admin/ai/knowledge/status");
    renderKnowledgeStatus(status);
  }

  async function loadJobs() {
    const data = await api("/api/v1/admin/jobs?job_type=rag_reindex&limit=10");
    const tbody = root.querySelector("[data-ai-jobs]");
    const count = root.querySelector("[data-ai-job-count]");
    tbody.innerHTML = "";
    if (count) count.textContent = data.pagination.total + " Jobs";
    data.items.forEach((job) => {
      const row = document.createElement("tr");
      row.append(
        cell(job.id),
        cell(job.job_type),
        cell(job.status),
        cell(job.attempts + "/" + job.max_attempts),
        cell(job.error_message || JSON.stringify(job.result || {}))
      );
      tbody.appendChild(row);
    });
  }

  function renderOperationsMetrics(data) {
    const database = data.database || {};
    const jobs = data.background_jobs || {};
    const ai = data.ai || {};
    const rag = data.rag || {};
    const generated = root.querySelector("[data-ops-generated]");
    const dbLatency = root.querySelector('[data-ops-kpi="database_latency_ms"]');
    const queueLength = root.querySelector('[data-ops-kpi="queue_length"]');
    const aiLatency = root.querySelector('[data-ops-kpi="ai_latency_ms"]');
    const ragStale = root.querySelector('[data-ops-kpi="rag_stale_ratio"]');
    if (generated) generated.textContent = data.generated_at ? new Date(data.generated_at).toLocaleTimeString("de-DE") : "-";
    if (dbLatency) dbLatency.textContent = text(database.latency_ms) + " ms";
    if (queueLength) queueLength.textContent = text(jobs.queue_length);
    if (aiLatency) aiLatency.textContent = text(ai.avg_latency_ms) + " ms";
    if (ragStale) ragStale.textContent = Math.round((rag.stale_ratio || 0) * 100) + "%";

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
    const source = root.querySelector("[data-ai-knowledge-source]").value;
    const status = root.querySelector("[data-ai-knowledge-status]").value;
    const data = await api(
      "/api/v1/admin/ai/knowledge?limit=50&source_type="
      + encodeURIComponent(source)
      + "&status="
      + encodeURIComponent(status)
    );
    const tbody = root.querySelector("[data-ai-knowledge]");
    tbody.innerHTML = "";
    if (!data.items.length) {
      const row = document.createElement("tr");
      const empty = document.createElement("td");
      empty.colSpan = 6;
      empty.textContent = "Keine Wissensquellen für diesen Filter.";
      row.appendChild(empty);
      tbody.appendChild(row);
      return;
    }
    data.items.forEach((documentItem) => {
      const row = document.createElement("tr");
      const actions = document.createElement("td");
      const reindexButton = document.createElement("button");
      reindexButton.type = "button";
      reindexButton.className = "btn btn-secondary btn-sm";
      reindexButton.dataset.reindexKnowledge = documentItem.id;
      reindexButton.textContent = "Indexieren";
      const button = document.createElement("button");
      button.type = "button";
      button.className = "btn btn-ghost btn-sm";
      button.dataset.deleteKnowledge = documentItem.id;
      button.textContent = "Löschen";
      actions.append(reindexButton, button);
      row.append(
        cell(documentItem.title),
        cell(documentItem.source_type),
        cell(documentItem.status),
        cell(documentItem.chunk_count),
        cell(documentItem.department),
        actions
      );
      tbody.appendChild(row);
    });
  }

  async function refreshAll() {
    await Promise.all([
      loadSummary(),
      loadEvents(),
      loadChats(),
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
  root.querySelector("[data-ai-knowledge-source]").addEventListener("change", loadKnowledge);
  root.querySelector("[data-ai-knowledge-status]").addEventListener("change", loadKnowledge);
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

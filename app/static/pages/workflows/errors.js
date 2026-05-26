import {
  DASHBOARD_KEYS,
  DASHBOARD_LABELS,
  EMPLOYEE_ACCESS_LEVELS,
  SHARED_MODULE_URLS,
  TASK_PRIORITIES,
  TASK_STATUSES,
  actionButton,
  api,
  applyAiActionPreview,
  badge,
  canView,
  canWrite,
  confirmAction,
  consumeAiActionPreview,
  downloadFile,
  employeeAccessLevel,
  emptyState,
  fillDepartments,
  fillMachineSelects,
  formDataToObject,
  formatDate,
  formatMoney,
  genericStatusBadgeClass,
  keywordText,
  labeledBadge,
  listData,
  loadWorkflowShared,
  paginationTotal,
  priorityBadgeClass,
  priorityLabel,
  registerWorkflowInitializers,
  renderInlineActionPreview,
  renderQuellePanel,
  renderShiftCalendar,
  requestText,
  resolveWorkflowInitializer,
  revealSurface,
  row,
  runAction,
  setButtonBusy,
  setFormBusy,
  setSelectOptions,
  setStatusMessage,
  setText,
  sharedModulePromise,
  sharedNamespace,
  shiftLabel,
  showInfoDialog,
  showInterfaceToast,
  sourceTypeLabel,
  statusBadgeClass,
  statusLabel,
  taskFormPayload,
  token,
  user
} from "./shared.js";

async function initErrors() {
  const list = document.querySelector("[data-error-list]");
  const form = document.querySelector("[data-error-form]");
  const analyzeForm = document.querySelector("[data-error-analyze-form]");
  const analysisBox = document.querySelector("[data-error-analysis]");
  const applyAnalysis = document.querySelector("[data-apply-error-analysis]");
  const similarPanel = document.querySelector("[data-similar-errors-panel]");
  const similarList = document.querySelector("[data-similar-errors-list]");
  const searchInput = document.querySelector("[data-error-search]");
  const searchFocus = document.querySelector("[data-error-search-focus]");
  const analysisFocus = document.querySelector("[data-error-analysis-focus]");
  const similarFocus = document.querySelector("[data-error-similar-focus]");
  const filterButtons = Array.from(document.querySelectorAll("[data-error-filter]"));
  const statusFilter = document.querySelector("[data-error-status-filter]");
  const severityFilter = document.querySelector("[data-error-severity-filter]");
  const categoryFilter = document.querySelector("[data-error-category-filter]");
  const filterReset = document.querySelector("[data-error-filter-reset]");
  const filterSummary = document.querySelector("[data-error-filter-summary]");
  const analysisQuelles = document.querySelector("[data-error-rag-sources]");
  const actionPreview = document.querySelector("[data-error-action-preview]");
  if (!list || !form || !token()) return;
  let currentAnalysis = null;
  let currentAssistantResult = null;
  let currentErrors = [];

  const errorEditDialog = document.getElementById("error-edit-dialog");
  const eedId       = document.getElementById("eed-id");
  const eedDept     = document.getElementById("eed-department");
  const eedMachine  = document.getElementById("eed-machine");
  const eedCode     = document.getElementById("eed-code");
  const eedStatus   = document.getElementById("eed-status");
  const eedSeverity = document.getElementById("eed-severity");
  const eedCategory = document.getElementById("eed-category");
  const eedTitle    = document.getElementById("eed-title-input");
  const eedSymptoms = document.getElementById("eed-symptoms");
  const eedCauses   = document.getElementById("eed-causes");
  const eedSolution = document.getElementById("eed-solution");
  const eedImpact   = document.getElementById("eed-impact");
  const eedDowntime = document.getElementById("eed-downtime");
  const eedProductionLoss = document.getElementById("eed-production-loss");
  const eedRepeatCount = document.getElementById("eed-repeat-count");
  const eedSave     = document.getElementById("eed-save");
  const eedCancel   = document.getElementById("eed-cancel");
  const eedMsg      = document.getElementById("eed-msg");
  const errActionTh = document.querySelector("[data-errors-action-th]");

  if (canWrite("errors") && errActionTh) {
    errActionTh.hidden = false;
    errActionTh.textContent = "Aktionen";
  }

  function openErrorEdit(entry) {
    if (!errorEditDialog) return;
    eedId.value       = entry.id;
    eedMachine.value  = entry.machine || "";
    eedCode.value     = entry.error_code || "";
    if (eedStatus) eedStatus.value = entry.status || "open";
    if (eedSeverity) eedSeverity.value = entry.severity || "medium";
    if (eedCategory) eedCategory.value = entry.cause_category || "";
    eedTitle.value    = entry.title || "";
    if (eedSymptoms) eedSymptoms.value = entry.symptoms || entry.description || "";
    eedCauses.value   = entry.possible_causes || "";
    eedSolution.value = entry.solution || "";
    if (eedImpact) eedImpact.value = entry.impact || "";
    if (eedDowntime) eedDowntime.value = String(entry.downtime_minutes || 0);
    if (eedProductionLoss) {
      eedProductionLoss.value = String(entry.production_loss_minutes || 0);
    }
    if (eedRepeatCount) eedRepeatCount.value = String(entry.repeat_count || 0);
    if (eedDept) {
      Array.from(eedDept.options).forEach((opt) => {
        opt.selected = opt.value === (entry.department && entry.department.name);
      });
    }
    if (eedMsg) eedMsg.textContent = "";
    errorEditDialog.showModal();
  }

  if (eedCancel) eedCancel.addEventListener("click", () => errorEditDialog.close());
  if (errorEditDialog) {
    errorEditDialog.addEventListener("keydown", (e) => { if (e.key === "Escape") errorEditDialog.close(); });
  }
  if (eedSave) eedSave.addEventListener("click", async () => {
    try {
      setStatusMessage(eedMsg, "Wird gespeichert...");
      await api("/api/v1/errors/" + eedId.value, {
        method: "PUT",
        body: JSON.stringify({
          machine: eedMachine.value,
          error_code: eedCode.value,
          status: eedStatus ? eedStatus.value : undefined,
          severity: eedSeverity ? eedSeverity.value : undefined,
          cause_category: eedCategory ? eedCategory.value : undefined,
          title: eedTitle.value,
          symptoms: eedSymptoms ? eedSymptoms.value : undefined,
          description: eedSymptoms ? eedSymptoms.value : undefined,
          possible_causes: eedCauses.value,
          solution: eedSolution.value,
          impact: eedImpact ? eedImpact.value : undefined,
          downtime_minutes: eedDowntime ? eedDowntime.value : undefined,
          production_loss_minutes: eedProductionLoss ? eedProductionLoss.value : undefined,
          repeat_count: eedRepeatCount ? eedRepeatCount.value : undefined,
          department: eedDept ? eedDept.value : undefined
        })
      });
      errorEditDialog.close();
      await load();
    } catch (err) {
      setStatusMessage(eedMsg, err.message, true);
    }
  });

  function highlightedBlock(label, value, variant) {
    const block = document.createElement("div");
    block.className = "knowledge-block" + (variant ? " " + variant : "");
    const title = document.createElement("span");
    title.textContent = label;
    const text = document.createElement("strong");
    text.textContent = value || "-";
    block.append(title, text);
    return block;
  }

  function errorStatusLabel(status) {
    const labels = {
      open: "Offen",
      in_progress: "In Bearbeitung",
      closed: "Geschlossen"
    };
    return labels[status] || "Offen";
  }

  function errorStatusClass(status) {
    if (status === "closed") return "badge status-badge is-done";
    if (status === "in_progress") return "badge status-badge is-progress";
    return "badge status-badge is-open";
  }

  function errorSeverityLabel(severity) {
    const labels = {
      critical: "Kritisch",
      high: "Hoch",
      medium: "Mittel",
      low: "Niedrig"
    };
    return labels[severity] || "Mittel";
  }

  function errorSeverityClass(severity) {
    if (severity === "critical") return "badge priority-badge is-urgent";
    if (severity === "high") return "badge priority-badge is-soon";
    if (severity === "low") return "badge priority-badge is-normal";
    return "badge priority-badge is-medium";
  }

  function formatIncidentMinutes(value) {
    const minutes = Number(value || 0);
    if (minutes >= 60) return (minutes / 60).toFixed(1).replace(".", ",") + " h";
    return Math.round(minutes) + " min";
  }

  function incidentDate(value) {
    if (!value) return "-";
    return new Date(value).toLocaleString("de-DE", {
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit"
    });
  }

  function incidentSearchText(entry) {
    return [
      entry.error_code,
      entry.machine,
      entry.title,
      entry.description,
      entry.symptoms,
      entry.possible_causes,
      entry.solution,
      entry.department && entry.department.name,
      entry.status,
      errorStatusLabel(entry.status),
      entry.severity,
      errorSeverityLabel(entry.severity),
      entry.cause_category,
      entry.impact
    ].filter(Boolean).join(" ").toLowerCase();
  }

  function updateIncidentStats(errors) {
    const openCount = errors.filter((entry) => (entry.status || "open") !== "closed").length;
    const criticalCount = errors.filter((entry) => entry.severity === "critical" || entry.severity === "high").length;
    const downtime = errors.reduce((sum, entry) => sum + Number(entry.downtime_minutes || 0), 0);
    const categories = new Set(errors.map((entry) => entry.cause_category).filter(Boolean));
    document.querySelectorAll("[data-error-count]").forEach((element) => {
      element.textContent = errors.length + " Einträge";
    });
    setText("[data-error-open-count]", openCount);
    setText("[data-error-critical-count]", criticalCount);
    setText("[data-error-downtime-count]", formatIncidentMinutes(downtime));
    setText("[data-error-category-count]", categories.size);
  }

  function populateIncidentCategoryFilter(errors) {
    if (!categoryFilter) return;
    const previous = categoryFilter.value;
    const categories = Array.from(new Set(
      errors.map((entry) => entry.cause_category).filter(Boolean)
    )).sort((first, second) => first.localeCompare(second, "de-DE"));
    categoryFilter.innerHTML = '<option value="">Alle Kategorien</option>';
    categories.forEach((category) => {
      const option = document.createElement("option");
      option.value = category;
      option.textContent = category;
      categoryFilter.appendChild(option);
    });
    categoryFilter.value = categories.includes(previous) ? previous : "";
  }

  function analysisValue(payload, fieldName) {
    if (!payload) return "";
    if (fieldName === "symptoms") {
      return payload.symptoms || payload.description || "";
    }
    return payload[fieldName] || "";
  }

  function renderSimilarErrors(result) {
    if (!similarPanel || !similarList) return;
    const matches = result.results || [];
    similarPanel.hidden = false;
    similarList.innerHTML = "";
    if (!matches.length) {
      similarList.innerHTML = '<tr><td colspan="5"><div class="guided-empty-state"><strong>Keine ähnlichen Fehler gefunden</strong><p>Lege den Eintrag an, wenn Code, Maschine und Ursache plausibel sind. Er wird danach als Quelle für spätere Analysen nutzbar.</p></div></td></tr>';
      return;
    }
    matches.forEach((match) => {
      similarList.appendChild(row([
        String(match.score),
        badge(match.entry.error_code, "badge status-badge is-open"),
        match.entry.machine,
        match.entry.title,
        match.reason
      ]));
    });
  }

  async function loadSimilarErrors(data) {
    const result = await api("/api/v1/errors/similar", {
      method: "POST",
      body: JSON.stringify({
        text: data.description || data.symptoms || data.title || "",
        machine: data.machine || "",
        limit: 5
      })
    });
    renderSimilarErrors(result);
  }

  function applyErrorPreview(preview) {
    const payload = (preview && preview.payload) || {};
    if (!payload.title && !payload.description) return;
    currentAnalysis = payload;
    if (analysisBox) {
      analysisBox.hidden = false;
      analysisBox.querySelectorAll("[data-error-analysis-field]").forEach((field) => {
        field.value = analysisValue(payload, field.dataset.errorAnalysisField);
      });
    }
    if (form.elements.machine) form.elements.machine.value = payload.machine || "";
    if (form.elements.department) {
      form.elements.department.value = payload.department || form.elements.department.value;
    }
    if (form.elements.error_code && !form.elements.error_code.value) {
      form.elements.error_code.value = "NEU";
    }
    if (form.elements.title) form.elements.title.value = payload.title || "";
    if (form.elements.symptoms) {
      form.elements.symptoms.value = payload.symptoms || payload.description || "";
    }
    if (form.elements.possible_causes) {
      form.elements.possible_causes.value = payload.possible_causes || "";
    }
    if (form.elements.solution) form.elements.solution.value = payload.solution || "";
    revealSurface(form);
    form.elements.title.focus();
  }

  function updateErrorRagPanels(result) {
    currentAssistantResult = result || null;
    renderQuellePanel(analysisQuelles, result && result.sources);
    renderInlineActionPreview(actionPreview, result && result.action_preview);
  }

  async function enrichErrorAnalysis(data, message) {
    try {
      const result = await api("/api/v1/ai/error-assistant", {
        method: "POST",
        body: JSON.stringify({ query: data.description, limit: 5 })
      });
      updateErrorRagPanels(result);
      if (message && result.diagnostics && result.diagnostics.rag_source_count) {
        setStatusMessage(
          message,
          "Analyse erstellt. " + result.diagnostics.rag_source_count + " Quellen gefunden."
        );
      }
    } catch (error) {
      updateErrorRagPanels(null);
      if (message) {
        setStatusMessage(message, "Analyse erstellt. Quellenkontext nicht verfügbar: " + error.message);
      }
    }
  }

  function activeErrorFilter() {
    const active = filterButtons.find((button) => button.classList.contains("is-active"));
    return active ? active.dataset.errorFilter : "all";
  }

  function errorMatchesFilter(entry, filterName) {
    if (!filterName || filterName === "all") return true;
    if ((entry.cause_category || "").toLowerCase() === filterName.toLowerCase()) return true;
    return incidentSearchText(entry).includes(filterName.toLowerCase());
  }

  function errorCard(entry) {
    const card = document.createElement("article");
    const status = entry.status || "open";
    const severity = entry.severity || "medium";
    card.className = "error-card incident-card is-status-" + status + " is-severity-" + severity;
    card.dataset.searchText = incidentSearchText(entry);

    const header = document.createElement("div");
    header.className = "error-card-header";
    const titleWrap = document.createElement("div");
    const title = document.createElement("h3");
    title.className = "error-card-title";
    title.textContent = entry.title || "Unbenannter Fehler";
    const meta = document.createElement("div");
    meta.className = "error-card-meta";
    [
      entry.machine || "Maschine offen",
      entry.department && entry.department.name,
      entry.cause_category || "Kategorie offen"
    ].filter(Boolean).forEach((value) => {
      const item = document.createElement("span");
      item.textContent = value;
      meta.appendChild(item);
    });
    titleWrap.append(title, meta);
    const badges = document.createElement("div");
    badges.className = "incident-card-badges";
    badges.append(
      badge(entry.error_code || "CODE", "badge status-badge is-open"),
      badge(errorStatusLabel(status), errorStatusClass(status)),
      badge(errorSeverityLabel(severity), errorSeverityClass(severity))
    );
    header.append(titleWrap, badges);

    const metrics = document.createElement("div");
    metrics.className = "incident-card-metrics";
    [
      ["Stillstand", formatIncidentMinutes(entry.downtime_minutes)],
      ["Produktionsverlust", formatIncidentMinutes(entry.production_loss_minutes)],
      ["Wiederholungen", String(Number(entry.repeat_count || 0))],
      [status === "closed" ? "Geschlossen" : "Zuletzt gesehen", incidentDate(entry.closed_at || entry.last_seen_at || entry.created_at)]
    ].forEach(([label, value]) => {
      const item = document.createElement("span");
      const small = document.createElement("small");
      const strong = document.createElement("strong");
      small.textContent = label;
      strong.textContent = value;
      item.append(small, strong);
      metrics.appendChild(item);
    });

    const blocks = document.createElement("div");
    blocks.className = "error-card-blocks";
    blocks.append(
      highlightedBlock("Symptome", entry.symptoms || entry.description, "is-symptom"),
      highlightedBlock("Ursache", entry.possible_causes, "is-cause"),
      highlightedBlock("Lösung", entry.solution, "is-solution"),
      highlightedBlock("Auswirkung", entry.impact, "is-impact")
    );

    const actions = document.createElement("div");
    actions.className = "error-card-actions";
    const similar = actionButton("Ähnliche Fehler finden", async (event) => {
      event.currentTarget.disabled = true;
      try {
        await loadSimilarErrors({
          description: [
            entry.title,
            entry.symptoms || entry.description,
            entry.possible_causes,
            entry.solution,
            entry.impact
          ].filter(Boolean).join(" "),
          machine: entry.machine
        });
      } finally {
        event.currentTarget.disabled = false;
      }
    });
    similar.className = "btn btn-outline btn-sm";
    actions.appendChild(similar);
    if (canWrite("errors")) {
      if (status !== "closed") {
        actions.appendChild(actionButton("Schließen", async () => {
          await api("/api/v1/errors/" + entry.id + "/close", { method: "POST" });
          await load();
        }, { successMessage: "Störung geschlossen.", busyText: "Schließt..." }));
      }
      actions.appendChild(actionButton("Bearbeiten", () => openErrorEdit(entry)));
      actions.appendChild(actionButton("Löschen", async () => {
        if (!window.confirm("Fehler '" + entry.title + "' wirklich löschen?")) return;
        await api("/api/v1/errors/" + entry.id, { method: "DELETE" });
        await load();
      }, true));
    }

    card.append(header, metrics, blocks, actions);
    return card;
  }

  function renderErrors() {
    const query = searchInput ? searchInput.value.trim().toLowerCase() : "";
    const selectedFilter = activeErrorFilter();
    const filteredErrors = currentErrors.filter((entry) => {
      if (!errorMatchesFilter(entry, selectedFilter)) return false;
      if (statusFilter && statusFilter.value && (entry.status || "open") !== statusFilter.value) return false;
      if (severityFilter && severityFilter.value && (entry.severity || "medium") !== severityFilter.value) return false;
      if (categoryFilter && categoryFilter.value && (entry.cause_category || "") !== categoryFilter.value) return false;
      if (!query) return true;
      return incidentSearchText(entry).includes(query);
    });
    list.innerHTML = "";
    if (filterSummary) {
      filterSummary.textContent = filteredErrors.length + " von " + currentErrors.length + " Einträgen sichtbar";
    }
    if (!filteredErrors.length) {
      list.innerHTML = '<div class="guided-empty-state"><strong>Keine passenden Fehler gefunden</strong><p>Beispielsuche: Fehlercode, Maschine oder Symptom. Wenn es ein neuer Fall ist, lege ihn mit Ursache und Lösung im Katalog an.</p></div>';
      return;
    }
    filteredErrors.forEach((entry) => {
      list.appendChild(errorCard(entry));
    });
  }

  async function load() {
    currentErrors = listData(await api("/api/v1/errors?limit=100"));
    updateIncidentStats(currentErrors);
    populateIncidentCategoryFilter(currentErrors);
    renderErrors();
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(form).entries());
    data.description = data.symptoms || data.title;
    const message = document.querySelector("[data-error-message]");
    setFormBusy(form, true, "Speichert...");
    try {
      setStatusMessage(message, "Fehler wird geprüft...");
      await loadSimilarErrors(data);
      await api("/api/v1/errors", { method: "POST", body: JSON.stringify(data) });
      form.reset();
      await initDepartments();
      await load();
      setStatusMessage(message, "Fehler gespeichert.");
    } catch (error) {
      setStatusMessage(message, error.message, true);
    } finally {
      setFormBusy(form, false);
    }
  });

  if (analyzeForm && analysisBox) {
    analyzeForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const message = document.querySelector("[data-error-analyze-message]");
      const data = Object.fromEntries(new FormData(analyzeForm).entries());
      setFormBusy(analyzeForm, true, "Analysiert...");
      setStatusMessage(message, "AI analysiert...");
      try {
        currentAnalysis = await api("/api/v1/errors/analyze", {
          method: "POST",
          body: JSON.stringify(data)
        });
        analysisBox.hidden = false;
        analysisBox.querySelectorAll("[data-error-analysis-field]").forEach((field) => {
          field.value = analysisValue(currentAnalysis, field.dataset.errorAnalysisField);
        });
        setStatusMessage(message, "Analyse erstellt.");
        await enrichErrorAnalysis(data, message);
        await loadSimilarErrors({
          description: data.description,
          machine: currentAnalysis.machine
        });
      } catch (error) {
        setStatusMessage(message, error.message, true);
      } finally {
        setFormBusy(analyzeForm, false);
      }
    });
  }

  if (applyAnalysis) {
    applyAnalysis.addEventListener("click", () => {
      if (!currentAnalysis) return;
      const values = {};
      analysisBox.querySelectorAll("[data-error-analysis-field]").forEach((field) => {
        values[field.dataset.errorAnalysisField] = field.value;
      });
      form.elements.machine.value = values.machine || "";
      form.elements.department.value = values.department || "";
      form.elements.title.value = values.title || "";
      if (form.elements.symptoms) form.elements.symptoms.value = values.symptoms || "";
      if (form.elements.description) form.elements.description.value = values.symptoms || "";
      form.elements.possible_causes.value = values.possible_causes || "";
      form.elements.solution.value = values.solution || "";
      if (currentAssistantResult) updateErrorRagPanels(currentAssistantResult);
      revealSurface(form);
      form.elements.title.focus();
    });
  }

  if (searchInput) {
    const query = new URLSearchParams(window.location.search);
    searchInput.value = query.get("search") || query.get("q") || "";
    searchInput.addEventListener("input", renderErrors);
  }

  [statusFilter, severityFilter, categoryFilter].filter(Boolean).forEach((filter) => {
    filter.addEventListener("change", renderErrors);
  });

  if (filterReset) {
    filterReset.addEventListener("click", () => {
      if (searchInput) searchInput.value = "";
      if (statusFilter) statusFilter.value = "";
      if (severityFilter) severityFilter.value = "";
      if (categoryFilter) categoryFilter.value = "";
      filterButtons.forEach((item) => item.classList.toggle("is-active", item.dataset.errorFilter === "all"));
      renderErrors();
    });
  }

  filterButtons.forEach((button) => {
    button.addEventListener("click", () => {
      filterButtons.forEach((item) => item.classList.toggle("is-active", item === button));
      renderErrors();
    });
  });

  if (searchFocus && searchInput) {
    searchFocus.addEventListener("click", () => {
      searchInput.focus();
    });
  }

  if (similarFocus) {
    similarFocus.addEventListener("click", async () => {
      const description = searchInput && searchInput.value.trim()
        ? searchInput.value.trim()
        : (currentErrors[0] && [currentErrors[0].title, currentErrors[0].possible_causes].filter(Boolean).join(" "));
      if (!description) {
        if (searchInput) searchInput.focus();
        return;
      }
      await loadSimilarErrors({ description });
    });
  }

  if (analysisFocus && analyzeForm) {
    analysisFocus.addEventListener("click", () => {
      revealSurface(analyzeForm);
      const input = analyzeForm.querySelector("textarea");
      if (input) input.focus();
    });
  }

  await load();
  applyErrorPreview(consumeAiActionPreview("errors"));
}

export { initErrors };

registerWorkflowInitializers({
  initErrors: initErrors
});

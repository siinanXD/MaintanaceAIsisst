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

async function initMachines() {
  const list = document.querySelector("[data-machine-list]");
  const form = document.querySelector("[data-machine-form]");
  const historyPanel = document.querySelector("[data-machine-history-panel]");
  const historyTitle = document.querySelector("[data-machine-history-title]");
  const historyZusammenfassung = document.querySelector("[data-machine-history-summary]");
  const historyCounts = document.querySelector("[data-machine-history-counts]");
  const historyList = document.querySelector("[data-machine-history-list]");
  const assistantForm = document.querySelector("[data-machine-assistant-form]");
  const assistantAnswer = document.querySelector("[data-machine-assistant-answer]");
  const assistantQuelles = document.querySelector("[data-machine-assistant-sources]");
  const assistantFocus = document.querySelector("[data-machine-assistant-focus]");
  const recommendationPanel = document.querySelector("[data-maintenance-recommendations-panel]");
  const recommendationList = document.querySelector("[data-maintenance-recommendations-list]");
  const recommendationZusammenfassung = document.querySelector("[data-maintenance-recommendations-summary]");
  if (!list || !form || !token()) return;
  let activeHistoryMachine = null;

  const machineEditDialog = document.getElementById("machine-edit-dialog");
  const medId       = document.getElementById("med-id");
  const medName     = document.getElementById("med-name");
  const medProduced = document.getElementById("med-produced");
  const medEmployees = document.getElementById("med-employees");
  const medSave     = document.getElementById("med-save");
  const medCancel   = document.getElementById("med-cancel");
  const medMsg      = document.getElementById("med-msg");

  function openMachineEdit(machine) {
    if (!machineEditDialog) return;
    medId.value        = machine.id;
    medName.value      = machine.name;
    medProduced.value  = machine.produced_item || "";
    medEmployees.value = machine.required_employees || 1;
    if (medMsg) medMsg.textContent = "";
    machineEditDialog.showModal();
  }

  if (medCancel) medCancel.addEventListener("click", () => machineEditDialog.close());
  if (machineEditDialog) {
    machineEditDialog.addEventListener("keydown", (e) => { if (e.key === "Escape") machineEditDialog.close(); });
  }
  if (medSave) medSave.addEventListener("click", async () => {
    setButtonBusy(medSave, true, "Speichert...");
    try {
      setStatusMessage(medMsg, "Wird gespeichert...");
      await api("/api/v1/machines/" + medId.value, {
        method: "PUT",
        body: JSON.stringify({
          name: medName.value,
          produced_item: medProduced.value,
          required_employees: parseInt(medEmployees.value, 10) || 1
        })
      });
      machineEditDialog.close();
      await load();
      const machineMsg = document.querySelector("[data-machine-message]");
      if (machineMsg) machineMsg.textContent = "Maschine aktualisiert.";
    } catch (err) {
      setStatusMessage(medMsg, err.message, true);
    } finally {
      setButtonBusy(medSave, false);
    }
  });

  function renderHistoryCounts(counts) {
    if (!historyCounts) return;
    historyCounts.innerHTML = "";
    [
      ["Aufgaben", counts.tasks || 0],
      ["Fehler", counts.errors || 0],
      ["Dokumente", counts.documents || 0],
      ["Gesamt", counts.total || 0]
    ].forEach(([label, value]) => {
      const item = document.createElement("div");
      item.className = "stat-row";
      const labelElement = document.createElement("span");
      labelElement.textContent = label;
      const valueElement = document.createElement("strong");
      valueElement.textContent = String(value);
      item.append(labelElement, valueElement);
      historyCounts.appendChild(item);
    });
  }

  function historyLink(item) {
    if (!item.url) return "-";
    const link = document.createElement("a");
    link.className = "btn btn-outline btn-sm";
    link.href = item.url;
    link.textContent = "Oeffnen";
    return link;
  }

  function renderMachineHistory(history) {
    if (!historyPanel || !historyList) return;
    activeHistoryMachine = history.machine;
    historyPanel.hidden = false;
    if (historyTitle) historyTitle.textContent = "Anlagenakte: " + history.machine.name;
    if (historyZusammenfassung) historyZusammenfassung.textContent = history.summary.text || "";
    renderHistoryCounts(history.source_counts || {});
    historyList.innerHTML = "";
    if (!history.timeline || !history.timeline.length) {
      historyList.innerHTML = '<tr><td colspan="6">Keine Historie gefunden.</td></tr>';
    } else {
      history.timeline.forEach((item) => {
        historyList.appendChild(row([
          item.type,
          item.date ? new Date(item.date).toLocaleString("de-DE") : "-",
          item.title,
          item.status,
          item.summary,
          historyLink(item)
        ]));
      });
    }
    historyPanel.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function loadMachineHistory(machine) {
    const history = await api("/api/v1/machines/" + machine.id + "/history");
    renderMachineHistory(history);
  }

  if (assistantForm) {
    assistantForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!activeHistoryMachine) return;
      const data = Object.fromEntries(new FormData(assistantForm).entries());
      setFormBusy(assistantForm, true, "Fragt...");
      setStatusMessage(assistantAnswer, "Maschinen-Assistent denkt...");
      try {
        const result = await api("/api/v1/machines/" + activeHistoryMachine.id + "/assistant", {
          method: "POST",
          body: JSON.stringify(data)
        });
        const fallback = result.diagnostics && (
          result.diagnostics.fallback_used || result.diagnostics.status === "fallback_used"
        )
          ? "Ausweichantwort: "
          : "";
        setStatusMessage(assistantAnswer, fallback + result.answer);
        renderQuellePanel(assistantQuelles, result.sources);
      } catch (error) {
        setStatusMessage(assistantAnswer, error.message, true);
        renderQuellePanel(assistantQuelles, []);
      } finally {
        setFormBusy(assistantForm, false);
      }
    });
  }

  function recommendationRiskLabel(riskLevel) {
    const labels = {
      critical: "kritisch",
      high: "hoch",
      medium: "mittel",
      low: "niedrig"
    };
    return labels[riskLevel] || riskLevel || "niedrig";
  }

  function recommendationCard(item) {
    const card = document.createElement("article");
    card.className = "resource-card maintenance-recommendation-card";
    const header = document.createElement("div");
    header.className = "resource-card-header";
    const titleBlock = document.createElement("div");
    const title = document.createElement("h3");
    title.className = "resource-card-title";
    title.textContent = (item.machine && item.machine.name) || "Maschine";
    const subtitle = document.createElement("p");
    subtitle.className = "resource-card-subtitle";
    subtitle.textContent = item.reason || "Historie und Quellen prüfen.";
    titleBlock.append(title, subtitle);
    const badges = document.createElement("div");
    badges.className = "resource-card-badges";
    badges.appendChild(badge(recommendationRiskLabel(item.risk_level), "badge badge-ai"));
    header.append(titleBlock, badges);

    const metrics = document.createElement("div");
    metrics.className = "resource-meta-grid";
    [
      ["Score", String(item.score || 0)],
      ["Aufgaben", String((item.source_counts && item.source_counts.tasks) || 0)],
      ["Fehler", String((item.source_counts && item.source_counts.errors) || 0)],
      ["Quellen", String((item.source_counts && item.source_counts.rag_sources) || 0)]
    ].forEach(([label, value]) => {
      const metric = document.createElement("div");
      metric.className = "resource-metric";
      const labelElement = document.createElement("span");
      labelElement.className = "resource-label";
      labelElement.textContent = label;
      const valueElement = document.createElement("span");
      valueElement.className = "resource-value";
      valueElement.textContent = value;
      metric.append(labelElement, valueElement);
      metrics.appendChild(metric);
    });

    const action = document.createElement("p");
    action.className = "resource-note";
    action.textContent = item.recommended_action || "Nächsten Wartungsschritt planen.";

    const actions = document.createElement("div");
    actions.className = "resource-actions";
    if (item.machine && item.machine.id) {
      actions.appendChild(actionButton("Historie", () => loadMachineHistory(item.machine)));
    }

    card.append(header, metrics, action, actions);
    return card;
  }

  function renderMaintenanceRecommendations(payload) {
    if (!recommendationList) return;
    const items = Array.isArray(payload && payload.items) ? payload.items : listData(payload);
    recommendationList.innerHTML = "";
    if (recommendationZusammenfassung) {
      recommendationZusammenfassung.textContent = items.length
        ? items.length + " präventive Hinweise aus Aufgaben, Fehlern und Quellen."
        : "Keine auffälligen Wartungssignale gefunden.";
    }
    if (!items.length) {
      const empty = document.createElement("p");
      empty.className = "panel-meta";
      empty.textContent = "Keine präventiven Empfehlungen vorhanden.";
      recommendationList.appendChild(empty);
      return;
    }
    items.forEach((item) => {
      recommendationList.appendChild(recommendationCard(item));
    });
  }

  async function loadMaintenanceRecommendations() {
    if (!recommendationPanel || !recommendationList) return;
    try {
      const payload = await api("/api/v1/machines/maintenance-recommendations?limit=5");
      renderMaintenanceRecommendations(payload);
    } catch (error) {
      recommendationList.innerHTML = "";
      if (recommendationZusammenfassung) {
        recommendationZusammenfassung.textContent = "Praeventive Wartung konnte nicht geladen werden: " + error.message;
      }
    }
  }

  if (assistantFocus) {
    assistantFocus.addEventListener("click", () => {
      if (historyPanel && historyPanel.hidden) {
        const firstHistoryButton = list.querySelector("button");
        if (firstHistoryButton) firstHistoryButton.focus();
        return;
      }
      if (assistantForm) {
        assistantForm.scrollIntoView({ behavior: "smooth", block: "center" });
        const input = assistantForm.querySelector("input");
        if (input) input.focus();
      }
    });
  }

  function renderMachineEmptyState(message) {
    list.innerHTML = "";
    const empty = document.createElement("article");
    empty.className = "guided-empty-state empty-state";
    const title = document.createElement("strong");
    title.textContent = message;
    const detail = document.createElement("p");
    detail.textContent = canWrite("machines")
      ? "Lege die erste Maschine an, damit Aufgaben, Störungen und Dokumente sauber zugeordnet werden."
      : "Sobald Maschinen angelegt sind, erscheinen sie hier mit Status und Schnellaktionen.";
    empty.append(title, detail);
    list.appendChild(empty);
  }

  function machineRecordCard(machine) {
    const card = document.createElement("article");
    card.className = "record-card machine-record-card";
    card.dataset.searchText = [
      machine.name,
      machine.produced_item,
      machine.required_employees
    ].filter(Boolean).join(" ");

    const header = document.createElement("div");
    header.className = "record-card-header";
    const titleBlock = document.createElement("div");
    const title = document.createElement("h3");
    title.className = "record-card-title";
    title.textContent = machine.name || "Maschine";
    const subtitle = document.createElement("p");
    subtitle.className = "record-card-subtitle";
    subtitle.textContent = machine.produced_item || "Kein Produktionsinhalt hinterlegt";
    titleBlock.append(title, subtitle);
    header.append(titleBlock, badge("Aktiv", "badge badge-status is-done"));

    const meta = document.createElement("div");
    meta.className = "record-card-meta";
    [
      ["Personalbedarf", (machine.required_employees || 1) + " MA"],
      ["Letzte Störung", machine.last_error || "Keine Angabe"],
      ["Offene Aufgaben", String(machine.open_tasks || 0)]
    ].forEach(([label, value]) => {
      const item = document.createElement("span");
      const itemLabel = document.createElement("small");
      const itemValue = document.createElement("strong");
      itemLabel.textContent = label;
      itemValue.textContent = value;
      item.append(itemLabel, itemValue);
      meta.appendChild(item);
    });

    const actions = document.createElement("div");
    actions.className = "record-card-actions";
    const profileLink = document.createElement("a");
    profileLink.className = "btn btn-primary btn-sm";
    profileLink.href = "/machines/" + machine.id;
    profileLink.textContent = "Profil";
    actions.appendChild(profileLink);
    actions.appendChild(actionButton("Historie", () => loadMachineHistory(machine)));
    if (canWrite("machines")) {
      actions.appendChild(actionButton("Bearbeiten", () => openMachineEdit(machine)));
      actions.appendChild(actionButton("Löschen", async () => {
        const confirmed = await confirmAction({
          title: "Maschine löschen",
          message: machine.name + " wirklich löschen? Zugeordnete Historie bleibt in den Fachseiten sichtbar.",
          confirmText: "Löschen"
        });
        if (!confirmed) return;
        await api("/api/v1/machines/" + machine.id, { method: "DELETE" });
        await load();
      }, {
        danger: true,
        busyText: "Löscht...",
        successMessage: "Maschine gelöscht."
      }));
    }

    card.append(header, meta, actions);
    return card;
  }

  async function load() {
    const machinePayload = await api("/api/v1/machines?limit=200");
    const machines = listData(machinePayload);
    const machineCount = document.querySelector("[data-machine-count]");
    list.innerHTML = "";
    if (machineCount) {
      machineCount.textContent = paginationTotal(machinePayload, machines) + " Maschinen";
    }
    if (!machines.length) {
      renderMachineEmptyState("Noch keine Maschinen vorhanden.");
      return machines;
    }
    machines.forEach((machine) => {
      list.appendChild(machineRecordCard(machine));
    });
    return machines;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(form).entries());
    const message = document.querySelector("[data-machine-message]");
    setFormBusy(form, true, "Speichert...");
    try {
      setStatusMessage(message, "Maschine wird gespeichert...");
      await api("/api/v1/machines", { method: "POST", body: JSON.stringify(data) });
      form.reset();
      form.elements.required_employees.value = "1";
      await load();
      setStatusMessage(message, "Maschine gespeichert.");
    } catch (error) {
      setStatusMessage(message, error.message, true);
    } finally {
      setFormBusy(form, false);
    }
  });

  const machines = await load();
  await loadMaintenanceRecommendations();
  const machinePreview = consumeAiActionPreview("machines");
  if (machinePreview && machinePreview.payload) {
    const machine = machines.find((item) => item.id === machinePreview.payload.machine_id);
    if (machine) {
      await loadMachineHistory(machine);
      const input = assistantForm && assistantForm.querySelector("input");
      if (input) {
        input.value = machinePreview.payload.question || "";
        input.focus();
      }
    }
  }
}

export { initMachines };

registerWorkflowInitializers({
  initMachines: initMachines
});

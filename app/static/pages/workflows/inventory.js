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

async function initInventory() {
  const list = document.querySelector("[data-inventory-list]");
  const form = document.querySelector("[data-inventory-form]");
  const forecastForm = document.querySelector("[data-inventory-forecast-form]");
  const forecastList = document.querySelector("[data-inventory-forecast-list]");
  const forecastMessage = document.querySelector("[data-inventory-forecast-message]");
  const forecastUnmatched = document.querySelector("[data-inventory-forecast-unmatched]");
  if (!list || !form || !token()) return;

  function forecastRiskBadgeClass(riskLevel) {
    if (riskLevel === "critical") return "badge badge-error text-white";
    if (riskLevel === "high") return "badge badge-warning text-slate-900";
    return "badge badge-info text-white";
  }

  /**
   * Update inventory KPI cards from the loaded material list.
   *
   * @param {Array<object>} materials Loaded inventory materials.
   * @returns {void}
   */
  function updateInventoryStats(materials) {
    const thresholdInput = document.querySelector("#forecast-threshold");
    const threshold = Number(thresholdInput && thresholdInput.value ? thresholdInput.value : 5);
    const totalValue = materials.reduce((sum, material) => {
      return sum + Number(material.total_value || 0);
    }, 0);
    const lowStock = materials.filter((material) => Number(material.quantity || 0) <= threshold).length;
    const linked = materials.filter((material) => material.machine && material.machine.name).length;
    setText("[data-inventory-count]", materials.length + " Artikel");
    setText("[data-inventory-low-count]", lowStock + " kritisch");
    setText("[data-inventory-total-value]", formatMoney(totalValue));
    setText("[data-inventory-linked-count]", linked + " zugeordnet");
  }

  /**
   * Render one material as an operational inventory card.
   *
   * @param {object} material Inventory material payload.
   * @returns {HTMLElement} Rendered card.
   */
  function inventoryCard(material) {
    const quantity = Number(material.quantity || 0);
    const machineName = material.machine && material.machine.name ? material.machine.name : "Keine Maschine";
    const card = document.createElement("article");
    card.className = "record-card inventory-card" + (quantity <= 5 ? " is-low-stock" : "");
    card.dataset.searchText = [
      material.name,
      material.manufacturer,
      machineName,
      String(quantity)
    ].filter(Boolean).join(" ").toLowerCase();

    const header = document.createElement("div");
    header.className = "record-card-header";
    const titleBlock = document.createElement("div");
    const title = document.createElement("h3");
    title.className = "record-card-title";
    title.textContent = material.name || "Material";
    const subtitle = document.createElement("p");
    subtitle.className = "record-card-subtitle";
    subtitle.textContent = [material.manufacturer || "Hersteller offen", machineName].join(" · ");
    titleBlock.append(title, subtitle);
    header.append(
      titleBlock,
      badge(quantity <= 5 ? "niedrig" : "verfügbar", quantity <= 5 ? "badge badge-priority is-soon" : "badge badge-status is-done")
    );

    const meta = document.createElement("div");
    meta.className = "record-card-meta inventory-card-meta";
    [
      ["Bestand", String(quantity)],
      ["Einzelkosten", formatMoney(material.unit_cost)],
      ["Gesamtwert", formatMoney(material.total_value)],
      ["Maschine", machineName]
    ].forEach(([label, value]) => {
      const item = document.createElement("span");
      const small = document.createElement("small");
      const strong = document.createElement("strong");
      small.textContent = label;
      strong.textContent = value || "-";
      item.append(small, strong);
      meta.appendChild(item);
    });

    const actions = document.createElement("div");
    actions.className = "record-card-actions";
    if (material.machine && material.machine.id) {
      const machineLink = document.createElement("a");
      machineLink.className = "btn btn-outline btn-sm";
      machineLink.href = "/machines/" + material.machine.id;
      machineLink.textContent = "Maschinenprofil";
      actions.appendChild(machineLink);
    }
    if (canWrite("inventory")) {
      actions.appendChild(actionButton("Löschen", async () => {
        if (!window.confirm(material.name + " wirklich löschen?")) return;
        await api("/api/v1/inventory/" + material.id, { method: "DELETE" });
        await load();
      }, true));
    }

    card.append(header, meta, actions);
    return card;
  }

  function renderForecast(forecast) {
    if (!forecastList) return;
    forecastList.innerHTML = "";
    if (forecastUnmatched) forecastUnmatched.innerHTML = "";
    const items = forecast.items || [];
    if (!items.length) {
      forecastList.innerHTML = '<tr><td colspan="6">Keine kritischen Lagerhinweise gefunden.</td></tr>';
    } else {
      items.forEach((item) => {
        forecastList.appendChild(row([
          item.material && item.material.name,
          item.machine && item.machine.name,
          String(item.quantity),
          badge(item.risk_level, forecastRiskBadgeClass(item.risk_level)),
          item.task && item.task.title,
          [item.recommended_action, item.match_reason].filter(Boolean).join(" | ")
        ]));
      });
    }
    if (forecastUnmatched) {
      const unmatchedAufgaben = forecast.unmatched_tasks || [];
      if (unmatchedAufgaben.length) {
        const title = document.createElement("h3");
        title.className = "panel-title";
        title.textContent = "Aufgaben ohne Maschinenbezug";
        forecastUnmatched.appendChild(title);
        unmatchedAufgaben.forEach((item) => {
          const rowItem = document.createElement("div");
          rowItem.className = "stat-row";
          rowItem.innerHTML = `<span>${item.task.title}</span><strong>${item.risk_level}</strong>`;
          rowItem.title = item.recommended_action || item.reason || "";
          forecastUnmatched.appendChild(rowItem);
        });
      }
    }
  if (forecastMessage) {
      forecastMessage.classList.remove("is-error");
      const summary = forecast.summary || {};
      const unmatched = (forecast.unmatched_tasks || []).length;
      forecastMessage.textContent = [
        "Kritisch: " + (summary.critical || 0),
        "Hoch: " + (summary.high || 0),
        "Mittel: " + (summary.medium || 0),
        unmatched ? "Ohne Maschine: " + unmatched : ""
      ].filter(Boolean).join(" | ");
    }
  }

  async function loadForecast() {
    if (!forecastForm) return;
    const data = Object.fromEntries(new FormData(forecastForm).entries());
    data.status = "open";
    data.limit = 20;
    const forecast = await api("/api/v1/inventory/forecast", {
      method: "POST",
      body: JSON.stringify(data)
    });
    renderForecast(forecast);
  }

  async function load() {
    await fillMachineSelects();
    const materialPayload = await api("/api/v1/inventory?limit=200");
    const materials = listData(materialPayload);
    list.innerHTML = "";
    updateInventoryStats(materials);
    if (!materials.length) {
      list.appendChild(emptyState(
        "Noch kein Material angelegt.",
        "Lege die ersten Ersatzteile an, damit Lagerwert und Maschinenbezug sichtbar werden."
      ));
      return;
    }
    materials.forEach((material) => {
      list.appendChild(inventoryCard(material));
    });
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(form).entries());
    const message = document.querySelector("[data-inventory-message]");
    setFormBusy(form, true, "Speichert...");
    try {
      setStatusMessage(message, "Material wird gespeichert...");
      await api("/api/v1/inventory", { method: "POST", body: JSON.stringify(data) });
      form.reset();
      await load();
      setStatusMessage(message, "Material gespeichert.");
    } catch (error) {
      setStatusMessage(message, error.message, true);
    } finally {
      setFormBusy(form, false);
    }
  });

  if (forecastForm) {
    forecastForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      setFormBusy(forecastForm, true, "Berechnet...");
      setStatusMessage(forecastMessage, "Prognose wird berechnet...");
      try {
        await loadForecast();
      } catch (error) {
        setStatusMessage(forecastMessage, error.message, true);
      } finally {
        setFormBusy(forecastForm, false);
      }
    });
  }

  await load();
}

export { initInventory };

registerWorkflowInitializers({
  initInventory: initInventory
});

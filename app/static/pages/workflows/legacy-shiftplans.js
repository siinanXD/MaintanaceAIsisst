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

async function initShiftPlans() {
  const list = document.querySelector("[data-shiftplan-list]");
  const form = document.querySelector("[data-shiftplan-form]");
  const calendar = document.querySelector("[data-shiftplan-calendar]");
  if (!list || !form || !token()) return;

  const startInput = form.querySelector("[name='start_date']");
  if (startInput && !startInput.value) {
    startInput.value = new Date().toISOString().slice(0, 10);
  }

  function parseVacationText(value) {
    return String(value || "")
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => {
        const parts = line.split(",").map((part) => part.trim());
        return {
          employee_id: parts[0],
          date: parts[1],
          notes: parts.slice(2).join(", ") || "Urlaub"
        };
      });
  }

  function planCalendar(plan) {
    return {
      entries: (plan.entries || []).map((entry) => ({
        work_date: entry.work_date,
        shift: entry.shift,
        start_time: entry.start_time,
        end_time: entry.end_time,
        machine: entry.machine,
        notes: [
          entry.employee && entry.employee.name,
          entry.machine && entry.machine.name,
          entry.notes
        ].filter(Boolean).join(" | "),
        color: shiftColor(entry.shift)
      }))
    };
  }

  function shiftColor(shift) {
    if (shift === "Frueh") return "green";
    if (shift === "Spaet") return "blue";
    if (shift === "Nacht") return "red";
    if (shift === "Frei") return "violet";
    if (shift === "Urlaub") return "amber";
    return "slate";
  }

  function renderPlan(plan) {
    const article = document.createElement("article");
    article.className = "shiftplan-card";

    const header = document.createElement("div");
    header.className = "panel-header";
    const title = document.createElement("div");
    title.innerHTML = `<h3 class="panel-title">${plan.title}</h3><p class="panel-meta">${plan.start_date} - ${plan.days} Tage - ${plan.rhythm || "Rhythmus offen"}</p>`;
    header.append(title);
    if (canWrite("shiftplans")) {
      const remove = actionButton("Löschen", async () => {
        if (!window.confirm(plan.title + " wirklich löschen?")) return;
        await api("/api/v1/shiftplans/" + plan.id, { method: "DELETE" });
        await load();
      }, true);
      header.append(remove);
    }

    const notes = document.createElement("p");
    notes.className = "panel-meta";
    notes.textContent = plan.notes || "Plan wurde gespeichert.";

    const warningBox = document.createElement("div");
    warningBox.className = "stats-list";
    const warnings = plan.warnings || [];
    if (warnings.length) {
      warnings.slice(0, 6).forEach((warning) => {
        const item = document.createElement("div");
        item.className = "stat-row";
        item.innerHTML = `<span>${warning.type}</span><strong>${warning.severity}</strong>`;
        item.title = warning.message;
        warningBox.appendChild(item);
      });
    }

    const wrap = document.createElement("div");
    wrap.className = "table-wrap";
    const table = document.createElement("table");
    table.className = "table data-table";
    table.innerHTML = "<thead><tr><th>Datum</th><th>Schicht</th><th>Zeit</th><th>Mitarbeiter</th><th>Maschine</th><th>Notiz</th></tr></thead>";
    const body = document.createElement("tbody");
    plan.entries.forEach((entry) => {
      body.appendChild(row([
        entry.work_date,
        entry.shift,
        entry.start_time + " - " + entry.end_time,
        entry.employee && entry.employee.name,
        entry.machine && entry.machine.name,
        entry.notes
      ]));
    });
    table.appendChild(body);
    wrap.appendChild(table);
    const planCalendarElement = document.createElement("div");
    planCalendarElement.className = "shift-calendar";
    renderShiftCalendar(planCalendarElement, planCalendar(plan));
    if (warnings.length) {
      article.append(header, notes, warningBox, planCalendarElement, wrap);
    } else {
      article.append(header, notes, planCalendarElement, wrap);
    }
    return article;
  }

  async function load() {
    const plans = await api("/api/v1/shiftplans");
    list.innerHTML = "";
    if (!plans.length) {
      list.innerHTML = '<div class="empty-state">Noch kein Schichtplan generiert.</div>';
      if (calendar) renderShiftCalendar(calendar, { entries: [] });
      return;
    }
    if (calendar) renderShiftCalendar(calendar, planCalendar(plans[0]));
    plans.forEach((plan) => list.appendChild(renderPlan(plan)));
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const message = document.querySelector("[data-shiftplan-message]");
    setFormBusy(form, true, "Plant...");
    setStatusMessage(message, "KI plant...");
    const data = Object.fromEntries(new FormData(form).entries());
    data.vacations = parseVacationText(data.vacations_text);
    delete data.vacations_text;
    try {
      const plan = await api("/api/v1/shiftplans/generate", { method: "POST", body: JSON.stringify(data) });
      form.reset();
      if (startInput) startInput.value = new Date().toISOString().slice(0, 10);
      if (message) {
        const warningCount = (plan.warnings || []).length;
        message.textContent = warningCount
          ? "Schichtplan generiert mit " + warningCount + " Warnungen."
          : "Schichtplan generiert.";
      }
      await load();
    } catch (error) {
      setStatusMessage(message, error.message, true);
    } finally {
      setFormBusy(form, false);
    }
  });

  await load();
}

export { initShiftPlans };

registerWorkflowInitializers({
  initShiftPlans: initShiftPlans
});

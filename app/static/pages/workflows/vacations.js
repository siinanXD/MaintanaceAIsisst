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

async function initVacations() {
  if (!document.querySelector("[data-vac-submit]") || !token()) return;

  const BASE_VAC = "/api/v1/vacations";
  const BASE_EMP = "/api/v1/employees";
  const BASE_AUTH = "/api/v1/auth";

  const form = document.querySelector("[data-vac-form]");
  const empSel = document.querySelector("[data-vac-employee]");
  const startInput = document.querySelector("[data-vac-start]");
  const endInput = document.querySelector("[data-vac-end]");
  const shiftSelect = document.querySelector("[data-vac-shift]");
  const representativeSelect = document.querySelector("[data-vac-representative]");
  const reasonInput = document.querySelector("[data-vac-reason]");
  const daysWrap = document.querySelector("[data-vac-days-wrap]");
  const daysBadge = document.querySelector("[data-vac-days-count]");
  const notesInput = document.querySelector("[data-vac-notes]");
  const submitBtn = document.querySelector("[data-vac-submit]");
  const msgEl = document.querySelector("[data-vac-msg]");
  const pendingList = document.querySelector("[data-vac-pending-list]");
  const pendingEmpty = document.querySelector("[data-vac-pending-empty]");
  const pendingCount = document.querySelector("[data-vac-pending-count]");
  const conflictCount = document.querySelector("[data-vac-conflict-count]");
  const yearSel = document.querySelector("[data-vac-year]");
  const summaryList = document.querySelector("[data-vac-summary-list]");
  const filterStatus = document.querySelector("[data-vac-filter-status]");
  const filterBtn = document.querySelector("[data-vac-filter-btn]");
  const tableBody = document.querySelector("[data-vac-table-body]");
  const tableEmpty = document.querySelector("[data-vac-empty]");
  const historyList = document.querySelector("[data-vac-history-list]");
  const balancePreview = document.querySelector("[data-vac-balance-preview]");
  const impactPreview = document.querySelector("[data-vac-impact]");
  const calendarList = document.querySelector("[data-vac-calendar-list]");
  const teamStatus = document.querySelector("[data-vac-team-status]");
  const selectedAvailableEl = document.querySelector("[data-vac-selected-available]");
  const usedTotalEl = document.querySelector("[data-vac-used-total]");
  const pendingTotalEl = document.querySelector("[data-vac-pending-total]");

  let currentUser = user();
  let employeeBalances = new Map();
  let employees = [];
  let allRequests = [];
  let sending = false;
  let impactRequestToken = 0;

  function fmtDate(iso) {
    if (!iso) return "-";
    const parts = iso.split("-");
    if (parts.length !== 3) return iso;
    return parts[2] + "." + parts[1] + "." + parts[0];
  }

  function currentDepartmentName() {
    if (!currentUser || !currentUser.department) return "";
    if (typeof currentUser.department === "string") return currentUser.department;
    return currentUser.department.name || "";
  }

  function canDecideRequest(vacation) {
    if (!currentUser) return false;
    if (currentUser.role === "master_admin") return true;
    const permissions = currentUser.permissions || {};
    const employeePermission = permissions.employees || {};
    const requestDepartment = vacation && vacation.employee ? vacation.employee.department : "";
    return Boolean(
      employeePermission.can_write
      && currentDepartmentName()
      && requestDepartment === currentDepartmentName()
    );
  }

  function canCancelRequest(vacation) {
    if (!currentUser || !vacation || vacation.status === "cancelled") return false;
    if (currentUser.role === "master_admin") return true;
    if (currentUser.employee_id === vacation.employee_id) return true;
    return canDecideRequest(vacation);
  }

  function setMessage(message, type) {
    if (!msgEl) return;
    msgEl.textContent = message || "";
    msgEl.classList.remove("is-error", "is-success");
    if (type) msgEl.classList.add("is-" + type);
  }

  function setLoading(container, message) {
    if (!container) return;
    container.innerHTML = "";
    const loading = document.createElement("p");
    loading.className = "empty-state";
    loading.textContent = message;
    container.appendChild(loading);
  }

  function renderEmpty(parent, message) {
    if (!parent) return;
    parent.innerHTML = "";
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = message;
    parent.appendChild(empty);
  }

  function countWorkdays(start, end) {
    let count = 0;
    const day = new Date(start + "T00:00:00");
    const last = new Date(end + "T00:00:00");
    while (day <= last) {
      if (day.getDay() >= 1 && day.getDay() <= 5) count += 1;
      day.setDate(day.getDate() + 1);
    }
    return count;
  }

  function selectedEmployeeId() {
    return parseInt(empSel.value || "0", 10);
  }

  function selectedEmployee() {
    const employeeId = selectedEmployeeId();
    return employees.find((item) => item.id === employeeId) || null;
  }

  function selectedBalance() {
    return employeeBalances.get(selectedEmployeeId()) || null;
  }

  function requestedDays() {
    const start = startInput.value;
    const end = endInput.value;
    if (!start || !end || end < start) return null;
    return countWorkdays(start, end);
  }

  function shiftLabel(value) {
    const labels = {
      Frueh: "Früh",
      Spaet: "Spät",
      Nacht: "Nacht",
      Tag: "Tagdienst",
      Alle: "Alle Schichten"
    };
    return labels[value] || "Keine feste Schicht";
  }

  function statusLabel(status) {
    return {
      approved: "Genehmigt",
      rejected: "Abgelehnt",
      pending: "Ausstehend",
      cancelled: "Storniert"
    }[status] || status || "-";
  }

  function statusBadge(status) {
    const badge = document.createElement("span");
    badge.className = "vacation-status-badge is-" + (status || "muted");
    badge.textContent = statusLabel(status);
    return badge;
  }

  function impactBadge(level) {
    const badge = document.createElement("span");
    badge.className = "vacation-impact-badge is-" + (level || "ok");
    badge.textContent = level === "critical" ? "Kritisch" : (level === "warning" ? "Warnung" : "OK");
    return badge;
  }

  function validationError() {
    if (!empSel.value || !startInput.value || !endInput.value) return "";
    if (endInput.value < startInput.value) return "Enddatum darf nicht vor dem Startdatum liegen.";
    const days = requestedDays();
    if (!days) return "Im gewählten Zeitraum liegt kein Arbeitstag.";
    const balance = selectedBalance();
    if (balance && days > balance.available) {
      return "Der Antrag überschreitet den verfügbaren Resturlaub.";
    }
    return "";
  }

  function updateKpis() {
    const balance = selectedBalance();
    const balances = Array.from(employeeBalances.values());
    const usedTotal = balances.reduce((sum, item) => sum + (item.used || 0), 0);
    const reservedTotal = balances.reduce((sum, item) => sum + (item.pending || 0), 0);
    const riskyRequests = allRequests.filter((item) => (
      ["pending", "approved"].includes(item.status)
      && ["warning", "critical"].includes(item.impact_level)
    ));
    if (selectedAvailableEl) selectedAvailableEl.textContent = balance ? String(balance.available) : "-";
    if (usedTotalEl) usedTotalEl.textContent = String(usedTotal);
    if (pendingTotalEl) pendingTotalEl.textContent = String(reservedTotal);
    if (conflictCount) conflictCount.textContent = String(riskyRequests.length);
  }

  function updateDaysCount() {
    const days = requestedDays();
    if (days !== null && daysBadge && daysWrap) {
      daysBadge.textContent = days + " Arbeitstage";
      daysWrap.hidden = false;
    } else if (daysWrap) {
      daysWrap.hidden = true;
    }
    updateBalancePreview();
  }

  function updateBalancePreview() {
    const balance = selectedBalance();
    const employee = selectedEmployee();
    const days = requestedDays();
    const error = validationError();
    if (!balancePreview) return;
    balancePreview.classList.toggle("is-error", Boolean(error));
    if (error) {
      balancePreview.textContent = error;
    } else if (balance && days !== null) {
      balancePreview.textContent = employee.name + ": "
        + balance.available + " Tage verfügbar, "
        + days + " Tage angefragt.";
    } else if (balance && employee) {
      balancePreview.textContent = employee.name + ": "
        + balance.available + " verfügbar, "
        + balance.pending + " reserviert, "
        + balance.used + " genehmigt.";
    } else {
      balancePreview.textContent = "Wähle Mitarbeiter und Zeitraum.";
    }
    if (!sending) submitBtn.disabled = Boolean(error && empSel.value && startInput.value && endInput.value);
  }

  function fillYearOptions() {
    const thisYear = new Date().getFullYear();
    yearSel.innerHTML = "";
    for (let year = thisYear - 1; year <= thisYear + 2; year += 1) {
      const option = document.createElement("option");
      option.value = String(year);
      option.textContent = String(year);
      if (year === thisYear) option.selected = true;
      yearSel.appendChild(option);
    }
  }

  function syncYearFromStartDate() {
    if (!startInput.value) return false;
    const startYear = startInput.value.slice(0, 4);
    const hasOption = Array.from(yearSel.options).some((option) => option.value === startYear);
    if (hasOption && yearSel.value !== startYear) {
      yearSel.value = startYear;
      return true;
    }
    return false;
  }

  function createMetric(label, value) {
    const item = document.createElement("span");
    item.className = "vacation-metric";
    const strong = document.createElement("strong");
    strong.textContent = value || "-";
    const small = document.createElement("small");
    small.textContent = label;
    item.append(strong, small);
    return item;
  }

  function createMetaLine(parts) {
    const line = document.createElement("p");
    line.className = "vacation-card-meta";
    line.textContent = parts.filter(Boolean).join(" · ");
    return line;
  }

  function requestCard(vacation, mode) {
    const card = document.createElement("article");
    card.className = "vacation-request-card is-" + (vacation.impact_level || "ok");

    const header = document.createElement("header");
    const titleWrap = document.createElement("div");
    const title = document.createElement("h3");
    title.textContent = vacation.employee ? vacation.employee.name : String(vacation.employee_id);
    titleWrap.append(
      title,
      createMetaLine([
        vacation.department || (vacation.employee && vacation.employee.department),
        fmtDate(vacation.start_date) + " bis " + fmtDate(vacation.end_date),
        vacation.days_used + " Tage",
        shiftLabel(vacation.shift_type)
      ])
    );
    const badges = document.createElement("div");
    badges.className = "vacation-card-badges";
    badges.append(statusBadge(vacation.status), impactBadge(vacation.impact_level));
    header.append(titleWrap, badges);

    const metrics = document.createElement("div");
    metrics.className = "vacation-card-metrics";
    const balance = employeeBalances.get(vacation.employee_id);
    metrics.append(
      createMetric("Verfügbar", balance ? String(balance.available) : "-"),
      createMetric("Vertreter", vacation.representative ? vacation.representative.name : "offen"),
      createMetric("Entscheider", vacation.approved_by || "offen")
    );

    const body = document.createElement("div");
    body.className = "vacation-card-body";
    if (vacation.reason) body.appendChild(createMetaLine(["Grund", vacation.reason]));
    if (vacation.notes) body.appendChild(createMetaLine(["Notiz", vacation.notes]));
    if (vacation.impact_summary) body.appendChild(createMetaLine(["Auswirkung", vacation.impact_summary]));

    const actions = document.createElement("div");
    actions.className = "vacation-card-actions";
    if (mode === "pending" && canDecideRequest(vacation)) {
      const approveBtn = document.createElement("button");
      approveBtn.className = "btn btn-success btn-xs";
      approveBtn.type = "button";
      approveBtn.textContent = "Genehmigen";
      approveBtn.addEventListener("click", () => decide(vacation.id, "approve"));
      const rejectBtn = document.createElement("button");
      rejectBtn.className = "btn btn-error btn-xs";
      rejectBtn.type = "button";
      rejectBtn.textContent = "Ablehnen";
      rejectBtn.addEventListener("click", () => decide(vacation.id, "reject"));
      actions.append(approveBtn, rejectBtn);
    }
    if (canCancelRequest(vacation) && ["pending", "approved"].includes(vacation.status)) {
      const cancelBtn = document.createElement("button");
      cancelBtn.className = "btn btn-outline btn-xs";
      cancelBtn.type = "button";
      cancelBtn.textContent = "Stornieren";
      cancelBtn.addEventListener("click", () => cancelVacation(vacation.id));
      actions.appendChild(cancelBtn);
    }
    if (!actions.children.length) {
      const state = document.createElement("span");
      state.className = "vacation-card-state";
      state.textContent = statusLabel(vacation.status);
      actions.appendChild(state);
    }

    card.append(header, metrics, body, actions);
    return card;
  }

  function renderSummaryCards(data) {
    summaryList.innerHTML = "";
    data.forEach((summary) => {
      const card = document.createElement("article");
      const available = Number(summary.available || 0);
      card.className = "vacation-summary-card";
      if (available <= 0) card.classList.add("is-critical");
      else if (available <= 5 || Number(summary.pending || 0) >= 5) card.classList.add("is-warning");

      const header = document.createElement("header");
      const title = document.createElement("h3");
      title.textContent = summary.name || "-";
      const department = document.createElement("p");
      department.textContent = [
        summary.department || "Bereich offen",
        summary.current_shift || summary.shift_model || "",
        summary.team ? "Team " + summary.team : ""
      ].filter(Boolean).join(" · ");
      header.append(title, department);

      const numbers = document.createElement("div");
      numbers.className = "vacation-summary-numbers";
      numbers.append(
        createMetric("Verfügbar", String(summary.available || 0)),
        createMetric("Reserviert", String(summary.pending || 0)),
        createMetric("Genehmigt", String(summary.used || 0)),
        createMetric("Gesamt", String(summary.total || 0))
      );

      const qualification = document.createElement("p");
      qualification.className = "vacation-card-meta";
      qualification.textContent = summary.qualifications
        ? "Qualifikation: " + summary.qualifications
        : "Qualifikation nicht hinterlegt";
      card.append(header, numbers, qualification);
      summaryList.appendChild(card);
    });
  }

  function renderCalendarList(requests) {
    if (!calendarList) return;
    const active = requests
      .filter((item) => ["pending", "approved"].includes(item.status))
      .sort((a, b) => String(a.start_date).localeCompare(String(b.start_date)))
      .slice(0, 8);
    calendarList.innerHTML = "";
    if (!active.length) {
      renderEmpty(calendarList, "Keine aktiven Urlaubszeiträume im ausgewählten Jahr.");
      if (teamStatus) teamStatus.textContent = "Keine offenen Personalwarnungen.";
      return;
    }
    const critical = active.filter((item) => item.impact_level === "critical").length;
    const warning = active.filter((item) => item.impact_level === "warning").length;
    if (teamStatus) {
      teamStatus.textContent = critical
        ? critical + " kritische Personalhinweise"
        : (warning ? warning + " Warnhinweise im Team" : "Teamlage ohne auffällige Konflikte.");
    }
    active.forEach((vacation) => {
      const item = document.createElement("article");
      item.className = "vacation-calendar-item is-" + (vacation.impact_level || "ok");
      const title = document.createElement("strong");
      title.textContent = vacation.employee ? vacation.employee.name : String(vacation.employee_id);
      const meta = createMetaLine([
        fmtDate(vacation.start_date) + " bis " + fmtDate(vacation.end_date),
        statusLabel(vacation.status),
        vacation.impact_summary || "keine Warnung"
      ]);
      item.append(title, meta);
      calendarList.appendChild(item);
    });
  }

  function fillHiddenHistoryTable(data) {
    if (!tableBody) return;
    tableBody.innerHTML = "";
    data.forEach((vacation) => {
      const row = document.createElement("tr");
      ["employee", "start_date", "days_used", "status", "notes"].forEach((key) => {
        const cell = document.createElement("td");
        if (key === "employee") cell.textContent = vacation.employee ? vacation.employee.name : String(vacation.employee_id);
        else if (key === "start_date") cell.textContent = fmtDate(vacation.start_date) + " - " + fmtDate(vacation.end_date);
        else if (key === "status") cell.textContent = statusLabel(vacation.status);
        else cell.textContent = String(vacation[key] || "-");
        row.appendChild(cell);
      });
      tableBody.appendChild(row);
    });
  }

  async function loadCurrentUser() {
    try {
      currentUser = await api(BASE_AUTH + "/me");
    } catch (err) {
      currentUser = user();
    }
  }

  async function loadVacEmployees() {
    empSel.innerHTML = '<option value="" disabled selected>Bitte wählen...</option>';
    representativeSelect.innerHTML = '<option value="">Noch nicht festgelegt</option>';
    try {
      employees = listData(await api(BASE_EMP + "?limit=200"));
    } catch (err) {
      employees = currentUser && currentUser.employee ? [currentUser.employee] : [];
      setMessage("Mitarbeiter konnten nicht geladen werden: " + err.message, "error");
    }
    employees.forEach((employee) => {
      const label = employee.name + (employee.department ? " (" + employee.department + ")" : "");
      const employeeOption = document.createElement("option");
      employeeOption.value = employee.id;
      employeeOption.textContent = label;
      empSel.appendChild(employeeOption);

      const representativeOption = document.createElement("option");
      representativeOption.value = employee.id;
      representativeOption.textContent = label;
      representativeSelect.appendChild(representativeOption);
    });
    if (currentUser && currentUser.role !== "master_admin" && currentUser.employee_id) {
      empSel.value = String(currentUser.employee_id);
      empSel.disabled = true;
    }
    syncRepresentativeOptions();
    updateBalancePreview();
  }

  function syncRepresentativeOptions() {
    const employee = selectedEmployee();
    Array.from(representativeSelect.options).forEach((option) => {
      if (!option.value) return;
      const candidate = employees.find((item) => String(item.id) === option.value);
      option.hidden = Boolean(
        employee
        && candidate
        && (candidate.id === employee.id || candidate.department !== employee.department)
      );
    });
    if (representativeSelect.selectedOptions[0]?.hidden) representativeSelect.value = "";
  }

  async function loadSummary() {
    setLoading(summaryList, "Resturlaub wird geladen...");
    try {
      const data = listData(await api(BASE_VAC + "/summary?year=" + encodeURIComponent(yearSel.value)));
      employeeBalances = new Map(data.map((item) => [item.employee_id, item]));
      if (!data.length) {
        renderEmpty(summaryList, "Keine Mitarbeiterdaten für dieses Jahr.");
      } else {
        renderSummaryCards(data);
      }
      updateKpis();
      updateBalancePreview();
    } catch (err) {
      renderEmpty(summaryList, "Resturlaub konnte nicht geladen werden: " + err.message);
    }
  }

  async function loadRequests() {
    const params = new URLSearchParams({ year: yearSel.value });
    allRequests = listData(await api(BASE_VAC + "?" + params.toString()));
    updateKpis();
    renderCalendarList(allRequests);
  }

  async function loadPending() {
    setLoading(pendingList, "Ausstehende Anträge werden geladen...");
    try {
      const data = allRequests.filter((item) => item.status === "pending");
      pendingList.innerHTML = "";
      if (pendingCount) pendingCount.textContent = String(data.length);
      if (!data.length) {
        pendingEmpty.hidden = false;
        pendingList.appendChild(pendingEmpty);
        return;
      }
      pendingEmpty.hidden = true;
      data.forEach((vacation) => pendingList.appendChild(requestCard(vacation, "pending")));
    } catch (err) {
      if (pendingCount) pendingCount.textContent = "0";
      renderEmpty(pendingList, "Ausstehende Anträge konnten nicht geladen werden: " + err.message);
    }
  }

  async function loadHistory() {
    if (!historyList) return;
    setLoading(historyList, "Historie wird geladen...");
    try {
      let data = allRequests.slice();
      if (filterStatus.value) data = data.filter((item) => item.status === filterStatus.value);
      historyList.innerHTML = "";
      fillHiddenHistoryTable(data);
      if (tableEmpty) tableEmpty.hidden = data.length > 0;
      if (!data.length) {
        renderEmpty(historyList, "Keine Einträge vorhanden.");
        return;
      }
      data.forEach((vacation) => historyList.appendChild(requestCard(vacation, "history")));
    } catch (err) {
      renderEmpty(historyList, "Historie konnte nicht geladen werden: " + err.message);
      if (tableEmpty) tableEmpty.hidden = true;
    }
  }

  async function updateImpactPreview() {
    updateDaysCount();
    syncRepresentativeOptions();
    const error = validationError();
    if (!impactPreview) return;
    impactPreview.classList.remove("is-ok", "is-warning", "is-critical", "is-error");
    if (!empSel.value || !startInput.value || !endInput.value) {
      impactPreview.textContent = "Die betriebliche Auswirkung erscheint nach der Auswahl.";
      return;
    }
    if (error) {
      impactPreview.classList.add("is-error");
      impactPreview.textContent = error;
      return;
    }
    const requestId = ++impactRequestToken;
    impactPreview.textContent = "Auswirkung wird geprüft...";
    try {
      const params = new URLSearchParams({
        employee_id: empSel.value,
        start_date: startInput.value,
        end_date: endInput.value,
        shift_type: shiftSelect.value || "",
        representative_employee_id: representativeSelect.value || ""
      });
      const preview = await api(BASE_VAC + "/impact?" + params.toString());
      if (requestId !== impactRequestToken) return;
      const impact = preview.impact || {};
      impactPreview.classList.add("is-" + (impact.level || "ok"));
      impactPreview.textContent = impact.summary || "Keine auffälligen Konflikte erkannt.";
    } catch (err) {
      impactPreview.classList.add("is-error");
      impactPreview.textContent = err.message;
    }
  }

  async function decide(id, action) {
    try {
      setMessage("Antrag wird aktualisiert...", "");
      await api(BASE_VAC + "/" + id + "/" + action, { method: "POST" });
      setMessage("Antrag wurde aktualisiert.", "success");
      await refreshVacationData();
    } catch (err) {
      setMessage(err.message, "error");
    }
  }

  async function cancelVacation(id) {
    try {
      setMessage("Antrag wird storniert...", "");
      await api(BASE_VAC + "/" + id + "/cancel", { method: "POST" });
      setMessage("Antrag wurde storniert.", "success");
      await refreshVacationData();
    } catch (err) {
      setMessage(err.message, "error");
    }
  }

  async function refreshVacationData() {
    await loadSummary();
    await loadRequests();
    await Promise.all([loadPending(), loadHistory()]);
    await updateImpactPreview();
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const employeeId = empSel.value;
    const start = startInput.value;
    const end = endInput.value;
    if (!employeeId || !start || !end) {
      setMessage("Bitte alle Pflichtfelder ausfüllen.", "error");
      return;
    }
    const error = validationError();
    if (error) {
      setMessage(error, "error");
      return;
    }
    sending = true;
    submitBtn.disabled = true;
    setMessage("Antrag wird gesendet...", "");
    try {
      await api(BASE_VAC, {
        method: "POST",
        body: JSON.stringify({
          employee_id: parseInt(employeeId, 10),
          start_date: start,
          end_date: end,
          shift_type: shiftSelect.value || "",
          representative_employee_id: representativeSelect.value || null,
          reason: reasonInput.value,
          notes: notesInput.value
        })
      });
      setMessage("Antrag gestellt.", "success");
      startInput.value = "";
      endInput.value = "";
      shiftSelect.value = "";
      representativeSelect.value = "";
      reasonInput.value = "";
      notesInput.value = "";
      daysWrap.hidden = true;
      await refreshVacationData();
    } catch (err) {
      setMessage(err.message, "error");
    } finally {
      sending = false;
      submitBtn.disabled = false;
      updateBalancePreview();
    }
  }

  const today = new Date().toISOString().slice(0, 10);
  startInput.min = today;
  endInput.min = today;
  fillYearOptions();

  empSel.addEventListener("change", updateImpactPreview);
  representativeSelect.addEventListener("change", updateImpactPreview);
  shiftSelect.addEventListener("change", updateImpactPreview);
  startInput.addEventListener("change", async () => {
    const changed = syncYearFromStartDate();
    await updateImpactPreview();
    if (changed) await refreshVacationData();
  });
  endInput.addEventListener("change", updateImpactPreview);
  if (form) form.addEventListener("submit", handleSubmit);
  else submitBtn.addEventListener("click", handleSubmit);
  yearSel.addEventListener("change", refreshVacationData);
  filterBtn.addEventListener("click", loadHistory);

  await loadCurrentUser();
  await loadVacEmployees();
  await refreshVacationData();
}

export { initVacations };

registerWorkflowInitializers({
  initVacations: initVacations
});

(function () {
  function token() {
    return window.maintenanceAuth ? window.maintenanceAuth.token() : null;
  }

  function user() {
    return window.maintenanceAuth ? window.maintenanceAuth.user() : null;
  }

  function canView(dashboard) {
    return window.maintenanceAuth && window.maintenanceAuth.canView
      ? window.maintenanceAuth.canView(dashboard)
      : false;
  }

  function canWrite(dashboard) {
    return window.maintenanceAuth && window.maintenanceAuth.canWrite
      ? window.maintenanceAuth.canWrite(dashboard)
      : false;
  }

  function employeeAccessLevel() {
    return window.maintenanceAuth && window.maintenanceAuth.employeeAccessLevel
      ? window.maintenanceAuth.employeeAccessLevel()
      : "none";
  }

  const DASHBOARD_LABELS = {
    dashboard: "Dashboard",
    tasks: "Tasks",
    errors: "Fehlerliste",
    employees: "Mitarbeiter",
    shiftplans: "Schichtplan",
    machines: "Maschinen",
    inventory: "Lager",
    documents: "Dokumente",
    admin_users: "Users"
  };

  const DASHBOARD_KEYS = Object.keys(DASHBOARD_LABELS);
  const EMPLOYEE_ACCESS_LEVELS = ["none", "basic", "shift", "confidential"];
  const TASK_PRIORITIES = ["urgent", "soon", "normal"];
  const TASK_STATUSES = ["open", "in_progress", "done", "cancelled"];

  async function api(path, options) {
    const headers = Object.assign({ "Content-Type": "application/json" }, options && options.headers);
    const authToken = token();
    if (authToken) headers.Authorization = "Bearer " + authToken;

    const response = await fetch(path, Object.assign({}, options, { headers }));
    if (response.status === 401 || response.status === 422) {
      if (window.maintenanceAuth && window.maintenanceAuth.clearSession) {
        window.maintenanceAuth.clearSession({ redirect: true });
      }
      throw new Error("Sitzung abgelaufen. Bitte neu einloggen.");
    }
    if (response.status === 204) return null;
    const data = await response.json().catch(() => null);
    if (!response.ok) throw new Error((data && (data.message || data.error)) || "Anfrage konnte nicht verarbeitet werden.");
    if (data && data.success === true && Object.prototype.hasOwnProperty.call(data, "data")) {
      return data.data;
    }
    return data;
  }

  function fillDepartments(selects, departments) {
    const currentUser = user();
    selects.forEach((select) => {
      select.innerHTML = "";
      const placeholder = document.createElement("option");
      placeholder.value = "";
      placeholder.textContent = "Bereich auswaehlen";
      placeholder.disabled = true;
      placeholder.selected = true;
      select.appendChild(placeholder);

      departments.forEach((department) => {
        if (currentUser && currentUser.role !== "master_admin" && currentUser.department && currentUser.department.name !== department.name) {
          return;
        }
        const option = document.createElement("option");
        option.value = department.name;
        option.textContent = department.name;
        select.appendChild(option);
      });

      if (select.options.length === 1) {
        const option = document.createElement("option");
        option.value = "";
        option.textContent = "Keine Bereiche verfuegbar";
        option.disabled = true;
        select.appendChild(option);
        select.classList.add("has-error");
      } else {
        select.classList.remove("has-error");
        if (select.options.length === 2) {
          select.selectedIndex = 1;
        }
      }
    });
  }

  function row(cells) {
    const tr = document.createElement("tr");
    cells.forEach((cell) => {
      const td = document.createElement("td");
      if (cell instanceof Node) td.appendChild(cell);
      else td.textContent = cell || "-";
      tr.appendChild(td);
    });
    return tr;
  }

  function formatMoney(value) {
    return new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR" }).format(Number(value || 0));
  }

  function priorityBadgeClass(priority) {
    if (priority === "urgent") return "badge badge-priority is-urgent";
    if (priority === "soon") return "badge badge-priority is-soon";
    return "badge badge-priority is-normal";
  }

  function statusBadgeClass(status) {
    if (status === "in_progress") return "badge badge-status is-progress";
    if (status === "done") return "badge badge-status is-done";
    if (status === "cancelled") return "badge badge-status is-cancelled";
    return "badge badge-status is-open";
  }

  function priorityLabel(priority) {
    const labels = {
      urgent: "Urgent",
      soon: "Soon",
      normal: "Normal"
    };
    return labels[priority] || priority || "-";
  }

  function statusLabel(status) {
    const labels = {
      open: "Offen",
      in_progress: "In Arbeit",
      done: "Erledigt",
      cancelled: "Abgebrochen"
    };
    return labels[status] || status || "-";
  }

  function badge(text, className) {
    const element = document.createElement("span");
    element.className = className;
    element.textContent = text || "-";
    return element;
  }

  function labeledBadge(value, className, labelFormatter) {
    return badge(labelFormatter ? labelFormatter(value) : value, className);
  }

  function setText(selector, value) {
    document.querySelectorAll(selector).forEach((element) => {
      element.textContent = String(value);
    });
  }

  function setStatusMessage(element, message, isError) {
    if (!element) return;
    element.textContent = message || "";
    element.classList.toggle("is-error", Boolean(isError));
    element.classList.toggle("is-success", Boolean(message && !isError));
  }

  function actionButton(label, onClick, danger) {
    const button = document.createElement("button");
    button.className = danger ? "btn btn-error btn-sm text-white" : "btn btn-outline btn-sm";
    button.type = "button";
    button.textContent = label;
    button.addEventListener("click", onClick);
    return button;
  }

  function setCountBadge(selector, count, singular, plural) {
    document.querySelectorAll(selector).forEach((element) => {
      element.textContent = count + " " + (count === 1 ? singular : plural);
    });
  }

  function splitTagText(value) {
    return String(value || "")
      .split(/[,;\n]/)
      .map((item) => item.trim())
      .filter(Boolean);
  }

  function metaTile(label, value) {
    const item = document.createElement("div");
    item.className = "resource-metric";
    const labelElement = document.createElement("span");
    labelElement.className = "resource-label";
    labelElement.textContent = label;
    const valueElement = document.createElement("strong");
    valueElement.className = "resource-value";
    valueElement.textContent = value || "-";
    item.append(labelElement, valueElement);
    return item;
  }

  function resourceCard(title, subtitle) {
    const card = document.createElement("article");
    card.className = "resource-card";
    const header = document.createElement("div");
    header.className = "resource-card-header";
    const text = document.createElement("div");
    const titleElement = document.createElement("h3");
    titleElement.className = "resource-card-title";
    titleElement.textContent = title || "-";
    const subtitleElement = document.createElement("p");
    subtitleElement.className = "resource-card-subtitle";
    subtitleElement.textContent = subtitle || "";
    text.append(titleElement, subtitleElement);
    const badges = document.createElement("div");
    badges.className = "resource-card-badges";
    header.append(text, badges);
    card.append(header);
    return { card, badges };
  }

  function formatDate(value) {
    if (!value) return "-";
    return new Date(value + "T00:00:00").toLocaleDateString("de-DE", {
      weekday: "short",
      day: "2-digit",
      month: "2-digit"
    });
  }

  function shiftLabel(shift) {
    const labels = {
      Frueh: "Fruehschicht",
      Spaet: "Spaetschicht",
      Nacht: "Nachtschicht",
      Frei: "Frei",
      Urlaub: "Urlaub"
    };
    return labels[shift] || shift || "-";
  }

  function renderShiftCalendar(container, calendar) {
    if (!container) return;
    container.innerHTML = "";
    if (calendar.message) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = calendar.message;
      container.appendChild(empty);
      return;
    }
    const entries = calendar.entries || [];
    if (!entries.length) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = "Keine Kalendereintraege gefunden.";
      container.appendChild(empty);
      return;
    }
    entries.forEach((entry) => {
      const item = document.createElement("article");
      item.className = "shift-calendar-day is-" + (entry.color || "slate");
      const time = entry.start_time && entry.end_time
        ? entry.start_time + " - " + entry.end_time
        : entry.shift;
      item.innerHTML = `
        <span class="shift-calendar-date">${formatDate(entry.work_date)}</span>
        <strong class="shift-calendar-shift">${shiftLabel(entry.shift)}</strong>
        <span class="shift-calendar-time">${time || "-"}</span>
        <span class="shift-calendar-meta">${(entry.machine && entry.machine.name) || entry.notes || ""}</span>
      `;
      container.appendChild(item);
    });
  }

  function revealSurface(element) {
    const collapsible = element.closest("[data-mobile-collapsible]");
    if (collapsible) {
      collapsible.open = true;
      collapsible.dataset.mobileTouched = "true";
    }
    element.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function setSelectOptions(select, options, selectedValue) {
    select.innerHTML = "";
    options.forEach((value) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = value;
      select.appendChild(option);
    });
    select.value = selectedValue || options[0] || "";
  }

  function taskFormPayload(form) {
    const data = Object.fromEntries(new FormData(form).entries());
    Object.keys(data).forEach((key) => {
      if (data[key] === "") delete data[key];
    });
    return data;
  }

  async function initDepartments() {
    const selects = document.querySelectorAll("select[name='department']");
    if (!selects.length || !token()) return;
    try {
      const departments = await api("/api/departments");
      fillDepartments(selects, departments);
    } catch (error) {
      selects.forEach((select) => {
        select.innerHTML = "";
        const option = document.createElement("option");
        option.value = "";
        option.textContent = "Bereiche konnten nicht geladen werden";
        option.disabled = true;
        option.selected = true;
        select.appendChild(option);
        select.classList.add("has-error");
      });
    }
  }

  async function initTasks() {
    const list = document.querySelector("[data-task-list]");
    const form = document.querySelector("[data-task-form]");
    const priorityList = document.querySelector("[data-task-priority-list]");
    const priorityRefreshButtons = document.querySelectorAll("[data-task-priority-refresh]");
    const suggestForm = document.querySelector("[data-task-suggest-form]");
    const suggestionBox = document.querySelector("[data-task-suggestion]");
    const applySuggestion = document.querySelector("[data-apply-task-suggestion]");
    const submitButton = document.querySelector("[data-task-submit-button]");
    const cancelEditButton = document.querySelector("[data-task-edit-cancel]");
    if (!list || !form || !token()) return;
    let currentSuggestion = null;
    let editingTaskId = null;

    function riskBadgeClass(riskLevel) {
      if (riskLevel === "critical") return "badge badge-error text-white";
      if (riskLevel === "high") return "badge badge-warning text-slate-900";
      if (riskLevel === "medium") return "badge badge-info text-white";
      return "badge badge-success text-white";
    }

    async function loadPriorities() {
      if (!priorityList) return;
      priorityList.innerHTML = "";
      let priorities = [];
      try {
        priorities = await api("/api/tasks/prioritize", {
          method: "POST",
          body: JSON.stringify({ status: "open", limit: 10 })
        });
      } catch (error) {
        priorityList.innerHTML = '<tr><td colspan="5">Priorisierung konnte nicht geladen werden.</td></tr>';
        return;
      }
      if (!priorities.length) {
        priorityList.innerHTML = '<tr><td colspan="5">Keine offenen Tasks zu priorisieren.</td></tr>';
        return;
      }
      priorities.forEach((item) => {
        priorityList.appendChild(row([
          String(item.score),
          badge(item.risk_level, riskBadgeClass(item.risk_level)),
          item.task.title,
          item.reason,
          item.recommended_action
        ]));
      });
    }

    function resetTaskForm() {
      editingTaskId = null;
      form.reset();
      if (form.elements.status) form.elements.status.value = "open";
      if (form.elements.priority) form.elements.priority.value = "normal";
      if (submitButton) submitButton.textContent = "Task speichern";
      if (cancelEditButton) cancelEditButton.hidden = true;
    }

    async function editTask(task) {
      editingTaskId = task.id;
      form.elements.title.value = task.title || "";
      form.elements.department.value = (task.department && task.department.name) || "";
      form.elements.priority.value = task.priority || "normal";
      if (form.elements.status) form.elements.status.value = task.status || "open";
      form.elements.due_date.value = task.due_date || "";
      form.elements.description.value = task.description || "";
      if (submitButton) submitButton.textContent = "Task aktualisieren";
      if (cancelEditButton) cancelEditButton.hidden = false;
      revealSurface(form);
      form.elements.title.focus();
    }

    async function runTaskAction(task, action) {
      const endpoint = "/api/tasks/" + task.id + "/" + action;
      const message = document.querySelector("[data-task-message]");
      try {
        setStatusMessage(message, action === "start" ? "Task wird gestartet..." : "Task wird abgeschlossen...");
        await api(endpoint, { method: "POST" });
        await load();
        await loadPriorities();
        setStatusMessage(message, action === "start" ? "Task gestartet." : "Task abgeschlossen.");
      } catch (error) {
        setStatusMessage(message, error.message, true);
      }
    }

    function taskCard(task) {
      const card = document.createElement("article");
      card.className = "task-card";

      const top = document.createElement("div");
      top.className = "task-card-top";

      const title = document.createElement("h3");
      title.className = "task-card-title";
      title.textContent = task.title;

      const badges = document.createElement("div");
      badges.className = "flex flex-wrap justify-end gap-2";
      badges.append(
        labeledBadge(task.priority, priorityBadgeClass(task.priority), priorityLabel),
        labeledBadge(task.status, statusBadgeClass(task.status), statusLabel)
      );

      top.append(title, badges);

      const description = document.createElement("p");
      description.className = "task-card-description";
      description.textContent = task.description || "Keine Beschreibung";

      const meta = document.createElement("div");
      meta.className = "task-card-meta";
      [
        task.department && task.department.name,
        task.due_date ? "Faellig: " + task.due_date : "Keine Faelligkeit"
      ].filter(Boolean).forEach((value) => {
        const item = document.createElement("span");
        item.textContent = value;
        meta.appendChild(item);
      });

      const actions = document.createElement("div");
      actions.className = "task-card-actions";
      if (canWrite("tasks") && task.status === "open") {
        const start = actionButton("Starten", () => runTaskAction(task, "start"));
        start.className = "btn btn-primary btn-sm";
        actions.appendChild(start);
      }
      if (canWrite("tasks") && task.status !== "done" && task.status !== "cancelled") {
        const complete = actionButton("Erledigt", () => runTaskAction(task, "complete"));
        complete.className = "btn btn-success btn-sm text-white";
        actions.appendChild(complete);
      }
      if (canWrite("tasks")) {
        actions.appendChild(actionButton("Bearbeiten", () => editTask(task)));
      }

      card.append(top, description, meta, actions);
      return card;
    }

    async function load() {
      const tasks = await api("/api/tasks");
      list.innerHTML = "";
      if (!tasks.length) {
        list.innerHTML = '<div class="empty-state md:col-span-2 xl:col-span-3">Noch keine Tasks vorhanden.</div>';
        return;
      }
      tasks.forEach((task) => list.appendChild(taskCard(task)));
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const data = taskFormPayload(form);
      const wasEditing = Boolean(editingTaskId);
      const path = editingTaskId ? "/api/tasks/" + editingTaskId : "/api/tasks";
      const method = editingTaskId ? "PUT" : "POST";
      const message = document.querySelector("[data-task-message]");
      try {
        setStatusMessage(message, wasEditing ? "Task wird aktualisiert..." : "Task wird gespeichert...");
        await api(path, { method, body: JSON.stringify(data) });
        resetTaskForm();
        await initDepartments();
        await load();
        await loadPriorities();
        setStatusMessage(message, wasEditing ? "Task aktualisiert." : "Task gespeichert.");
      } catch (error) {
        setStatusMessage(message, error.message, true);
      }
    });

    if (cancelEditButton) {
      cancelEditButton.addEventListener("click", () => {
        resetTaskForm();
        const message = document.querySelector("[data-task-message]");
        setStatusMessage(message, "Bearbeitung abgebrochen.");
      });
    }

    if (suggestForm && suggestionBox) {
      suggestForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const message = document.querySelector("[data-task-suggest-message]");
        const data = Object.fromEntries(new FormData(suggestForm).entries());
        setStatusMessage(message, "AI erstellt Vorschlag...");
        try {
          currentSuggestion = await api("/api/tasks/suggest", {
            method: "POST",
            body: JSON.stringify(data)
          });
          suggestionBox.hidden = false;
          suggestionBox.querySelectorAll("[data-suggest-field]").forEach((field) => {
            field.value = currentSuggestion[field.dataset.suggestField] || "";
          });
          setStatusMessage(message, "Vorschlag erstellt.");
        } catch (error) {
          setStatusMessage(message, error.message, true);
        }
      });
    }

    if (applySuggestion) {
      applySuggestion.addEventListener("click", () => {
        if (!currentSuggestion) return;
        const values = {};
        suggestionBox.querySelectorAll("[data-suggest-field]").forEach((field) => {
          values[field.dataset.suggestField] = field.value;
        });
        form.elements.title.value = values.title || "";
        form.elements.department.value = values.department || "";
        form.elements.priority.value = values.priority || "normal";
        if (form.elements.status) form.elements.status.value = values.status || "open";
        form.elements.description.value = [
          values.description,
          values.possible_cause ? "Moegliche Ursache: " + values.possible_cause : "",
          values.recommended_action ? "Naechste Aktion: " + values.recommended_action : ""
        ].filter(Boolean).join("\n\n");
        revealSurface(form);
        form.elements.title.focus();
      });
    }

    priorityRefreshButtons.forEach((priorityRefresh) => {
      priorityRefresh.addEventListener("click", async () => {
        await loadPriorities();
      });
    });

    await load();
    await loadPriorities();
  }

  async function initErrors() {
    const list = document.querySelector("[data-error-list]");
    const form = document.querySelector("[data-error-form]");
    const analyzeForm = document.querySelector("[data-error-analyze-form]");
    const analysisBox = document.querySelector("[data-error-analysis]");
    const applyAnalysis = document.querySelector("[data-apply-error-analysis]");
    const similarPanel = document.querySelector("[data-similar-errors-panel]");
    const similarList = document.querySelector("[data-similar-errors-list]");
    const searchInput = document.querySelector("[data-error-search]");
    const errorCount = document.querySelector("[data-error-count]");
    const searchFocus = document.querySelector("[data-error-search-focus]");
    const analysisFocus = document.querySelector("[data-error-analysis-focus]");
    if (!list || !form || !token()) return;
    let currentAnalysis = null;
    let currentErrors = [];

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

    function renderSimilarErrors(result) {
      if (!similarPanel || !similarList) return;
      const matches = result.results || [];
      similarPanel.hidden = false;
      similarList.innerHTML = "";
      if (!matches.length) {
        similarList.innerHTML = '<tr><td colspan="5">Keine aehnlichen Fehler gefunden.</td></tr>';
        return;
      }
      matches.forEach((match) => {
        similarList.appendChild(row([
          String(match.score),
          badge(match.entry.error_code, "badge badge-status is-open"),
          match.entry.machine,
          match.entry.title,
          match.reason
        ]));
      });
    }

    async function loadSimilarErrors(data) {
      const result = await api("/api/errors/similar", {
        method: "POST",
        body: JSON.stringify({
          text: data.description || data.title || "",
          machine: data.machine || "",
          limit: 5
        })
      });
      renderSimilarErrors(result);
    }

    function renderErrors() {
      const query = searchInput ? searchInput.value.trim().toLowerCase() : "";
      const filteredErrors = currentErrors.filter((entry) => {
        if (!query) return true;
        return [
          entry.error_code,
          entry.machine,
          entry.title,
          entry.possible_causes,
          entry.solution,
          entry.department && entry.department.name
        ].filter(Boolean).join(" ").toLowerCase().includes(query);
      });
      list.innerHTML = "";
      if (errorCount) errorCount.textContent = filteredErrors.length + " Eintraege";
      if (!filteredErrors.length) {
        list.innerHTML = '<tr><td colspan="6">Keine passenden Fehler gefunden.</td></tr>';
        return;
      }
      filteredErrors.forEach((entry) => {
        list.appendChild(row([
          badge(entry.error_code, "badge badge-status is-open"),
          entry.machine,
          entry.title,
          entry.department && entry.department.name,
          highlightedBlock("Ursache", entry.possible_causes, "is-cause"),
          highlightedBlock("Loesung", entry.solution, "is-solution")
        ]));
      });
    }

    async function load() {
      currentErrors = await api("/api/errors");
      renderErrors();
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const data = Object.fromEntries(new FormData(form).entries());
      data.description = data.title;
      const message = document.querySelector("[data-error-message]");
      try {
        setStatusMessage(message, "Fehler wird geprueft...");
        await loadSimilarErrors(data);
        await api("/api/errors", { method: "POST", body: JSON.stringify(data) });
        form.reset();
        await initDepartments();
        await load();
        setStatusMessage(message, "Fehler gespeichert.");
      } catch (error) {
        setStatusMessage(message, error.message, true);
      }
    });

    if (analyzeForm && analysisBox) {
      analyzeForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const message = document.querySelector("[data-error-analyze-message]");
        const data = Object.fromEntries(new FormData(analyzeForm).entries());
        setStatusMessage(message, "AI analysiert...");
        try {
          currentAnalysis = await api("/api/errors/analyze", {
            method: "POST",
            body: JSON.stringify(data)
          });
          analysisBox.hidden = false;
          analysisBox.querySelectorAll("[data-error-analysis-field]").forEach((field) => {
            field.value = currentAnalysis[field.dataset.errorAnalysisField] || "";
          });
          setStatusMessage(message, "Analyse erstellt.");
          await loadSimilarErrors({
            description: data.description,
            machine: currentAnalysis.machine
          });
        } catch (error) {
          setStatusMessage(message, error.message, true);
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
        form.elements.possible_causes.value = values.possible_causes || "";
        form.elements.solution.value = values.solution || "";
        revealSurface(form);
        form.elements.title.focus();
      });
    }

    if (searchInput) {
      searchInput.addEventListener("input", renderErrors);
    }

    if (searchFocus && searchInput) {
      searchFocus.addEventListener("click", () => {
        searchInput.focus();
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
  }

  async function initUsers() {
    const list = document.querySelector("[data-user-list]");
    if (!list || !token()) return;
    const editor = document.querySelector("[data-permission-editor]");
    const editorTitle = document.querySelector("[data-permission-editor-title]");
    const permissionList = document.querySelector("[data-permission-list]");
    const permissionForm = document.querySelector("[data-permission-form]");
    const permissionMessage = document.querySelector("[data-permission-message]");
    let selectedUser = null;
    let employees = [];

    function employeeSelect(item) {
      const select = document.createElement("select");
      select.className = "select select-bordered";
      select.dataset.userEmployeeSelect = String(item.id);
      const empty = document.createElement("option");
      empty.value = "";
      empty.textContent = "Nicht verknuepft";
      select.appendChild(empty);
      employees.forEach((employee) => {
        const option = document.createElement("option");
        option.value = String(employee.id);
        option.textContent = employee.name + " (" + employee.personnel_number + ")";
        select.appendChild(option);
      });
      select.value = item.employee_id ? String(item.employee_id) : "";
      select.addEventListener("change", async () => {
        await api("/api/admin/users/" + item.id, {
          method: "PUT",
          body: JSON.stringify({ employee_id: select.value })
        });
        const currentSessionUser = user();
        if (currentSessionUser && currentSessionUser.id === item.id && window.maintenanceAuth) {
          await window.maintenanceAuth.refreshUser();
        }
        await load();
      });
      return select;
    }

    function checkboxCell(dashboard, action, checked, disabled) {
      const input = document.createElement("input");
      input.type = "checkbox";
      input.checked = Boolean(checked);
      input.disabled = Boolean(disabled);
      input.dataset.dashboard = dashboard;
      input.dataset.permissionAction = action;
      return input;
    }

    function accessLevelSelect(dashboard, selected, disabled) {
      const select = document.createElement("select");
      select.className = "select select-bordered";
      select.disabled = Boolean(disabled);
      select.dataset.dashboard = dashboard;
      select.dataset.permissionAction = "employee_access_level";
      EMPLOYEE_ACCESS_LEVELS.forEach((level) => {
        const option = document.createElement("option");
        option.value = level;
        option.textContent = level;
        select.appendChild(option);
      });
      select.value = selected || "none";
      return select;
    }

    function renderPermissionEditor(item) {
      if (!editor || !permissionList || !permissionForm) return;
      selectedUser = item;
      editor.hidden = false;
      if (editorTitle) {
        editorTitle.textContent = item.username + " - Rechte je Dashboard";
      }
      if (permissionMessage) permissionMessage.textContent = "";
      permissionList.innerHTML = "";

      DASHBOARD_KEYS.forEach((dashboard) => {
        const permission = (item.permissions && item.permissions[dashboard]) || {};
        const isAdminUsersDashboard = dashboard === "admin_users";
        const isMasterAdmin = item.role === "master_admin";
        permissionList.appendChild(row([
          DASHBOARD_LABELS[dashboard],
          checkboxCell(
            dashboard,
            "can_view",
            isAdminUsersDashboard ? isMasterAdmin : permission.can_view,
            isAdminUsersDashboard
          ),
          checkboxCell(
            dashboard,
            "can_write",
            isAdminUsersDashboard ? isMasterAdmin : permission.can_write,
            isAdminUsersDashboard
          ),
          dashboard === "employees"
            ? accessLevelSelect(dashboard, permission.employee_access_level)
            : "-"
        ]));
      });
    }

    if (permissionForm) {
      permissionForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (!selectedUser) return;
        const payload = { permissions: {} };
        DASHBOARD_KEYS.forEach((dashboard) => {
          payload.permissions[dashboard] = {
            can_view: false,
            can_write: false,
            employee_access_level: "none"
          };
        });
        permissionForm.querySelectorAll("[data-dashboard]").forEach((input) => {
          const dashboard = input.dataset.dashboard;
          const action = input.dataset.permissionAction;
          if (action === "employee_access_level") {
            payload.permissions[dashboard].employee_access_level = input.value;
          } else {
            payload.permissions[dashboard][action] = input.checked;
          }
        });
        payload.permissions.admin_users.can_view = selectedUser.role === "master_admin";
        payload.permissions.admin_users.can_write = selectedUser.role === "master_admin";
        try {
          const updated = await api("/api/admin/users/" + selectedUser.id + "/permissions", {
            method: "PUT",
            body: JSON.stringify(payload)
          });
          const currentSessionUser = user();
          if (currentSessionUser && currentSessionUser.id === updated.id && window.maintenanceAuth) {
            await window.maintenanceAuth.refreshUser();
          }
          selectedUser = updated;
          await load();
          if (permissionMessage) permissionMessage.textContent = "Rechte gespeichert.";
        } catch (error) {
          if (permissionMessage) permissionMessage.textContent = error.message;
        }
      });
    }

    async function load() {
      const users = await api("/api/admin/users");
      try {
        employees = await api("/api/employees");
      } catch (error) {
        employees = [];
      }
      list.innerHTML = "";
      users.forEach((item) => {
        const actions = document.createElement("div");
        actions.className = "table-actions";

        const reset = document.createElement("button");
        reset.className = "btn btn-outline btn-sm";
        reset.type = "button";
        reset.textContent = "Passwort";
        reset.addEventListener("click", async () => {
          const password = window.prompt("Neues Passwort fuer " + item.username);
          if (!password) return;
          await api("/api/admin/users/" + item.id + "/reset-password", {
            method: "POST",
            body: JSON.stringify({ password })
          });
        });

        const lock = document.createElement("button");
        lock.className = "btn btn-outline btn-sm";
        lock.type = "button";
        lock.textContent = item.is_active ? "Sperren" : "Entsperren";
        lock.addEventListener("click", async () => {
          await api("/api/admin/users/" + item.id + "/" + (item.is_active ? "lock" : "unlock"), { method: "POST" });
          await load();
        });

        const remove = document.createElement("button");
        remove.className = "btn btn-error btn-sm text-white";
        remove.type = "button";
        remove.textContent = "Loeschen";
        remove.addEventListener("click", async () => {
          if (!window.confirm(item.username + " wirklich loeschen?")) return;
          await api("/api/admin/users/" + item.id, { method: "DELETE" });
          await load();
        });

        const permissions = document.createElement("button");
        permissions.className = "btn btn-primary btn-sm";
        permissions.type = "button";
        permissions.textContent = "Rechte";
        permissions.addEventListener("click", () => renderPermissionEditor(item));

        actions.append(permissions, reset, lock, remove);
        list.appendChild(row([
          item.username,
          item.email,
          item.role,
          item.department && item.department.name,
          employeeSelect(item),
          item.is_active ? "aktiv" : "gesperrt",
          actions
        ]));
      });
      if (selectedUser) {
        const freshSelectedUser = users.find((item) => item.id === selectedUser.id);
        if (freshSelectedUser) {
          renderPermissionEditor(freshSelectedUser);
        }
      }
      return users;
    }

    await load();
  }

  async function initEmployees() {
    const list = document.querySelector("[data-employee-list]");
    const form = document.querySelector("[data-employee-form]");
    const message = document.querySelector("[data-employee-message]");
    if (!list || !form || !token()) return;

    async function uploadDocument(employeeId, file) {
      const formData = new FormData();
      formData.append("document", file);
      const response = await fetch("/api/employees/" + employeeId + "/documents", {
        method: "POST",
        headers: { "Authorization": "Bearer " + token() },
        body: formData
      });
      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        throw new Error((errorData && errorData.error) || "Upload fehlgeschlagen");
      }
      return response.json();
    }

    async function downloadEmployeeDocument(documentItem) {
      const response = await fetch(documentItem.download_url, {
        headers: { "Authorization": "Bearer " + token() }
      });
      if (!response.ok) throw new Error("Download fehlgeschlagen");
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = documentItem.original_filename;
      link.click();
      window.URL.revokeObjectURL(url);
    }

    async function load() {
      const employees = await api("/api/employees");
      list.innerHTML = "";
      setCountBadge("[data-employee-count]", employees.length, "Mitarbeitender", "Mitarbeitende");
      if (!employees.length) {
        list.innerHTML = '<div class="empty-state">Noch keine Mitarbeitenden erfasst.</div>';
        return;
      }
      employees.forEach((employee) => {
        const shiftText = employee.current_shift || employee.shift_model || "Schicht offen";
        const departmentText = employee.department || "Bereich offen";
        const { card, badges } = resourceCard(employee.name, employee.personnel_number);
        badges.appendChild(badge(departmentText, "badge badge-status is-open"));
        badges.appendChild(badge(shiftText, "badge badge-shift"));

        const meta = document.createElement("div");
        meta.className = "resource-meta-grid";
        meta.append(
          metaTile("Abteilung", departmentText),
          metaTile("Team", employee.team ? "Team " + employee.team : "Nicht zugeordnet"),
          metaTile("Schicht", shiftText),
          metaTile("Maschine", employee.favorite_machine || "Keine bevorzugt")
        );

        const tags = document.createElement("div");
        tags.className = "badge-list";
        const qualifications = splitTagText(employee.qualifications);
        if (qualifications.length) {
          qualifications.slice(0, 6).forEach((qualification) => {
            tags.appendChild(badge(qualification, "badge badge-skill"));
          });
        } else {
          tags.appendChild(badge("Keine Qualifikation hinterlegt", "badge badge-review is-unchecked"));
        }

        const documentNote = document.createElement("div");
        documentNote.className = "resource-note";
        const documentCount = (employee.documents || []).length;
        documentNote.textContent = documentCount
          ? documentCount + " Dokument" + (documentCount === 1 ? "" : "e") + " hinterlegt"
          : "Keine Dokumente hinterlegt";

        const links = document.createElement("div");
        links.className = "document-links";
        (employee.documents || []).forEach((document) => {
          const download = actionButton(document.original_filename, async () => {
            try {
              await downloadEmployeeDocument(document);
            } catch (error) {
              if (message) message.textContent = error.message;
            }
          });
          download.className = "btn btn-link btn-sm justify-start px-0";
          links.appendChild(download);
        });

        if (canWrite("employees") && employeeAccessLevel() === "confidential") {
          const upload = document.createElement("label");
          upload.className = "resource-upload";
          upload.textContent = "Dokumente hochladen";
          const input = document.createElement("input");
          input.type = "file";
          input.multiple = true;
          input.addEventListener("change", async () => {
            if (!input.files.length) return;
            input.disabled = true;
            if (message) message.textContent = "Dokumente werden hochgeladen...";
            try {
              const files = Array.from(input.files);
              for (const file of files) {
                await uploadDocument(employee.id, file);
              }
              input.value = "";
              await load();
              if (message) message.textContent = files.length === 1
                ? "Dokument hochgeladen."
                : files.length + " Dokumente hochgeladen.";
            } catch (error) {
              if (message) message.textContent = error.message;
            } finally {
              input.disabled = false;
            }
          });
          upload.appendChild(input);
          documentNote.appendChild(upload);
        }
        if ((employee.documents || []).length) documentNote.appendChild(links);

        card.append(meta, tags, documentNote);
        list.appendChild(card);
      });
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const data = Object.fromEntries(new FormData(form).entries());
      await api("/api/employees", { method: "POST", body: JSON.stringify(data) });
      form.reset();
      await load();
      if (message) message.textContent = "Mitarbeiter gespeichert.";
    });

    await load();
  }

  async function fillMachineSelects() {
    const selects = document.querySelectorAll("[data-machine-select]");
    if (!selects.length || !token()) return [];
    if (!canView("machines")) return [];
    const machines = await api("/api/machines");
    selects.forEach((select) => {
      const current = select.value;
      select.innerHTML = '<option value="">Keine Maschine</option>';
      machines.forEach((machine) => {
        const option = document.createElement("option");
        option.value = machine.id;
        option.textContent = machine.name;
        select.appendChild(option);
      });
      select.value = current;
    });
    return machines;
  }

  async function initMachines() {
    const list = document.querySelector("[data-machine-list]");
    const form = document.querySelector("[data-machine-form]");
    const historyPanel = document.querySelector("[data-machine-history-panel]");
    const historyTitle = document.querySelector("[data-machine-history-title]");
    const historySummary = document.querySelector("[data-machine-history-summary]");
    const historyCounts = document.querySelector("[data-machine-history-counts]");
    const historyList = document.querySelector("[data-machine-history-list]");
    const assistantForm = document.querySelector("[data-machine-assistant-form]");
    const assistantAnswer = document.querySelector("[data-machine-assistant-answer]");
    const assistantFocus = document.querySelector("[data-machine-assistant-focus]");
    if (!list || !form || !token()) return;
    let activeHistoryMachine = null;

    function renderHistoryCounts(counts) {
      if (!historyCounts) return;
      historyCounts.innerHTML = "";
      [
        ["Tasks", counts.tasks || 0],
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
      if (historySummary) historySummary.textContent = history.summary.text || "";
      renderHistoryCounts(history.source_counts || {});
      historyList.innerHTML = "";
      if (!history.timeline || !history.timeline.length) {
        historyList.innerHTML = '<div class="empty-state">Keine Historie gefunden.</div>';
      } else {
        history.timeline.slice(0, 12).forEach((item) => {
          const timelineItem = document.createElement("article");
          timelineItem.className = "timeline-item";
          const header = document.createElement("div");
          header.className = "timeline-item-header";
          const text = document.createElement("div");
          const title = document.createElement("h3");
          title.className = "timeline-title";
          title.textContent = item.title || "-";
          const date = document.createElement("p");
          date.className = "panel-meta";
          date.textContent = item.date ? new Date(item.date).toLocaleString("de-DE") : "-";
          text.append(title, date);
          header.append(text, badge(item.type, "badge badge-status is-open"));
          const summary = document.createElement("p");
          summary.className = "timeline-summary";
          summary.textContent = item.summary || "Kein Detailtext hinterlegt.";
          const actions = document.createElement("div");
          actions.className = "resource-actions";
          const link = historyLink(item);
          if (link instanceof Node) actions.appendChild(link);
          timelineItem.append(header, summary, actions);
          historyList.appendChild(timelineItem);
        });
      }
      historyPanel.scrollIntoView({ behavior: "smooth", block: "start" });
    }

    async function loadMachineHistory(machine) {
      const history = await api("/api/machines/" + machine.id + "/history");
      renderMachineHistory(history);
    }

    if (assistantForm) {
      assistantForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (!activeHistoryMachine) return;
        const data = Object.fromEntries(new FormData(assistantForm).entries());
        setStatusMessage(assistantAnswer, "Maschinen-Assistent denkt...");
        try {
          const result = await api("/api/machines/" + activeHistoryMachine.id + "/assistant", {
            method: "POST",
            body: JSON.stringify(data)
          });
          const fallback = result.diagnostics && (
            result.diagnostics.fallback_used || result.diagnostics.status === "fallback_used"
          )
            ? "Fallback-Antwort: "
            : "";
          setStatusMessage(assistantAnswer, fallback + result.answer);
        } catch (error) {
          setStatusMessage(assistantAnswer, error.message, true);
        }
      });
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

    function updateMachineCardHistory(card, history) {
      const counts = history.source_counts || {};
      const timeline = history.timeline || [];
      const openTasks = timeline.filter((item) => (
        item.type === "task" && !["done", "cancelled"].includes(item.status)
      ));
      const statusBadge = card.querySelector("[data-machine-status]");
      if (statusBadge) {
        const hasWarnings = openTasks.length || counts.errors;
        statusBadge.className = hasWarnings
          ? "badge badge-review is-warning"
          : "badge badge-review is-checked";
        statusBadge.textContent = hasWarnings ? "Hinweise" : "Stabil";
      }

      const lastMaintenance = card.querySelector("[data-machine-last-maintenance]");
      if (lastMaintenance) {
        const latest = timeline.find((item) => item.type === "document" || item.type === "task");
        lastMaintenance.textContent = latest && latest.date
          ? new Date(latest.date).toLocaleDateString("de-DE")
          : "Keine Historie";
      }

      const openTaskElement = card.querySelector("[data-machine-open-tasks]");
      if (openTaskElement) {
        openTaskElement.textContent = openTasks.length
          ? openTasks.length + " offen"
          : "Keine offenen Tasks";
      }

      const note = card.querySelector("[data-machine-note]");
      if (note) {
        note.textContent = history.summary && history.summary.text
          ? history.summary.text
          : "Keine Wartungshinweise verfuegbar.";
      }
    }

    function renderMachineCard(machine) {
      const { card, badges } = resourceCard(machine.name, machine.produced_item || "Produktion nicht hinterlegt");
      const status = badge("Historie offen", "badge badge-review is-unchecked");
      status.dataset.machineStatus = "true";
      badges.append(status, badge(machine.required_employees + " MA", "badge badge-machine"));

      const meta = document.createElement("div");
      meta.className = "resource-meta-grid";
      const lastMaintenance = metaTile("Letzte Wartung", "Wird geladen");
      lastMaintenance.querySelector("strong").dataset.machineLastMaintenance = "true";
      const openTasks = metaTile("Offene Tasks", "Wird geladen");
      openTasks.querySelector("strong").dataset.machineOpenTasks = "true";
      meta.append(
        metaTile("Bereich", machine.produced_item || "Nicht angegeben"),
        metaTile("Personalbedarf", machine.required_employees + " Mitarbeitende"),
        lastMaintenance,
        openTasks
      );

      const note = document.createElement("p");
      note.className = "resource-note";
      note.dataset.machineNote = "true";
      note.textContent = "Historie wird geladen.";

      const actions = document.createElement("div");
      actions.className = "resource-actions";
      actions.appendChild(actionButton("Historie", () => loadMachineHistory(machine)));
      if (canWrite("machines")) {
        actions.appendChild(actionButton("Loeschen", async () => {
          if (!window.confirm(machine.name + " wirklich loeschen?")) return;
          await api("/api/machines/" + machine.id, { method: "DELETE" });
          await load();
        }, true));
      }

      card.append(meta, note, actions);
      return card;
    }

    async function load() {
      const machines = await api("/api/machines");
      list.innerHTML = "";
      setCountBadge("[data-machine-count]", machines.length, "Maschine", "Maschinen");
      if (!machines.length) {
        list.innerHTML = '<div class="empty-state">Noch keine Maschinen erfasst.</div>';
        return;
      }
      machines.forEach((machine) => {
        const card = renderMachineCard(machine);
        list.appendChild(card);
        api("/api/machines/" + machine.id + "/history")
          .then((history) => updateMachineCardHistory(card, history))
          .catch(() => {
            const note = card.querySelector("[data-machine-note]");
            if (note) note.textContent = "Historie konnte nicht geladen werden.";
          });
      });
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const data = Object.fromEntries(new FormData(form).entries());
      await api("/api/machines", { method: "POST", body: JSON.stringify(data) });
      form.reset();
      form.elements.required_employees.value = "1";
      await load();
      const message = document.querySelector("[data-machine-message]");
      if (message) message.textContent = "Maschine gespeichert.";
    });

    await load();
  }

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
        const unmatchedTasks = forecast.unmatched_tasks || [];
        if (unmatchedTasks.length) {
          const title = document.createElement("h3");
          title.className = "panel-title";
          title.textContent = "Tasks ohne Maschinenbezug";
          forecastUnmatched.appendChild(title);
          unmatchedTasks.forEach((item) => {
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
      const forecast = await api("/api/inventory/forecast", {
        method: "POST",
        body: JSON.stringify(data)
      });
      renderForecast(forecast);
    }

    async function load() {
      await fillMachineSelects();
      const materials = await api("/api/inventory");
      list.innerHTML = "";
      materials.forEach((material) => {
        const actions = document.createElement("div");
        actions.className = "table-actions";
        if (canWrite("inventory")) {
          actions.appendChild(actionButton("Loeschen", async () => {
            if (!window.confirm(material.name + " wirklich loeschen?")) return;
            await api("/api/inventory/" + material.id, { method: "DELETE" });
            await load();
          }, true));
        }
        list.appendChild(row([
          material.name,
          formatMoney(material.unit_cost),
          String(material.quantity),
          material.machine && material.machine.name,
          material.manufacturer,
          formatMoney(material.total_value),
          actions
        ]));
      });
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const data = Object.fromEntries(new FormData(form).entries());
      await api("/api/inventory", { method: "POST", body: JSON.stringify(data) });
      form.reset();
      await load();
      const message = document.querySelector("[data-inventory-message]");
      if (message) message.textContent = "Material gespeichert.";
    });

    if (forecastForm) {
      forecastForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (forecastMessage) forecastMessage.textContent = "Prognose wird berechnet...";
        try {
          await loadForecast();
        } catch (error) {
          if (forecastMessage) {
            forecastMessage.textContent = error.message;
            forecastMessage.classList.add("is-error");
          }
        }
      });
    }

    await load();
  }

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
        const remove = actionButton("Loeschen", async () => {
          if (!window.confirm(plan.title + " wirklich loeschen?")) return;
          await api("/api/shiftplans/" + plan.id, { method: "DELETE" });
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
      const plans = await api("/api/shiftplans");
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
      if (message) message.textContent = "KI plant...";
      const data = Object.fromEntries(new FormData(form).entries());
      data.vacations = parseVacationText(data.vacations_text);
      delete data.vacations_text;
      try {
        const plan = await api("/api/shiftplans/generate", { method: "POST", body: JSON.stringify(data) });
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
        if (message) {
          message.textContent = error.message;
          message.classList.add("is-error");
        }
      }
    });

    await load();
  }

  async function initDashboard() {
    const taskRail = document.querySelector("[data-dashboard-task-rail]");
    const taskCountElements = document.querySelectorAll("[data-dashboard-task-count]");
    const taskDetailModal = document.querySelector("[data-task-detail-modal]");
    const taskDetailTitle = document.querySelector("[data-task-detail-title]");
    const taskDetailSubtitle = document.querySelector("[data-task-detail-subtitle]");
    const taskDetailBody = document.querySelector("[data-task-detail-body]");
    const taskDetailMessage = document.querySelector("[data-task-detail-message]");
    const taskStartButton = document.querySelector("[data-task-start-button]");
    const taskCompleteButton = document.querySelector("[data-task-complete-button]");
    const taskDetailClose = document.querySelector("[data-task-detail-close]");
    const reportGenerate = document.querySelector("[data-report-generate]");
    const errorStats = document.querySelector("[data-dashboard-error-stats]");
    const inventoryStats = document.querySelector("[data-dashboard-inventory-stats]");
    if ((!taskRail && !errorStats && !inventoryStats) || !token()) return;

    let activeTask = null;
    let activeTaskId = null;

    function formatDateTime(value) {
      if (!value) return "-";
      return new Date(value).toLocaleString("de-DE");
    }

    function formatUser(value) {
      if (!value) return "-";
      return value.username || value.email || "User #" + value.id;
    }

    function detailRow(label, value) {
      const item = document.createElement("div");
      item.className = "task-detail-row";

      const labelElement = document.createElement("span");
      labelElement.textContent = label;

      const valueElement = document.createElement("strong");
      valueElement.textContent = value || "-";

      item.append(labelElement, valueElement);
      return item;
    }

    function renderTaskDetail(task) {
      if (!taskDetailModal || !taskDetailBody) return;

      activeTask = task;
      activeTaskId = task.id;
      taskDetailTitle.textContent = task.title;
      taskDetailSubtitle.textContent = (task.department && task.department.name) || "-";
      taskDetailBody.innerHTML = "";
      taskDetailBody.append(
        detailRow("Titel", task.title),
        detailRow("Beschreibung", task.description || "Keine Beschreibung"),
        detailRow("Prioritaet", task.priority),
        detailRow("Status", task.status),
        detailRow("Department", task.department && task.department.name),
        detailRow("Ersteller", formatUser(task.creator)),
        detailRow("Erstellt am", formatDateTime(task.created_at)),
        detailRow("Aktuell bearbeitet von", formatUser(task.current_worker)),
        detailRow("Gestartet am", formatDateTime(task.started_at)),
        detailRow("Erledigt von", formatUser(task.completed_by_user)),
        detailRow("Erledigt am", formatDateTime(task.completed_at))
      );

      updateTaskActionButtons(task);
      showTaskMessage("");
    }

    function updateTaskActionButtons(task, isBusy) {
      if (taskStartButton) {
        taskStartButton.hidden = !canWrite("tasks");
        taskStartButton.disabled = Boolean(isBusy) || task.status !== "open";
      }
      if (taskCompleteButton) {
        taskCompleteButton.hidden = !canWrite("tasks");
        taskCompleteButton.disabled = Boolean(isBusy) || task.status === "done" || task.status === "cancelled";
      }
    }

    function showTaskMessage(message, isError) {
      if (!taskDetailMessage) return;
      taskDetailMessage.textContent = message;
      taskDetailMessage.classList.toggle("is-error", Boolean(isError));
      taskDetailMessage.classList.toggle("is-success", Boolean(message && !isError));
    }

    async function openTaskDetail(taskId) {
      const task = await api("/api/tasks/" + taskId);
      renderTaskDetail(task);
      if (taskDetailModal) taskDetailModal.hidden = false;
    }

    async function refreshActiveTask(message) {
      if (!activeTaskId) return;
      const task = await api("/api/tasks/" + activeTaskId);
      renderTaskDetail(task);
      showTaskMessage(message);
      await loadDashboardTasks();
    }

    function reportPayload() {
      const payload = {};
      if (reportGenerate && reportGenerate.checked) {
        payload.generate_report = true;
        document.querySelectorAll("[data-report-field]").forEach((field) => {
          payload[field.dataset.reportField] = field.value;
        });
        payload.notes = payload.action || "";
      }
      return payload;
    }

    async function runTaskAction(path, successMessage, body) {
      if (!activeTaskId || !activeTask) return;
      updateTaskActionButtons(activeTask, true);
      showTaskMessage("Wird verarbeitet...");

      try {
        const options = { method: "POST" };
        if (body && Object.keys(body).length) {
          options.body = JSON.stringify(body);
        }
        const result = await api(path, options);
        if (result && result.generated_document) {
          successMessage += " Wartungsbericht wurde erzeugt.";
        }
        await refreshActiveTask(successMessage);
      } catch (error) {
        updateTaskActionButtons(activeTask);
        showTaskMessage(error.message, true);
      }
    }

    async function loadDashboardTasks() {
      const tasks = await api("/api/tasks");
      taskRail.innerHTML = "";
      taskCountElements.forEach((taskCount) => {
        taskCount.textContent = String(tasks.length);
      });
      if (!tasks.length) {
        taskRail.innerHTML = '<div class="empty-state">Noch keine Tasks vorhanden.</div>';
      } else {
        tasks.forEach((task) => {
          const card = document.createElement("button");
          card.type = "button";
          card.className = "task-card";
          card.addEventListener("click", () => openTaskDetail(task.id));
          const priorityClass = task.priority === "urgent" ? "is-urgent" : task.priority === "soon" ? "is-soon" : "is-normal";
          card.innerHTML = `
            <div class="task-card-top">
              <strong>${task.title}</strong>
              <span class="badge ${priorityClass}">${task.priority}</span>
            </div>
            <p>${task.description || "Keine Beschreibung"}</p>
            <small>${task.department ? task.department.name : "-"} · ${task.status} · ${task.due_date}</small>
          `;
          taskRail.appendChild(card);
        });
      }
    }

    if (taskDetailClose && taskDetailModal) {
      taskDetailClose.addEventListener("click", () => {
        taskDetailModal.hidden = true;
      });
    }

    if (taskStartButton) {
      taskStartButton.addEventListener("click", async () => {
        await runTaskAction(
          "/api/tasks/" + activeTaskId + "/start",
          "Task gestartet."
        );
      });
    }

    if (taskCompleteButton) {
      taskCompleteButton.addEventListener("click", async () => {
        await runTaskAction(
          "/api/tasks/" + activeTaskId + "/complete",
          "Task abgeschlossen.",
          reportPayload()
        );
      });
    }

    if (taskRail && canView("tasks")) {
      await loadDashboardTasks();
    }

    if (errorStats && canView("errors")) {
      const errors = await api("/api/errors");
      const counts = new Map();
      errors.forEach((entry) => {
        const name = entry.department ? entry.department.name : "Ohne Bereich";
        counts.set(name, (counts.get(name) || 0) + 1);
      });
      errorStats.innerHTML = "";
      if (!counts.size) {
        errorStats.innerHTML = '<div class="empty-state">Noch keine Fehler erfasst.</div>';
      } else {
        counts.forEach((count, name) => {
          const item = document.createElement("div");
          item.className = "stat-row";
          item.innerHTML = `<span>${name}</span><strong>${count}</strong>`;
          errorStats.appendChild(item);
        });
      }
    }

    if (inventoryStats && canView("inventory")) {
      const summary = await api("/api/inventory/summary");
      inventoryStats.innerHTML = "";
      inventoryStats.append(
        rowLikeStat("Materialien", String(summary.material_count)),
        rowLikeStat("Gesamtanzahl", String(summary.total_quantity)),
        rowLikeStat("Gesamtwert", formatMoney(summary.total_value))
      );
    }

    function rowLikeStat(label, value) {
      const item = document.createElement("div");
      item.className = "stat-row";
      item.innerHTML = `<span>${label}</span><strong>${value}</strong>`;
      return item;
    }
  }

  async function initDailyCockpit() {
    const taskBoard = document.querySelector("[data-dashboard-task-board]");
    const taskCountElements = document.querySelectorAll("[data-dashboard-task-count]");
    const taskDetailModal = document.querySelector("[data-task-detail-modal]");
    const taskDetailTitle = document.querySelector("[data-task-detail-title]");
    const taskDetailSubtitle = document.querySelector("[data-task-detail-subtitle]");
    const taskDetailBody = document.querySelector("[data-task-detail-body]");
    const taskDetailMessage = document.querySelector("[data-task-detail-message]");
    const taskStartButton = document.querySelector("[data-task-start-button]");
    const taskCompleteButton = document.querySelector("[data-task-complete-button]");
    const taskDetailClose = document.querySelector("[data-task-detail-close]");
    const reportGenerate = document.querySelector("[data-report-generate]");
    const cockpitSuggestForm = document.querySelector("[data-cockpit-suggest-form]");
    const cockpitDraft = document.querySelector("[data-cockpit-draft]");
    const cockpitDraftCancel = document.querySelector("[data-cockpit-draft-cancel]");
    const cockpitMessage = document.querySelector("[data-cockpit-message]");
    const globalLive = document.querySelector("[data-global-live-region]");
    const errorStats = document.querySelector("[data-dashboard-error-stats]");
    const inventoryStats = document.querySelector("[data-dashboard-inventory-stats]");
    const priorityList = document.querySelector("[data-dashboard-priority-list]");
    const briefingSummary = document.querySelector("[data-daily-briefing-summary]");
    const briefingList = document.querySelector("[data-daily-briefing-list]");
    const shiftCalendar = document.querySelector("[data-dashboard-shift-calendar]");
    const shiftCalendarMessage = document.querySelector("[data-dashboard-calendar-message]");
    const shiftCalendarEmployee = document.querySelector("[data-dashboard-calendar-employee]");
    if ((!taskBoard && !errorStats && !inventoryStats && !briefingList) || !token()) return;

    let activeTask = null;
    let activeTaskId = null;

    function announce(message, isError) {
      if (globalLive) globalLive.textContent = message;
      if (cockpitMessage) {
        cockpitMessage.textContent = message;
        cockpitMessage.classList.toggle("is-error", Boolean(isError));
        cockpitMessage.classList.toggle("is-success", Boolean(message && !isError));
      }
    }

    function todayIso() {
      return new Date().toISOString().slice(0, 10);
    }

    function isOverdue(task) {
      return task.due_date && task.due_date < todayIso() && task.status !== "done";
    }

    function updateDashboardTaskMetrics(tasks) {
      const openTasks = tasks.filter((task) => task.status === "open");
      const progressTasks = tasks.filter((task) => task.status === "in_progress");
      const doneTasks = tasks.filter((task) => task.status === "done");
      const criticalTasks = tasks.filter((task) => task.priority === "urgent" || isOverdue(task));
      taskCountElements.forEach((taskCount) => {
        taskCount.textContent = String(tasks.length);
      });
      setText("[data-dashboard-open-count]", openTasks.length);
      setText("[data-dashboard-progress-count]", progressTasks.length);
      setText("[data-dashboard-done-count]", doneTasks.length);
      setText("[data-dashboard-critical-count]", criticalTasks.length);
    }

    function formatDateTime(value) {
      if (!value) return "-";
      return new Date(value).toLocaleString("de-DE");
    }

    function formatUser(value) {
      if (!value) return "-";
      return value.username || value.email || "User #" + value.id;
    }

    function detailRow(label, value) {
      const item = document.createElement("div");
      item.className = "task-detail-row";
      const labelElement = document.createElement("span");
      labelElement.textContent = label;
      const valueElement = document.createElement("strong");
      valueElement.textContent = value || "-";
      item.append(labelElement, valueElement);
      return item;
    }

    function taskEditField(label, field) {
      const wrapper = document.createElement("label");
      wrapper.className = "field";
      const labelElement = document.createElement("span");
      labelElement.textContent = label;
      wrapper.append(labelElement, field);
      return wrapper;
    }

    function taskEditForm(task) {
      const editForm = document.createElement("form");
      editForm.className = "task-detail-row md:col-span-2";
      editForm.dataset.taskEditForm = "true";

      const title = document.createElement("input");
      title.className = "input input-bordered";
      title.name = "title";
      title.required = true;
      title.value = task.title || "";

      const department = document.createElement("input");
      department.className = "input input-bordered";
      department.name = "department";
      department.required = true;
      department.value = (task.department && task.department.name) || "";

      const priority = document.createElement("select");
      priority.className = "select select-bordered";
      priority.name = "priority";
      setSelectOptions(priority, TASK_PRIORITIES, task.priority || "normal");

      const status = document.createElement("select");
      status.className = "select select-bordered";
      status.name = "status";
      setSelectOptions(status, TASK_STATUSES, task.status || "open");

      const dueDate = document.createElement("input");
      dueDate.className = "input input-bordered";
      dueDate.name = "due_date";
      dueDate.type = "date";
      dueDate.value = task.due_date || "";

      const description = document.createElement("textarea");
      description.className = "textarea textarea-bordered";
      description.name = "description";
      description.value = task.description || "";

      const fields = document.createElement("div");
      fields.className = "form-grid";
      fields.append(
        taskEditField("Titel", title),
        taskEditField("Bereich", department),
        taskEditField("Prioritaet", priority),
        taskEditField("Status", status),
        taskEditField("Faellig am", dueDate),
        taskEditField("Beschreibung", description)
      );

      const actions = document.createElement("div");
      actions.className = "toolbar form-actions";
      const submit = document.createElement("button");
      submit.className = "btn btn-primary";
      submit.type = "submit";
      submit.textContent = "Aenderungen speichern";
      actions.appendChild(submit);

      editForm.append(fields, actions);
      editForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        try {
          submit.disabled = true;
          await api("/api/tasks/" + task.id, {
            method: "PUT",
            body: JSON.stringify(taskFormPayload(editForm))
          });
          const updatedTask = await api("/api/tasks/" + task.id);
          renderTaskDetail(updatedTask);
          await loadDashboardTasks();
          showTaskMessage("Task aktualisiert.");
        } catch (error) {
          showTaskMessage(error.message, true);
        } finally {
          submit.disabled = false;
        }
      });
      return editForm;
    }

    function showTaskMessage(message, isError) {
      if (!taskDetailMessage) return;
      taskDetailMessage.textContent = message;
      taskDetailMessage.classList.toggle("is-error", Boolean(isError));
      taskDetailMessage.classList.toggle("is-success", Boolean(message && !isError));
      if (globalLive && message) globalLive.textContent = message;
    }

    function reportPayload() {
      const payload = {};
      if (reportGenerate && reportGenerate.checked) {
        payload.generate_report = true;
        document.querySelectorAll("[data-report-field]").forEach((field) => {
          payload[field.dataset.reportField] = field.value;
        });
        payload.notes = payload.action || "";
      }
      return payload;
    }

    function updateTaskActionButtons(task, isBusy) {
      if (taskStartButton) {
        taskStartButton.hidden = !canWrite("tasks");
        taskStartButton.disabled = Boolean(isBusy) || task.status !== "open";
      }
      if (taskCompleteButton) {
        taskCompleteButton.hidden = !canWrite("tasks");
        taskCompleteButton.disabled = Boolean(isBusy) || task.status === "done" || task.status === "cancelled";
      }
    }

    function renderTaskDetail(task) {
      if (!taskDetailModal || !taskDetailBody) return;
      activeTask = task;
      activeTaskId = task.id;
      taskDetailTitle.textContent = task.title;
      taskDetailSubtitle.textContent = (task.department && task.department.name) || "-";
      taskDetailBody.innerHTML = "";
      taskDetailBody.append(
        detailRow("Titel", task.title),
        detailRow("Beschreibung", task.description || "Keine Beschreibung"),
        detailRow("Prioritaet", task.priority),
        detailRow("Status", task.status),
        detailRow("Bereich", task.department && task.department.name),
        detailRow("Ersteller", formatUser(task.creator)),
        detailRow("Erstellt am", formatDateTime(task.created_at)),
        detailRow("Aktuell bearbeitet von", formatUser(task.current_worker)),
        detailRow("Gestartet am", formatDateTime(task.started_at)),
        detailRow("Erledigt von", formatUser(task.completed_by_user)),
        detailRow("Erledigt am", formatDateTime(task.completed_at))
      );
      if (canWrite("tasks")) {
        taskDetailBody.appendChild(taskEditForm(task));
      }
      updateTaskActionButtons(task);
      showTaskMessage("");
    }

    async function openTaskDetail(taskId) {
      const task = await api("/api/tasks/" + taskId);
      renderTaskDetail(task);
      if (taskDetailModal) {
        taskDetailModal.hidden = false;
        const closeButton = taskDetailModal.querySelector("[data-task-detail-close]");
        if (closeButton) closeButton.focus();
      }
    }

    async function runTaskAction(taskId, action, body) {
      const path = "/api/tasks/" + taskId + "/" + action;
      const success = action === "start" ? "Task gestartet." : "Task abgeschlossen.";
      const options = { method: "POST" };
      if (body && Object.keys(body).length) {
        options.body = JSON.stringify(body);
      }
      try {
        const result = await api(path, options);
        const suffix = result && result.generated_document
          ? " Wartungsbericht wurde erzeugt."
          : "";
        announce(success + suffix);
        if (activeTaskId === taskId) {
          renderTaskDetail(await api("/api/tasks/" + taskId));
          showTaskMessage(success + suffix);
        }
        await loadDashboardTasks();
      } catch (error) {
        announce(error.message, true);
        showTaskMessage(error.message, true);
      }
    }

    function emptyCockpitCard(groupName) {
      const card = document.createElement("article");
      card.className = "cockpit-task-card is-empty";
      const text = document.createElement("p");
      text.textContent = groupName === "urgent"
        ? "Keine dringenden Tasks."
        : groupName === "today"
          ? "Keine Tasks fuer heute."
          : "Keine Tasks in Arbeit.";
      card.appendChild(text);
      if (cockpitSuggestForm && canWrite("tasks")) {
        const captureButton = actionButton("Stoerung erfassen", () => {
          cockpitSuggestForm.scrollIntoView({ behavior: "smooth", block: "start" });
          const input = cockpitSuggestForm.querySelector("textarea");
          if (input) input.focus();
        });
        captureButton.className = "btn btn-primary btn-sm";
        card.appendChild(captureButton);
      }
      return card;
    }

    function cockpitTaskCard(task) {
      const card = document.createElement("article");
      card.className = "cockpit-task-card";
      const title = document.createElement("h4");
      title.className = "cockpit-task-title";
      title.textContent = task.title;
      const priority = labeledBadge(task.priority, priorityBadgeClass(task.priority), priorityLabel);
      const status = labeledBadge(task.status, statusBadgeClass(task.status), statusLabel);
      const badges = document.createElement("div");
      badges.className = "flex flex-wrap gap-2";
      badges.append(priority, status);
      const meta = document.createElement("div");
      meta.className = "cockpit-task-meta";
      [
        task.department && task.department.name,
        task.due_date,
        task.current_worker ? formatUser(task.current_worker) : null
      ].filter(Boolean).forEach((value) => {
        const item = document.createElement("span");
        item.textContent = value;
        meta.appendChild(item);
      });
      const actions = document.createElement("div");
      actions.className = "cockpit-task-actions";
      actions.appendChild(actionButton("Details", () => openTaskDetail(task.id)));
      if (canWrite("tasks") && task.status === "open") {
        const start = actionButton("Starten", () => runTaskAction(task.id, "start"));
        start.className = "btn btn-primary btn-sm";
        actions.appendChild(start);
      }
      if (canWrite("tasks") && task.status !== "done" && task.status !== "cancelled") {
        const complete = actionButton("Erledigt", () => runTaskAction(task.id, "complete"));
        complete.className = "btn btn-success btn-sm text-white";
        actions.appendChild(complete);
      }
      card.append(title, badges, meta, actions);
      return card;
    }

    async function loadDashboardTasks() {
      const tasks = await api("/api/tasks");
      const lists = {
        urgent: document.querySelector("[data-cockpit-list='urgent']"),
        today: document.querySelector("[data-cockpit-list='today']"),
        progress: document.querySelector("[data-cockpit-list='progress']")
      };
      Object.values(lists).forEach((list) => {
        if (list) list.innerHTML = "";
      });
      updateDashboardTaskMetrics(tasks);
      const groups = { urgent: [], today: [], progress: [] };
      tasks.forEach((task) => {
        if (task.status === "in_progress") groups.progress.push(task);
        else if (task.priority === "urgent") groups.urgent.push(task);
        else if (task.due_date === todayIso()) groups.today.push(task);
      });
      Object.entries(groups).forEach(([name, group]) => {
        const list = lists[name];
        if (!list) return;
        if (!group.length) {
          list.appendChild(emptyCockpitCard(name));
          return;
        }
        group.forEach((task) => list.appendChild(cockpitTaskCard(task)));
      });
    }

    if (taskDetailClose && taskDetailModal) {
      taskDetailClose.addEventListener("click", () => {
        taskDetailModal.hidden = true;
      });
    }

    if (taskStartButton) {
      taskStartButton.addEventListener("click", () => {
        if (activeTaskId) runTaskAction(activeTaskId, "start");
      });
    }

    if (taskCompleteButton) {
      taskCompleteButton.addEventListener("click", () => {
        if (activeTaskId) runTaskAction(activeTaskId, "complete", reportPayload());
      });
    }

    if (cockpitSuggestForm && cockpitDraft) {
      cockpitSuggestForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const data = Object.fromEntries(new FormData(cockpitSuggestForm).entries());
        announce("KI erstellt Vorschlag...");
        try {
          const suggestion = await api("/api/tasks/suggest", {
            method: "POST",
            body: JSON.stringify(data)
          });
          cockpitDraft.hidden = false;
          cockpitDraft.elements.title.value = suggestion.title || "";
          cockpitDraft.elements.department.value = suggestion.department || "";
          cockpitDraft.elements.priority.value = suggestion.priority || "normal";
          cockpitDraft.elements.status.value = suggestion.status || "open";
          cockpitDraft.elements.description.value = [
            suggestion.description,
            suggestion.possible_cause ? "Moegliche Ursache: " + suggestion.possible_cause : "",
            suggestion.recommended_action ? "Naechste Aktion: " + suggestion.recommended_action : ""
          ].filter(Boolean).join("\n\n");
          announce("Vorschlag erstellt. Bitte pruefen und speichern.");
        } catch (error) {
          announce(error.message, true);
        }
      });

      cockpitDraft.addEventListener("submit", async (event) => {
        event.preventDefault();
        const data = Object.fromEntries(new FormData(cockpitDraft).entries());
        try {
          await api("/api/tasks", { method: "POST", body: JSON.stringify(data) });
          cockpitSuggestForm.reset();
          cockpitDraft.reset();
          cockpitDraft.hidden = true;
          announce("Task gespeichert.");
          await loadDashboardTasks();
        } catch (error) {
          announce(error.message, true);
        }
      });
    }

    if (cockpitDraftCancel && cockpitDraft) {
      cockpitDraftCancel.addEventListener("click", () => {
        cockpitDraft.reset();
        cockpitDraft.hidden = true;
        announce("Vorschlag verworfen.");
      });
    }

    function rowLikeStat(label, value) {
      const item = document.createElement("div");
      item.className = "stat-row";
      item.innerHTML = `<span>${label}</span><strong>${value}</strong>`;
      return item;
    }

    function priorityInsightCard(label, value, variant) {
      const item = document.createElement("article");
      item.className = "priority-insight" + (variant ? " " + variant : "");
      const title = document.createElement("span");
      title.textContent = label;
      const score = document.createElement("strong");
      score.textContent = value;
      item.append(title, score);
      return item;
    }

    async function loadDashboardPriorities() {
      if (!priorityList || !canView("tasks")) return;
      priorityList.innerHTML = "";
      let priorities = [];
      try {
        priorities = await api("/api/tasks/prioritize", {
          method: "POST",
          body: JSON.stringify({ status: "open", limit: 3 })
        });
      } catch (error) {
        priorityList.appendChild(priorityInsightCard("KI-Priorisierung", "Nicht verfuegbar", "is-muted"));
        return;
      }
      if (!priorities.length) {
        priorityList.appendChild(priorityInsightCard("KI-Priorisierung", "Keine offenen Tasks", "is-muted"));
        return;
      }
      priorities.forEach((item) => {
        priorityList.appendChild(priorityInsightCard(
          item.task.title,
          item.score + " / " + item.risk_level,
          item.risk_level === "critical" || item.risk_level === "high" ? "is-critical" : ""
        ));
      });
    }

    async function loadDailyBriefing() {
      if (!briefingList) return;
      let briefing = null;
      try {
        briefing = await api("/api/ai/daily-briefing");
      } catch (error) {
        if (briefingSummary) briefingSummary.textContent = "Briefing konnte nicht geladen werden.";
        briefingList.innerHTML = "";
        briefingList.appendChild(rowLikeStat("Status", "Nicht verfuegbar"));
        return;
      }
      if (briefingSummary) briefingSummary.textContent = briefing.summary;
      briefingList.innerHTML = "";
      const briefingCount = briefing.sections.reduce((sum, section) => sum + (section.count || 0), 0);
      setText("[data-dashboard-briefing-count]", briefingCount);
      if (!briefing.sections.length) {
        briefingList.appendChild(rowLikeStat("Status", "Keine Hinweise"));
        return;
      }
      briefing.sections.forEach((section) => {
        briefingList.appendChild(rowLikeStat(section.title, String(section.count)));
        section.items.slice(0, 2).forEach((item) => {
          briefingList.appendChild(rowLikeStat(item.title, item.severity));
        });
      });
    }

    async function setupDashboardCalendarFilter() {
      if (!shiftCalendarEmployee || !canView("employees")) return;
      try {
        const employees = await api("/api/employees");
        shiftCalendarEmployee.hidden = false;
        employees.forEach((employee) => {
          const option = document.createElement("option");
          option.value = String(employee.id);
          option.textContent = employee.name;
          shiftCalendarEmployee.appendChild(option);
        });
      } catch (error) {
        shiftCalendarEmployee.hidden = true;
      }
    }

    async function loadShiftCalendar() {
      if (!shiftCalendar) return;
      const params = new URLSearchParams();
      params.set("days", "14");
      if (shiftCalendarEmployee && shiftCalendarEmployee.value) {
        params.set("employee_id", shiftCalendarEmployee.value);
      }
      try {
        const calendar = await api("/api/shiftplans/calendar?" + params.toString());
        renderShiftCalendar(shiftCalendar, calendar);
        if (shiftCalendarMessage) {
          shiftCalendarMessage.textContent = calendar.employee
            ? "Kalender fuer " + calendar.employee.name
            : (calendar.message || "Schichtkalender");
          shiftCalendarMessage.classList.remove("is-error");
        }
      } catch (error) {
        renderShiftCalendar(shiftCalendar, { message: error.message, entries: [] });
        if (shiftCalendarMessage) {
          shiftCalendarMessage.textContent = error.message;
          shiftCalendarMessage.classList.add("is-error");
        }
      }
    }

    if (taskBoard && canView("tasks")) {
      await loadDashboardTasks();
      await loadDashboardPriorities();
    }

    await loadDailyBriefing();
    await setupDashboardCalendarFilter();
    await loadShiftCalendar();

    if (shiftCalendarEmployee) {
      shiftCalendarEmployee.addEventListener("change", loadShiftCalendar);
    }

    if (errorStats && canView("errors")) {
      const errors = await api("/api/errors");
      setText("[data-dashboard-machine-issue-count]", errors.length);
      const counts = new Map();
      errors.forEach((entry) => {
        const name = entry.department ? entry.department.name : "Ohne Bereich";
        counts.set(name, (counts.get(name) || 0) + 1);
      });
      errorStats.innerHTML = "";
      if (!counts.size) {
        errorStats.innerHTML = '<div class="empty-state">Noch keine Fehler erfasst.</div>';
      } else {
        counts.forEach((count, name) => {
          const item = document.createElement("div");
          item.className = "stat-row";
          item.innerHTML = `<span>${name}</span><strong>${count}</strong>`;
          errorStats.appendChild(item);
        });
      }
    }

    if (inventoryStats && canView("inventory")) {
      const summary = await api("/api/inventory/summary");
      inventoryStats.innerHTML = "";
      inventoryStats.append(
        rowLikeStat("Materialien", String(summary.material_count)),
        rowLikeStat("Gesamtanzahl", String(summary.total_quantity)),
        rowLikeStat("Gesamtwert", formatMoney(summary.total_value))
      );
    }

  }

  async function initDocuments() {
    const list = document.querySelector("[data-document-list]");
    const form = document.querySelector("[data-document-filter-form]");
    const reset = document.querySelector("[data-document-filter-reset]");
    const uploadCheckForm = document.querySelector("[data-document-upload-check-form]");
    const uploadCheckMessage = document.querySelector("[data-document-upload-check-message]");
    const reviewPanel = document.querySelector("[data-document-review-panel]");
    const reviewSummary = document.querySelector("[data-document-review-summary]");
    const reviewScore = document.querySelector("[data-document-review-score]");
    const reviewStatus = document.querySelector("[data-document-review-status]");
    const reviewSource = document.querySelector("[data-document-review-source]");
    const reviewStatusBadge = document.querySelector("[data-document-review-status-badge]");
    const reviewFindings = document.querySelector("[data-document-review-findings]");
    const reviewRecommendations = document.querySelector("[data-document-review-recommendations]");
    if (!list || !form || !token()) return;
    const reviewStateByDocument = new Map();

    function reviewStatusLabel(status) {
      if (status === "good") return "Gut";
      if (status === "needs_review") return "Pruefen";
      return "Unvollstaendig";
    }

    function reviewBadgeInfo(review) {
      if (!review) {
        return { label: "ungeprueft", className: "badge badge-review is-unchecked" };
      }
      const critical = (review.findings || []).some((finding) => finding.severity === "critical");
      if (critical || review.status === "incomplete") {
        return { label: "Warnungen gefunden", className: "badge badge-review is-critical" };
      }
      if ((review.findings || []).length || review.status === "needs_review") {
        return { label: "geprueft mit Hinweisen", className: "badge badge-review is-warning" };
      }
      return { label: "geprueft", className: "badge badge-review is-checked" };
    }

    function scoreBadgeInfo(review) {
      if (!review) {
        return { label: "ungeprueft", className: "badge badge-review is-unchecked" };
      }
      const critical = (review.findings || []).some((finding) => finding.severity === "critical");
      if (critical || review.status === "incomplete") {
        return { label: "Fehler", className: "badge badge-review is-critical" };
      }
      if ((review.findings || []).length || review.status === "needs_review") {
        return { label: "Warnungen", className: "badge badge-review is-warning" };
      }
      return { label: "bestanden", className: "badge badge-review is-checked" };
    }

    function documentTypeLabel(type) {
      if (type === "maintenance_report") return "Bericht";
      if (type === "uploaded_document") return "Upload";
      return type || "Dokument";
    }

    function allowedUploadExtension(filename) {
      return [".html", ".htm", ".txt"].some((extension) => (
        String(filename || "").toLowerCase().endsWith(extension)
      ));
    }

    function documentReviewSource(review, fallback) {
      if (fallback) return fallback;
      if (review && review.document && review.document.source === "upload") return "Upload";
      if (review && review.document && review.document.document_type) {
        return documentTypeLabel(review.document.document_type);
      }
      return "Dokument";
    }

    function fieldValue(fields, names) {
      const source = fields || {};
      for (const name of names) {
        const value = source[name];
        if (value && value !== "-") return value;
      }
      return "";
    }

    function fieldChecklistItem(title, value) {
      if (!value) {
        return reviewChecklistItem(title, "Keine Angabe erkannt.", "warning");
      }
      return reviewChecklistItem(title, value, "good");
    }

    function missingSummary(review) {
      const findings = review.findings || [];
      if (!findings.length) return "Keine fehlenden Pflichtangaben gefunden.";
      return findings
        .map((finding) => finding.field + ": " + finding.message)
        .join(" | ");
    }

    function reviewChecklistItem(title, message, severity) {
      const item = document.createElement("article");
      item.className = "review-check-item is-" + (severity || "good");
      const marker = document.createElement("span");
      marker.className = "review-check-marker";
      marker.textContent = severity === "critical" ? "!" : severity === "warning" ? "?" : "OK";
      const content = document.createElement("div");
      content.className = "review-check-content";
      const titleElement = document.createElement("strong");
      titleElement.textContent = title || "Allgemein";
      const messageElement = document.createElement("span");
      messageElement.textContent = message || "Keine Hinweise gefunden.";
      content.append(titleElement, messageElement);
      item.append(marker, content);
      return item;
    }

    function renderReviewChecklist(review) {
      const fields = review.extracted_fields || {};
      reviewFindings.innerHTML = "";
      reviewFindings.append(
        fieldChecklistItem("Erkannte Maschine", fieldValue(fields, ["Maschine", "Anlage"])),
        fieldChecklistItem(
          "Erkannter Fehler",
          fieldValue(fields, ["Fehler", "Fehlercode", "Task-Titel", "Beschreibung"]),
        ),
        fieldChecklistItem("Moegliche Ursache", fieldValue(fields, ["Ursache", "Moegliche Ursache", "Moegliche Ursachen"])),
        fieldChecklistItem(
          "Vorgeschlagene Massnahme",
          fieldValue(fields, ["Durchgefuehrte Massnahme", "Massnahme", "Massnahmen", "Loesung", "Solution"]),
        ),
        reviewChecklistItem(
          "Fehlende Angaben",
          missingSummary(review),
          (review.findings || []).length ? "critical" : "good",
        ),
      );
    }

    function renderDocumentReview(review, sourceLabel) {
      if (!reviewPanel || !reviewFindings) return;
      reviewPanel.hidden = false;
      if (reviewSummary) {
        const documentTitle = review.document && review.document.title
          ? review.document.title
          : "ausgewaehltes Dokument";
        reviewSummary.textContent = "Pruefung fuer " + documentTitle;
      }
      if (reviewScore) reviewScore.textContent = String(review.quality_score);
      if (reviewStatus) reviewStatus.textContent = reviewStatusLabel(review.status);
      if (reviewSource) reviewSource.textContent = documentReviewSource(review, sourceLabel);
      if (reviewStatusBadge) {
        const info = scoreBadgeInfo(review);
        reviewStatusBadge.className = info.className;
        reviewStatusBadge.textContent = info.label;
      }
      renderReviewChecklist(review);
      if (reviewRecommendations) {
        const recommendations = review.recommendations || [];
        reviewRecommendations.textContent = recommendations.length
          ? "Empfehlungen: " + recommendations.join(" | ")
          : "Keine Empfehlungen erforderlich.";
      }
      reviewPanel.scrollIntoView({ behavior: "smooth", block: "start" });
    }

    async function reviewDocument(documentItem) {
      try {
        const review = await api("/api/documents/" + documentItem.id + "/review", {
          method: "POST"
        });
        reviewStateByDocument.set(documentItem.id, review);
        renderDocumentReview(review, "Gespeicherter Bericht");
        await load();
      } catch (error) {
        setStatusMessage(uploadCheckMessage, error.message || "Dokumentpruefung fehlgeschlagen.", true);
      }
    }

    async function checkUploadedDocument(file) {
      const formData = new FormData();
      formData.append("file", file);
      const response = await fetch("/api/documents/check", {
        method: "POST",
        headers: { "Authorization": "Bearer " + token() },
        body: formData
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error((payload && (payload.message || payload.error)) || "Dokument konnte nicht geprueft werden.");
      }
      return payload && payload.success === true && Object.prototype.hasOwnProperty.call(payload, "data")
        ? payload.data
        : payload;
    }

    async function downloadDocument(documentItem) {
      const response = await fetch(documentItem.download_url, {
        headers: { "Authorization": "Bearer " + token() }
      });
      if (!response.ok) throw new Error("Download fehlgeschlagen");
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "maintenance_report_task_" + documentItem.task_id + ".html";
      link.click();
      window.URL.revokeObjectURL(url);
    }

    function renderDocumentCard(documentItem) {
      const review = reviewStateByDocument.get(documentItem.id);
      const { card, badges } = resourceCard(documentItem.title, "Task " + documentItem.task_id);
      const reviewInfo = reviewBadgeInfo(review);
      badges.appendChild(badge(reviewInfo.label, reviewInfo.className));
      badges.appendChild(badge(documentTypeLabel(documentItem.document_type), "badge badge-status is-open"));

      const meta = document.createElement("div");
      meta.className = "resource-meta-grid";
      meta.append(
        metaTile("Bereich", documentItem.department || "Nicht angegeben"),
        metaTile("Maschine", documentItem.machine || "Nicht angegeben"),
        metaTile("Erstellt", new Date(documentItem.created_at).toLocaleString("de-DE")),
        metaTile("Pruefscore", review ? String(review.quality_score) : "Noch offen")
      );

      const note = document.createElement("p");
      note.className = "resource-note";
      if (!review) {
        note.textContent = "Dieses Dokument wurde in dieser Sitzung noch nicht geprueft.";
      } else if (review.findings && review.findings.length) {
        note.textContent = review.findings.length + " Hinweis" + (review.findings.length === 1 ? "" : "e") + " gefunden.";
      } else {
        note.textContent = "Die letzte Pruefung hat keine Findings gefunden.";
      }

      const actions = document.createElement("div");
      actions.className = "resource-actions";
      actions.appendChild(actionButton("Pruefen", async () => {
        await reviewDocument(documentItem);
      }));
      actions.appendChild(actionButton("Download", async () => {
        await downloadDocument(documentItem);
      }));
      card.append(meta, note, actions);
      return card;
    }

    async function load() {
      const params = new URLSearchParams();
      new FormData(form).forEach((value, key) => {
        if (value) params.set(key, value);
      });
      const suffix = params.toString() ? "?" + params.toString() : "";
      const documents = await api("/api/documents" + suffix);
      list.innerHTML = "";
      setCountBadge("[data-document-count]", documents.length, "Dokument", "Dokumente");
      if (!documents.length) {
        list.innerHTML = '<div class="empty-state">Keine Dokumente gefunden.</div>';
        return;
      }
      documents.forEach((documentItem) => {
        list.appendChild(renderDocumentCard(documentItem));
      });
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      await load();
    });

    if (reset) {
      reset.addEventListener("click", async () => {
        form.reset();
        await load();
      });
    }

    if (uploadCheckForm) {
      uploadCheckForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const fileInput = uploadCheckForm.querySelector("input[type='file']");
        const file = fileInput && fileInput.files ? fileInput.files[0] : null;
        if (!file) {
          setStatusMessage(uploadCheckMessage, "Bitte zuerst eine Datei auswaehlen.", true);
          return;
        }
        if (!allowedUploadExtension(file.name)) {
          setStatusMessage(uploadCheckMessage, "Dateityp nicht unterstuetzt. Bitte HTML, HTM oder TXT verwenden.", true);
          return;
        }
        setStatusMessage(uploadCheckMessage, "Dokument wird geprueft...");
        try {
          const review = await checkUploadedDocument(file);
          renderDocumentReview(review, "Upload");
          setStatusMessage(uploadCheckMessage, "Dokumentpruefung abgeschlossen.");
        } catch (error) {
          setStatusMessage(
            uploadCheckMessage,
            error.message || "Serverfehler bei der Dokumentpruefung.",
            true,
          );
        }
      });
    }

    await load();
  }

  function initMobileCollapsibleSections() {
    const sections = Array.from(document.querySelectorAll("[data-mobile-collapsible]"));
    if (!sections.length || !window.matchMedia) return;

    const mobileQuery = window.matchMedia("(max-width: 639px)");
    let syncing = false;

    function syncSections() {
      syncing = true;
      sections.forEach((section) => {
        if (mobileQuery.matches) {
          if (!section.dataset.mobileTouched) section.open = false;
          return;
        }
        section.open = true;
      });
      syncing = false;
    }

    sections.forEach((section) => {
      section.addEventListener("toggle", () => {
        if (syncing) return;
        if (mobileQuery.matches) section.dataset.mobileTouched = "true";
      });
    });

    syncSections();
    if (mobileQuery.addEventListener) {
      mobileQuery.addEventListener("change", syncSections);
    } else if (mobileQuery.addListener) {
      mobileQuery.addListener(syncSections);
    }
  }

  document.addEventListener("DOMContentLoaded", async () => {
    initMobileCollapsibleSections();
    if (!token()) return;
    try {
      if (window.maintenanceAuth && window.maintenanceAuth.refreshUser) {
        await window.maintenanceAuth.ensureReady();
      }
      await initDepartments();
      await initDailyCockpit();
      await initTasks();
      await initErrors();
      await initUsers();
      await initEmployees();
      await initMachines();
      await initInventory();
      await initShiftPlans();
      await initDocuments();
    } catch (error) {
      console.warn(error);
    }
  });
})();

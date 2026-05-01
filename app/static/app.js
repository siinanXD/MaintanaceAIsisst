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
    if (!response.ok) throw new Error((data && (data.message || data.error)) || "API error");
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
    if (priority === "urgent") return "badge badge-error text-white";
    if (priority === "soon") return "badge badge-warning text-slate-900";
    return "badge badge-success text-white";
  }

  function statusBadgeClass(status) {
    if (status === "in_progress") return "badge badge-primary text-white";
    if (status === "done") return "badge badge-success text-white";
    if (status === "cancelled") return "badge badge-error text-white";
    return "badge badge-info text-white";
  }

  function badge(text, className) {
    const element = document.createElement("span");
    element.className = className;
    element.textContent = text || "-";
    return element;
  }

  function actionButton(label, onClick, danger) {
    const button = document.createElement("button");
    button.className = danger ? "btn btn-error btn-sm text-white" : "btn btn-outline btn-sm";
    button.type = "button";
    button.textContent = label;
    button.addEventListener("click", onClick);
    return button;
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
    const priorityRefresh = document.querySelector("[data-task-priority-refresh]");
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
        await api(endpoint, { method: "POST" });
        if (list) {
          if (list.querySelector(".empty-state")) list.innerHTML = "";
          list.prepend(renderPlan(plan));
        }
        await loadPriorities();
        if (message) {
          message.textContent = action === "start" ? "Task gestartet." : "Task abgeschlossen.";
        }
      } catch (error) {
        if (message) {
          message.textContent = error.message;
        }
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
        badge(task.priority, priorityBadgeClass(task.priority)),
        badge(task.status, statusBadgeClass(task.status))
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
        const start = actionButton("Start Task", () => runTaskAction(task, "start"));
        start.className = "btn btn-primary btn-sm";
        actions.appendChild(start);
      }
      if (canWrite("tasks") && task.status !== "done" && task.status !== "cancelled") {
        const complete = actionButton("Complete Task", () => runTaskAction(task, "complete"));
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
        await api(path, { method, body: JSON.stringify(data) });
        resetTaskForm();
        await initDepartments();
        await load();
        await loadPriorities();
        if (message) message.textContent = wasEditing ? "Task aktualisiert." : "Task gespeichert.";
      } catch (error) {
        if (message) message.textContent = error.message;
      }
    });

    if (cancelEditButton) {
      cancelEditButton.addEventListener("click", () => {
        resetTaskForm();
        const message = document.querySelector("[data-task-message]");
        if (message) message.textContent = "Bearbeitung abgebrochen.";
      });
    }

    if (suggestForm && suggestionBox) {
      suggestForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const message = document.querySelector("[data-task-suggest-message]");
        const data = Object.fromEntries(new FormData(suggestForm).entries());
        if (message) message.textContent = "KI erstellt Vorschlag...";
        try {
          currentSuggestion = await api("/api/tasks/suggest", {
            method: "POST",
            body: JSON.stringify(data)
          });
          suggestionBox.hidden = false;
          suggestionBox.querySelectorAll("[data-suggest-field]").forEach((field) => {
            field.value = currentSuggestion[field.dataset.suggestField] || "";
          });
          if (message) message.textContent = "Vorschlag erstellt.";
        } catch (error) {
          if (message) message.textContent = error.message;
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

    if (priorityRefresh) {
      priorityRefresh.addEventListener("click", async () => {
        await loadPriorities();
      });
    }

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
    if (!list || !form || !token()) return;
    let currentAnalysis = null;

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
          match.entry.error_code,
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

    async function load() {
      const errors = await api("/api/errors");
      list.innerHTML = "";
      errors.forEach((entry) => {
        list.appendChild(row([
          entry.error_code,
          entry.machine,
          entry.title,
          entry.department && entry.department.name,
          entry.solution
        ]));
      });
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const data = Object.fromEntries(new FormData(form).entries());
      data.description = data.title;
      await loadSimilarErrors(data);
      await api("/api/errors", { method: "POST", body: JSON.stringify(data) });
      form.reset();
      await initDepartments();
      await load();
      const message = document.querySelector("[data-error-message]");
      if (message) message.textContent = "Fehler gespeichert.";
    });

    if (analyzeForm && analysisBox) {
      analyzeForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const message = document.querySelector("[data-error-analyze-message]");
        const data = Object.fromEntries(new FormData(analyzeForm).entries());
        if (message) message.textContent = "KI analysiert...";
        try {
          currentAnalysis = await api("/api/errors/analyze", {
            method: "POST",
            body: JSON.stringify(data)
          });
          analysisBox.hidden = false;
          analysisBox.querySelectorAll("[data-error-analysis-field]").forEach((field) => {
            field.value = currentAnalysis[field.dataset.errorAnalysisField] || "";
          });
          if (message) message.textContent = "Analyse erstellt.";
          await loadSimilarErrors({
            description: data.description,
            machine: currentAnalysis.machine
          });
        } catch (error) {
          if (message) message.textContent = error.message;
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
      employees.forEach((employee) => {
        const docs = document.createElement("div");
        docs.className = "document-cell";

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
        if (!(employee.documents || []).length) {
          const empty = document.createElement("span");
          empty.className = "panel-meta";
          empty.textContent = "Keine Dokumente";
          links.appendChild(empty);
        }

        if (canWrite("employees") && employeeAccessLevel() === "confidential") {
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
          docs.append(links, input);
        } else {
          docs.append(links);
        }

        list.appendChild(row([
          employee.personnel_number,
          employee.name,
          employee.department,
          employee.current_shift || employee.shift_model,
          employee.team ? "Team " + employee.team : "-",
          employee.salary_group || "-",
          employee.qualifications || "-",
          employee.favorite_machine || "-",
          docs
        ]));
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
      const history = await api("/api/machines/" + machine.id + "/history");
      renderMachineHistory(history);
    }

    if (assistantForm) {
      assistantForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (!activeHistoryMachine) return;
        const data = Object.fromEntries(new FormData(assistantForm).entries());
        if (assistantAnswer) assistantAnswer.textContent = "Maschinen-Assistent denkt...";
        try {
          const result = await api("/api/machines/" + activeHistoryMachine.id + "/assistant", {
            method: "POST",
            body: JSON.stringify(data)
          });
          if (assistantAnswer) assistantAnswer.textContent = result.answer;
        } catch (error) {
          if (assistantAnswer) assistantAnswer.textContent = error.message;
        }
      });
    }

    async function load() {
      const machines = await api("/api/machines");
      list.innerHTML = "";
      machines.forEach((machine) => {
        const actions = document.createElement("div");
        actions.className = "table-actions";
        actions.appendChild(actionButton("Historie", () => loadMachineHistory(machine)));
        if (canWrite("machines")) {
          actions.appendChild(actionButton("Loeschen", async () => {
            if (!window.confirm(machine.name + " wirklich loeschen?")) return;
            await api("/api/machines/" + machine.id, { method: "DELETE" });
            await load();
          }, true));
        }
        list.appendChild(row([
          machine.name,
          machine.produced_item,
          String(machine.required_employees),
          actions
        ]));
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
      const priority = badge(task.priority, priorityBadgeClass(task.priority));
      const status = badge(task.status, statusBadgeClass(task.status));
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
      taskCountElements.forEach((taskCount) => {
        taskCount.textContent = String(tasks.length);
      });
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
        priorityList.appendChild(rowLikeStat("KI-Priorisierung", "Nicht verfuegbar"));
        return;
      }
      if (!priorities.length) {
        priorityList.appendChild(rowLikeStat("KI-Priorisierung", "Keine offenen Tasks"));
        return;
      }
      priorities.forEach((item) => {
        priorityList.appendChild(rowLikeStat(
          item.task.title,
          item.score + " / " + item.risk_level
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
    const reviewPanel = document.querySelector("[data-document-review-panel]");
    const reviewSummary = document.querySelector("[data-document-review-summary]");
    const reviewScore = document.querySelector("[data-document-review-score]");
    const reviewStatus = document.querySelector("[data-document-review-status]");
    const reviewFindings = document.querySelector("[data-document-review-findings]");
    const reviewRecommendations = document.querySelector("[data-document-review-recommendations]");
    if (!list || !form || !token()) return;

    function reviewStatusLabel(status) {
      if (status === "good") return "Gut";
      if (status === "needs_review") return "Pruefen";
      return "Unvollstaendig";
    }

    function renderDocumentReview(review) {
      if (!reviewPanel || !reviewFindings) return;
      reviewPanel.hidden = false;
      if (reviewSummary) {
        reviewSummary.textContent = "Pruefung fuer " + review.document.title;
      }
      if (reviewScore) reviewScore.textContent = String(review.quality_score);
      if (reviewStatus) reviewStatus.textContent = reviewStatusLabel(review.status);
      reviewFindings.innerHTML = "";
      if (!review.findings.length) {
        reviewFindings.innerHTML = '<tr><td colspan="3">Keine Findings gefunden.</td></tr>';
      } else {
        review.findings.forEach((finding) => {
          reviewFindings.appendChild(row([
            finding.field,
            finding.severity,
            finding.message
          ]));
        });
      }
      if (reviewRecommendations) {
        reviewRecommendations.textContent = review.recommendations.length
          ? "Empfehlungen: " + review.recommendations.join(" | ")
          : "Keine Empfehlungen erforderlich.";
      }
      reviewPanel.scrollIntoView({ behavior: "smooth", block: "start" });
    }

    async function reviewDocument(documentItem) {
      const review = await api("/api/documents/" + documentItem.id + "/review", {
        method: "POST"
      });
      renderDocumentReview(review);
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

    async function load() {
      const params = new URLSearchParams();
      new FormData(form).forEach((value, key) => {
        if (value) params.set(key, value);
      });
      const suffix = params.toString() ? "?" + params.toString() : "";
      const documents = await api("/api/documents" + suffix);
      list.innerHTML = "";
      if (!documents.length) {
        list.innerHTML = '<tr><td colspan="6">Keine Dokumente gefunden.</td></tr>';
        return;
      }
      documents.forEach((documentItem) => {
        const actions = document.createElement("div");
        actions.className = "table-actions";
        actions.appendChild(actionButton("Pruefen", async () => {
          await reviewDocument(documentItem);
        }));
        actions.appendChild(actionButton("Download", async () => {
          await downloadDocument(documentItem);
        }));
        list.appendChild(row([
          documentItem.title,
          String(documentItem.task_id),
          documentItem.department,
          documentItem.machine,
          new Date(documentItem.created_at).toLocaleString("de-DE"),
          actions
        ]));
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

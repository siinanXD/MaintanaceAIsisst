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

async function initDepartments() {
  const selects = document.querySelectorAll("select[name='department']");
  if (!selects.length || !token()) return;
  try {
    const departments = await api("/api/v1/departments");
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

async function initAufgaben() {
  const list = document.querySelector("[data-task-list]");
  const kanbanBoard = document.querySelector("[data-task-kanban-board]");
  const form = document.querySelector("[data-task-form]");
  const priorityList = document.querySelector("[data-task-priority-list]");
  const priorityRefreshButtons = document.querySelectorAll("[data-task-priority-refresh]");
  const suggestForm = document.querySelector("[data-task-suggest-form]");
  const suggestionBox = document.querySelector("[data-task-suggestion]");
  const applySuggestion = document.querySelector("[data-apply-task-suggestion]");
  const submitButton = document.querySelector("[data-task-submit-button]");
  const cancelEditButton = document.querySelector("[data-task-edit-cancel]");
  const taskFilterSearch = document.querySelector("[data-task-filter-search]");
  const taskFilterStatus = document.querySelector("[data-task-filter-status]");
  const taskFilterPriority = document.querySelector("[data-task-filter-priority]");
  const taskFilterDepartment = document.querySelector("[data-task-filter-department]");
  const taskFilterDue = document.querySelector("[data-task-filter-due]");
  const taskFilterReset = document.querySelector("[data-task-filter-reset]");
  const taskFilterSummary = document.querySelector("[data-task-filter-summary]");
  const taskCountElements = document.querySelectorAll("[data-dashboard-task-count]");
  if ((!list && !kanbanBoard) || !form || !token()) return;
  let currentSuggestion = null;
  let editingTaskId = null;
  let allTasks = [];
  const taskFilters = [
    taskFilterSearch,
    taskFilterStatus,
    taskFilterPriority,
    taskFilterDepartment,
    taskFilterDue
  ].filter(Boolean);

  function riskBadgeClass(riskLevel) {
    if (riskLevel === "critical") return "badge badge-error text-white";
    if (riskLevel === "high") return "badge badge-warning text-slate-900";
    if (riskLevel === "medium") return "badge badge-info text-white";
    return "badge badge-success text-white";
  }

  function taskTodayIso() {
    const now = new Date();
    const month = String(now.getMonth() + 1).padStart(2, "0");
    const day = String(now.getDate()).padStart(2, "0");
    return now.getFullYear() + "-" + month + "-" + day;
  }

  function taskDueState(task) {
    if (task.status === "done" || task.status === "cancelled") return "closed";
    if (!task.due_date) return "planned";
    const today = taskTodayIso();
    if (task.due_date < today) return "overdue";
    if (task.due_date === today) return "today";
    return "planned";
  }

  function taskDueLabel(task) {
    const state = taskDueState(task);
    if (state === "overdue") return "Überfällig seit " + formatDate(task.due_date);
    if (state === "today") return "Heute fällig";
    if (state === "closed" && task.completed_at) return "Erledigt " + formatDateTimeValue(task.completed_at);
    return task.due_date ? "Fällig " + formatDate(task.due_date) : "Keine Fälligkeit";
  }

  function taskMachineHint(task) {
    const explicit = task.machine_name || (task.machine && task.machine.name) || task.machine;
    if (typeof explicit === "string" && explicit.trim()) return explicit.trim();
    const text = [task.title, task.description].filter(Boolean).join(" ");
    const match = text.match(/\b(Maschine|Anlage|Presse|Linie|Roboter|CNC|Band)\s*[A-Za-z0-9\-_.]*/i);
    return match ? match[0] : "Maschine offen";
  }

  function taskTypeLabel(task) {
    const text = keywordText([task.title, task.description].filter(Boolean).join(" "));
    if (text.includes("sicherheit") || text.includes("not-aus") || text.includes("schutz")) return "Sicherheit";
    if (text.includes("repar") || text.includes("defekt") || text.includes("storung")) return "Reparatur";
    if (text.includes("pruf") || text.includes("kontroll") || text.includes("check")) return "Prüfung";
    if (text.includes("reinig") || text.includes("sauber")) return "Reinigung";
    if (text.includes("produktion") || text.includes("auftrag") || text.includes("linie")) return "Produktion";
    if (text.includes("wart") || text.includes("service") || text.includes("inspektion")) return "Wartung";
    return "Aufgabe";
  }

  function taskOwnerLabel(task) {
    const worker = task.current_worker || task.completed_by_user || task.creator;
    if (!worker) return "nicht zugewiesen";
    return worker.name || worker.username || worker.email || ("User #" + worker.id);
  }

  function formatDateTimeValue(value) {
    if (!value) return "-";
    return new Date(value).toLocaleString("de-DE", {
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit"
    });
  }

  function taskMetricLabel(task) {
    if (task.actual_minutes) return "Ist " + task.actual_minutes + " min";
    if (task.planned_minutes) return "Plan " + task.planned_minutes + " min";
    if (task.response_minutes) return "Reaktion " + Math.round(task.response_minutes) + " min";
    return "Zeit offen";
  }

  function taskSearchText(task) {
    return [
      task.title,
      task.description,
      task.priority,
      priorityLabel(task.priority),
      task.status,
      statusLabel(task.status),
      task.department && task.department.name,
      taskMachineHint(task),
      taskTypeLabel(task),
      taskOwnerLabel(task),
      task.due_date
    ].filter(Boolean).join(" ").toLowerCase();
  }

  function updateTaskStats(tasks) {
    const open = tasks.filter((task) => task.status === "open").length;
    const progress = tasks.filter((task) => task.status === "in_progress").length;
    const done = tasks.filter((task) => task.status === "done").length;
    const overdue = tasks.filter((task) => taskDueState(task) === "overdue").length;
    taskCountElements.forEach((taskCount) => {
      taskCount.textContent = String(tasks.length);
    });
    setText("[data-task-open-count]", open);
    setText("[data-task-progress-count]", progress);
    setText("[data-task-done-count]", done);
    setText("[data-task-overdue-count]", overdue);
  }

  function populateTaskDepartmentFilter(tasks) {
    if (!taskFilterDepartment) return;
    const previous = taskFilterDepartment.value;
    const departments = Array.from(new Set(
      tasks
        .map((task) => task.department && task.department.name)
        .filter(Boolean)
    )).sort((first, second) => first.localeCompare(second, "de-DE"));
    taskFilterDepartment.innerHTML = '<option value="">Alle Bereiche</option>';
    departments.forEach((department) => {
      const option = document.createElement("option");
      option.value = department;
      option.textContent = department;
      taskFilterDepartment.appendChild(option);
    });
    taskFilterDepartment.value = departments.includes(previous) ? previous : "";
  }

  function taskMatchesFilters(task) {
    const search = taskFilterSearch ? taskFilterSearch.value.trim().toLowerCase() : "";
    const status = taskFilterStatus ? taskFilterStatus.value : "";
    const priority = taskFilterPriority ? taskFilterPriority.value : "";
    const department = taskFilterDepartment ? taskFilterDepartment.value : "";
    const dueState = taskFilterDue ? taskFilterDue.value : "";
    if (search && !taskSearchText(task).includes(search)) return false;
    if (status && task.status !== status) return false;
    if (priority && task.priority !== priority) return false;
    if (department && (!task.department || task.department.name !== department)) return false;
    if (dueState && taskDueState(task) !== dueState) return false;
    return true;
  }

  function taskSortScore(task) {
    const priorityRank = { urgent: 0, soon: 1, normal: 2 };
    const statusRank = { in_progress: 0, open: 1, done: 2, cancelled: 3 };
    const dueRank = { overdue: 0, today: 1, planned: 2, closed: 3 };
    return [
      dueRank[taskDueState(task)] == null ? 4 : dueRank[taskDueState(task)],
      priorityRank[task.priority] == null ? 3 : priorityRank[task.priority],
      statusRank[task.status] == null ? 4 : statusRank[task.status],
      task.due_date || "9999-12-31"
    ].join("|");
  }

  function filteredTasks() {
    return allTasks
      .filter(taskMatchesFilters)
      .sort((first, second) => taskSortScore(first).localeCompare(taskSortScore(second)));
  }

  function renderFilteredTasks() {
    const tasks = filteredTasks();
    if (list) {
      list.innerHTML = "";
      tasks.forEach((task) => list.appendChild(taskCard(task)));
    }
    renderKanban(tasks);
    if (taskFilterSummary) {
      taskFilterSummary.textContent = tasks.length + " von " + allTasks.length + " Aufgaben sichtbar";
    }
  }

  function renderPriorityHint(title, text) {
    if (!priorityList) return;
    priorityList.innerHTML = '<div class="guided-empty-state"><strong>'
      + title
      + '</strong><p>'
      + text
      + '</p></div>';
  }

  function markPrioritiesStale() {
    renderPriorityHint(
      "Prioritätslage nicht neu berechnet",
      "Die Aufgaben wurden geändert. Aktualisiere die Prioritätslage bei Bedarf manuell."
    );
  }

  async function loadPriorities() {
    if (!priorityList) return;
    renderPriorityHint(
      "Priorisierung läuft",
      "Die wichtigsten offenen Aufgaben werden neu bewertet."
    );
    let priorities = [];
    try {
      priorities = listData(await api("/api/v1/tasks/prioritize", {
        method: "POST",
        body: JSON.stringify({ status: "open", limit: 10 })
      }));
    } catch (error) {
      priorityList.innerHTML = '<div class="guided-empty-state"><strong>Priorisierung konnte nicht geladen werden.</strong><p>Die Aufgabeliste bleibt nutzbar. Prüfe später erneut oder sortiere nach Fälligkeit und Risiko.</p></div>';
      return;
    }
    if (!priorities.length) {
      priorityList.innerHTML = '<div class="guided-empty-state"><strong>Keine offenen Aufgaben</strong><p>Wenn Arbeit entsteht, lege einen Aufgabe an oder nutze den AI-Vorschlag aus einer kurzen Beschreibung.</p><a class="btn btn-primary btn-sm" href="#task-list">Aufgabeliste prüfen</a></div>';
      return;
    }
    priorityList.innerHTML = "";
    priorities.forEach((item) => {
      const scoreClass = (item.risk_level === "critical" || item.risk_level === "high")
        ? "priority-score-num is-high"
        : item.risk_level === "medium"
          ? "priority-score-num is-medium"
          : "priority-score-num is-low";

      const card = document.createElement("div");
      card.className = "priority-score-card";

      const scoreEl = document.createElement("div");
      scoreEl.className = scoreClass;
      scoreEl.textContent = String(item.score);

      const body = document.createElement("div");
      body.className = "priority-score-body";

      const top = document.createElement("div");
      top.className = "priority-score-top";
      top.appendChild(badge(item.risk_level, riskBadgeClass(item.risk_level)));
      const titleEl = document.createElement("span");
      titleEl.className = "priority-score-title";
      titleEl.textContent = item.task.title;
      top.appendChild(titleEl);

      const reasonEl = document.createElement("p");
      reasonEl.className = "priority-score-reason";
      reasonEl.textContent = item.reason;

      const actionEl = document.createElement("p");
      actionEl.className = "priority-score-action";
      actionEl.textContent = item.recommended_action;

      body.append(top, reasonEl, actionEl);
      card.append(scoreEl, body);
      priorityList.appendChild(card);
    });
  }

  function resetAufgabeForm() {
    editingTaskId = null;
    form.reset();
    if (form.elements.status) form.elements.status.value = "open";
    if (form.elements.priority) form.elements.priority.value = "normal";
    if (submitButton) submitButton.textContent = "Aufgabe speichern";
    if (cancelEditButton) cancelEditButton.hidden = true;
  }

  function applyTaskPreview(preview) {
    const payload = (preview && preview.payload) || {};
    if (!payload.title) return;
    resetAufgabeForm();
    form.elements.title.value = payload.title || "";
    form.elements.department.value = payload.department || form.elements.department.value;
    form.elements.priority.value = payload.priority || "normal";
    if (form.elements.status) form.elements.status.value = payload.status || "open";
    if (form.elements.due_date && !form.elements.due_date.value) {
      form.elements.due_date.value = new Date().toISOString().slice(0, 10);
    }
    form.elements.description.value = [
      payload.description,
      payload.possible_cause ? "Mögliche Ursache: " + payload.possible_cause : "",
      payload.recommended_action ? "Nächste Aktion: " + payload.recommended_action : ""
    ].filter(Boolean).join("\n\n");
    revealSurface(form);
    form.elements.title.focus();
  }

  async function editAufgabe(task) {
    editingTaskId = task.id;
    form.elements.title.value = task.title || "";
    form.elements.department.value = (task.department && task.department.name) || "";
    form.elements.priority.value = task.priority || "normal";
    if (form.elements.status) form.elements.status.value = task.status || "open";
    form.elements.due_date.value = task.due_date || "";
    form.elements.description.value = task.description || "";
    if (submitButton) submitButton.textContent = "Aufgabe aktualisieren";
    if (cancelEditButton) cancelEditButton.hidden = false;
    revealSurface(form);
    form.elements.title.focus();
  }

  async function runTaskAction(task, action, button) {
    const endpoint = "/api/v1/tasks/" + task.id + "/" + action;
    const message = document.querySelector("[data-task-message]");
    if (button) button.disabled = true;
    try {
      setStatusMessage(message, action === "start" ? "Aufgabe wird gestartet..." : "Aufgabe wird abgeschlossen...");
      await api(endpoint, { method: "POST" });
      await load();
      markPrioritiesStale();
      setStatusMessage(message, action === "start" ? "Aufgabe gestartet." : "Aufgabe abgeschlossen.");
    } catch (error) {
      setStatusMessage(message, error.message, true);
      if (button) button.disabled = false;
    }
  }

  function taskCard(task) {
    const card = document.createElement("article");
    const dueState = taskDueState(task);
    card.className = [
      "task-card",
      "is-" + (task.status || "open"),
      "is-priority-" + (task.priority || "normal"),
      dueState === "overdue" ? "is-overdue" : "",
      dueState === "today" ? "is-due-today" : ""
    ].filter(Boolean).join(" ");
    card.dataset.searchText = taskSearchText(task);
    card.dataset.status = task.status || "";
    card.dataset.priority = task.priority || "";
    card.dataset.department = (task.department && task.department.name) || "";
    card.dataset.dueState = dueState;

    const top = document.createElement("div");
    top.className = "task-card-top";

    const heading = document.createElement("div");
    heading.className = "task-card-heading";
    const type = document.createElement("span");
    type.className = "task-type-badge";
    type.textContent = taskTypeLabel(task);
    const title = document.createElement("h3");
    title.className = "task-card-title";
    title.textContent = task.title;
    heading.append(type, title);

    const badges = document.createElement("div");
    badges.className = "task-card-badges";
    badges.append(
      labeledBadge(task.priority, priorityBadgeClass(task.priority) + " priority-badge", priorityLabel),
      labeledBadge(task.status, statusBadgeClass(task.status) + " status-badge", statusLabel)
    );

    top.append(heading, badges);

    const description = document.createElement("p");
    description.className = "task-card-description";
    description.textContent = task.description || "Keine Beschreibung";

    const meta = document.createElement("div");
    meta.className = "task-card-meta";
    [
      "Bereich: " + ((task.department && task.department.name) || "offen"),
      "Maschine: " + taskMachineHint(task),
      taskDueLabel(task),
      "Verantwortlich: " + taskOwnerLabel(task),
      taskMetricLabel(task)
    ].filter(Boolean).forEach((value) => {
      const item = document.createElement("span");
      item.textContent = value;
      if (value.includes("Überfällig")) item.classList.add("is-risk");
      meta.appendChild(item);
    });

    const timeline = document.createElement("div");
    timeline.className = "task-card-timeline";
    [
      ["Erstellt", formatDateTimeValue(task.created_at)],
      task.started_at ? ["Gestartet", formatDateTimeValue(task.started_at)] : null,
      task.completed_at ? ["Abgeschlossen", formatDateTimeValue(task.completed_at)] : null
    ].filter(Boolean).forEach(([label, value]) => {
      const item = document.createElement("span");
      const name = document.createElement("small");
      const amount = document.createElement("strong");
      name.textContent = label;
      amount.textContent = value;
      item.append(name, amount);
      timeline.appendChild(item);
    });

    const actions = document.createElement("div");
    actions.className = "task-card-actions";
    if (canWrite("tasks") && task.status === "open") {
      const start = actionButton("Starten", (evt) => runTaskAction(task, "start", evt.currentTarget));
      start.className = "btn btn-primary btn-sm";
      start.setAttribute("aria-label", "Aufgabe starten: " + task.title);
      actions.appendChild(start);
    }
    if (canWrite("tasks") && task.status !== "done" && task.status !== "cancelled") {
      const complete = actionButton("Abschließen", (evt) => runTaskAction(task, "complete", evt.currentTarget));
      complete.className = "btn btn-success btn-sm text-white";
      complete.setAttribute("aria-label", "Aufgabe abschließen: " + task.title);
      actions.appendChild(complete);
    }
    if (canWrite("tasks")) {
      actions.appendChild(actionButton("Bearbeiten", () => editAufgabe(task)));
    }
    if (canWrite("tasks") && task.status !== "in_progress") {
      const del = actionButton("Löschen", async (evt) => {
        if (!confirm('Aufgabe "' + task.title + '" wirklich löschen?')) return;
        evt.currentTarget.disabled = true;
        const statusMsg = document.querySelector("[data-task-message]");
        try {
          await api("/api/v1/tasks/" + task.id, { method: "DELETE" });
          await load();
          markPrioritiesStale();
          setStatusMessage(statusMsg, "Aufgabe gelöscht.");
        } catch (error) {
          setStatusMessage(statusMsg, error.message, true);
          evt.currentTarget.disabled = false;
        }
      });
      del.className = "btn btn-error btn-sm text-white";
      actions.appendChild(del);
    }

    card.append(top, description, meta, timeline, actions);
    return card;
  }

  function taskBucket(status) {
    if (status === "done" || status === "cancelled") return "done";
    if (status === "in_progress") return "in_progress";
    return "open";
  }

  function renderKanban(tasks) {
    if (!kanbanBoard) return;
    const buckets = {
      open: [],
      in_progress: [],
      done: []
    };
    tasks.forEach((task) => {
      buckets[taskBucket(task.status)].push(task);
    });
    Object.entries(buckets).forEach(([name, group]) => {
      const columnList = kanbanBoard.querySelector("[data-kanban-list='" + name + "']");
      const count = kanbanBoard.querySelector("[data-kanban-count='" + name + "']");
      if (count) count.textContent = String(group.length);
      if (!columnList) return;
      columnList.innerHTML = "";
      if (!group.length) {
        const empty = document.createElement("div");
        empty.className = "empty-state kanban-empty-state";
        empty.textContent = name === "open"
          ? "Keine offenen Aufgaben."
          : name === "in_progress"
            ? "Nichts in Bearbeitung."
            : "Noch nichts erledigt.";
        columnList.appendChild(empty);
        return;
      }
      group
        .sort((first, second) => taskSortScore(first).localeCompare(taskSortScore(second)))
        .forEach((task) => columnList.appendChild(taskCard(task)));
    });
  }

  async function load() {
    const tasks = listData(await api("/api/v1/tasks?limit=100"));
    allTasks = tasks;
    updateTaskStats(allTasks);
    populateTaskDepartmentFilter(allTasks);
    if (!allTasks.length) {
      renderKanban(allTasks);
      if (list) {
        list.innerHTML = '<div class="guided-empty-state md:col-span-2 xl:col-span-3"><strong>Noch keine Aufgaben vorhanden</strong><p>Beispiel: "Presse 3 Hydraulik prüfen". Starte mit einer neuen Aufgabe oder lasse aus einer Meldung einen Vorschlag erstellen.</p><a class="btn btn-primary btn-sm" href="#task-create">Aufgabe anlegen</a></div>';
      }
      if (taskFilterSummary) taskFilterSummary.textContent = "Noch keine Aufgaben vorhanden.";
      return;
    }
    renderFilteredTasks();
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = taskFormPayload(form);
    const wasEditing = Boolean(editingTaskId);
    const path = editingTaskId ? "/api/v1/tasks/" + editingTaskId : "/api/v1/tasks";
    const method = editingTaskId ? "PUT" : "POST";
    const message = document.querySelector("[data-task-message]");
    setFormBusy(form, true, wasEditing ? "Aktualisiert..." : "Speichert...");
    try {
      setStatusMessage(message, wasEditing ? "Aufgabe wird aktualisiert..." : "Aufgabe wird gespeichert...");
      await api(path, { method, body: JSON.stringify(data) });
      resetAufgabeForm();
      await initDepartments();
      await load();
      markPrioritiesStale();
      setStatusMessage(message, wasEditing ? "Aufgabe aktualisiert." : "Aufgabe gespeichert.");
    } catch (error) {
      setStatusMessage(message, error.message, true);
    } finally {
      setFormBusy(form, false);
    }
  });

  if (cancelEditButton) {
    cancelEditButton.addEventListener("click", () => {
      resetAufgabeForm();
      const message = document.querySelector("[data-task-message]");
      setStatusMessage(message, "Bearbeitung abgebrochen.");
    });
  }

  if (suggestForm && suggestionBox) {
    suggestForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const message = document.querySelector("[data-task-suggest-message]");
      const data = Object.fromEntries(new FormData(suggestForm).entries());
      setFormBusy(suggestForm, true, "Erstellt...");
      setStatusMessage(message, "AI erstellt Vorschlag...");
      try {
        currentSuggestion = await api("/api/v1/tasks/suggest", {
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
      } finally {
        setFormBusy(suggestForm, false);
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
        values.possible_cause ? "Mögliche Ursache: " + values.possible_cause : "",
        values.recommended_action ? "Nächste Aktion: " + values.recommended_action : ""
      ].filter(Boolean).join("\n\n");
      revealSurface(form);
      form.elements.title.focus();
    });
  }

  priorityRefreshButtons.forEach((btn) => {
    btn.addEventListener("click", async () => {
      setButtonBusy(btn, true, "Lädt...");
      btn.disabled = true;
      const original = btn.textContent;
      btn.textContent = "Wird geladen...";
      try {
        await loadPriorities();
      } finally {
        btn.textContent = original;
        btn.disabled = false;
        setButtonBusy(btn, false);
      }
    });
  });

  taskFilters.forEach((filter) => {
    const eventName = filter.tagName === "INPUT" ? "input" : "change";
    filter.addEventListener(eventName, renderFilteredTasks);
  });

  if (taskFilterReset) {
    taskFilterReset.addEventListener("click", () => {
      taskFilters.forEach((filter) => {
        filter.value = "";
      });
      renderFilteredTasks();
    });
  }

  if (taskFilterSearch) {
    const query = new URLSearchParams(window.location.search);
    taskFilterSearch.value = query.get("search") || query.get("q") || "";
  }

  renderPriorityHint(
    "Bei Bedarf aktualisieren",
    "Die Task-Seite lädt ohne automatische AI-Priorisierung. Nutze Aktualisieren, wenn du eine neue Risikoreihenfolge brauchst."
  );
  await load();
  applyTaskPreview(consumeAiActionPreview("tasks"));
}

export { initDepartments, initAufgaben as initTasks, initAufgaben };

registerWorkflowInitializers({
  initDepartments: initDepartments,
  initTasks: initAufgaben,
  initAufgaben: initAufgaben
});

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
    handover: "Schichtübergabe",
    vacations: "Urlaubsplanung",
    machines: "Maschinen",
    inventory: "Lager",
    documents: "Dokumente",
    admin_users: "Users"
  };

  const DASHBOARD_KEYS = Object.keys(DASHBOARD_LABELS);
  const EMPLOYEE_ACCESS_LEVELS = ["none", "basic", "shift", "confidential"];
  const TASK_PRIORITIES = ["urgent", "soon", "normal"];
  const TASK_STATUSES = ["open", "in_progress", "done", "cancelled"];

  function listData(result) {
    if (Array.isArray(result)) return result;
    if (result && Array.isArray(result.data)) return result.data;
    return [];
  }

  async function api(path, options) {
    return window.maintenanceApi.request(path, options);
  }

  async function downloadFile(url, filename) {
    return window.maintenanceApi.downloadFile(url, filename);
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

  function normalizeSearchText(value) {
    return String(value || "")
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "");
  }

  function initLocalListSearch() {
    const searchInputs = Array.from(document.querySelectorAll("[data-list-search]"));
    searchInputs.forEach((input) => {
      const targetSelector = input.dataset.listSearchTarget;
      if (!targetSelector) return;
      const target = document.querySelector(targetSelector);
      if (!target) return;

      const applyFilter = () => {
        const query = normalizeSearchText(input.value);
        const itemSelector = target.tagName === "TBODY" ? "tr" : ":scope > *";
        Array.from(target.querySelectorAll(itemSelector)).forEach((item) => {
          const isEmptyState = item.classList.contains("empty-state");
          const matches = !query || normalizeSearchText(item.textContent).includes(query);
          item.hidden = !isEmptyState && !matches;
        });
      };

      input.addEventListener("input", applyFilter);
      new MutationObserver(applyFilter).observe(target, { childList: true });
      applyFilter();
    });
  }

  function currentShiftFor(date) {
    const minutes = date.getHours() * 60 + date.getMinutes();
    if (minutes >= 6 * 60 && minutes < 14 * 60) {
      return {
        key: "early",
        label: "Fr\u00fchschicht",
        time: "06:00 - 14:00"
      };
    }
    if (minutes >= 14 * 60 && minutes < 22 * 60) {
      return {
        key: "late",
        label: "Sp\u00e4tschicht",
        time: "14:00 - 22:00"
      };
    }
    return {
      key: "night",
      label: "Nachtschicht",
      time: "22:00 - 06:00"
    };
  }

  function formatTopbarDate(date) {
    return new Intl.DateTimeFormat("de-DE", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric"
    }).format(date);
  }

  function initTopbarClock() {
    const dateElement = document.querySelector("[data-current-date]");
    const shiftButton = document.querySelector("[data-current-shift]");
    const shiftLabel = document.querySelector("[data-current-shift-label]");
    const shiftTime = document.querySelector("[data-current-shift-time]");
    if (!dateElement && !shiftLabel && !shiftTime) return;

    const render = () => {
      const now = new Date();
      const shift = currentShiftFor(now);
      if (dateElement) {
        dateElement.textContent = formatTopbarDate(now);
        dateElement.title = now.toLocaleDateString("de-DE", { weekday: "long" });
      }
      if (shiftLabel) shiftLabel.textContent = shift.label;
      if (shiftTime) shiftTime.textContent = shift.time;
      if (shiftButton) {
        shiftButton.classList.remove("is-early", "is-late", "is-night");
        shiftButton.classList.add("is-" + shift.key);
        shiftButton.title = "Aktuell: " + shift.label + " (" + shift.time + ")";
        shiftButton.setAttribute("aria-label", "Aktuell laufende Schicht: " + shift.label);
      }
    };

    render();
    window.setInterval(render, 60 * 1000);
  }

  function showInterfaceToast(message) {
    let toast = document.querySelector("[data-interface-toast]");
    if (!toast) {
      toast = document.createElement("div");
      toast.className = "interface-toast";
      toast.dataset.interfaceToast = "true";
      document.body.appendChild(toast);
    }
    toast.textContent = message;
    toast.hidden = false;
    window.clearTimeout(showInterfaceToast.timeoutId);
    showInterfaceToast.timeoutId = window.setTimeout(() => {
      toast.hidden = true;
    }, 2600);

    const liveRegion = document.querySelector("[data-global-live-region]");
    if (liveRegion) liveRegion.textContent = message;
  }

  function initTopbarActions() {
    const workButton = document.querySelector("[data-topbar-work]");
    const dateButton = document.querySelector("[data-topbar-date]");
    const shiftButton = document.querySelector("[data-current-shift]");
    const notificationButton = document.querySelector("[data-topbar-notifications]");

    if (workButton) {
      workButton.addEventListener("click", () => {
        showInterfaceToast("Werk 1 ist aktiv. Weitere Werke sind noch nicht konfiguriert.");
      });
    }
    if (dateButton) {
      dateButton.addEventListener("click", () => {
        window.location.href = "/shiftplans";
      });
    }
    if (shiftButton) {
      shiftButton.addEventListener("click", () => {
        window.location.href = "/shiftplans";
      });
    }
    if (notificationButton) {
      notificationButton.addEventListener("click", () => {
        const briefing = document.querySelector("#daily-briefing");
        if (briefing) {
          briefing.scrollIntoView({ behavior: "smooth", block: "start" });
          showInterfaceToast("Briefing und kritische Hinweise geoeffnet.");
          return;
        }
        window.location.href = "/";
      });
    }
  }

  function dashboardTodayIso() {
    return new Date().toISOString().slice(0, 10);
  }

  function dashboardShiftTime(entry, fallbackStart, fallbackEnd) {
    return {
      start: entry && entry.start_time ? entry.start_time : fallbackStart,
      end: entry && entry.end_time ? entry.end_time : fallbackEnd
    };
  }

  function dashboardTimeToMinutes(value) {
    const parts = String(value || "00:00").split(":");
    const hours = Math.max(0, Math.min(23, parseInt(parts[0], 10) || 0));
    const minutes = Math.max(0, Math.min(59, parseInt(parts[1], 10) || 0));
    return hours * 60 + minutes;
  }

  function dashboardTimelineGeometry(start, end) {
    const startMinutes = dashboardTimeToMinutes(start);
    let endMinutes = dashboardTimeToMinutes(end);
    if (endMinutes <= startMinutes) endMinutes += 24 * 60;
    const visibleStart = Math.max(0, Math.min(startMinutes, 24 * 60));
    const visibleEnd = Math.max(0, Math.min(endMinutes, 24 * 60));
    return {
      left: (visibleStart / (24 * 60)) * 100,
      width: Math.max(((visibleEnd - visibleStart) / (24 * 60)) * 100, 2)
    };
  }

  function dashboardCurrentShiftKey(date) {
    const minutes = date.getHours() * 60 + date.getMinutes();
    if (minutes >= 6 * 60 && minutes < 14 * 60) return "Frueh";
    if (minutes >= 14 * 60 && minutes < 22 * 60) return "Spaet";
    return "Nacht";
  }

  function dashboardTimelinePercent(date) {
    const minutes = date.getHours() * 60 + date.getMinutes();
    return (minutes / (24 * 60)) * 100;
  }

  function dashboardTimelineBarText(entry) {
    if (!entry) return "Plan offen";
    const machineName = entry.machine && entry.machine.name ? entry.machine.name : "";
    return machineName || entry.notes || "Geplant";
  }

  function dashboardEmployeesToShiftCalendar(employees) {
    const today = dashboardTodayIso();
    const shifts = [
      { key: "Frueh", start: "06:00", end: "14:00" },
      { key: "Spaet", start: "14:00", end: "22:00" },
      { key: "Nacht", start: "22:00", end: "06:00" }
    ];
    const counts = employees.reduce((map, employee) => {
      const shift = employee.current_shift || "Frei";
      map.set(shift, (map.get(shift) || 0) + 1);
      return map;
    }, new Map());

    return {
      days: 1,
      employee: null,
      entries: shifts.map((shift) => ({
        color: shift.key === "Frueh" ? "green" : shift.key === "Spaet" ? "blue" : "violet",
        end_time: shift.end,
        id: null,
        machine: null,
        notes: String(counts.get(shift.key) || 0) + " Mitarbeiter",
        plan_id: null,
        shift: shift.key,
        start_time: shift.start,
        work_date: today
      })),
      message: employees.length
        ? "Live aus Mitarbeiter-Schichten"
        : "Keine Mitarbeiterdaten fuer die Schichtuebersicht.",
      start_date: today
    };
  }

  function dashboardTimelineRow(label, shiftKey, fallbackStart, fallbackEnd, variant, entry, activeShiftKey) {
    const rowElement = document.createElement("div");
    rowElement.className = "timeline-row";
    if (shiftKey === activeShiftKey) rowElement.classList.add("is-active");

    const title = document.createElement("strong");
    const time = dashboardShiftTime(entry, fallbackStart, fallbackEnd);
    const small = document.createElement("small");
    small.textContent = time.start + " - " + time.end;
    title.append(document.createTextNode(label), small);

    const track = document.createElement("span");
    track.className = "timeline-track";
    const bar = document.createElement("span");
    bar.className = "timeline-bar " + variant;
    bar.textContent = dashboardTimelineBarText(entry);
    const geometry = dashboardTimelineGeometry(time.start, time.end);
    bar.style.left = geometry.left.toFixed(2) + "%";
    bar.style.width = geometry.width.toFixed(2) + "%";
    track.appendChild(bar);
    rowElement.append(title, track);
    return rowElement;
  }

  function renderDashboardShiftTimeline(timeline, calendar) {
    if (!timeline) return;
    timeline.innerHTML = "";

    const axis = document.createElement("div");
    axis.className = "timeline-axis";
    ["00", "04", "08", "12", "16", "20", "24"].forEach((label) => {
      const item = document.createElement("span");
      item.textContent = label;
      axis.appendChild(item);
    });
    timeline.appendChild(axis);

    const now = new Date();
    const entries = Array.isArray(calendar && calendar.entries) ? calendar.entries : [];
    const todayEntries = entries.filter((entry) => entry.work_date === dashboardTodayIso() && entry.shift !== "Frei");
    const byShift = new Map(todayEntries.map((entry) => [entry.shift, entry]));
    const activeShiftKey = dashboardCurrentShiftKey(now);
    timeline.append(
      dashboardTimelineRow("Fruehschicht", "Frueh", "06:00", "14:00", "is-green", byShift.get("Frueh"), activeShiftKey),
      dashboardTimelineRow("Spaetschicht", "Spaet", "14:00", "22:00", "is-blue", byShift.get("Spaet"), activeShiftKey),
      dashboardTimelineRow("Nachtschicht", "Nacht", "22:00", "06:00", "is-violet", byShift.get("Nacht"), activeShiftKey)
    );

    const markerTrack = document.createElement("div");
    markerTrack.className = "now-marker-track";
    const marker = document.createElement("div");
    marker.className = "now-marker";
    marker.style.left = dashboardTimelinePercent(now).toFixed(2) + "%";
    marker.title = "Jetzt: " + now.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
    markerTrack.appendChild(marker);
    timeline.appendChild(markerTrack);

    if (calendar && calendar.message) {
      const message = document.createElement("div");
      message.className = "timeline-status";
      message.textContent = calendar.message;
      timeline.appendChild(message);
    }
  }

  async function initDashboardShiftRealtime() {
    const timeline = document.querySelector("[data-dashboard-shift-timeline]");
    if (!timeline || !token()) return;
    const calendarContainer = document.querySelector("[data-dashboard-shift-calendar]");
    const message = document.querySelector("[data-dashboard-calendar-message]");
    const employeeSelect = document.querySelector("[data-dashboard-calendar-employee]");
    let dashboardEmployees = [];
    let intervalId = null;

    async function setupEmployeeFilter() {
      if (!employeeSelect || !canView("employees")) return;
      if (employeeSelect.dataset.shiftFilterReady === "true") return;
      try {
        const employees = listData(await api("/api/v1/employees?limit=100"));
        dashboardEmployees = employees;
        const allOption = employeeSelect.querySelector('option[value=""]');
        if (allOption) allOption.textContent = "Alle Mitarbeiter";
        employeeSelect.hidden = false;
        employees.forEach((employee) => {
          const option = document.createElement("option");
          option.value = String(employee.id);
          option.textContent = employee.name;
          employeeSelect.appendChild(option);
        });
        employeeSelect.dataset.shiftFilterReady = "true";
      } catch (error) {
        employeeSelect.hidden = true;
      }
    }

    async function loadRealtimeShiftCalendar() {
      const params = new URLSearchParams();
      params.set("days", "14");
      if (employeeSelect && employeeSelect.value) {
        params.set("employee_id", employeeSelect.value);
      }
      try {
        let calendar = null;
        if (employeeSelect && employeeSelect.value) {
          calendar = await api("/api/v1/shiftplans/calendar?" + params.toString());
        } else if (canView("employees")) {
          dashboardEmployees = listData(await api("/api/v1/employees?limit=100"));
          calendar = dashboardEmployeesToShiftCalendar(dashboardEmployees);
        } else {
          calendar = await api("/api/v1/shiftplans/calendar?" + params.toString());
        }
        if (calendarContainer) renderShiftCalendar(calendarContainer, calendar);
        renderDashboardShiftTimeline(timeline, calendar);
        if (message) {
          message.textContent = calendar.employee
            ? "Kalender fuer " + calendar.employee.name
            : (calendar.message || "Schichtkalender live aktualisiert");
          message.classList.remove("is-error");
        }
      } catch (error) {
        const fallback = { message: error.message, entries: [] };
        if (calendarContainer) renderShiftCalendar(calendarContainer, fallback);
        renderDashboardShiftTimeline(timeline, fallback);
        if (message) {
          message.textContent = error.message;
          message.classList.add("is-error");
        }
      }
    }

    await setupEmployeeFilter();
    await loadRealtimeShiftCalendar();
    if (employeeSelect && employeeSelect.dataset.shiftRealtimeBound !== "true") {
      employeeSelect.addEventListener("change", loadRealtimeShiftCalendar);
      employeeSelect.dataset.shiftRealtimeBound = "true";
    }
    if (timeline.dataset.shiftRealtimeStarted !== "true") {
      intervalId = window.setInterval(loadRealtimeShiftCalendar, 60 * 1000);
      timeline.dataset.shiftRealtimeStarted = "true";
      timeline.dataset.shiftRealtimeInterval = String(intervalId);
    }
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

  function consumeAiActionPreview(target) {
    try {
      const raw = window.sessionStorage.getItem("maintenance_ai_action_preview");
      if (!raw) return null;
      const preview = JSON.parse(raw);
      if (!preview || preview.target !== target) return null;
      window.sessionStorage.removeItem("maintenance_ai_action_preview");
      return preview;
    } catch (error) {
      window.sessionStorage.removeItem("maintenance_ai_action_preview");
      return null;
    }
  }

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
        priorities = await api("/api/v1/tasks/prioritize", {
          method: "POST",
          body: JSON.stringify({ status: "open", limit: 10 })
        });
      } catch (error) {
        priorityList.innerHTML = '<div class="empty-state">Priorisierung konnte nicht geladen werden.</div>';
        return;
      }
      if (!priorities.length) {
        priorityList.innerHTML = '<div class="empty-state">Keine offenen Tasks zu priorisieren.</div>';
        return;
      }
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

    function resetTaskForm() {
      editingTaskId = null;
      form.reset();
      if (form.elements.status) form.elements.status.value = "open";
      if (form.elements.priority) form.elements.priority.value = "normal";
      if (submitButton) submitButton.textContent = "Task speichern";
      if (cancelEditButton) cancelEditButton.hidden = true;
    }

    function applyTaskPreview(preview) {
      const payload = (preview && preview.payload) || {};
      if (!payload.title) return;
      resetTaskForm();
      form.elements.title.value = payload.title || "";
      form.elements.department.value = payload.department || form.elements.department.value;
      form.elements.priority.value = payload.priority || "normal";
      if (form.elements.status) form.elements.status.value = payload.status || "open";
      if (form.elements.due_date && !form.elements.due_date.value) {
        form.elements.due_date.value = new Date().toISOString().slice(0, 10);
      }
      form.elements.description.value = [
        payload.description,
        payload.possible_cause ? "Moegliche Ursache: " + payload.possible_cause : "",
        payload.recommended_action ? "Naechste Aktion: " + payload.recommended_action : ""
      ].filter(Boolean).join("\n\n");
      revealSurface(form);
      form.elements.title.focus();
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

    async function runTaskAction(task, action, button) {
      const endpoint = "/api/v1/tasks/" + task.id + "/" + action;
      const message = document.querySelector("[data-task-message]");
      if (button) button.disabled = true;
      try {
        setStatusMessage(message, action === "start" ? "Task wird gestartet..." : "Task wird abgeschlossen...");
        await api(endpoint, { method: "POST" });
        await load();
        await loadPriorities();
        setStatusMessage(message, action === "start" ? "Task gestartet." : "Task abgeschlossen.");
      } catch (error) {
        setStatusMessage(message, error.message, true);
        if (button) button.disabled = false;
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
        const start = actionButton("Starten", (evt) => runTaskAction(task, "start", evt.currentTarget));
        start.className = "btn btn-primary btn-sm";
        actions.appendChild(start);
      }
      if (canWrite("tasks") && task.status !== "done" && task.status !== "cancelled") {
        const complete = actionButton("Erledigt", (evt) => runTaskAction(task, "complete", evt.currentTarget));
        complete.className = "btn btn-success btn-sm text-white";
        actions.appendChild(complete);
      }
      if (canWrite("tasks")) {
        actions.appendChild(actionButton("Bearbeiten", () => editTask(task)));
      }
      if (canWrite("tasks") && task.status !== "in_progress") {
        const del = actionButton("Löschen", async (evt) => {
          if (!confirm('Task "' + task.title + '" wirklich löschen?')) return;
          evt.currentTarget.disabled = true;
          const statusMsg = document.querySelector("[data-task-message]");
          try {
            await api("/api/v1/tasks/" + task.id, { method: "DELETE" });
            await load();
            await loadPriorities();
            setStatusMessage(statusMsg, "Task gelöscht.");
          } catch (error) {
            setStatusMessage(statusMsg, error.message, true);
            evt.currentTarget.disabled = false;
          }
        });
        del.className = "btn btn-error btn-sm text-white";
        actions.appendChild(del);
      }

      card.append(top, description, meta, actions);
      return card;
    }

    async function load() {
      const tasks = listData(await api("/api/v1/tasks"));
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
      const path = editingTaskId ? "/api/v1/tasks/" + editingTaskId : "/api/v1/tasks";
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

    priorityRefreshButtons.forEach((btn) => {
      btn.addEventListener("click", async () => {
        btn.disabled = true;
        const original = btn.textContent;
        btn.textContent = "Wird geladen…";
        try {
          await loadPriorities();
        } finally {
          btn.textContent = original;
          btn.disabled = false;
        }
      });
    });

    await load();
    await loadPriorities();
    applyTaskPreview(consumeAiActionPreview("tasks"));
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

    const errorEditDialog = document.getElementById("error-edit-dialog");
    const eedId       = document.getElementById("eed-id");
    const eedDept     = document.getElementById("eed-department");
    const eedMachine  = document.getElementById("eed-machine");
    const eedCode     = document.getElementById("eed-code");
    const eedTitle    = document.getElementById("eed-title-input");
    const eedCauses   = document.getElementById("eed-causes");
    const eedSolution = document.getElementById("eed-solution");
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
      eedTitle.value    = entry.title || "";
      eedCauses.value   = entry.possible_causes || "";
      eedSolution.value = entry.solution || "";
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
            title: eedTitle.value,
            possible_causes: eedCauses.value,
            solution: eedSolution.value,
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
      const result = await api("/api/v1/errors/similar", {
        method: "POST",
        body: JSON.stringify({
          text: data.description || data.title || "",
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
          field.value = payload[field.dataset.errorAnalysisField] || "";
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
      if (form.elements.possible_causes) {
        form.elements.possible_causes.value = payload.possible_causes || "";
      }
      if (form.elements.solution) form.elements.solution.value = payload.solution || "";
      revealSurface(form);
      form.elements.title.focus();
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
        const cells = [
          badge(entry.error_code, "badge badge-status is-open"),
          entry.machine,
          entry.title,
          entry.department && entry.department.name,
          highlightedBlock("Ursache", entry.possible_causes, "is-cause"),
          highlightedBlock("Loesung", entry.solution, "is-solution")
        ];
        if (canWrite("errors")) {
          const actions = document.createElement("div");
          actions.className = "table-actions";
          actions.appendChild(actionButton("Bearbeiten", () => openErrorEdit(entry)));
          actions.appendChild(actionButton("Loeschen", async () => {
            if (!window.confirm("Fehler '" + entry.title + "' wirklich loeschen?")) return;
            await api("/api/v1/errors/" + entry.id, { method: "DELETE" });
            await load();
          }, true));
          cells.push(actions);
        }
        list.appendChild(row(cells));
      });
    }

    async function load() {
      currentErrors = listData(await api("/api/v1/errors"));
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
        await api("/api/v1/errors", { method: "POST", body: JSON.stringify(data) });
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
          currentAnalysis = await api("/api/v1/errors/analyze", {
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
    applyErrorPreview(consumeAiActionPreview("errors"));
  }

  async function initUsers() {
    const list = document.querySelector("[data-user-list]");
    if (!list || !token()) return;
    const editor = document.querySelector("[data-permission-editor]");
    const editorTitle = document.querySelector("[data-permission-editor-title]");
    const permissionList = document.querySelector("[data-permission-list]");
    const permissionForm = document.querySelector("[data-permission-form]");
    const permissionMessage = document.querySelector("[data-permission-message]");
    const filterQ = document.querySelector("[data-filter-q]");
    const filterRole = document.querySelector("[data-filter-role]");
    const filterStatus = document.querySelector("[data-filter-status]");
    const emptyHint = document.querySelector("[data-user-empty]");
    const tableWrap = document.querySelector("[data-user-table]");
    const aiAnalyticsCard = document.querySelector("[data-ai-analytics-card]");
    const aiEventsTotal = document.querySelector("[data-ai-events-total]");
    const aiFallbackCount = document.querySelector("[data-ai-fallback-count]");
    const aiFeedbackRate = document.querySelector("[data-ai-feedback-rate]");
    const aiNotHelpful = document.querySelector("[data-ai-not-helpful]");
    const aiLatency = document.querySelector("[data-ai-latency]");
    const aiTokens = document.querySelector("[data-ai-tokens]");
    const aiCost = document.querySelector("[data-ai-cost]");
    const aiLatestEvents = document.querySelector("[data-ai-latest-events]");
    const aiWorkflows = document.querySelector("[data-ai-workflows]");
    const aiErrorCategories = document.querySelector("[data-ai-error-categories]");
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
        await api("/api/v1/admin/users/" + item.id, {
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

    async function loadAiAnalytics() {
      if (!aiAnalyticsCard) return;
      try {
        const summary = await api("/api/v1/admin/ai/summary");
        aiAnalyticsCard.hidden = false;
        if (aiEventsTotal) aiEventsTotal.textContent = String(summary.events_total || 0);
        if (aiFallbackCount) aiFallbackCount.textContent = String(summary.fallback_count || 0);
        if (aiFeedbackRate) {
          const rate = summary.feedback && summary.feedback.helpful_rate;
          aiFeedbackRate.textContent = rate === null || rate === undefined
            ? "-"
            : Math.round(rate * 100) + "%";
        }
        if (aiNotHelpful) {
          aiNotHelpful.textContent = String((summary.feedback && summary.feedback.not_helpful) || 0);
        }
        if (aiLatency) aiLatency.textContent = String(summary.average_latency_ms || 0);
        if (aiTokens) aiTokens.textContent = compactNumber(summary.total_tokens || 0);
        if (aiCost) aiCost.textContent = "$" + Number(summary.estimated_cost_usd || 0).toFixed(4);
        renderMetricList(aiWorkflows, summary.workflow_counts, "Keine Workflows");
        renderMetricList(aiErrorCategories, summary.error_counts, "Keine Fehler");
        if (aiLatestEvents) {
          aiLatestEvents.innerHTML = "";
          const latest = summary.latest_events || [];
          if (!latest.length) {
            aiLatestEvents.innerHTML = '<tr><td colspan="7">Noch keine AI-Events vorhanden.</td></tr>';
            return;
          }
          latest.forEach((event) => {
            aiLatestEvents.appendChild(row([
              event.workflow,
              event.status,
              event.model || "-",
              String(event.source_count || 0),
              String(event.latency_ms || 0) + " ms",
              event.fallback_used ? "ja" : "nein",
              formatDate(event.created_at)
            ]));
          });
        }
      } catch (error) {
        if (aiAnalyticsCard) aiAnalyticsCard.hidden = true;
      }
    }

    function compactNumber(value) {
      const number = Number(value || 0);
      if (number >= 1000000) return (number / 1000000).toFixed(1) + "M";
      if (number >= 1000) return (number / 1000).toFixed(1) + "k";
      return String(number);
    }

    function renderMetricList(container, values, emptyText) {
      if (!container) return;
      container.innerHTML = "";
      const entries = Object.entries(values || {}).sort((left, right) => right[1] - left[1]).slice(0, 5);
      if (!entries.length) {
        const empty = document.createElement("div");
        empty.className = "panel-meta";
        empty.textContent = emptyText;
        container.appendChild(empty);
        return;
      }
      entries.forEach(([label, count]) => {
        const item = document.createElement("div");
        item.className = "stacked-list-row";
        const name = document.createElement("span");
        name.textContent = label || "-";
        const value = document.createElement("strong");
        value.textContent = String(count);
        item.append(name, value);
        container.appendChild(item);
      });
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
          const updated = await api("/api/v1/admin/users/" + selectedUser.id + "/permissions", {
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
      const q = filterQ ? filterQ.value.trim() : "";
      const role = filterRole ? filterRole.value : "";
      const status = filterStatus ? filterStatus.value : "";
      const hasFilter = q || role || status;

      if (!hasFilter) {
        if (emptyHint) emptyHint.hidden = false;
        if (tableWrap) tableWrap.hidden = true;
        list.innerHTML = "";
        return [];
      }
      if (emptyHint) emptyHint.hidden = true;
      if (tableWrap) tableWrap.hidden = false;

      const params = new URLSearchParams();
      if (q) params.set("q", q);
      if (role) params.set("role", role);
      if (status) params.set("status", status);
      const users = await api("/api/v1/admin/users?" + params.toString());
      try {
        employees = listData(await api("/api/v1/employees"));
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
          await api("/api/v1/admin/users/" + item.id + "/reset-password", {
            method: "POST",
            body: JSON.stringify({ password })
          });
        });

        const lock = document.createElement("button");
        lock.className = "btn btn-outline btn-sm";
        lock.type = "button";
        lock.textContent = item.is_active ? "Sperren" : "Entsperren";
        lock.addEventListener("click", async () => {
          await api("/api/v1/admin/users/" + item.id + "/" + (item.is_active ? "lock" : "unlock"), { method: "POST" });
          await load();
        });

        const remove = document.createElement("button");
        remove.className = "btn btn-error btn-sm text-white";
        remove.type = "button";
        remove.textContent = "Loeschen";
        remove.addEventListener("click", async () => {
          if (!window.confirm(item.username + " wirklich loeschen?")) return;
          await api("/api/v1/admin/users/" + item.id, { method: "DELETE" });
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

    let debounceTimer = null;
    function scheduleLoad() {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(load, 300);
    }
    if (filterQ) filterQ.addEventListener("input", scheduleLoad);
    if (filterRole) filterRole.addEventListener("change", load);
    if (filterStatus) filterStatus.addEventListener("change", load);
    await loadAiAnalytics();
  }

  async function initEmployees() {
    const list = document.querySelector("[data-employee-list]");
    const form = document.querySelector("[data-employee-form]");
    const message = document.querySelector("[data-employee-message]");
    if (!list || !form || !token()) return;

    const empEditDialog  = document.getElementById("emp-edit-dialog");
    const empdId         = document.getElementById("empd-id");
    const empdName       = document.getElementById("empd-name");
    const empdPnr        = document.getElementById("empd-pnr");
    const empdBirth      = document.getElementById("empd-birth");
    const empdCity       = document.getElementById("empd-city");
    const empdStreet     = document.getElementById("empd-street");
    const empdPostal     = document.getElementById("empd-postal");
    const empdDept       = document.getElementById("empd-dept");
    const empdShiftModel = document.getElementById("empd-shift-model");
    const empdCurrentShift = document.getElementById("empd-current-shift");
    const empdTeam       = document.getElementById("empd-team");
    const empdSalary     = document.getElementById("empd-salary");
    const empdMachine    = document.getElementById("empd-machine");
    const empdQuals      = document.getElementById("empd-qualifications");
    const empdSave       = document.getElementById("empd-save");
    const empdCancel     = document.getElementById("empd-cancel");
    const empdMsg        = document.getElementById("empd-msg");

    function openEmployeeEdit(employee) {
      if (!empEditDialog) return;
      empdId.value          = employee.id;
      empdName.value        = employee.name || "";
      empdPnr.value         = employee.personnel_number || "";
      empdBirth.value       = employee.birth_date || "";
      empdCity.value        = employee.city || "";
      empdStreet.value      = employee.street || "";
      empdPostal.value      = employee.postal_code || "";
      empdDept.value        = employee.department || "";
      empdShiftModel.value  = employee.shift_model || "gleitzeit";
      empdCurrentShift.value = employee.current_shift || "";
      empdTeam.value        = employee.team ? String(employee.team) : "";
      empdSalary.value      = employee.salary_group || "";
      empdMachine.value     = employee.favorite_machine || "";
      empdQuals.value       = employee.qualifications || "";
      if (empdMsg) empdMsg.textContent = "";
      empEditDialog.showModal();
    }

    if (empdCancel) empdCancel.addEventListener("click", () => empEditDialog.close());
    if (empEditDialog) {
      empEditDialog.addEventListener("keydown", (e) => { if (e.key === "Escape") empEditDialog.close(); });
    }
    if (empdSave) empdSave.addEventListener("click", async () => {
      try {
        setStatusMessage(empdMsg, "Wird gespeichert...");
        await api("/api/v1/employees/" + empdId.value, {
          method: "PUT",
          body: JSON.stringify({
            name: empdName.value,
            personnel_number: empdPnr.value,
            birth_date: empdBirth.value || null,
            city: empdCity.value,
            street: empdStreet.value,
            postal_code: empdPostal.value,
            department: empdDept.value,
            shift_model: empdShiftModel.value,
            current_shift: empdCurrentShift.value,
            team: empdTeam.value ? parseInt(empdTeam.value, 10) : null,
            salary_group: empdSalary.value,
            favorite_machine: empdMachine.value,
            qualifications: empdQuals.value
          })
        });
        empEditDialog.close();
        await load();
        if (message) message.textContent = "Mitarbeiter aktualisiert.";
      } catch (err) {
        setStatusMessage(empdMsg, err.message, true);
      }
    });

    async function uploadDocument(employeeId, file) {
      const formData = new FormData();
      formData.append("document", file);
      const response = await fetch("/api/v1/employees/" + employeeId + "/documents", {
        method: "POST",
        headers: { "Authorization": "Bearer " + token() },
        body: formData
      });
      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        throw new Error((errorData && (errorData.message || errorData.error)) || "Upload fehlgeschlagen");
      }
      return response.json();
    }

    async function downloadEmployeeDocument(documentItem) {
      await downloadFile(documentItem.download_url, documentItem.original_filename);
    }

    function employeeCard(employee, opts) {
      const card = document.createElement("article");
      card.className = "resource-card";

      const header = document.createElement("div");
      header.className = "resource-card-header";

      const titleBlock = document.createElement("div");
      const nameEl = document.createElement("h3");
      nameEl.className = "resource-card-title";
      nameEl.textContent = employee.name;
      const pnr = document.createElement("p");
      pnr.className = "resource-card-subtitle";
      pnr.textContent = employee.personnel_number || "–";
      titleBlock.append(nameEl, pnr);

      const cardBadges = document.createElement("div");
      cardBadges.className = "resource-card-badges";
      if (employee.department) cardBadges.appendChild(badge(employee.department, "badge badge-neutral"));
      if (employee.team) cardBadges.appendChild(badge("Team " + employee.team, "badge badge-info"));
      header.append(titleBlock, cardBadges);

      const metaGrid = document.createElement("div");
      metaGrid.className = "resource-meta-grid";
      [
        ["Schichtmodell", employee.shift_model],
        ["Schicht", employee.current_shift],
        ["Gehaltsklasse", employee.salary_group],
        ["Lieblingsmaschine", employee.favorite_machine]
      ].forEach(function (pair) {
        if (!pair[1]) return;
        const cell = document.createElement("div");
        cell.className = "resource-metric";
        const lbl = document.createElement("span");
        lbl.className = "resource-label";
        lbl.textContent = pair[0];
        const val = document.createElement("span");
        val.className = "resource-value";
        val.textContent = pair[1];
        cell.append(lbl, val);
        metaGrid.appendChild(cell);
      });

      const qualBadges = document.createElement("div");
      qualBadges.className = "badge-list";
      (employee.qualifications || "").split(",").forEach(function (q) {
        const t = q.trim();
        if (t) qualBadges.appendChild(badge(t, "badge badge-sm badge-outline"));
      });

      const actions = document.createElement("div");
      actions.className = "resource-actions";
      (employee.documents || []).forEach(function (doc) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "btn btn-link btn-xs px-0 justify-start";
        btn.textContent = doc.original_filename;
        btn.addEventListener("click", async function () {
          try { await opts.downloadEmployeeDocument(doc); }
          catch (err) { if (opts.message) opts.message.textContent = err.message; }
        });
        actions.appendChild(btn);
      });
      if (!(employee.documents || []).length) {
        const noDoc = document.createElement("span");
        noDoc.className = "panel-meta text-xs";
        noDoc.textContent = "Keine Dokumente";
        actions.appendChild(noDoc);
      }

      card.append(header, metaGrid, qualBadges, actions);

      if (opts.canWrite && opts.employeeAccessLevel === "confidential") {
        const uploadWrap = document.createElement("div");
        uploadWrap.className = "resource-upload";
        const input = document.createElement("input");
        input.type = "file";
        input.multiple = true;
        input.addEventListener("change", async function () {
          if (!input.files.length) return;
          input.disabled = true;
          if (opts.message) opts.message.textContent = "Dokumente werden hochgeladen...";
          try {
            const files = Array.from(input.files);
            for (const file of files) await opts.uploadDocument(employee.id, file);
            input.value = "";
            await opts.reload();
            if (opts.message) opts.message.textContent = files.length === 1
              ? "Dokument hochgeladen." : files.length + " Dokumente hochgeladen.";
          } catch (err) {
            if (opts.message) opts.message.textContent = err.message;
          } finally { input.disabled = false; }
        });
        uploadWrap.appendChild(input);
        card.appendChild(uploadWrap);

        const editDeleteRow = document.createElement("div");
        editDeleteRow.className = "table-actions";
        editDeleteRow.appendChild(actionButton("Bearbeiten", () => opts.openEdit(employee)));
        editDeleteRow.appendChild(actionButton("Loeschen", async () => {
          if (!window.confirm(employee.name + " wirklich loeschen?")) return;
          try {
            await api("/api/v1/employees/" + employee.id, { method: "DELETE" });
            await opts.reload();
            if (opts.message) opts.message.textContent = "Mitarbeiter geloescht.";
          } catch (err) {
            if (opts.message) opts.message.textContent = err.message;
          }
        }, true));
        card.appendChild(editDeleteRow);
      }

      return card;
    }

    async function load() {
      const countBadge = document.querySelector("[data-employee-count]");
      const employees = listData(await api("/api/v1/employees"));
      list.innerHTML = "";
      if (countBadge) countBadge.textContent = employees.length + " Mitarbeitende";
      if (!employees.length) {
        const empty = document.createElement("div");
        empty.className = "empty-state";
        empty.textContent = "Keine Mitarbeiter vorhanden.";
        list.appendChild(empty);
        return;
      }
      const opts = {
        canWrite: canWrite("employees"),
        employeeAccessLevel: employeeAccessLevel(),
        downloadEmployeeDocument,
        uploadDocument,
        openEdit: openEmployeeEdit,
        message,
        reload: load
      };
      employees.forEach(function (employee) { list.appendChild(employeeCard(employee, opts)); });
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const data = Object.fromEntries(new FormData(form).entries());
      await api("/api/v1/employees", { method: "POST", body: JSON.stringify(data) });
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
    const machines = await api("/api/v1/machines");
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

  async function initVacations() {
    if (!document.querySelector("[data-vac-submit]") || !token()) return;

    const BASE_VAC = "/api/v1/vacations";
    const BASE_EMP = "/api/v1/employees";
    const BASE_AUTH = "/api/v1/auth";

    const empSel = document.querySelector("[data-vac-employee]");
    const startInput = document.querySelector("[data-vac-start]");
    const endInput = document.querySelector("[data-vac-end]");
    const daysWrap = document.querySelector("[data-vac-days-wrap]");
    const daysBadge = document.querySelector("[data-vac-days-count]");
    const notesInput = document.querySelector("[data-vac-notes]");
    const submitBtn = document.querySelector("[data-vac-submit]");
    const msgEl = document.querySelector("[data-vac-msg]");
    const pendingList = document.querySelector("[data-vac-pending-list]");
    const pendingEmpty = document.querySelector("[data-vac-pending-empty]");
    const pendingCount = document.querySelector("[data-vac-pending-count]");
    const yearSel = document.querySelector("[data-vac-year]");
    const summaryList = document.querySelector("[data-vac-summary-list]");
    const filterStatus = document.querySelector("[data-vac-filter-status]");
    const filterBtn = document.querySelector("[data-vac-filter-btn]");
    const tableBody = document.querySelector("[data-vac-table-body]");
    const tableEmpty = document.querySelector("[data-vac-empty]");
    const balancePreview = document.querySelector("[data-vac-balance-preview]");
    const selectedAvailableEl = document.querySelector("[data-vac-selected-available]");
    const usedTotalEl = document.querySelector("[data-vac-used-total]");
    const pendingTotalEl = document.querySelector("[data-vac-pending-total]");

    let currentUser = user();
    let employeeBalances = new Map();
    let employees = [];
    let sending = false;

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

    function canWithdrawRequest(vacation) {
      if (!currentUser || !vacation) return false;
      return currentUser.role === "master_admin" || currentUser.employee_id === vacation.employee_id;
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
      loading.className = "panel-meta";
      loading.textContent = message;
      container.appendChild(loading);
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

    function selectedBalance() {
      const employeeId = parseInt(empSel.value || "0", 10);
      return employeeBalances.get(employeeId) || null;
    }

    function selectedEmployeeName() {
      const employeeId = parseInt(empSel.value || "0", 10);
      const employee = employees.find((item) => item.id === employeeId);
      return employee ? employee.name : "Mitarbeiter";
    }

    function requestedDays() {
      const start = startInput.value;
      const end = endInput.value;
      if (!start || !end || end < start) return null;
      return countWorkdays(start, end);
    }

    function validationError() {
      const employeeId = empSel.value;
      const start = startInput.value;
      const end = endInput.value;
      if (!employeeId || !start || !end) return "";
      if (end < start) return "Enddatum darf nicht vor dem Startdatum liegen.";
      const days = requestedDays();
      if (!days) return "Im gewaehlten Zeitraum liegt kein Arbeitstag.";
      const balance = selectedBalance();
      if (balance && days > balance.available) {
        return "Der Antrag ueberschreitet den verfuegbaren Resturlaub.";
      }
      return "";
    }

    function updateKpis() {
      const balance = selectedBalance();
      const balances = Array.from(employeeBalances.values());
      const usedTotal = balances.reduce((sum, item) => sum + (item.used || 0), 0);
      const pendingTotal = balances.reduce((sum, item) => sum + (item.pending || 0), 0);
      if (selectedAvailableEl) {
        selectedAvailableEl.textContent = balance ? String(balance.available) : "-";
      }
      if (usedTotalEl) usedTotalEl.textContent = String(usedTotal);
      if (pendingTotalEl) pendingTotalEl.textContent = String(pendingTotal);
    }

    function updateDaysCount() {
      const days = requestedDays();
      if (days !== null) {
        daysBadge.textContent = days + " Arbeitstage";
        daysWrap.hidden = false;
      } else {
        daysWrap.hidden = true;
      }
      updateBalancePreview();
    }

    function updateBalancePreview() {
      const balance = selectedBalance();
      const days = requestedDays();
      const error = validationError();
      if (!balancePreview) return;
      balancePreview.classList.toggle("is-error", Boolean(error));
      if (error) {
        balancePreview.textContent = error;
      } else if (balance && days !== null) {
        balancePreview.textContent = selectedEmployeeName() + ": "
          + balance.available + " Tage verfuegbar, "
          + days + " Tage angefragt.";
      } else if (balance) {
        balancePreview.textContent = selectedEmployeeName() + ": "
          + balance.available + " verfuegbar, "
          + balance.pending + " reserviert, "
          + balance.used + " genehmigt.";
      } else {
        balancePreview.textContent = "Waehle Mitarbeiter und Zeitraum.";
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

    function renderEmpty(parent, message) {
      parent.innerHTML = "";
      const empty = document.createElement("p");
      empty.className = "panel-meta";
      empty.textContent = message;
      parent.appendChild(empty);
    }

    function statusBadge(status) {
      const statusMap = {
        approved: "badge-success",
        rejected: "badge-error",
        pending: "badge-warning"
      };
      const labelMap = {
        approved: "Genehmigt",
        rejected: "Abgelehnt",
        pending: "Ausstehend"
      };
      const badge = document.createElement("span");
      badge.className = "badge " + (statusMap[status] || "badge-neutral");
      badge.textContent = labelMap[status] || status || "-";
      return badge;
    }

    function balanceCell(value, kind) {
      const cell = document.createElement("td");
      const badge = document.createElement("span");
      const numericValue = Number(value || 0);
      badge.className = "vacation-balance-chip";
      if (kind === "available" && numericValue <= 0) {
        badge.classList.add("is-critical");
      } else if (kind === "available" && numericValue <= 5) {
        badge.classList.add("is-warning");
      } else if (kind === "pending" && numericValue >= 5) {
        badge.classList.add("is-warning");
      } else if (kind === "used") {
        badge.classList.add("is-muted");
      }
      badge.textContent = String(numericValue);
      cell.appendChild(badge);
      return cell;
    }

    function renderSummaryTable(data) {
      const table = document.createElement("table");
      table.className = "table table-sm vacation-summary-table";

      const thead = document.createElement("thead");
      const headerRow = document.createElement("tr");
      ["Mitarbeiter", "Abteilung", "Verfuegbar", "Reserviert", "Genehmigt", "Gesamt"].forEach((label) => {
        const th = document.createElement("th");
        th.textContent = label;
        headerRow.appendChild(th);
      });
      thead.appendChild(headerRow);

      const tbody = document.createElement("tbody");
      data.forEach((summary) => {
        const row = document.createElement("tr");
        if ((summary.available || 0) <= 0) {
          row.classList.add("is-critical");
        } else if ((summary.available || 0) <= 5 || (summary.pending || 0) >= 5) {
          row.classList.add("is-warning");
        }

        const nameCell = document.createElement("td");
        nameCell.className = "vacation-summary-name";
        nameCell.textContent = summary.name || "-";

        const departmentCell = document.createElement("td");
        departmentCell.textContent = summary.department || "-";

        const totalCell = document.createElement("td");
        totalCell.textContent = String(summary.total || 0);

        row.append(
          nameCell,
          departmentCell,
          balanceCell(summary.available, "available"),
          balanceCell(summary.pending, "pending"),
          balanceCell(summary.used, "used"),
          totalCell
        );
        tbody.appendChild(row);
      });

      table.append(thead, tbody);
      summaryList.appendChild(table);
    }

    async function loadCurrentUser() {
      try {
        currentUser = await api(BASE_AUTH + "/me");
      } catch (err) {
        currentUser = user();
      }
    }

    async function loadVacEmployees() {
      empSel.innerHTML = '<option value="" disabled selected>Bitte waehlen...</option>';
      try {
        employees = listData(await api(BASE_EMP));
      } catch (err) {
        employees = currentUser && currentUser.employee ? [currentUser.employee] : [];
        setMessage("Mitarbeiter konnten nicht geladen werden: " + err.message, "error");
      }
      employees.forEach((employee) => {
        const option = document.createElement("option");
        option.value = employee.id;
        option.textContent = employee.name + (employee.department ? " (" + employee.department + ")" : "");
        empSel.appendChild(option);
      });
      if (currentUser && currentUser.role !== "master_admin" && currentUser.employee_id) {
        empSel.value = String(currentUser.employee_id);
        empSel.disabled = true;
      }
      updateBalancePreview();
    }

    async function loadSummary() {
      setLoading(summaryList, "Resturlaub wird geladen...");
      try {
        const data = listData(await api(BASE_VAC + "/summary?year=" + encodeURIComponent(yearSel.value)));
        employeeBalances = new Map(data.map((item) => [item.employee_id, item]));
        summaryList.innerHTML = "";
        if (!data.length) {
          renderEmpty(summaryList, "Keine Mitarbeiterdaten fuer dieses Jahr.");
          updateKpis();
          updateBalancePreview();
          return;
        }
        renderSummaryTable(data);
        updateKpis();
        updateBalancePreview();
      } catch (err) {
        renderEmpty(summaryList, "Resturlaub konnte nicht geladen werden: " + err.message);
      }
    }

    function renderPendingCard(vacation) {
      const card = document.createElement("article");
      card.className = "vacation-pending-card";

      const info = document.createElement("div");
      const title = document.createElement("strong");
      title.textContent = vacation.employee ? vacation.employee.name : String(vacation.employee_id);
      const meta = document.createElement("p");
      meta.className = "panel-meta";
      const department = vacation.employee && vacation.employee.department ? vacation.employee.department : "-";
      meta.textContent = department + " | " + fmtDate(vacation.start_date) + " - "
        + fmtDate(vacation.end_date) + " | " + vacation.days_used + " Tage";
      info.append(title, meta);

      const balance = employeeBalances.get(vacation.employee_id);
      const impact = document.createElement("p");
      impact.className = "panel-meta";
      impact.textContent = balance
        ? "Reserviert: " + vacation.days_used + " Tage, aktuell verfuegbar: " + balance.available
        : "Reserviert: " + vacation.days_used + " Tage";
      info.appendChild(impact);

      if (vacation.notes) {
        const notes = document.createElement("p");
        notes.className = "panel-meta";
        notes.textContent = vacation.notes;
        info.appendChild(notes);
      }

      const actions = document.createElement("div");
      actions.className = "vacation-card-actions";
      if (canDecideRequest(vacation)) {
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
      if (canWithdrawRequest(vacation)) {
        const withdrawBtn = document.createElement("button");
        withdrawBtn.className = "btn btn-ghost btn-xs";
        withdrawBtn.type = "button";
        withdrawBtn.textContent = "Zurueckziehen";
        withdrawBtn.addEventListener("click", () => withdraw(vacation.id));
        actions.appendChild(withdrawBtn);
      }
      if (!actions.children.length) {
        const state = document.createElement("span");
        state.className = "badge badge-warning";
        state.textContent = "Wartet";
        actions.appendChild(state);
      }

      card.append(info, actions);
      return card;
    }

    async function loadPending() {
      setLoading(pendingList, "Ausstehende Antraege werden geladen...");
      try {
        const params = new URLSearchParams({ status: "pending", year: yearSel.value });
        const data = listData(await api(BASE_VAC + "?" + params.toString()));
        pendingList.innerHTML = "";
        if (pendingCount) pendingCount.textContent = String(data.length);
        if (!data.length) {
          pendingEmpty.hidden = false;
          pendingList.appendChild(pendingEmpty);
          return;
        }
        pendingEmpty.hidden = true;
        data.forEach((vacation) => pendingList.appendChild(renderPendingCard(vacation)));
      } catch (err) {
        if (pendingCount) pendingCount.textContent = "0";
        renderEmpty(pendingList, "Ausstehende Antraege konnten nicht geladen werden: " + err.message);
      }
    }

    async function loadHistory() {
      tableBody.innerHTML = "";
      const loadingRow = document.createElement("tr");
      const loadingCell = document.createElement("td");
      loadingCell.colSpan = 5;
      loadingCell.className = "panel-meta";
      loadingCell.textContent = "Historie wird geladen...";
      loadingRow.appendChild(loadingCell);
      tableBody.appendChild(loadingRow);
      if (tableEmpty) tableEmpty.hidden = true;
      try {
        const params = new URLSearchParams({ year: yearSel.value });
        if (filterStatus.value) params.set("status", filterStatus.value);
        let data = listData(await api(BASE_VAC + "?" + params.toString()));
        data = filterStatus.value ? data : data.filter((item) => item.status !== "pending");
        tableBody.innerHTML = "";
        if (tableEmpty) tableEmpty.hidden = data.length > 0;
        data.forEach((vacation) => {
          const row = document.createElement("tr");
          const nameCell = document.createElement("td");
          nameCell.textContent = vacation.employee ? vacation.employee.name : String(vacation.employee_id);
          const rangeCell = document.createElement("td");
          rangeCell.textContent = fmtDate(vacation.start_date) + " - " + fmtDate(vacation.end_date);
          const daysCell = document.createElement("td");
          daysCell.textContent = String(vacation.days_used);
          const statusCell = document.createElement("td");
          statusCell.appendChild(statusBadge(vacation.status));
          const notesCell = document.createElement("td");
          notesCell.textContent = vacation.notes || "-";
          row.append(nameCell, rangeCell, daysCell, statusCell, notesCell);
          tableBody.appendChild(row);
        });
      } catch (err) {
        tableBody.innerHTML = "";
        const row = document.createElement("tr");
        const cell = document.createElement("td");
        cell.colSpan = 5;
        cell.className = "panel-meta";
        cell.textContent = "Historie konnte nicht geladen werden: " + err.message;
        row.appendChild(cell);
        tableBody.appendChild(row);
        if (tableEmpty) tableEmpty.hidden = true;
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

    async function withdraw(id) {
      try {
        setMessage("Antrag wird zurueckgezogen...", "");
        await api(BASE_VAC + "/" + id, { method: "DELETE" });
        setMessage("Antrag wurde zurueckgezogen.", "success");
        await refreshVacationData();
      } catch (err) {
        setMessage(err.message, "error");
      }
    }

    async function refreshVacationData() {
      await loadSummary();
      await Promise.all([loadPending(), loadHistory()]);
    }

    async function handleSubmit() {
      const employeeId = empSel.value;
      const start = startInput.value;
      const end = endInput.value;
      if (!employeeId || !start || !end) {
        setMessage("Bitte alle Pflichtfelder ausfuellen.", "error");
        return;
      }
      const error = validationError();
      if (error) {
        setMessage(error, "error");
        return;
      }
      sending = true;
      submitBtn.disabled = true;
      setMessage("Wird gesendet...", "");
      try {
        await api(BASE_VAC, {
          method: "POST",
          body: JSON.stringify({
            employee_id: parseInt(employeeId, 10),
            start_date: start,
            end_date: end,
            notes: notesInput.value
          })
        });
        setMessage("Antrag gestellt.", "success");
        startInput.value = "";
        endInput.value = "";
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

    empSel.addEventListener("change", () => {
      updateKpis();
      updateBalancePreview();
    });
    startInput.addEventListener("change", async () => {
      const changed = syncYearFromStartDate();
      updateDaysCount();
      if (changed) await refreshVacationData();
    });
    endInput.addEventListener("change", updateDaysCount);
    submitBtn.addEventListener("click", handleSubmit);
    yearSel.addEventListener("change", refreshVacationData);
    filterBtn.addEventListener("click", loadHistory);

    await loadCurrentUser();
    await loadVacEmployees();
    await refreshVacationData();
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
      }
    });

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
      const history = await api("/api/v1/machines/" + machine.id + "/history");
      renderMachineHistory(history);
    }

    if (assistantForm) {
      assistantForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (!activeHistoryMachine) return;
        const data = Object.fromEntries(new FormData(assistantForm).entries());
        setStatusMessage(assistantAnswer, "Maschinen-Assistent denkt...");
        try {
          const result = await api("/api/v1/machines/" + activeHistoryMachine.id + "/assistant", {
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

    async function load() {
      const machines = await api("/api/v1/machines");
      const machineCount = document.querySelector("[data-machine-count]");
      list.innerHTML = "";
      if (machineCount) machineCount.textContent = machines.length + " Maschinen";
      if (!machines.length) {
        list.innerHTML = '<tr><td colspan="4">Keine Maschinen vorhanden.</td></tr>';
        return machines;
      }
      machines.forEach((machine) => {
        const actions = document.createElement("div");
        actions.className = "table-actions";
        actions.appendChild(actionButton("Historie", () => loadMachineHistory(machine)));
        if (canWrite("machines")) {
          actions.appendChild(actionButton("Bearbeiten", () => openMachineEdit(machine)));
          actions.appendChild(actionButton("Loeschen", async () => {
            if (!window.confirm(machine.name + " wirklich loeschen?")) return;
            await api("/api/v1/machines/" + machine.id, { method: "DELETE" });
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
      return machines;
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const data = Object.fromEntries(new FormData(form).entries());
      await api("/api/v1/machines", { method: "POST", body: JSON.stringify(data) });
      form.reset();
      form.elements.required_employees.value = "1";
      await load();
      const message = document.querySelector("[data-machine-message]");
      if (message) message.textContent = "Maschine gespeichert.";
    });

    const machines = await load();
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
      const forecast = await api("/api/v1/inventory/forecast", {
        method: "POST",
        body: JSON.stringify(data)
      });
      renderForecast(forecast);
    }

    async function load() {
      await fillMachineSelects();
      const materials = await api("/api/v1/inventory");
      list.innerHTML = "";
      materials.forEach((material) => {
        const actions = document.createElement("div");
        actions.className = "table-actions";
        if (canWrite("inventory")) {
          actions.appendChild(actionButton("Loeschen", async () => {
            if (!window.confirm(material.name + " wirklich loeschen?")) return;
            await api("/api/v1/inventory/" + material.id, { method: "DELETE" });
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
      await api("/api/v1/inventory", { method: "POST", body: JSON.stringify(data) });
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
      if (message) message.textContent = "KI plant...";
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
      const task = await api("/api/v1/tasks/" + taskId);
      renderTaskDetail(task);
      if (taskDetailModal) taskDetailModal.hidden = false;
    }

    async function refreshActiveTask(message) {
      if (!activeTaskId) return;
      const task = await api("/api/v1/tasks/" + activeTaskId);
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
      const tasks = listData(await api("/api/v1/tasks"));
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
          "/api/v1/tasks/" + activeTaskId + "/start",
          "Task gestartet."
        );
      });
    }

    if (taskCompleteButton) {
      taskCompleteButton.addEventListener("click", async () => {
        await runTaskAction(
          "/api/v1/tasks/" + activeTaskId + "/complete",
          "Task abgeschlossen.",
          reportPayload()
        );
      });
    }

    if (taskRail && canView("tasks")) {
      await loadDashboardTasks();
    }

    if (errorStats && canView("errors")) {
      const errors = listData(await api("/api/v1/errors"));
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
      const summary = await api("/api/v1/inventory/summary");
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
    const inventoryShortages = document.querySelector("[data-dashboard-inventory-shortages]");
    const employeeOverview = document.querySelector("[data-dashboard-employee-overview]");
    const priorityList = document.querySelector("[data-dashboard-priority-list]");
    const briefingSummary = document.querySelector("[data-daily-briefing-summary]");
    const briefingList = document.querySelector("[data-daily-briefing-list]");
    const shiftCalendar = document.querySelector("[data-dashboard-shift-calendar]");
    const shiftTimeline = document.querySelector("[data-dashboard-shift-timeline]");
    const shiftCalendarMessage = document.querySelector("[data-dashboard-calendar-message]");
    const shiftCalendarEmployee = document.querySelector("[data-dashboard-calendar-employee]");
    if ((!taskBoard && !errorStats && !inventoryStats && !briefingList && !employeeOverview && !shiftTimeline) || !token()) return;

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
      const activeTasks = tasks.filter((task) => task.status !== "done" && task.status !== "cancelled");
      const openTasks = activeTasks.filter((task) => task.status === "open");
      const progressTasks = activeTasks.filter((task) => task.status === "in_progress");
      const doneTasks = tasks.filter((task) => task.status === "done");
      const criticalTasks = activeTasks.filter((task) => task.priority === "urgent" || isOverdue(task));
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
          await api("/api/v1/tasks/" + task.id, {
            method: "PUT",
            body: JSON.stringify(taskFormPayload(editForm))
          });
          const updatedTask = await api("/api/v1/tasks/" + task.id);
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
      const task = await api("/api/v1/tasks/" + taskId);
      renderTaskDetail(task);
      if (taskDetailModal) {
        taskDetailModal.hidden = false;
        const closeButton = taskDetailModal.querySelector("[data-task-detail-close]");
        if (closeButton) closeButton.focus();
      }
    }

    async function runTaskAction(taskId, action, body) {
      const path = "/api/v1/tasks/" + taskId + "/" + action;
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
          renderTaskDetail(await api("/api/v1/tasks/" + taskId));
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
        const captureButton = actionButton("Aufgaben oeffnen", () => {
          if (cockpitSuggestForm.hidden) {
            window.location.href = "/tasks";
            return;
          }
          revealSurface(cockpitSuggestForm);
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
      const tasks = listData(await api("/api/v1/tasks"));
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
      const activeTasks = tasks.filter((task) => task.status !== "done" && task.status !== "cancelled");
      activeTasks.forEach((task) => {
        if (task.status === "in_progress") groups.progress.push(task);
        else if (task.priority === "urgent" || isOverdue(task)) groups.urgent.push(task);
        else if (task.due_date === todayIso()) groups.today.push(task);
      });
      Object.entries(groups).forEach(([name, group]) => {
        setText("[data-cockpit-count='" + name + "']", group.length);
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
          const suggestion = await api("/api/v1/tasks/suggest", {
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
          await api("/api/v1/tasks", { method: "POST", body: JSON.stringify(data) });
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

    function emptyDashboardMessage(message) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = message;
      return empty;
    }

    function initials(name) {
      return String(name || "?")
        .split(/\s+/)
        .filter(Boolean)
        .slice(0, 2)
        .map((part) => part[0].toUpperCase())
        .join("") || "?";
    }

    function formatDashboardTime(value) {
      if (!value) return "-";
      return new Date(value).toLocaleTimeString("de-DE", {
        hour: "2-digit",
        minute: "2-digit"
      });
    }

    function firstQualification(employee) {
      return String(employee.qualifications || "")
        .split(/[,\n;]/)
        .map((part) => part.trim())
        .filter(Boolean)[0] || employee.department || "Mitarbeiter";
    }

    function employeeStatus(employee) {
      const shift = String(employee.current_shift || employee.shift_model || "").toLowerCase();
      if (shift.includes("urlaub") || shift.includes("frei")) return "Abwesend";
      if (!shift) return "Geplant";
      return "Anwesend";
    }

    function employeeRow(employee, isHeader) {
      const rowElement = document.createElement("div");
      rowElement.className = isHeader ? "employee-row is-head" : "employee-row";
      rowElement.setAttribute("role", "row");
      if (isHeader) {
        ["Mitarbeiter", "Rolle", "Schicht", "Status"].forEach((label) => {
          const cell = document.createElement("span");
          cell.textContent = label;
          rowElement.appendChild(cell);
        });
        return rowElement;
      }

      const name = document.createElement("span");
      const avatar = document.createElement("span");
      avatar.className = "mini-avatar";
      avatar.textContent = initials(employee.name);
      name.append(avatar, document.createTextNode(employee.name || "Unbekannt"));

      const role = document.createElement("span");
      role.textContent = firstQualification(employee);

      const shift = document.createElement("span");
      shift.textContent = employee.current_shift || employee.shift_model || "-";

      const status = document.createElement("strong");
      status.textContent = employeeStatus(employee);
      status.classList.toggle("is-warning", status.textContent !== "Anwesend");

      rowElement.append(name, role, shift, status);
      return rowElement;
    }

    function renderEmployeeOverview(employees) {
      if (!employeeOverview) return;
      employeeOverview.innerHTML = "";
      employeeOverview.appendChild(employeeRow(null, true));
      if (!employees.length) {
        employeeOverview.appendChild(emptyDashboardMessage("Keine Mitarbeiterdaten verfuegbar."));
        return;
      }
      employees.slice(0, 5).forEach((employee) => {
        employeeOverview.appendChild(employeeRow(employee));
      });
    }

    function incidentBadge(index) {
      if (index < 2) return badge("Katalog", "badge badge-priority is-soon");
      return badge("Erfasst", "badge badge-priority is-normal");
    }

    function renderIncidentRows(errors) {
      if (!errorStats) return;
      errorStats.innerHTML = "";
      if (!errors.length) {
        errorStats.appendChild(emptyDashboardMessage("Keine Stoerungen erfasst."));
        return;
      }
      errors.slice(0, 5).forEach((entry, index) => {
        const rowElement = document.createElement("div");
        rowElement.className = "incident-row";

        const title = document.createElement("strong");
        title.textContent = entry.title || entry.error_code || "Stoerung";

        const machine = document.createElement("span");
        machine.textContent = (entry.machine_obj && entry.machine_obj.name) || entry.machine || "-";

        const time = document.createElement("span");
        time.textContent = formatDashboardTime(entry.created_at);

        const status = badge("Erfasst", "badge badge-status is-progress");
        rowElement.append(incidentBadge(index), title, machine, time, status);
        errorStats.appendChild(rowElement);
      });
    }

    function inventoryStatusCounts(materials) {
      return materials.reduce((counts, material) => {
        const quantity = Number(material.quantity || 0);
        if (quantity <= 3) counts.critical += 1;
        else if (quantity <= 10) counts.low += 1;
        else counts.ok += 1;
        return counts;
      }, { critical: 0, low: 0, ok: 0 });
    }

    function inventoryMetric(label, value, detail) {
      const item = document.createElement("div");
      const title = document.createElement("strong");
      title.textContent = label;
      const amount = document.createElement("span");
      amount.textContent = value;
      const meta = document.createElement("small");
      meta.textContent = detail;
      item.append(title, amount, meta);
      return item;
    }

    function renderInventorySummary(summary) {
      if (!inventoryStats) return;
      const materials = Array.isArray(summary.materials) ? summary.materials : [];
      const counts = inventoryStatusCounts(materials);
      inventoryStats.innerHTML = "";
      inventoryStats.append(
        inventoryMetric("Kritisch", String(counts.critical), "Artikel"),
        inventoryMetric("Niedrig", String(counts.low), "Artikel"),
        inventoryMetric("OK", String(counts.ok), "Artikel"),
        inventoryMetric("Gesamtwert", formatMoney(summary.total_value), "Lagerwert")
      );
      if (!inventoryShortages) return;
      inventoryShortages.innerHTML = "";
      materials
        .slice()
        .sort((first, second) => Number(first.quantity || 0) - Number(second.quantity || 0))
        .slice(0, 3)
        .forEach((material) => {
          const item = document.createElement("span");
          const amount = document.createElement("strong");
          amount.textContent = String(material.quantity || 0) + " Stk.";
          item.append(document.createTextNode(material.name || "Material"), amount);
          inventoryShortages.appendChild(item);
        });
      if (!materials.length) {
        inventoryShortages.appendChild(emptyDashboardMessage("Keine Lagerdaten verfuegbar."));
      }
    }

    function shiftTime(entry, fallbackStart, fallbackEnd) {
      return {
        start: entry && entry.start_time ? entry.start_time : fallbackStart,
        end: entry && entry.end_time ? entry.end_time : fallbackEnd
      };
    }

    function timeToMinutes(value) {
      const parts = String(value || "00:00").split(":");
      const hours = Math.max(0, Math.min(23, parseInt(parts[0], 10) || 0));
      const minutes = Math.max(0, Math.min(59, parseInt(parts[1], 10) || 0));
      return hours * 60 + minutes;
    }

    function timelineGeometry(start, end) {
      const startMinutes = timeToMinutes(start);
      let endMinutes = timeToMinutes(end);
      if (endMinutes <= startMinutes) endMinutes += 24 * 60;
      const visibleStart = Math.max(0, Math.min(startMinutes, 24 * 60));
      const visibleEnd = Math.max(0, Math.min(endMinutes, 24 * 60));
      return {
        left: (visibleStart / (24 * 60)) * 100,
        width: Math.max(((visibleEnd - visibleStart) / (24 * 60)) * 100, 2)
      };
    }

    function currentShiftKey(date) {
      const minutes = date.getHours() * 60 + date.getMinutes();
      if (minutes >= 6 * 60 && minutes < 14 * 60) return "Frueh";
      if (minutes >= 14 * 60 && minutes < 22 * 60) return "Spaet";
      return "Nacht";
    }

    function currentTimelinePercent(date) {
      const minutes = date.getHours() * 60 + date.getMinutes();
      return (minutes / (24 * 60)) * 100;
    }

    function timelineBarText(entry) {
      if (!entry) return "0 / 1";
      const machineName = entry.machine && entry.machine.name ? entry.machine.name : "";
      return machineName || "1 / 1";
    }

    function timelineRow(label, shiftKey, fallbackStart, fallbackEnd, variant, entry, activeShiftKey) {
      const rowElement = document.createElement("div");
      rowElement.className = "timeline-row";
      if (shiftKey === activeShiftKey) rowElement.classList.add("is-active");
      const title = document.createElement("strong");
      const time = shiftTime(entry, fallbackStart, fallbackEnd);
      const small = document.createElement("small");
      small.textContent = time.start + " - " + time.end;
      title.append(document.createTextNode(label), small);
      const bar = document.createElement("span");
      bar.className = "timeline-bar " + variant;
      bar.textContent = timelineBarText(entry);
      const geometry = timelineGeometry(time.start, time.end);
      bar.style.left = geometry.left.toFixed(2) + "%";
      bar.style.width = geometry.width.toFixed(2) + "%";
      rowElement.append(title, bar);
      return rowElement;
    }

    function renderShiftTimeline(calendar) {
      if (!shiftTimeline) return;
      shiftTimeline.innerHTML = "";
      const axis = document.createElement("div");
      axis.className = "timeline-axis";
      ["00", "04", "08", "12", "16", "20", "24"].forEach((label) => {
        const item = document.createElement("span");
        item.textContent = label;
        axis.appendChild(item);
      });
      shiftTimeline.appendChild(axis);
      if (calendar.message) {
        shiftTimeline.appendChild(emptyDashboardMessage(calendar.message));
        return;
      }
      const now = new Date();
      const entries = Array.isArray(calendar.entries) ? calendar.entries : [];
      const today = todayIso();
      const todayEntries = entries.filter((entry) => entry.work_date === today && entry.shift !== "Frei");
      const byShift = new Map(todayEntries.map((entry) => [entry.shift, entry]));
      const activeShiftKey = currentShiftKey(now);
      shiftTimeline.append(
        timelineRow("Fruehschicht", "Frueh", "06:00", "14:00", "is-green", byShift.get("Frueh"), activeShiftKey),
        timelineRow("Spaetschicht", "Spaet", "14:00", "22:00", "is-blue", byShift.get("Spaet"), activeShiftKey),
        timelineRow("Nachtschicht", "Nacht", "22:00", "06:00", "is-violet", byShift.get("Nacht"), activeShiftKey)
      );
      const marker = document.createElement("div");
      marker.className = "now-marker";
      marker.style.left = currentTimelinePercent(now).toFixed(2) + "%";
      marker.title = "Jetzt: " + now.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
      shiftTimeline.appendChild(marker);
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
        priorities = await api("/api/v1/tasks/prioritize", {
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
        briefing = await Promise.race([
          api("/api/v1/ai/daily-briefing"),
          new Promise((resolve) => {
            window.setTimeout(() => {
              resolve({
                summary: "Briefing wird spaeter aktualisiert.",
                sections: []
              });
            }, 5000);
          })
        ]);
      } catch (error) {
        if (briefingSummary) briefingSummary.textContent = "Briefing konnte nicht geladen werden.";
        briefingList.innerHTML = "";
        briefingList.appendChild(rowLikeStat("Status", "Nicht verfuegbar"));
        return;
      }
      briefing.sections = Array.isArray(briefing.sections) ? briefing.sections : [];
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
        const employees = listData(await api("/api/v1/employees"));
        shiftCalendarEmployee.hidden = false;
        employees.forEach((employee) => {
          const option = document.createElement("option");
          option.value = String(employee.id);
          option.textContent = employee.name;
          shiftCalendarEmployee.appendChild(option);
        });
        if (!shiftCalendarEmployee.value && employees.length) {
          shiftCalendarEmployee.value = String(employees[0].id);
        }
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
        const calendar = await api("/api/v1/shiftplans/calendar?" + params.toString());
        renderShiftCalendar(shiftCalendar, calendar);
        renderShiftTimeline(calendar);
        if (shiftCalendarMessage) {
          shiftCalendarMessage.textContent = calendar.employee
            ? "Kalender fuer " + calendar.employee.name
            : (calendar.message || "Schichtkalender");
          shiftCalendarMessage.classList.remove("is-error");
        }
      } catch (error) {
        renderShiftCalendar(shiftCalendar, { message: error.message, entries: [] });
        renderShiftTimeline({ message: error.message, entries: [] });
        if (shiftCalendarMessage) {
          shiftCalendarMessage.textContent = error.message;
          shiftCalendarMessage.classList.add("is-error");
        }
      }
    }

    function startDashboardShiftRealtime() {
      if (!shiftTimeline) return;
      window.setInterval(loadShiftCalendar, 60 * 1000);
    }

    const dashboardJobs = [];

    if (taskBoard && canView("tasks")) {
      dashboardJobs.push(loadDashboardTasks());
      dashboardJobs.push(loadDashboardPriorities());
    }

    dashboardJobs.push(loadDailyBriefing());

    if (errorStats && canView("errors")) {
      dashboardJobs.push((async () => {
        const errors = listData(await api("/api/v1/errors"));
        setText("[data-dashboard-machine-issue-count]", errors.length);
        renderIncidentRows(errors);
      })());
    } else if (errorStats) {
      errorStats.innerHTML = "";
      errorStats.appendChild(emptyDashboardMessage("Keine Berechtigung fuer Stoerungen."));
    }

    if (employeeOverview && canView("employees")) {
      dashboardJobs.push((async () => {
        try {
          renderEmployeeOverview(listData(await api("/api/v1/employees?limit=5")));
        } catch (error) {
          employeeOverview.innerHTML = "";
          employeeOverview.appendChild(emptyDashboardMessage("Mitarbeiterdaten konnten nicht geladen werden."));
        }
      })());
    }

    if (inventoryStats && canView("inventory")) {
      dashboardJobs.push((async () => {
        const summary = await api("/api/v1/inventory/summary");
        renderInventorySummary(summary);
      })());
    }

    const dashboardResults = await Promise.allSettled(dashboardJobs);
    dashboardResults
      .filter((result) => result.status === "rejected")
      .forEach((result) => console.warn(result.reason));

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
      const review = await api("/api/v1/documents/" + documentItem.id + "/review", {
        method: "POST"
      });
      renderDocumentReview(review);
    }

    async function downloadDocument(documentItem) {
      await downloadFile(documentItem.download_url, "maintenance_report_task_" + documentItem.task_id + ".html");
    }

    async function load() {
      const params = new URLSearchParams();
      new FormData(form).forEach((value, key) => {
        if (value) params.set(key, value);
      });
      const suffix = params.toString() ? "?" + params.toString() : "";
      const documents = await api("/api/v1/documents" + suffix);
      const documentCount = document.querySelector("[data-document-count]");
      list.innerHTML = "";
      if (documentCount) documentCount.textContent = documents.length + " Dokumente";
      if (!documents.length) {
        list.innerHTML = '<tr><td colspan="6">Keine Dokumente gefunden.</td></tr>';
        return documents;
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
      return documents;
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

    const documents = await load();
    const documentPreview = consumeAiActionPreview("documents");
    if (documentPreview && documentPreview.payload) {
      const documentItem = documents.find((item) => item.id === documentPreview.payload.document_id);
      if (documentItem) await reviewDocument(documentItem);
    }
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
    initLocalListSearch();
    initTopbarClock();
    initTopbarActions();
    if (!token()) return;
    try {
      if (window.maintenanceAuth && window.maintenanceAuth.refreshUser) {
        await window.maintenanceAuth.ensureReady();
      }
      await initDepartments();
      await initDashboardShiftRealtime();
      await initDailyCockpit();
      await initTasks();
      await initErrors();
      await initUsers();
      await initEmployees();
      await initVacations();
      await initMachines();
      await initInventory();
      await initShiftPlans();
      await initDocuments();
    } catch (error) {
      console.warn(error);
    }
  });
})();

(function () {
  const SHARED_MODULE_URLS = [
    "/static/shared/dom.js",
    "/static/shared/forms.js",
    "/static/shared/ui.js",
    "/static/shared/status-badges.js"
  ];
  let sharedModulePromise = null;

  /**
   * Load shared workflow helper scripts before page initializers run.
   *
   * @returns {Promise<void>} Resolves after all shared modules executed.
   */
  async function loadWorkflowShared() {
    if (!sharedModulePromise) {
      sharedModulePromise = Promise.all(SHARED_MODULE_URLS.map((url) => import(url)));
    }
    await sharedModulePromise;
  }

  /**
   * Return one shared helper namespace.
   *
   * @param {string} name Shared namespace name.
   * @returns {object} Shared helper namespace or an empty object.
   */
  function sharedNamespace(name) {
    return window.maintenanceShared && window.maintenanceShared[name]
      ? window.maintenanceShared[name]
      : {};
  }

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

  /**
   * Normalize German maintenance text for resilient keyword matching.
   *
   * @param {unknown} value Raw text value.
   * @returns {string} Lowercase ASCII-compatible keyword text.
   */
  function keywordText(value) {
    return String(value || "")
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/ue/g, "u")
      .replace(/ae/g, "a")
      .replace(/oe/g, "o");
  }

  function employeeAccessLevel() {
    return window.maintenanceAuth && window.maintenanceAuth.employeeAccessLevel
      ? window.maintenanceAuth.employeeAccessLevel()
      : "none";
  }

  const DASHBOARD_LABELS = {
    dashboard: "Cockpit",
    tasks: "Aufgaben",
    errors: "Fehlerliste",
    employees: "Mitarbeiter",
    shiftplans: "Schichtplan",
    machines: "Maschinen",
    inventory: "Lager",
    documents: "Dokumente",
    admin_users: "Benutzer"
  };

  const DASHBOARD_KEYS = Object.keys(DASHBOARD_LABELS);
  const EMPLOYEE_ACCESS_LEVELS = ["none", "basic", "shift", "confidential"];
  const TASK_PRIORITIES = ["urgent", "soon", "normal"];
  const TASK_STATUSES = ["open", "in_progress", "done", "cancelled"];

  /**
   * Normalize API list envelopes through the shared DOM helper.
   *
   * @param {unknown} result API response payload.
   * @returns {Array} Normalized list items.
   */
  function listData(result) {
    return sharedNamespace("dom").listData(result);
  }

  /**
   * Resolve a paginated API total through the shared DOM helper.
   *
   * @param {object|null|undefined} result API response payload.
   * @param {Array|null|undefined} fallbackItems Fallback list.
   * @returns {number} Total item count.
   */
  function paginationTotal(result, fallbackItems) {
    return sharedNamespace("dom").paginationTotal(result, fallbackItems);
  }

  /**
   * Create a table row through the shared DOM helper.
   *
   * @param {Array} cells Cell values.
   * @returns {HTMLTableRowElement} Table row.
   */
  function row(cells) {
    return sharedNamespace("dom").row(cells);
  }

  /**
   * Read form data through the shared forms helper.
   *
   * @param {HTMLFormElement} form Form to read.
   * @returns {object} Plain form payload.
   */
  function formDataToObject(form) {
    return sharedNamespace("forms").formDataToObject(form);
  }

  /**
   * Show a toast through the shared UI helper.
   *
   * @param {string} message Toast message.
   * @param {string|object} variant Toast variant or options.
   * @returns {void}
   */
  function showInterfaceToast(message, variant) {
    return sharedNamespace("ui").showInterfaceToast(message, variant);
  }

  /**
   * Set a status message through the shared UI helper.
   *
   * @param {Element|null} element Target element.
   * @param {string} message Message text.
   * @param {boolean|undefined} isError Whether this is an error.
   * @returns {void}
   */
  function setStatusMessage(element, message, isError) {
    return sharedNamespace("ui").setStatusMessage(element, message, isError);
  }

  /**
   * Set button busy state through the shared UI helper.
   *
   * @param {HTMLButtonElement|null} button Button element.
   * @param {boolean} busy Busy state.
   * @param {string} busyText Busy text.
   * @returns {void}
   */
  function setButtonBusy(button, busy, busyText) {
    return sharedNamespace("ui").setButtonBusy(button, busy, busyText);
  }

  /**
   * Set form busy state through the shared UI helper.
   *
   * @param {HTMLFormElement|null} form Form element.
   * @param {boolean} busy Busy state.
   * @param {string} busyText Busy text.
   * @returns {void}
   */
  function setFormBusy(form, busy, busyText) {
    return sharedNamespace("ui").setFormBusy(form, busy, busyText);
  }

  /**
   * Run an action through the shared UI helper.
   *
   * @param {object} options Action options.
   * @returns {Promise<unknown|null>} Action result.
   */
  function runAction(options) {
    return sharedNamespace("ui").runAction(options);
  }

  /**
   * Request text through the shared UI helper.
   *
   * @param {object} options Dialog options.
   * @returns {Promise<string|null>} Entered text.
   */
  function requestText(options) {
    return sharedNamespace("ui").requestText(options);
  }

  /**
   * Show information through the shared UI helper.
   *
   * @param {object} options Dialog options.
   * @returns {Promise<boolean>} Acknowledgement state.
   */
  function showInfoDialog(options) {
    return sharedNamespace("ui").showInfoDialog(options);
  }

  /**
   * Confirm an action through the shared UI helper.
   *
   * @param {object} options Dialog options.
   * @returns {Promise<boolean>} Confirmation state.
   */
  function confirmAction(options) {
    return sharedNamespace("ui").confirmAction(options);
  }

  /**
   * Create a reusable guided empty-state element.
   *
   * @param {string} title Empty-state title.
   * @param {string} hint Supporting hint text.
   * @returns {HTMLElement} Empty-state element.
   */
  function emptyState(title, hint) {
    return sharedNamespace("ui").emptyState(title, hint);
  }

  /**
   * Create a badge through the shared status-badge helper.
   *
   * @param {string|number|null|undefined} text Badge text.
   * @param {string} className Badge class.
   * @returns {HTMLSpanElement} Badge element.
   */
  function badge(text, className) {
    return sharedNamespace("statusBadges").badge(text, className);
  }

  /**
   * Create a formatted badge through the shared status-badge helper.
   *
   * @param {string|number|null|undefined} value Raw badge value.
   * @param {string} className Badge class.
   * @param {Function} labelFormatter Optional label formatter.
   * @returns {HTMLSpanElement} Badge element.
   */
  function labeledBadge(value, className, labelFormatter) {
    return sharedNamespace("statusBadges").labeledBadge(value, className, labelFormatter);
  }

  /**
   * Resolve task priority badge classes through the shared status-badge helper.
   *
   * @param {string} priority Aufgabe priority.
   * @returns {string} Badge classes.
   */
  function priorityBadgeClass(priority) {
    return sharedNamespace("statusBadges").taskPriorityBadgeClass(priority);
  }

  /**
   * Resolve task status badge classes through the shared status-badge helper.
   *
   * @param {string} status Aufgabe status.
   * @returns {string} Badge classes.
   */
  function statusBadgeClass(status) {
    return sharedNamespace("statusBadges").taskStatusBadgeClass(status);
  }

  /**
   * Resolve generic status badge classes through the shared status-badge helper.
   *
   * @param {string} status Status value.
   * @returns {string} Badge classes.
   */
  function genericStatusBadgeClass(status) {
    return sharedNamespace("statusBadges").genericStatusBadgeClass(status);
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
      placeholder.textContent = "Bereich auswählen";
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
        option.textContent = "Keine Bereiche verfügbar";
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

  function sourceTypeLabel(source) {
    const key = String((source && (source.module || source.type)) || "knowledge");
    const labels = {
      tasks: "Aufgabe",
      errors: "Fehler",
      machines: "Maschine",
      documents: "Dokument",
      reports: "Bericht",
      briefings: "Briefing",
      maintenance: "Wartung",
      knowledge: "Wissen"
    };
    return labels[key] || labels.knowledge;
  }

  function renderQuellePanel(container, sources, emptyText) {
    if (!container) return;
    const items = Array.isArray(sources) ? sources.filter(Boolean) : [];
    container.innerHTML = "";
    if (!items.length) {
      if (!emptyText) {
        container.hidden = true;
        return;
      }
      const empty = document.createElement("p");
      empty.className = "panel-meta";
      empty.textContent = emptyText;
      container.appendChild(empty);
      container.hidden = false;
      return;
    }

    const title = document.createElement("strong");
    title.className = "rag-source-title";
    title.textContent = "Quellen";
    const list = document.createElement("div");
    list.className = "rag-source-list";
    items.slice(0, 5).forEach((source) => {
      const item = source.url ? document.createElement("a") : document.createElement("div");
      item.className = "rag-source-chip";
      if (source.url) item.href = source.url;
      const label = document.createElement("span");
      label.textContent = sourceTypeLabel(source);
      const value = document.createElement("strong");
      value.textContent = source.title || "Wissensquelle";
      const reason = document.createElement("small");
      reason.textContent = source.reason || (source.score ? source.score + " Punkte" : "");
      item.append(label, value, reason);
      list.appendChild(item);
    });
    container.append(title, list);
    container.hidden = false;
  }

  function applyAiActionPreview(preview) {
    if (!preview || !preview.target) return;
    window.sessionStorage.setItem("maintenance_ai_action_preview", JSON.stringify(preview));
    window.location.href = preview.url || "/";
  }

  function renderInlineActionPreview(container, preview) {
    if (!container) return;
    container.innerHTML = "";
    if (!preview || !preview.label || !preview.target) {
      container.hidden = true;
      return;
    }
    const copy = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = preview.label;
    const meta = document.createElement("span");
    meta.textContent = "Aus der Analyse kann direkt eine Aufgabe vorbereitet werden.";
    copy.append(title, meta);
    const button = document.createElement("button");
    button.type = "button";
    button.className = "btn btn-primary btn-sm";
    button.textContent = "Aufgabe vorbereiten";
    button.addEventListener("click", () => applyAiActionPreview(preview));
    container.append(copy, button);
    container.hidden = false;
  }

  function dashboardTodayIso() {
    return localIsoDate(new Date());
  }

  function localIsoDate(value) {
    const date = value instanceof Date ? value : new Date(value);
    if (Number.isNaN(date.getTime())) return "";
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return year + "-" + month + "-" + day;
  }

  function isoDateOnly(value) {
    const text = String(value || "").slice(0, 10);
    return /^\d{4}-\d{2}-\d{2}$/.test(text) ? text : "";
  }

  function dateDiffDays(fromIso, toIso) {
    const from = isoDateOnly(fromIso).split("-").map(Number);
    const to = isoDateOnly(toIso).split("-").map(Number);
    if (from.length !== 3 || to.length !== 3 || from.some(Number.isNaN) || to.some(Number.isNaN)) {
      return 0;
    }
    const fromTime = Date.UTC(from[0], from[1] - 1, from[2]);
    const toTime = Date.UTC(to[0], to[1] - 1, to[2]);
    return Math.round((toTime - fromTime) / 86400000);
  }

  function relativeDateLabel(dateValue) {
    const target = isoDateOnly(dateValue);
    if (!target) return "";
    const diff = dateDiffDays(dashboardTodayIso(), target);
    if (diff === 0) return "heute fällig";
    if (diff === 1) return "morgen fällig";
    if (diff === -1) return "seit gestern überfällig";
    if (diff < 0) return "seit " + Math.abs(diff) + " Tagen überfällig";
    return "in " + diff + " Tagen fällig";
  }

  function relativeSeenLabel(dateValue) {
    const target = isoDateOnly(dateValue);
    if (!target) return "";
    const diff = dateDiffDays(target, dashboardTodayIso());
    if (diff < 0) return "gerade gemeldet";
    if (diff === 0) return "heute gemeldet";
    if (diff === 1) return "gestern gemeldet";
    return "vor " + diff + " Tagen gemeldet";
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
        : "Keine Mitarbeiterdaten für die SchichtÜbersicht.",
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
      dashboardTimelineRow("Frühschicht", "Frueh", "06:00", "14:00", "is-green", byShift.get("Frueh"), activeShiftKey),
      dashboardTimelineRow("Spätschicht", "Spaet", "14:00", "22:00", "is-blue", byShift.get("Spaet"), activeShiftKey),
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
            ? "Kalender für " + calendar.employee.name
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

  function priorityLabel(priority) {
    const labels = {
      urgent: "Kritisch",
      soon: "Bald",
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

  function setText(selector, value) {
    document.querySelectorAll(selector).forEach((element) => {
      element.textContent = String(value);
    });
  }

  function actionButton(label, onClick, dangerOrOptions) {
    const options = typeof dangerOrOptions === "object" && dangerOrOptions !== null
      ? dangerOrOptions
      : { danger: Boolean(dangerOrOptions) };
    const button = document.createElement("button");
    button.className = options.danger ? "btn btn-error btn-sm text-white" : "btn btn-outline btn-sm";
    button.type = "button";
    button.textContent = label;
    button.addEventListener("click", async (event) => {
      if (button.disabled) return;
      await runAction({
        action: () => onClick(event),
        button,
        busyText: options.busyText || "Läuft...",
        errorMessage: options.errorMessage,
        statusElement: options.statusElement,
        successMessage: options.successMessage,
        toast: options.toast
      });
    });
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
      Frueh: "Frühschicht",
      Spaet: "Spätschicht",
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
    const data = formDataToObject(form);
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
        priorities = await api("/api/v1/tasks/prioritize", {
          method: "POST",
          body: JSON.stringify({ status: "open", limit: 10 })
        });
      } catch (error) {
        priorityList.innerHTML = '<div class="guided-empty-state"><strong>Priorisierung konnte nicht geladen werden.</strong><p>Die Aufgabeliste bleibt nutzbar. Prüfe später erneut oder sortiere nach Fälligkeit und Risiko.</p></div>';
        return;
      }
      if (!priorities.length) {
        priorityList.innerHTML = '<div class="guided-empty-state"><strong>Keine offenen Aufgaben</strong><p>Wenn Arbeit entsteht, lege einen Aufgabe an oder nutze den AI-Vorschlag aus einer kurzen Beschreibung.</p><a class="btn btn-primary btn-sm" href="#task-list">Aufgabeliste prüfen</a></div>';
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

  async function initUsers() {
    const list = document.querySelector("[data-user-list]");
    if (!list || !token()) return;
    const editor = document.querySelector("[data-permission-editor]");
    const editorTitle = document.querySelector("[data-permission-editor-title]");
    const permissionDefaults = document.querySelector("[data-permission-defaults]");
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
    const auditLogList = document.querySelector("[data-audit-log-list]");
    const auditSearch = document.querySelector("[data-audit-search]");
    const auditRefresh = document.querySelector("[data-audit-refresh]");
    const backupList = document.querySelector("[data-backup-list]");
    const backupCreate = document.querySelector("[data-backup-create]");
    const backupMessage = document.querySelector("[data-backup-message]");
    let selectedUser = null;
    let employees = [];
    let permissionSchema = null;

    function employeeSelect(item) {
      const select = document.createElement("select");
      select.className = "select select-bordered";
      select.dataset.userEmployeeSelect = String(item.id);
      const empty = document.createElement("option");
      empty.value = "";
      empty.textContent = "Nicht verknüpft";
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

    async function loadPermissionSchema() {
      try {
        permissionSchema = await api("/api/v1/admin/permissions/schema");
      } catch (error) {
        permissionSchema = null;
      }
    }

    function schemaDashboards() {
      if (permissionSchema && Array.isArray(permissionSchema.dashboards)) {
        return permissionSchema.dashboards.map((dashboard) => dashboard.key);
      }
      return DASHBOARD_KEYS;
    }

    function dashboardLabel(dashboard) {
      const match = permissionSchema && Array.isArray(permissionSchema.dashboards)
        ? permissionSchema.dashboards.find((item) => item.key === dashboard)
        : null;
      return match ? match.label : (DASHBOARD_LABELS[dashboard] || dashboard);
    }

    function employeeAccessLabel(level) {
      const match = permissionSchema && Array.isArray(permissionSchema.employee_access_levels)
        ? permissionSchema.employee_access_levels.find((item) => item.key === level)
        : null;
      return match ? match.label : level;
    }

    function roleDefaultPermission(role, dashboard) {
      const defaults = permissionSchema && permissionSchema.role_defaults
        ? permissionSchema.role_defaults[role] || {}
        : {};
      return defaults[dashboard] || {
        can_view: false,
        can_write: false,
        employee_access_level: "none"
      };
    }

    function permissionZusammenfassung(permission) {
      const parts = [];
      if (permission.can_view) parts.push("Anzeigen");
      if (permission.can_write) parts.push("Bearbeiten");
      if (permission.employee_access_level && permission.employee_access_level !== "none") {
        parts.push(employeeAccessLabel(permission.employee_access_level));
      }
      return parts.length ? parts.join(", ") : "Keine Rechte";
    }

    function permissionChanged(left, right) {
      return Boolean(left.can_view) !== Boolean(right.can_view)
        || Boolean(left.can_write) !== Boolean(right.can_write)
        || (left.employee_access_level || "none") !== (right.employee_access_level || "none");
    }

    function collectPermissionPayload() {
      const payload = { permissions: {} };
      schemaDashboards().forEach((dashboard) => {
        payload.permissions[dashboard] = {
          can_view: false,
          can_write: false,
          employee_access_level: "none"
        };
      });
      permissionForm.querySelectorAll("[data-dashboard]").forEach((input) => {
        const dashboard = input.dataset.dashboard;
        const action = input.dataset.permissionAction;
        if (!payload.permissions[dashboard]) return;
        if (action === "employee_access_level") {
          payload.permissions[dashboard].employee_access_level = input.value;
        } else {
          payload.permissions[dashboard][action] = input.checked;
        }
      });
      if (payload.permissions.admin_users) {
        payload.permissions.admin_users.can_view = selectedUser.role === "master_admin";
        payload.permissions.admin_users.can_write = selectedUser.role === "master_admin";
      }
      return payload;
    }

    function permissionChangeZusammenfassung(payload) {
      const changes = [];
      schemaDashboards().forEach((dashboard) => {
        const before = (selectedUser.permissions && selectedUser.permissions[dashboard]) || {
          can_view: false,
          can_write: false,
          employee_access_level: "none"
        };
        const after = payload.permissions[dashboard] || {
          can_view: false,
          can_write: false,
          employee_access_level: "none"
        };
        if (!permissionChanged(before, after)) return;
        changes.push(
          dashboardLabel(dashboard) + ": " + permissionZusammenfassung(before)
            + " -> " + permissionZusammenfassung(after)
        );
      });
      return changes;
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
      const accessLevels = permissionSchema && Array.isArray(permissionSchema.employee_access_levels)
        ? permissionSchema.employee_access_levels.map((level) => level.key)
        : EMPLOYEE_ACCESS_LEVELS;
      accessLevels.forEach((level) => {
        const option = document.createElement("option");
        option.value = level;
        option.textContent = employeeAccessLabel(level);
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
        editorTitle.textContent = item.username + " - Rechte je Cockpit";
      }
      if (permissionDefaults) {
        permissionDefaults.textContent = "Rollen-Default: " + item.role
          + " | Abweichungen werden vor dem Speichern angezeigt.";
      }
      if (permissionMessage) permissionMessage.textContent = "";
      permissionList.innerHTML = "";

      const groups = permissionSchema && Array.isArray(permissionSchema.groups)
        ? permissionSchema.groups
        : [{ label: "Rechte", dashboards: schemaDashboards() }];
      groups.forEach((group) => {
        const groupRow = document.createElement("tr");
        const groupCell = document.createElement("td");
        groupCell.colSpan = 4;
        groupCell.className = "panel-meta";
        groupCell.textContent = group.label;
        groupRow.appendChild(groupCell);
        permissionList.appendChild(groupRow);
        group.dashboards.forEach((dashboard) => {
          const permission = (item.permissions && item.permissions[dashboard]) || {};
          const defaultPermission = roleDefaultPermission(item.role, dashboard);
          const isAdminUsersDashboard = dashboard === "admin_users";
          const isMasterAdmin = item.role === "master_admin";
          const label = document.createElement("div");
          const name = document.createElement("strong");
          name.textContent = dashboardLabel(dashboard);
          const defaultHint = document.createElement("p");
          defaultHint.className = "panel-meta";
          defaultHint.textContent = "Default: " + permissionZusammenfassung(defaultPermission);
          label.append(name, defaultHint);
          permissionList.appendChild(row([
            label,
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
      });
    }

    if (permissionForm) {
      permissionForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (!selectedUser) return;
        const payload = collectPermissionPayload();
        const changes = permissionChangeZusammenfassung(payload);
        if (changes.length) {
          const confirmed = window.confirm("Diese Rechte speichern?\n\n" + changes.join("\n"));
          if (!confirmed) return;
        }
        setFormBusy(permissionForm, true, "Speichert...");
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
          await loadAuditLog();
          if (permissionMessage) permissionMessage.textContent = "Rechte gespeichert.";
        } catch (error) {
          if (permissionMessage) permissionMessage.textContent = error.message;
        } finally {
          setFormBusy(permissionForm, false);
        }
      });
    }

    async function loadAuditLog() {
      if (!auditLogList) return;
      const params = new URLSearchParams();
      params.set("limit", "25");
      if (auditSearch && auditSearch.value.trim()) {
        params.set("q", auditSearch.value.trim());
      }
      try {
        const result = await api("/api/v1/admin/audit-log?" + params.toString());
        const entries = listData(result);
        auditLogList.innerHTML = "";
        if (!entries.length) {
          auditLogList.innerHTML = '<tr><td colspan="4">Keine Audit-Einträge vorhanden.</td></tr>';
          return;
        }
        entries.forEach((entry) => {
          auditLogList.appendChild(row([
            formatDate(entry.created_at),
            entry.action,
            entry.resource_type + (entry.resource_id ? " #" + entry.resource_id : ""),
            (entry.actor && entry.actor.username) || "-"
          ]));
        });
      } catch (error) {
        auditLogList.innerHTML = '<tr><td colspan="4">Audit-Log konnte nicht geladen werden.</td></tr>';
      }
    }

    function formatBytes(value) {
      const bytes = Number(value || 0);
      if (bytes >= 1048576) return (bytes / 1048576).toFixed(1) + " MB";
      if (bytes >= 1024) return (bytes / 1024).toFixed(1) + " KB";
      return bytes + " B";
    }

    async function loadBackups() {
      if (!backupList) return;
      try {
        const result = await api("/api/v1/admin/backups");
        const backups = listData(result);
        backupList.innerHTML = "";
        if (!backups.length) {
          backupList.innerHTML = '<tr><td colspan="4">Noch keine Backups vorhanden.</td></tr>';
          return;
        }
        backups.forEach((item) => {
          const actions = document.createElement("div");
          actions.className = "table-actions";
          actions.appendChild(actionButton("Download", async () => {
            await downloadFile(item.download_url, item.filename);
          }));
          actions.appendChild(actionButton("Restore", async () => {
            const confirmed = window.confirm(
              "Backup wiederherstellen?\nVor dem Restore wird automatisch ein Sicherheitsbackup erstellt."
            );
            if (!confirmed) return;
            if (backupMessage) backupMessage.textContent = "Restore läuft...";
            await api("/api/v1/admin/backups/" + item.id + "/restore", {
              method: "POST",
              body: JSON.stringify({ confirm: true })
            });
            if (backupMessage) backupMessage.textContent = "Backup wiederhergestellt.";
            await loadBackups();
            await loadAuditLog();
          }));
          backupList.appendChild(row([
            item.filename,
            formatBytes(item.size_bytes),
            formatDate(item.created_at),
            actions
          ]));
        });
      } catch (error) {
        backupList.innerHTML = '<tr><td colspan="4">Backups konnten nicht geladen werden.</td></tr>';
      }
    }

    async function load() {
      const q = filterQ ? filterQ.value.trim() : "";
      const role = filterRole ? filterRole.value : "";
      const status = filterStatus ? filterStatus.value : "";

      if (emptyHint) {
        emptyHint.hidden = false;
        emptyHint.textContent = "Nutzer werden geladen...";
        emptyHint.classList.remove("is-error");
      }
      if (tableWrap) tableWrap.hidden = true;
      list.innerHTML = "";

      const params = new URLSearchParams();
      if (q) params.set("q", q);
      if (role) params.set("role", role);
      if (status) params.set("status", status);
      const queryString = params.toString();
      let users = [];
      try {
        users = listData(await api("/api/v1/admin/users" + (queryString ? "?" + queryString : "")));
      } catch (error) {
        if (emptyHint) {
          emptyHint.hidden = false;
          emptyHint.textContent = error.message || "Nutzer konnten nicht geladen werden.";
          emptyHint.classList.add("is-error");
        }
        if (tableWrap) tableWrap.hidden = true;
        return [];
      }
      try {
        employees = listData(await api("/api/v1/employees?limit=200"));
      } catch (error) {
        employees = [];
      }
      list.innerHTML = "";
      if (!users.length) {
        if (emptyHint) {
          emptyHint.hidden = false;
          emptyHint.textContent = q || role || status
            ? "Keine Nutzer für diese Filter gefunden."
            : "Noch keine Nutzer vorhanden.";
          emptyHint.classList.remove("is-error");
        }
        if (tableWrap) tableWrap.hidden = true;
        return users;
      }
      if (emptyHint) {
        emptyHint.hidden = true;
        emptyHint.classList.remove("is-error");
      }
      if (tableWrap) tableWrap.hidden = false;
      users.forEach((item) => {
        const actions = document.createElement("div");
        actions.className = "table-actions";

        const reset = document.createElement("button");
        reset.className = "btn btn-outline btn-sm";
        reset.type = "button";
        reset.textContent = "Passwort";
        reset.addEventListener("click", async () => {
          const password = await requestText({
            title: "Passwort zurücksetzen",
            message: "Neues Passwort für " + item.username + " vergeben.",
            label: "Neues Passwort",
            inputType: "password",
            required: true,
            confirmText: "Speichern"
          });
          if (password === null) return;
          setButtonBusy(reset, true, "Speichert...");
          try {
            await api("/api/v1/admin/users/" + item.id + "/reset-password", {
              method: "POST",
              body: JSON.stringify({ password })
            });
            if (permissionMessage) permissionMessage.textContent = "Passwort aktualisiert.";
            await loadAuditLog();
          } catch (error) {
            if (permissionMessage) permissionMessage.textContent = error.message;
          } finally {
            setButtonBusy(reset, false);
          }
        });

        const lock = document.createElement("button");
        lock.className = "btn btn-outline btn-sm";
        lock.type = "button";
        lock.textContent = item.is_active ? "Sperren" : "Entsperren";
        lock.addEventListener("click", async () => {
          setButtonBusy(lock, true, "Läuft...");
          try {
            await api("/api/v1/admin/users/" + item.id + "/" + (item.is_active ? "lock" : "unlock"), { method: "POST" });
            if (permissionMessage) permissionMessage.textContent = item.is_active ? "User gesperrt." : "User entsperrt.";
            await load();
            await loadAuditLog();
          } catch (error) {
            if (permissionMessage) permissionMessage.textContent = error.message;
          } finally {
            setButtonBusy(lock, false);
          }
        });

        const remove = document.createElement("button");
        remove.className = "btn btn-error btn-sm text-white";
        remove.type = "button";
        remove.textContent = "Löschen";
        remove.addEventListener("click", async () => {
          const confirmed = await confirmAction({
            title: "User löschen",
            message: item.username + " wirklich löschen? Diese Aktion kann nicht direkt rückgängig gemacht werden.",
            confirmText: "Löschen"
          });
          if (!confirmed) return;
          setButtonBusy(remove, true, "Löscht...");
          try {
            await api("/api/v1/admin/users/" + item.id, { method: "DELETE" });
            if (permissionMessage) permissionMessage.textContent = "User gelöscht.";
            await load();
            await loadAuditLog();
          } catch (error) {
            if (permissionMessage) permissionMessage.textContent = error.message;
          } finally {
            setButtonBusy(remove, false);
          }
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
    let auditDebounceTimer = null;
    function scheduleAuditLoad() {
      clearTimeout(auditDebounceTimer);
      auditDebounceTimer = setTimeout(loadAuditLog, 300);
    }
    if (filterQ) filterQ.addEventListener("input", scheduleLoad);
    if (filterRole) filterRole.addEventListener("change", load);
    if (filterStatus) filterStatus.addEventListener("change", load);
    if (auditSearch) auditSearch.addEventListener("input", scheduleAuditLoad);
    if (auditRefresh) auditRefresh.addEventListener("click", loadAuditLog);
    if (backupCreate) {
      backupCreate.addEventListener("click", async () => {
        setButtonBusy(backupCreate, true, "Erstellt...");
        if (backupMessage) backupMessage.textContent = "Backup wird erstellt...";
        try {
          await api("/api/v1/admin/backups", { method: "POST" });
          if (backupMessage) backupMessage.textContent = "Backup erstellt.";
          await loadBackups();
          await loadAuditLog();
        } catch (error) {
          if (backupMessage) backupMessage.textContent = error.message;
        } finally {
          setButtonBusy(backupCreate, false);
        }
      });
    }
    await loadPermissionSchema();
    await load();
    await loadAiAnalytics();
    await loadAuditLog();
    await loadBackups();
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
      setButtonBusy(empdSave, true, "Speichert...");
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
      } finally {
        setButtonBusy(empdSave, false);
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
        throw new Error((errorData && (errorData.message || errorData.error)) || "Hochladen fehlgeschlagen");
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
      pnr.textContent = employee.personnel_number || "-";
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
        editDeleteRow.appendChild(actionButton("Löschen", async () => {
          if (!window.confirm(employee.name + " wirklich löschen?")) return;
          try {
            await api("/api/v1/employees/" + employee.id, { method: "DELETE" });
            await opts.reload();
            if (opts.message) opts.message.textContent = "Mitarbeiter gelöscht.";
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
      const employees = listData(await api("/api/v1/employees?limit=200"));
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
      setFormBusy(form, true, "Speichert...");
      try {
        setStatusMessage(message, "Mitarbeiter wird gespeichert...");
        await api("/api/v1/employees", { method: "POST", body: JSON.stringify(data) });
        form.reset();
        await load();
        setStatusMessage(message, "Mitarbeiter gespeichert.");
      } catch (error) {
        setStatusMessage(message, error.message, true);
      } finally {
        setFormBusy(form, false);
      }
    });

    await load();
  }

  async function fillMachineSelects() {
    const selects = document.querySelectorAll("[data-machine-select]");
    if (!selects.length || !token()) return [];
    if (!canView("machines")) return [];
    const machines = listData(await api("/api/v1/machines?limit=200"));
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

  async function initMachineProfile() {
    const root = document.querySelector("[data-machine-profile-page]");
    if (!root || !token()) return;
    const machineId = root.dataset.machineId;
    const message = root.querySelector("[data-machine-profile-message]");
    if (!machineId) {
      setStatusMessage(message, "Maschinen-ID fehlt.", true);
      return;
    }

    function profileData(payload) {
      return payload && payload.machine ? payload : ((payload && payload.data) || {});
    }

    function profileList(selector) {
      return root.querySelector(selector + " .machine-profile-list");
    }

    function valueText(value) {
      if (value === 0) return "0";
      return value || "-";
    }

    function dateLabel(value, options) {
      if (!value) return "-";
      const raw = String(value);
      const parsed = new Date(raw.includes("T") ? raw : raw + "T00:00:00");
      if (Number.isNaN(parsed.getTime())) return raw;
      return parsed.toLocaleDateString("de-DE", options || {
        day: "2-digit",
        month: "2-digit",
        year: "numeric"
      });
    }

    function minutesLabel(value) {
      const minutes = Number(value || 0);
      if (!minutes) return "0 min";
      if (minutes < 60) return minutes + " min";
      const hours = Math.floor(minutes / 60);
      const rest = minutes % 60;
      return rest ? hours + " h " + rest + " min" : hours + " h";
    }

    function machineStatusLabel(status) {
      const labels = {
        running: "Läuft",
        stopped: "Stillstand",
        maintenance: "Wartung",
        warning: "Warnung",
        offline: "Offline"
      };
      return labels[status] || status || "-";
    }

    function criticalityLabel(criticality) {
      const labels = {
        critical: "Kritisch",
        high: "Hoch",
        normal: "Normal",
        low: "Niedrig"
      };
      return labels[criticality] || criticality || "Normal";
    }

    function criticalityBadgeClass(criticality) {
      if (criticality === "critical" || criticality === "high") {
        return "badge badge-priority is-urgent";
      }
      if (criticality === "low") return "badge badge-priority is-normal";
      return "badge badge-status is-done";
    }

    function severityLabel(severity) {
      const labels = {
        critical: "Kritisch",
        high: "Hoch",
        medium: "Mittel",
        low: "Niedrig"
      };
      return labels[severity] || severity || "-";
    }

    function errorStatusLabel(status) {
      const labels = {
        open: "Offen",
        in_progress: "In Arbeit",
        closed: "Geschlossen"
      };
      return labels[status] || status || "-";
    }

    function profileEmpty(text, action) {
      const empty = document.createElement("div");
      empty.className = "machine-profile-empty";
      const strong = document.createElement("strong");
      strong.textContent = text;
      empty.appendChild(strong);
      if (action && action.href) {
        const link = document.createElement("a");
        link.className = "btn btn-outline btn-sm";
        link.href = action.href;
        link.textContent = action.label || "Öffnen";
        empty.appendChild(link);
      }
      return empty;
    }

    function metric(label, value) {
      const item = document.createElement("span");
      const labelElement = document.createElement("small");
      const valueElement = document.createElement("strong");
      labelElement.textContent = label;
      valueElement.textContent = valueText(value);
      item.append(labelElement, valueElement);
      return item;
    }

    function profileRecordCard(data) {
      const card = document.createElement("article");
      card.className = "machine-profile-record";

      const header = document.createElement("div");
      header.className = "machine-profile-record-header";
      const titleBlock = document.createElement("div");
      const title = document.createElement("h3");
      title.textContent = data.title || "-";
      const subtitle = document.createElement("p");
      subtitle.textContent = data.subtitle || "";
      titleBlock.append(title, subtitle);
      const badges = document.createElement("div");
      badges.className = "machine-profile-record-badges";
      (data.badges || []).forEach((item) => {
        badges.appendChild(badge(item[0], item[1]));
      });
      header.append(titleBlock, badges);
      card.appendChild(header);

      if (data.summary) {
        const summary = document.createElement("p");
        summary.className = "machine-profile-record-summary";
        summary.textContent = data.summary;
        card.appendChild(summary);
      }

      if (data.metrics && data.metrics.length) {
        const metrics = document.createElement("div");
        metrics.className = "machine-profile-record-metrics";
        data.metrics.forEach((item) => metrics.appendChild(metric(item[0], item[1])));
        card.appendChild(metrics);
      }

      if (data.url) {
        const actions = document.createElement("div");
        actions.className = "machine-profile-record-actions";
        const link = document.createElement("a");
        link.className = "btn btn-outline btn-sm";
        link.href = data.url;
        link.textContent = data.actionLabel || "Öffnen";
        actions.appendChild(link);
        card.appendChild(actions);
      }
      return card;
    }

    function renderRecords(container, items, emptyText, mapper, action) {
      if (!container) return;
      container.innerHTML = "";
      const rows = Array.isArray(items) ? items : [];
      if (!rows.length) {
        container.appendChild(profileEmpty(emptyText, action));
        return;
      }
      rows.forEach((item) => container.appendChild(profileRecordCard(mapper(item))));
    }

    function renderDenied(container, text) {
      if (!container) return;
      container.innerHTML = "";
      container.appendChild(profileEmpty(text || "Keine Berechtigung für diesen Bereich."));
    }

    function renderHero(profile) {
      const machine = profile.machine || {};
      const name = root.querySelector("[data-machine-profile-name]");
      const summary = root.querySelector("[data-machine-profile-summary]");
      const badges = root.querySelector("[data-machine-profile-badges]");
      const taskLink = root.querySelector("[data-machine-profile-task-link]");
      const errorLink = root.querySelector("[data-machine-profile-error-link]");
      const documentLink = root.querySelector("[data-machine-profile-document-link]");
      if (name) name.textContent = machine.name || "Maschine";
      if (summary) {
        summary.textContent = [
          machine.produced_item || "Kein Produkt hinterlegt",
          (machine.required_employees || 1) + " Mitarbeiter pro Schicht",
          machine.site && machine.site.name ? machine.site.name : "Werk nicht zugeordnet"
        ].join(" · ");
      }
      if (badges) {
        badges.innerHTML = "";
        badges.appendChild(
          badge(machineStatusLabel(machine.status), genericStatusBadgeClass(machine.status))
        );
        badges.appendChild(
          badge(criticalityLabel(machine.criticality), criticalityBadgeClass(machine.criticality))
        );
      }
      const query = encodeURIComponent(machine.name || "");
      if (taskLink) taskLink.href = "/tasks?search=" + query;
      if (errorLink) errorLink.href = "/errors?search=" + query;
      if (documentLink) documentLink.href = "/documents?search=" + query;
    }

    function renderKpis(profile) {
      const container = root.querySelector("[data-machine-profile-kpis]");
      const kpis = profile.kpis || {};
      if (!container) return;
      container.innerHTML = "";
      [
        ["Offene Aufgaben", kpis.open_tasks || 0, "Aktive Arbeit zur Maschine", "is-work"],
        ["Aktive Störungen", kpis.active_errors || 0, "Offen oder in Bearbeitung", "is-risk"],
        ["Kritisch", kpis.critical_errors || 0, "Hohe Dringlichkeit", "is-critical"],
        ["Wartung fällig", kpis.maintenance_due || 0, "Aktive Wartungspläne", "is-maintenance"],
        ["Dokumente", kpis.documents || 0, "Berichte und Handbücher", "is-knowledge"],
        ["Stillstand", minutesLabel(kpis.downtime_minutes), "Erfasste Ausfallzeit", "is-downtime"]
      ].forEach(([label, value, meta, tone]) => {
        const card = document.createElement("article");
        card.className = "machine-profile-kpi-card " + tone;
        const labelElement = document.createElement("span");
        const valueElement = document.createElement("strong");
        const metaElement = document.createElement("small");
        labelElement.textContent = label;
        valueElement.textContent = String(value);
        metaElement.textContent = meta;
        card.append(labelElement, valueElement, metaElement);
        container.appendChild(card);
      });
    }

    function renderMaster(profile) {
      const container = root.querySelector("[data-machine-profile-master] .machine-profile-facts");
      const machine = profile.machine || {};
      if (!container) return;
      container.innerHTML = "";
      [
        ["Status", machineStatusLabel(machine.status)],
        ["Kritikalität", criticalityLabel(machine.criticality)],
        ["Produkt", machine.produced_item || "-"],
        ["Personalbedarf", (machine.required_employees || 1) + " MA"],
        ["Werk", machine.site && machine.site.name ? machine.site.name : "-"],
        ["Angelegt", dateLabel(machine.created_at)]
      ].forEach((item) => container.appendChild(metric(item[0], item[1])));
    }

    function taskRecord(task) {
      return {
        title: task.title,
        subtitle: task.department && task.department.name ? task.department.name : "Bereich offen",
        summary: task.description || "Keine Beschreibung hinterlegt.",
        badges: [
          [priorityLabel(task.priority), priorityBadgeClass(task.priority)],
          [statusLabel(task.status), statusBadgeClass(task.status)]
        ],
        metrics: [
          ["Fällig", dateLabel(task.due_date)],
          ["Zuordnung", task.current_worker ? task.current_worker.username : "Nicht gestartet"],
          ["Bezug", task.machine_match || "-"]
        ],
        url: task.ui_url || "/tasks?search=" + encodeURIComponent(task.title || ""),
        actionLabel: "Aufgabe öffnen"
      };
    }

    function errorRecord(error) {
      return {
        title: [error.error_code, error.title].filter(Boolean).join(" · "),
        subtitle: error.cause_category || error.machine || "Störung",
        summary: error.symptoms || error.description || error.solution || "Keine Details hinterlegt.",
        badges: [
          [errorStatusLabel(error.status), genericStatusBadgeClass(error.status)],
          [severityLabel(error.severity), criticalityBadgeClass(error.severity)]
        ],
        metrics: [
          ["Auswirkung", error.impact || "-"],
          ["Stillstand", minutesLabel(error.downtime_minutes)],
          ["Erfasst", dateLabel(error.created_at)]
        ],
        url: error.ui_url || "/errors?search=" + encodeURIComponent(error.error_code || ""),
        actionLabel: "Störung öffnen"
      };
    }

    function maintenanceRecord(plan) {
      return {
        title: plan.title,
        subtitle: plan.department && plan.department.name ? plan.department.name : "Wartungsplan",
        summary: plan.description || "Kein Ablauf hinterlegt.",
        badges: [
          [priorityLabel(plan.priority), priorityBadgeClass(plan.priority)],
          [plan.is_due ? "Fällig" : "Geplant", plan.is_due ? "badge badge-priority is-soon" : "badge badge-status is-progress"]
        ],
        metrics: [
          ["Intervall", (plan.interval_days || 0) + " Tage"],
          ["Nächster Termin", dateLabel(plan.next_due_date)],
          ["Letzte Erzeugung", dateLabel(plan.last_generated_at)]
        ],
        url: plan.ui_url || "/machines",
        actionLabel: "Wartungspläne"
      };
    }

    function documentRecord(document, typeLabel) {
      return {
        title: document.title || document.original_filename || typeLabel,
        subtitle: typeLabel,
        summary: document.summary || document.analysis || "Noch keine Zusammenfassung hinterlegt.",
        badges: [
          [document.status || document.analysis_status || "not_started", genericStatusBadgeClass(document.status || document.analysis_status)]
        ],
        metrics: [
          ["Bereich", document.department || "-"],
          ["Version", document.version || "-"],
          ["Erstellt", dateLabel(document.created_at)]
        ],
        url: document.ui_url || "/documents",
        actionLabel: "Dokumente öffnen"
      };
    }

    function handoverRecord(handover) {
      return {
        title: dateLabel(handover.shift_date) + " · " + valueText(handover.shift_type),
        subtitle: handover.area || handover.department || "Schichtübergabe",
        summary: handover.machine_status || handover.action_taken || handover.content || "Keine Maschinennotiz hinterlegt.",
        badges: [
          [handover.status === "completed" ? "Bestätigt" : "Offen", genericStatusBadgeClass(handover.status)]
        ],
        metrics: [
          ["Vorher", handover.previous_shift || "-"],
          ["Nächste", handover.next_shift || "-"],
          ["Verantwortlich", handover.responsible_employee || handover.handed_over_by || "-"]
        ],
        url: handover.ui_url || "/handover",
        actionLabel: "Übergabe öffnen"
      };
    }

    function materialRecord(material) {
      return {
        title: material.name,
        subtitle: material.manufacturer || "Ersatzteil",
        summary: material.is_below_minimum
          ? "Mindestbestand unterschritten."
          : "Bestand im Profil hinterlegt.",
        badges: [
          [material.is_below_minimum ? "Prüfen" : "OK", material.is_below_minimum ? "badge badge-priority is-soon" : "badge badge-status is-done"]
        ],
        metrics: [
          ["Bestand", material.quantity || 0],
          ["Minimum", material.min_quantity || 0],
          ["Wert", (material.total_value || 0) + " EUR"]
        ],
        url: "/inventory",
        actionLabel: "Lager öffnen"
      };
    }

    function timelineRecord(item) {
      return {
        title: item.title,
        subtitle: dateLabel(item.date),
        summary: item.summary || "Kein Kurztext hinterlegt.",
        badges: [[item.label || item.type, genericStatusBadgeClass(item.status)]],
        metrics: [
          ["Typ", item.label || item.type],
          ["Status", item.status || "-"]
        ],
        url: item.ui_url,
        actionLabel: "Quelle öffnen"
      };
    }

    function renderProfile(profile) {
      const permissions = profile.permissions || {};
      renderHero(profile);
      renderKpis(profile);
      renderMaster(profile);

      if (permissions.tasks === false) {
        renderDenied(profileList("[data-machine-profile-tasks]"));
      } else {
        renderRecords(
          profileList("[data-machine-profile-tasks]"),
          profile.open_tasks,
          "Keine offenen Aufgaben zur Maschine.",
          taskRecord,
          { href: "/tasks", label: "Aufgabe anlegen" }
        );
      }

      if (permissions.errors === false) {
        renderDenied(profileList("[data-machine-profile-errors]"));
        renderDenied(profileList("[data-machine-profile-error-history]"));
      } else {
        renderRecords(
          profileList("[data-machine-profile-errors]"),
          profile.active_errors,
          "Keine aktive Störung zur Maschine.",
          errorRecord,
          { href: "/errors", label: "Störung melden" }
        );
        renderRecords(
          profileList("[data-machine-profile-error-history]"),
          profile.error_history,
          "Noch keine Fehlerhistorie vorhanden.",
          errorRecord
        );
      }

      if (permissions.documents === false) {
        renderDenied(profileList("[data-machine-profile-documents]"));
      } else {
        const documents = profile.documents || {};
        const reportRecords = (documents.reports || []).map((item) => ({ item, type: "Bericht" }));
        const manualRecords = (documents.manuals || []).map((item) => ({ item, type: "Handbuch" }));
        renderRecords(
          profileList("[data-machine-profile-documents]"),
          reportRecords.concat(manualRecords),
          "Keine Dokumente oder Handbücher zugeordnet.",
          (entry) => documentRecord(entry.item, entry.type),
          { href: "/documents", label: "Dokument hochladen" }
        );
      }

      renderRecords(
        profileList("[data-machine-profile-maintenance]"),
        profile.maintenance_plans,
        "Keine Wartungspläne für diese Maschine.",
        maintenanceRecord,
        { href: "/machines", label: "Wartungsplan prüfen" }
      );

      if (permissions.shiftplans === false) {
        renderDenied(profileList("[data-machine-profile-handovers]"));
      } else {
        renderRecords(
          profileList("[data-machine-profile-handovers]"),
          profile.shift_handovers,
          "Keine Übergaben zur Maschine.",
          handoverRecord,
          { href: "/handover", label: "Übergabe erfassen" }
        );
      }

      if (permissions.inventory === false) {
        renderDenied(profileList("[data-machine-profile-materials]"));
      } else {
        renderRecords(
          profileList("[data-machine-profile-materials]"),
          profile.materials,
          "Keine Ersatzteile zugeordnet.",
          materialRecord,
          { href: "/inventory", label: "Lager öffnen" }
        );
      }

      renderRecords(
        profileList("[data-machine-profile-timeline]"),
        profile.timeline,
        "Noch keine Signale im Maschinenverlauf.",
        timelineRecord
      );
    }

    try {
      setStatusMessage(message, "Maschinenprofil wird geladen...");
      const payload = await api("/api/v1/machines/" + machineId + "/profile");
      const profile = profileData(payload);
      renderProfile(profile);
      setStatusMessage(message, "Maschinenprofil bereit.");
    } catch (error) {
      setStatusMessage(message, error.message || "Maschinenprofil konnte nicht geladen werden.", true);
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
    const frequentCodes = document.querySelector("[data-dashboard-frequent-codes]");
    const inventoryStats = document.querySelector("[data-dashboard-inventory-stats]");
    const inventoryShortages = document.querySelector("[data-dashboard-inventory-shortages]");
    const employeeOverview = document.querySelector("[data-dashboard-employee-overview]");
    const priorityList = document.querySelector("[data-dashboard-priority-list]");
    const briefingZusammenfassung = document.querySelector("[data-daily-briefing-summary]");
    const briefingList = document.querySelector("[data-daily-briefing-list]");
    const operationsInsights = document.querySelector("[data-operations-insights]");
    const operationsStatus = document.querySelector("[data-operations-insights-status]");
    const operationsSiteFilter = document.querySelector("[data-operations-site-filter]");
    const operationsRangeFilter = document.querySelector("[data-operations-range-filter]");
    const operationsRefresh = document.querySelector("[data-operations-refresh]");
    const operationsKpiGrid = document.querySelector("[data-operations-kpi-grid]");
    const operationsDrilldown = document.querySelector("[data-operations-drilldown]");
    const aiOpsStatus = document.querySelector("[data-ai-ops-status]");
    const aiOpsUpdated = document.querySelector("[data-ai-ops-updated]");
    const aiOpsPriorityRail = document.querySelector("[data-ai-ops-priority-rail]");
    const aiSystemRail = document.querySelector("[data-ai-system-rail]");
    const aiRiskRadar = document.querySelector("[data-ai-risk-radar]");
    const aiKnowledgeHealth = document.querySelector("[data-ai-knowledge-health]");
    const executiveActivityFeed = document.querySelector("[data-dashboard-activity-feed]");
    const executiveWarningFeed = document.querySelector("[data-dashboard-warning-feed]");
    const executiveAiTrust = document.querySelector("[data-dashboard-ai-trust]");
    const executiveMachineStrip = document.querySelector("[data-dashboard-machine-strip]");
    const criticalTodayPanel = document.querySelector("[data-dashboard-critical-today]");
    const machineCards = document.querySelector("[data-dashboard-machine-cards]");
    const handoverList = document.querySelector("[data-dashboard-handover-list]");
    const peopleHints = document.querySelector("[data-dashboard-people-hints]");
    const quickAiButtons = document.querySelectorAll("[data-dashboard-quick-ai]");
    const shiftCalendar = document.querySelector("[data-dashboard-shift-calendar]");
    const shiftTimeline = document.querySelector("[data-dashboard-shift-timeline]");
    const shiftCalendarMessage = document.querySelector("[data-dashboard-calendar-message]");
    const shiftCalendarEmployee = document.querySelector("[data-dashboard-calendar-employee]");
    if ((!taskBoard && !errorStats && !inventoryStats && !briefingList && !employeeOverview && !shiftTimeline && !operationsInsights && !executiveActivityFeed) || !token()) return;

    let activeTask = null;
    let activeTaskId = null;
    const dashboardState = {
      aiStatus: null,
      briefing: null,
      errors: [],
      handovers: [],
      employees: [],
      inventory: null,
      knowledgeGaps: null,
      knowledgeStatus: null,
      machines: [],
      operations: null,
      retrievalTelemetry: null,
      vacations: [],
      tasks: []
    };

    function announce(message, isError) {
      if (globalLive) globalLive.textContent = message;
      if (cockpitMessage) {
        cockpitMessage.textContent = message;
        cockpitMessage.classList.toggle("is-error", Boolean(isError));
        cockpitMessage.classList.toggle("is-success", Boolean(message && !isError));
      }
    }

    function todayIso() {
      return dashboardTodayIso();
    }

    function isOverdue(task) {
      return task.due_date && task.due_date < todayIso() && task.status !== "done";
    }

    function setDashboardText(selector, value) {
      setText(selector, value == null || value === "" ? "-" : value);
    }

    function formatRatePercent(value) {
      return Math.round(Number(value || 0) * 100) + "%";
    }

    function formatMilliseconds(value) {
      return Math.round(Number(value || 0)) + " ms";
    }

    function currentUserIsMasterAdmin() {
      const currentUser = user();
      return Boolean(currentUser && currentUser.role === "master_admin");
    }

    function dashboardSignalClass(severity) {
      if (severity === "critical") return "is-critical";
      if (severity === "warning") return "is-warning";
      if (severity === "good") return "is-good";
      return "is-muted";
    }

    function dashboardSignalRank(severity) {
      const ranks = { critical: 0, warning: 1, good: 2, muted: 3 };
      return ranks[severity] == null ? 3 : ranks[severity];
    }

    function dashboardWorstSeverity(signals) {
      if (signals.some((item) => item.severity === "critical")) return "critical";
      if (signals.some((item) => item.severity === "warning")) return "warning";
      return signals.length ? "good" : "muted";
    }

    function dashboardStatusLabel(severity) {
      if (severity === "critical") return "Kritische Lage";
      if (severity === "warning") return "Prüfen";
      if (severity === "good") return "Stabil";
      return "Noch keine Daten";
    }

    function emptyRailMessage(message) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = message;
      return empty;
    }

    function controlCenterBadge(label, severity) {
      return badge(label, "badge badge-status " + (
        severity === "critical" ? "is-open" :
          severity === "warning" ? "is-progress" :
            severity === "good" ? "is-done" : "is-neutral"
      ));
    }

    function controlCenterLinkCard(kind, title, meta, severity, href, actionLabel) {
      const card = document.createElement(href ? "a" : "article");
      card.className = "control-center-item " + dashboardSignalClass(severity);
      if (href) card.href = href;
      const marker = document.createElement("span");
      marker.className = "control-center-item-marker";
      marker.textContent = kind;
      const body = document.createElement("div");
      const heading = document.createElement("strong");
      const detail = document.createElement("small");
      heading.textContent = title || "Hinweis";
      detail.textContent = meta || "";
      body.append(heading, detail);
      const action = document.createElement("span");
      action.className = "control-center-item-action";
      action.textContent = actionLabel || (href ? "Öffnen" : "Status");
      card.append(marker, body, action);
      return card;
    }

    function taskMachineHint(task) {
      const text = [task.title, task.description].filter(Boolean).join(" ");
      const match = text.match(/\b(Maschine|Anlage|Presse|Linie)\s*[A-Za-z0-9\-_.]*/i);
      return match ? match[0] : ((task.department && task.department.name) || "Bereich offen");
    }

    function taskMetaLine(task) {
      const parts = [
        priorityLabel(task.priority),
        statusLabel(task.status),
        relativeDateLabel(task.due_date),
        taskMachineHint(task)
      ].filter(Boolean);
      return parts.join(" · ");
    }

    function activeDashboardErrors(errors) {
      const recentWindowDays = 30;
      return listData(errors)
        .filter((entry) => {
          const status = String(entry.status || "").toLowerCase();
          if (status === "closed") return false;
          if (!entry.last_seen_at) return false;
          const seenDate = isoDateOnly(entry.last_seen_at);
          return !seenDate || dateDiffDays(seenDate, todayIso()) <= recentWindowDays;
        })
        .sort((first, second) => {
          const severityRank = { critical: 0, high: 1, medium: 2, low: 3 };
          const firstRank = severityRank[String(first.severity || "").toLowerCase()] ?? 4;
          const secondRank = severityRank[String(second.severity || "").toLowerCase()] ?? 4;
          if (firstRank !== secondRank) return firstRank - secondRank;
          return String(second.last_seen_at || second.created_at || "").localeCompare(
            String(first.last_seen_at || first.created_at || "")
          );
        });
    }

    function renderCriticalToday() {
      if (!criticalTodayPanel) return;
      const activeTasks = dashboardState.tasks.filter((task) => task.status !== "done" && task.status !== "cancelled");
      const criticalTasks = activeTasks.filter((task) => task.priority === "urgent" || isOverdue(task));
      const activeErrors = activeDashboardErrors(dashboardState.errors);
      const inventory = dashboardState.inventory || (dashboardState.operations && dashboardState.operations.inventory) || {};
      const machines = (dashboardState.operations && dashboardState.operations.machines) || {};
      const items = [];
      criticalTasks.slice(0, 4).forEach((task) => {
        items.push(controlCenterLinkCard("TA", task.title, taskMetaLine(task), "critical", "/tasks", task.status === "open" ? "Starten" : "Prüfen"));
      });
      activeErrors.slice(0, 4).forEach((entry) => {
        const machine = (entry.machine_obj && entry.machine_obj.name) || entry.machine || "Maschine offen";
        const meta = [machine, entry.error_code || "ohne Code", relativeSeenLabel(entry.last_seen_at) || "aktiv"].filter(Boolean).join(" · ");
        const severity = entry.severity === "critical" || entry.severity === "high" ? "critical" : "warning";
        items.push(controlCenterLinkCard("ST", entry.title || entry.error_code || "Störung", meta, severity, "/errors?status=open", "Störung prüfen"));
      });
      if (Number(machines.machines_down || 0)) {
        items.push(controlCenterLinkCard("MA", machines.machines_down + " Maschinen down", (machines.faults || 0) + " Störungen im Zeitraum", "critical", "/machines", "Maschinen"));
      }
      if (Number(inventory.critical_shortage_count || 0)) {
        items.push(controlCenterLinkCard("LG", inventory.critical_shortage_count + " kritische Lagerengpässe", (inventory.low_stock_count || 0) + " Artikel unter Mindestbestand", "critical", "/inventory", "Lager"));
      }
      criticalTodayPanel.innerHTML = "";
      if (!items.length) {
        criticalTodayPanel.appendChild(emptyRailMessage("Keine kritischen Punkte für heute. Beobachte neue Störungen, Fälligkeiten und Engpässe."));
        return;
      }
      items.slice(0, 8).forEach((item) => criticalTodayPanel.appendChild(item));
    }

    function machineStatusSeverity(machine) {
      const status = keywordText(machine.status);
      if (status.includes("down") || status.includes("stor") || status.includes("error") || status.includes("stop")) {
        return "critical";
      }
      if (status.includes("wart") || status.includes("maintenance") || status.includes("pause") || status.includes("pruf")) {
        return "warning";
      }
      if (status.includes("run") || status.includes("aktiv") || status.includes("ok") || status.includes("bereit")) {
        return "good";
      }
      return "muted";
    }

    function machineStatusText(machine) {
      const status = String(machine.status || "unbekannt");
      if (status === "running") return "Läuft";
      if (status === "down") return "Stillstand";
      if (status === "maintenance") return "Wartung";
      return status;
    }

    function updateMachineKpis() {
      const operations = dashboardState.operations || {};
      const machineMetrics = operations.machines || {};
      const machines = dashboardState.machines || [];
      const total = Number(machineMetrics.machines_total || machines.length || 0);
      const down = Number(machineMetrics.machines_down || machines.filter((machine) => machineStatusSeverity(machine) === "critical").length || 0);
      const warning = machines.filter((machine) => machineStatusSeverity(machine) === "warning").length;
      const healthy = Math.max(0, total - down - warning);
      setDashboardText("[data-dashboard-machine-status]", total ? (healthy + "/" + total) : "--");
      setDashboardText(
        "[data-dashboard-machine-kpi-meta]",
        total ? down + " kritisch, " + warning + " beobachten" : "Keine Maschinen geladen"
      );
      setProgress("[data-dashboard-machine-progress]", total ? (healthy / total) * 100 : 4);
    }

    function renderMachineCards() {
      if (!machineCards) {
        updateMachineKpis();
        return;
      }
      machineCards.innerHTML = "";
      const machines = dashboardState.machines || [];
      if (!machines.length) {
        machineCards.appendChild(emptyRailMessage("Keine Maschinen im aktuellen Zugriff."));
        updateMachineKpis();
        return;
      }
      machines.slice(0, 6).forEach((machine) => {
        const severity = machineStatusSeverity(machine);
        const card = document.createElement("a");
        card.className = "machine-status-card " + dashboardSignalClass(severity);
        card.href = "/machines";
        const title = document.createElement("strong");
        title.textContent = machine.name || "Maschine";
        const meta = document.createElement("small");
        meta.textContent = machine.produced_item || "Produktionsdaten offen";
        const footer = document.createElement("div");
        footer.append(
          controlCenterBadge(machineStatusText(machine), severity),
          controlCenterBadge(machine.criticality || "normal", machine.criticality === "critical" ? "critical" : "muted")
        );
        card.append(title, meta, footer);
        machineCards.appendChild(card);
      });
      updateMachineKpis();
    }

    function formatDashboardDate(value) {
      if (!value) return "-";
      return new Date(value).toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" });
    }

    function renderHandoverList(handovers) {
      if (!handoverList) return;
      dashboardState.handovers = handovers || [];
      handoverList.innerHTML = "";
      setDashboardText("[data-dashboard-shift-status]", dashboardState.handovers.length || "--");
      setDashboardText(
        "[data-dashboard-shift-meta]",
        dashboardState.handovers.length ? dashboardState.handovers.length + " Übergaben heute" : "Keine Übergabe heute"
      );
      setProgress("[data-dashboard-shift-progress]", dashboardState.handovers.length ? 72 : 18);
      if (!dashboardState.handovers.length) {
        handoverList.appendChild(emptyRailMessage("Heute gibt es noch keine gespeicherte Schichtübergabe."));
        return;
      }
      dashboardState.handovers.slice(0, 4).forEach((handover) => {
        const card = document.createElement("a");
        card.className = "handover-card " + (handover.status === "completed" ? "is-good" : "is-warning");
        card.href = "/handover";
        const title = document.createElement("strong");
        title.textContent = (handover.shift_type || "Schicht") + " · " + (handover.department || "Bereich");
        const meta = document.createElement("small");
        meta.textContent = [
          formatDashboardDate(handover.shift_date),
          handover.open_tasks ? "offene Punkte vorhanden" : "keine offenen Punkte erfasst",
          handover.machine_notes ? "Maschinenhinweise" : ""
        ].filter(Boolean).join(" · ");
        card.append(title, meta, controlCenterBadge(handover.status === "completed" ? "Bestätigt" : "Offen", handover.status === "completed" ? "good" : "warning"));
        handoverList.appendChild(card);
      });
    }

    function renderPeopleHints() {
      if (!peopleHints) return;
      const vacations = dashboardState.vacations || [];
      const employees = dashboardState.employees || [];
      const absent = employees.filter((employee) => employeeStatus(employee) === "Abwesend");
      const hints = [];
      if (vacations.length) {
        hints.push(controlCenterLinkCard("UR", vacations.length + " offene Urlaubsanträge", "Genehmigen oder ablehnen", "warning", "/vacations", "Urlaub"));
      }
      if (absent.length) {
        hints.push(controlCenterLinkCard("AB", absent.length + " abwesend markiert", absent.slice(0, 2).map((employee) => employee.name).join(", "), "warning", "/employees", "Team"));
      }
      if (employees.length && !hints.length) {
        hints.push(controlCenterLinkCard("PE", employees.length + " Mitarbeitende sichtbar", "Keine offenen Personalwarnungen", "good", "/employees", "Personal"));
      }
      peopleHints.innerHTML = "";
      if (!hints.length) {
        peopleHints.appendChild(emptyRailMessage("Keine Personalhinweise im aktuellen Zugriff."));
      } else {
        hints.forEach((hint) => peopleHints.appendChild(hint));
      }
      setDashboardText("[data-dashboard-people-status]", vacations.length || absent.length || employees.length || "--");
      setDashboardText(
        "[data-dashboard-people-meta]",
        vacations.length ? vacations.length + " offene Urlaubsanträge" : (absent.length ? absent.length + " abwesend" : "Keine offenen Personalwarnungen")
      );
      setProgress("[data-dashboard-people-progress]", vacations.length || absent.length ? 45 : 88);
    }

    function cockpitSignal(label, value, detail, severity, href) {
      const element = document.createElement(href ? "a" : "article");
      element.className = "ai-signal-card " + dashboardSignalClass(severity);
      if (href) element.href = href;
      const marker = document.createElement("span");
      marker.className = "ai-signal-marker";
      marker.textContent = severity === "critical" ? "!" : (severity === "warning" ? "!" : "OK");
      const body = document.createElement("div");
      const title = document.createElement("strong");
      const amount = document.createElement("span");
      const meta = document.createElement("small");
      title.textContent = label;
      amount.textContent = String(value);
      meta.textContent = detail || "";
      body.append(title, meta);
      element.append(marker, body, amount);
      return element;
    }

    function systemStatusRow(label, value, detail, severity) {
      const rowElement = document.createElement("div");
      rowElement.className = "ai-system-row " + dashboardSignalClass(severity);
      const title = document.createElement("span");
      const amount = document.createElement("strong");
      const meta = document.createElement("small");
      title.textContent = label;
      amount.textContent = String(value == null || value === "" ? "-" : value);
      meta.textContent = detail || "";
      rowElement.append(title, amount, meta);
      return rowElement;
    }

    function retrievalSloValues() {
      const telemetry = dashboardState.retrievalTelemetry || {};
      const slo = telemetry.retrieval_slo || {};
      return slo.last_values || {};
    }

    function updateDashboardStatus(signals) {
      if (!aiOpsStatus) return;
      const severity = dashboardWorstSeverity(signals);
      aiOpsStatus.textContent = dashboardStatusLabel(severity);
      aiOpsStatus.className = "ops-status-pill " + dashboardSignalClass(severity);
      if (aiOpsUpdated) {
        aiOpsUpdated.textContent = "Aktualisiert " + new Date().toLocaleTimeString("de-DE", {
          hour: "2-digit",
          minute: "2-digit"
        });
      }
    }

    function renderPriorityRail() {
      if (!aiOpsPriorityRail) return;
      const signals = [];
      const activeTasks = dashboardState.tasks.filter((task) => task.status !== "done" && task.status !== "cancelled");
      const criticalTasks = activeTasks.filter((task) => task.priority === "urgent" || isOverdue(task));
      const operations = dashboardState.operations || {};
      const machines = operations.machines || {};
      const inventory = dashboardState.inventory || operations.inventory || {};
      const sloValues = retrievalSloValues();
      const gapCount = dashboardState.knowledgeGaps ? Number(dashboardState.knowledgeGaps.open_count || 0) : 0;
      const safetyRiskCount = Number(sloValues.safety_risk_count || 0);
      const lowConfidenceRate = Number(sloValues.low_confidence_rate || 0);
      const noQuelleRate = Number(sloValues.no_source_rate || 0);
      const staleIndexCount = Number(sloValues.stale_index_count || 0);

      if (criticalTasks.length) {
        signals.push({
          label: "Kritische Aufgaben",
          value: criticalTasks.length,
          detail: criticalTasks[0].title || "Sofort prüfen",
          severity: "critical",
          href: "/tasks"
        });
      }
      if (dashboardState.errors.length) {
        signals.push({
          label: "Offene Störungen",
          value: dashboardState.errors.length,
          detail: (dashboardState.errors[0].error_code || dashboardState.errors[0].title || "Fehlerliste"),
          severity: dashboardState.errors.length > 2 ? "critical" : "warning",
          href: "/errors"
        });
      }
      if (Number(machines.repeat_faults || 0)) {
        signals.push({
          label: "Wiederkehrende Probleme",
          value: machines.repeat_faults,
          detail: (machines.faults || 0) + " Störungen im Zeitraum",
          severity: "warning",
          href: "/errors"
        });
      }
      if (Number(inventory.critical_shortage_count || 0)) {
        signals.push({
          label: "Materialengpässe",
          value: inventory.critical_shortage_count,
          detail: (inventory.low_stock_count || 0) + " unter Mindestbestand",
          severity: "critical",
          href: "/inventory"
        });
      }
      if (safetyRiskCount) {
        signals.push({
          label: "Sicherheitsrisiken",
          value: safetyRiskCount,
          detail: "KI-Sicherheit Events im Fenster",
          severity: "critical",
          href: "/admin/ai"
        });
      }
      if (gapCount) {
        signals.push({
          label: "Wissenslücken",
          value: gapCount,
          detail: "offene Wissenslücken",
          severity: gapCount > 3 ? "critical" : "warning",
          href: "/admin/ai"
        });
      }
      if (lowConfidenceRate >= 0.15 || noQuelleRate >= 0.1) {
        signals.push({
          label: "Suchqualität",
          value: formatRatePercent(Math.max(lowConfidenceRate, noQuelleRate)),
          detail: "Niedrige Sicherheit oder fehlende Quellen",
          severity: lowConfidenceRate >= 0.25 || noQuelleRate >= 0.2 ? "critical" : "warning",
          href: "/admin/ai"
        });
      }
      if (staleIndexCount) {
        signals.push({
          label: "Veralteter Index",
          value: staleIndexCount,
          detail: "Dokumente sollten reindexiert werden",
          severity: "warning",
          href: "/admin/ai"
        });
      }

      signals.sort((first, second) => dashboardSignalRank(first.severity) - dashboardSignalRank(second.severity));
      aiOpsPriorityRail.innerHTML = "";
      if (!signals.length) {
        aiOpsPriorityRail.appendChild(emptyRailMessage("Keine kritischen Operations-Signale im aktuellen Datenfenster."));
      } else {
        signals.slice(0, 7).forEach((item) => {
          aiOpsPriorityRail.appendChild(cockpitSignal(
            item.label,
            item.value,
            item.detail,
            item.severity,
            item.href
          ));
        });
      }
      updateDashboardStatus(signals);
    }

    function renderRiskRadar() {
      if (!aiRiskRadar) return;
      const sloValues = retrievalSloValues();
      const rows = [
        ["Sicherheit", Number(sloValues.safety_risk_count || 0), "Sicherheitsereignisse", Number(sloValues.safety_risk_count || 0) ? "critical" : "good"],
        ["Niedrige Sicherheit", formatRatePercent(sloValues.low_confidence_rate), "Antworten unter Schwelle", Number(sloValues.low_confidence_rate || 0) >= 0.15 ? "warning" : "good"],
        ["Ohne Quellen", formatRatePercent(sloValues.no_source_rate), "Antworten ohne Quelle", Number(sloValues.no_source_rate || 0) >= 0.1 ? "warning" : "good"],
        ["Ausweichantworten", formatRatePercent(sloValues.fallback_rate), "KI-Anbieter oder Suche", Number(sloValues.fallback_rate || 0) >= 0.1 ? "warning" : "good"],
        ["Negatives Feedback", formatRatePercent(sloValues.negative_feedback_rate), "Nutzerrückmeldungen", Number(sloValues.negative_feedback_rate || 0) >= 0.1 ? "warning" : "good"],
        ["Berechtigungsfilter", Number(sloValues.permission_filtered_candidate_count || 0), "gefilterte Kandidaten", "muted"]
      ];
      aiRiskRadar.innerHTML = "";
      rows.forEach(([label, value, detail, severity]) => {
        aiRiskRadar.appendChild(systemStatusRow(label, value, detail, severity));
      });
    }

    function renderAiSystemRail() {
      if (!aiSystemRail) return;
      const aiStatus = dashboardState.aiStatus || {};
      const sloValues = retrievalSloValues();
      aiSystemRail.innerHTML = "";
      if (!currentUserIsMasterAdmin()) {
        aiSystemRail.appendChild(systemStatusRow(
          "Admin-Metriken",
          "eingeschränkt",
          "KI-Sicherheit, Quellenabruf und Indexdetails sind nur für Master-Admins sichtbar.",
          "muted"
        ));
        setDashboardText("[data-dashboard-ai-status]", "Basis");
        setDashboardText("[data-dashboard-ai-status-meta]", "Admin-Metriken eingeschränkt");
        return;
      }
      const ready = aiStatus.ready === true;
      aiSystemRail.append(
        systemStatusRow("KI-Anbieter", aiStatus.provider || "-", ready ? "bereit" : "prüfen", ready ? "good" : "warning"),
        systemStatusRow("Modell", aiStatus.model || "-", aiStatus.streaming_enabled ? "Streaming aktiv" : "Streaming aus", "muted"),
        systemStatusRow("Suchzeit P95", formatMilliseconds(sloValues.retrieval_p95_ms), "Antwortkontext", Number(sloValues.retrieval_p95_ms || 0) > 2500 ? "warning" : "good"),
        systemStatusRow("Ausweichantworten", formatRatePercent(sloValues.fallback_rate), "KI-Anbieter oder Suche", Number(sloValues.fallback_rate || 0) >= 0.1 ? "warning" : "good"),
        systemStatusRow("Index-Sync-Fehler", Number(sloValues.vector_sync_failure_count || 0), "Index-Synchronisation", Number(sloValues.vector_sync_failure_count || 0) ? "critical" : "good")
      );
      setDashboardText("[data-dashboard-ai-status]", ready ? "bereit" : "prüfen");
      setDashboardText("[data-dashboard-ai-status-meta]", aiStatus.provider || "KI-Anbieter unbekannt");
    }

    function renderKnowledgeHealth() {
      if (!aiKnowledgeHealth) return;
      const status = dashboardState.knowledgeStatus || {};
      const vectorStatus = status.vector_store || {};
      const gaps = dashboardState.knowledgeGaps || {};
      const indexed = Number(status.indexed || 0);
      const documents = Number(status.documents || 0);
      const chunks = Number(status.chunks || 0);
      const stale = Number(status.stale || 0);
      const missingTextabschnitte = Number(vectorStatus.missing_chunk_count || 0);
      const reindexNeeded = Boolean(vectorStatus.reindex_recommended);
      aiKnowledgeHealth.innerHTML = "";
      if (!currentUserIsMasterAdmin()) {
        aiKnowledgeHealth.appendChild(systemStatusRow(
          "Wissensstatus",
          "eingeschränkt",
          "Indexdetails sind im KI-Administration sichtbar.",
          "muted"
        ));
        return;
      }
      aiKnowledgeHealth.append(
        systemStatusRow("Dokumente indexiert", indexed + "/" + documents, chunks + " Textabschnitte", documents && indexed < documents ? "warning" : "good"),
        systemStatusRow("Veraltete Dokumente", stale, "Aging und Reindex", stale ? "warning" : "good"),
        systemStatusRow("Fehlende Textabschnitte", missingTextabschnitte, "DB zu Vektor Store", missingTextabschnitte ? "critical" : "good"),
        systemStatusRow("Reindex", reindexNeeded ? "empfohlen" : "nicht nötig", (vectorStatus.reindex_reasons || []).join(", "), reindexNeeded ? "warning" : "good"),
        systemStatusRow("Wissenslücken", Number(gaps.open_count || 0), "offene Lücken", Number(gaps.open_count || 0) ? "warning" : "good")
      );
      setDashboardText("[data-dashboard-index-status]", reindexNeeded ? "Reindex" : "OK");
      setDashboardText(
        "[data-dashboard-index-status-meta]",
        indexed + "/" + documents + " Dokumente, " + chunks + " Textabschnitte"
      );
      setDashboardText("[data-dashboard-knowledge-gap-count]", Number(gaps.open_count || 0));
      setDashboardText("[data-dashboard-knowledge-gap-meta]", "offene Lücken");
    }

    function applySloKpis() {
      const sloValues = retrievalSloValues();
      setDashboardText("[data-dashboard-safety-count]", Number(sloValues.safety_risk_count || 0));
      setDashboardText("[data-dashboard-low-confidence-count]", formatRatePercent(sloValues.low_confidence_rate));
      setDashboardText("[data-dashboard-retrieval-health]", formatMilliseconds(sloValues.retrieval_p95_ms));
      setDashboardText(
        "[data-dashboard-retrieval-health-meta]",
        formatRatePercent(sloValues.no_source_rate) + " ohne Quellen"
      );
    }

    function setProgress(selector, value) {
      document.querySelectorAll(selector).forEach((element) => {
        element.style.width = Math.max(0, Math.min(100, Number(value || 0))) + "%";
      });
    }

    function activityItem(kind, title, meta, severity, href) {
      const element = document.createElement(href ? "a" : "div");
      element.className = "activity-feed-item " + dashboardSignalClass(severity);
      if (href) element.href = href;
      const marker = document.createElement("span");
      marker.className = "activity-feed-marker";
      marker.textContent = kind;
      const body = document.createElement("div");
      const heading = document.createElement("strong");
      const detail = document.createElement("small");
      heading.textContent = title || "Hinweis";
      detail.textContent = meta || "";
      body.append(heading, detail);
      element.append(marker, body);
      return element;
    }

    function briefingSignalCount() {
      const briefing = dashboardState.briefing || {};
      const sections = Array.isArray(briefing.sections) ? briefing.sections : [];
      return sections.reduce((sum, section) => sum + Number(section.count || 0), 0);
    }

    function renderMachineStrip() {
      if (!executiveMachineStrip) return;
      const operations = dashboardState.operations || {};
      const machines = operations.machines || {};
      const inventory = dashboardState.inventory || operations.inventory || {};
      executiveMachineStrip.innerHTML = "";
      executiveMachineStrip.append(
        systemStatusRow("Maschinen down", Number(machines.machines_down || 0) + "/" + Number(machines.machines_total || 0), (machines.faults || dashboardState.errors.length || 0) + " Störungen", Number(machines.machines_down || 0) ? "critical" : "good"),
        systemStatusRow("Wiederholungen", Number(machines.repeat_faults || 0), "Fehlertrend im Zeitraum", Number(machines.repeat_faults || 0) ? "warning" : "good"),
        systemStatusRow("MTTR", formatMinutes(machines.mttr_minutes), formatMinutes(machines.downtime_minutes) + " Ausfallzeit", Number(machines.mttr_minutes || 0) > 0 ? "warning" : "good"),
        systemStatusRow("Lager kritisch", Number(inventory.critical_shortage_count || 0), (inventory.low_stock_count || 0) + " niedrig", Number(inventory.critical_shortage_count || 0) ? "critical" : "good")
      );
    }

    function renderAiTrustPanel() {
      if (!executiveAiTrust) return;
      const sloValues = retrievalSloValues();
      const gapCount = dashboardState.knowledgeGaps ? Number(dashboardState.knowledgeGaps.open_count || 0) : 0;
      executiveAiTrust.innerHTML = "";
      executiveAiTrust.append(
        systemStatusRow("Niedrige Sicherheit", formatRatePercent(sloValues.low_confidence_rate), "Antworten unter Schwelle", Number(sloValues.low_confidence_rate || 0) >= 0.15 ? "warning" : "good"),
        systemStatusRow("Suchzeit P95", formatMilliseconds(sloValues.retrieval_p95_ms), formatRatePercent(sloValues.no_source_rate) + " ohne Quellen", Number(sloValues.retrieval_p95_ms || 0) > 2500 || Number(sloValues.no_source_rate || 0) >= 0.1 ? "warning" : "good"),
        systemStatusRow("Sicherheit", Number(sloValues.safety_risk_count || 0), "Sicherheitsereignisse im Fenster", Number(sloValues.safety_risk_count || 0) ? "critical" : "good"),
        systemStatusRow("Wissenslücken", gapCount, "offene Wissenslücken", gapCount ? "warning" : "good")
      );
    }

    function renderExecutiveWarnings() {
      if (!executiveWarningFeed) return;
      const activeTasks = dashboardState.tasks.filter((task) => task.status !== "done" && task.status !== "cancelled");
      const criticalTasks = activeTasks.filter((task) => task.priority === "urgent" || isOverdue(task));
      const sloValues = retrievalSloValues();
      const gapCount = dashboardState.knowledgeGaps ? Number(dashboardState.knowledgeGaps.open_count || 0) : 0;
      const items = [];
      if (criticalTasks.length) items.push(activityItem("KR", criticalTasks.length + " kritische Aufgaben", "Sofort priorisieren", "critical", "/tasks"));
      if (dashboardState.errors.length) items.push(activityItem("ST", dashboardState.errors.length + " offene Störungen", "Maschinenlage prüfen", dashboardState.errors.length > 2 ? "critical" : "warning", "/errors"));
      if (Number(sloValues.safety_risk_count || 0)) items.push(activityItem("SF", Number(sloValues.safety_risk_count || 0) + " Sicherheitsrisiken", "AI Antworten prüfen", "critical", "/admin/ai"));
      if (gapCount) items.push(activityItem("KG", gapCount + " Wissenslücken", "Wissensbasis ergänzen", "warning", "/admin/ai"));
      if (Number(sloValues.stale_index_count || 0)) items.push(activityItem("IX", Number(sloValues.stale_index_count || 0) + " veraltete Indexeinträge", "Reindex empfohlen", "warning", "/admin/ai"));
      executiveWarningFeed.innerHTML = "";
      if (!items.length) {
        executiveWarningFeed.appendChild(emptyRailMessage("Keine kritischen Warnungen im aktuellen Datenfenster."));
        return;
      }
      items.slice(0, 6).forEach((item) => executiveWarningFeed.appendChild(item));
    }

    function renderActivityFeed() {
      if (!executiveActivityFeed) return;
      const items = [];
      dashboardState.tasks.slice(0, 3).forEach((task) => {
        items.push(activityItem("TA", task.title || "Aufgabe", (task.priority || "normal") + " - " + (task.status || "offen"), task.priority === "urgent" || isOverdue(task) ? "warning" : "muted", "/tasks"));
      });
      dashboardState.errors.slice(0, 3).forEach((entry) => {
        items.push(activityItem("FE", entry.title || entry.error_code || "Störung", ((entry.machine_obj && entry.machine_obj.name) || entry.machine || "Maschine") + " - " + formatDashboardTime(entry.created_at), "warning", "/errors"));
      });
      const briefing = dashboardState.briefing || {};
      const sections = Array.isArray(briefing.sections) ? briefing.sections : [];
      sections.slice(0, 2).forEach((section) => {
        items.push(activityItem("AI", section.title || "Briefing", Number(section.count || 0) + " Hinweise", "muted", "#daily-briefing"));
      });
      const sloValues = retrievalSloValues();
      if (Number(sloValues.no_source_rate || 0) >= 0.1) {
        items.push(activityItem("RG", "Antworten ohne Quellen", formatRatePercent(sloValues.no_source_rate), "warning", "/admin/ai"));
      }
      executiveActivityFeed.innerHTML = "";
      if (!items.length) {
        executiveActivityFeed.appendChild(emptyRailMessage("Noch keine Aktivitäten im aktuellen Datenfenster."));
        return;
      }
      items.slice(0, 8).forEach((item) => executiveActivityFeed.appendChild(item));
    }

    function renderExecutiveKpis() {
      const activeTasks = dashboardState.tasks.filter((task) => task.status !== "done" && task.status !== "cancelled");
      const doneTasks = dashboardState.tasks.filter((task) => task.status === "done");
      const criticalTasks = activeTasks.filter((task) => task.priority === "urgent" || isOverdue(task));
      const activityCount = dashboardState.errors.length + dashboardState.tasks.length + briefingSignalCount();
      const sloValues = retrievalSloValues();
      const hasRisk = Boolean(criticalTasks.length || dashboardState.errors.length || Number(sloValues.safety_risk_count || 0) || Number(sloValues.vector_sync_failure_count || 0) || Number(sloValues.stale_index_count || 0));
      setDashboardText("[data-dashboard-unresolved-errors]", dashboardState.errors.length);
      setDashboardText("[data-dashboard-today-activity-count]", activityCount);
      setDashboardText("[data-dashboard-active-integrations]", currentUserIsMasterAdmin() ? "Assistenz" : "Basis");
      setDashboardText("[data-dashboard-system-status]", hasRisk ? "Prüfen" : "Stabil");
      setDashboardText("[data-dashboard-system-meta]", hasRisk ? "Warnungen aktiv" : "Keine kritischen Signale");
      setProgress("[data-dashboard-open-progress]", activeTasks.length ? Math.min(100, activeTasks.length * 8) : 4);
      setProgress("[data-dashboard-critical-progress]", criticalTasks.length ? Math.min(100, criticalTasks.length * 20) : 4);
      setProgress("[data-dashboard-done-progress]", dashboardState.tasks.length ? (doneTasks.length / dashboardState.tasks.length) * 100 : 4);
      setProgress("[data-dashboard-error-progress]", dashboardState.errors.length ? Math.min(100, dashboardState.errors.length * 18) : 4);
      setProgress("[data-dashboard-activity-progress]", activityCount ? Math.min(100, activityCount * 6) : 4);
      setProgress("[data-dashboard-ai-progress]", Number(sloValues.low_confidence_rate || 0) >= 0.15 ? 45 : 88);
      setProgress("[data-dashboard-integration-progress]", currentUserIsMasterAdmin() ? 75 : 35);
      setProgress("[data-dashboard-system-progress]", hasRisk ? 48 : 92);
    }

    function renderExecutiveDashboard() {
      renderExecutiveKpis();
      renderCriticalToday();
      renderMachineCards();
      renderPeopleHints();
      renderMachineStrip();
      renderAiTrustPanel();
      renderExecutiveWarnings();
      renderActivityFeed();
    }

    async function loadAiOperationsSignals() {
      if (!aiSystemRail && !aiRiskRadar && !aiKnowledgeHealth) return;
      if (!currentUserIsMasterAdmin()) {
        renderAiSystemRail();
        renderRiskRadar();
        renderKnowledgeHealth();
        renderExecutiveDashboard();
        return;
      }
      const [aiStatusResult, telemetryResult, knowledgeStatusResult, gapResult] = await Promise.allSettled([
        api("/api/v1/ai/status"),
        api("/api/v1/admin/ai/retrieval-telemetry?days=7&limit=5"),
        api("/api/v1/admin/ai/knowledge/status"),
        api("/api/v1/admin/ai/knowledge-gaps?status=open&limit=5")
      ]);
      if (aiStatusResult.status === "fulfilled") dashboardState.aiStatus = aiStatusResult.value;
      if (telemetryResult.status === "fulfilled") dashboardState.retrievalTelemetry = telemetryResult.value;
      if (knowledgeStatusResult.status === "fulfilled") dashboardState.knowledgeStatus = knowledgeStatusResult.value;
      if (gapResult.status === "fulfilled") dashboardState.knowledgeGaps = gapResult.value;
      applySloKpis();
      renderAiSystemRail();
      renderRiskRadar();
      renderKnowledgeHealth();
      renderExecutiveDashboard();
    }

    function updateDashboardAufgabeMetrics(tasks) {
      dashboardState.tasks = tasks;
      const activeTasks = tasks.filter((task) => task.status !== "done" && task.status !== "cancelled");
      const openAufgaben = activeTasks.filter((task) => task.status === "open");
      const progressAufgaben = activeTasks.filter((task) => task.status === "in_progress");
      const doneTasks = tasks.filter((task) => task.status === "done");
      const criticalTasks = activeTasks.filter((task) => task.priority === "urgent" || isOverdue(task));
      taskCountElements.forEach((taskCount) => {
        taskCount.textContent = String(tasks.length);
      });
      setText("[data-dashboard-open-count]", openAufgaben.length);
      setText("[data-dashboard-progress-count]", progressAufgaben.length);
      setText("[data-dashboard-done-count]", doneTasks.length);
      setText("[data-dashboard-critical-count]", criticalTasks.length);
      renderExecutiveDashboard();
      setDashboardText("[data-dashboard-open-meta]", progressAufgaben.length + " in Arbeit");
      setDashboardText("[data-dashboard-critical-meta]", criticalTasks.length ? "sofort prüfen" : "keine kritische Arbeit");
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
        taskEditField("Fällig am", dueDate),
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
          const updatedAufgabe = await api("/api/v1/tasks/" + task.id);
          renderAufgabeDetail(updatedAufgabe);
          await loadDashboardAufgaben();
          showAufgabeMessage("Aufgabe aktualisiert.");
        } catch (error) {
          showAufgabeMessage(error.message, true);
        } finally {
          submit.disabled = false;
        }
      });
      return editForm;
    }

    function showAufgabeMessage(message, isError) {
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

    function updateAufgabeActionButtons(task, isBusy) {
      if (taskStartButton) {
        taskStartButton.hidden = !canWrite("tasks");
        taskStartButton.disabled = Boolean(isBusy) || task.status !== "open";
      }
      if (taskCompleteButton) {
        taskCompleteButton.hidden = !canWrite("tasks");
        taskCompleteButton.disabled = Boolean(isBusy) || task.status === "done" || task.status === "cancelled";
      }
    }

    function renderAufgabeDetail(task) {
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
      updateAufgabeActionButtons(task);
      showAufgabeMessage("");
    }

    async function openAufgabeDetail(taskId) {
      const task = await api("/api/v1/tasks/" + taskId);
      renderAufgabeDetail(task);
      if (taskDetailModal) {
        taskDetailModal.hidden = false;
        const closeButton = taskDetailModal.querySelector("[data-task-detail-close]");
        if (closeButton) closeButton.focus();
      }
    }

    async function runTaskAction(taskId, action, body) {
      const path = "/api/v1/tasks/" + taskId + "/" + action;
      const success = action === "start" ? "Aufgabe gestartet." : "Aufgabe abgeschlossen.";
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
          renderAufgabeDetail(await api("/api/v1/tasks/" + taskId));
          showAufgabeMessage(success + suffix);
        }
        await loadDashboardAufgaben();
      } catch (error) {
        announce(error.message, true);
        showAufgabeMessage(error.message, true);
      }
    }

    function emptyCockpitCard(groupName) {
      const card = document.createElement("article");
      card.className = "cockpit-task-card is-empty";
      const text = document.createElement("p");
      text.textContent = groupName === "urgent"
        ? "Keine kritischen Aufgaben. Beobachte neue Störungen und überfällige Arbeit."
        : groupName === "today"
          ? "Keine Aufgaben für heute. Neue Arbeit kannst du direkt aus dem Cockpit anlegen."
          : "Keine Aufgaben in Arbeit. Starte offene Aufgaben, sobald Verantwortung und Material klar sind.";
      card.appendChild(text);
      if (cockpitSuggestForm && canWrite("tasks")) {
        const captureButton = actionButton("Aufgaben öffnen", () => {
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

    function cockpitAufgabeCard(task) {
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
        relativeDateLabel(task.due_date),
        task.current_worker ? formatUser(task.current_worker) : null
      ].filter(Boolean).forEach((value) => {
        const item = document.createElement("span");
        item.textContent = value;
        meta.appendChild(item);
      });
      const actions = document.createElement("div");
      actions.className = "cockpit-task-actions";
      actions.appendChild(actionButton("Details", () => openAufgabeDetail(task.id)));
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

    async function loadDashboardAufgaben() {
      const tasks = listData(await api("/api/v1/tasks?limit=100"));
      const lists = {
        urgent: document.querySelector("[data-cockpit-list='urgent']"),
        today: document.querySelector("[data-cockpit-list='today']"),
        progress: document.querySelector("[data-cockpit-list='progress']")
      };
      Object.values(lists).forEach((list) => {
        if (list) list.innerHTML = "";
      });
      updateDashboardAufgabeMetrics(tasks);
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
        group.forEach((task) => list.appendChild(cockpitAufgabeCard(task)));
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
        setFormBusy(cockpitSuggestForm, true, "Erstellt...");
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
            suggestion.possible_cause ? "Mögliche Ursache: " + suggestion.possible_cause : "",
            suggestion.recommended_action ? "Nächste Aktion: " + suggestion.recommended_action : ""
          ].filter(Boolean).join("\n\n");
          announce("Vorschlag erstellt. Bitte prüfen und speichern.");
        } catch (error) {
          announce(error.message, true);
        } finally {
          setFormBusy(cockpitSuggestForm, false);
        }
      });

      cockpitDraft.addEventListener("submit", async (event) => {
        event.preventDefault();
        const data = Object.fromEntries(new FormData(cockpitDraft).entries());
        setFormBusy(cockpitDraft, true, "Speichert...");
        try {
          await api("/api/v1/tasks", { method: "POST", body: JSON.stringify(data) });
          cockpitSuggestForm.reset();
          cockpitDraft.reset();
          cockpitDraft.hidden = true;
          announce("Aufgabe gespeichert.");
          await loadDashboardAufgaben();
        } catch (error) {
          announce(error.message, true);
        } finally {
          setFormBusy(cockpitDraft, false);
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

    quickAiButtons.forEach((button) => {
      if (button.dataset.bound === "true") return;
      button.addEventListener("click", () => {
        const chatToggle = document.querySelector(".chat-toggle");
        const chatInput = document.querySelector("#chat-message-input, [data-chat-input], textarea[name='message']");
        if (chatToggle) chatToggle.click();
        window.setTimeout(() => {
          if (chatInput && typeof chatInput.focus === "function") chatInput.focus();
        }, 120);
      });
      button.dataset.bound = "true";
    });

    function rowLikeStat(label, value) {
      const item = document.createElement("div");
      item.className = "stat-row";
      item.innerHTML = `<span>${label}</span><strong>${value}</strong>`;
      return item;
    }

    function briefingClass(severity) {
      if (severity === "critical" || severity === "urgent") return "is-critical";
      if (severity === "warning" || severity === "soon" || severity === "high") return "is-warning";
      return "is-success";
    }

    function briefingIcon(section, item) {
      if (section && section.type === "knowledge") return "AI";
      if (item && (item.severity === "critical" || item.severity === "urgent")) return "!";
      if (item && (item.severity === "warning" || item.severity === "soon")) return "!";
      return "OK";
    }

    function briefingItem(section, item) {
      const element = document.createElement(item && item.url ? "a" : "div");
      element.className = "briefing-item " + briefingClass(item && item.severity);
      if (item && item.url) element.href = item.url;
      const icon = document.createElement("span");
      icon.textContent = briefingIcon(section, item);
      const title = document.createElement("strong");
      title.textContent = (item && item.title) || "Hinweis";
      const meta = document.createElement("small");
      meta.textContent = (item && (item.summary || item.severity)) || "";
      element.append(icon, title, meta);
      return element;
    }

    function emptyDashboardMessage(message) {
      const empty = document.createElement("div");
      empty.className = "guided-empty-state";
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
      dashboardState.employees = employees;
      employeeOverview.innerHTML = "";
      employeeOverview.appendChild(employeeRow(null, true));
      if (!employees.length) {
        employeeOverview.appendChild(emptyDashboardMessage("Keine Mitarbeiterdaten verfügbar."));
        renderPeopleHints();
        return;
      }
      employees.slice(0, 5).forEach((employee) => {
        employeeOverview.appendChild(employeeRow(employee));
      });
      renderPeopleHints();
    }

    function incidentBadge(entry) {
      const severity = String(entry && entry.severity || "").toLowerCase();
      if (severity === "critical" || severity === "high") {
        return badge("Aktiv", "badge badge-priority is-urgent");
      }
      return badge("Aktiv", "badge badge-priority is-soon");
    }

    function renderFrequentCodes(errors) {
      if (!frequentCodes) return;
      const counts = errors.reduce((items, entry) => {
        const code = entry.error_code || entry.code || "ohne Code";
        items[code] = (items[code] || 0) + 1;
        return items;
      }, {});
      frequentCodes.innerHTML = "";
      const sortedCodes = Object.entries(counts)
        .sort((first, second) => second[1] - first[1])
        .slice(0, 5);
      if (!sortedCodes.length) {
        frequentCodes.appendChild(emptyDashboardMessage("Keine Fehlercodes im aktuellen Fenster."));
        return;
      }
      sortedCodes.forEach(([code, count]) => {
        const item = document.createElement("span");
        const amount = document.createElement("strong");
        item.textContent = code;
        amount.textContent = String(count);
        item.appendChild(amount);
        frequentCodes.appendChild(item);
      });
    }

    function renderIncidentRows(errors) {
      if (!errorStats) return;
      const activeErrors = activeDashboardErrors(errors);
      dashboardState.errors = activeErrors;
      renderFrequentCodes(activeErrors);
      errorStats.innerHTML = "";
      if (!activeErrors.length) {
        errorStats.appendChild(emptyDashboardMessage("Keine aktiven Störungen im aktuellen Fenster."));
        setDashboardText("[data-dashboard-machine-status]", "0");
        renderExecutiveDashboard();
        setDashboardText("[data-dashboard-machine-status-meta]", "keine aktiven Störungen");
        return;
      }
      activeErrors.slice(0, 5).forEach((entry) => {
        const rowElement = document.createElement("div");
        rowElement.className = "incident-row";

        const title = document.createElement("strong");
        title.textContent = entry.title || entry.error_code || "Störung";

        const machine = document.createElement("span");
        machine.textContent = (entry.machine_obj && entry.machine_obj.name) || entry.machine || "-";

        const time = document.createElement("span");
        time.textContent = relativeSeenLabel(entry.last_seen_at) || formatDashboardTime(entry.created_at);

        const status = badge(statusLabel(entry.status), "badge badge-status is-progress");
        rowElement.append(incidentBadge(entry), title, machine, time, status);
        errorStats.appendChild(rowElement);
      });
      setDashboardText("[data-dashboard-machine-status]", String(activeErrors.length));
      renderExecutiveDashboard();
      setDashboardText("[data-dashboard-machine-status-meta]", "aktive Störungen");
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

    function inventoryCountsFromZusammenfassung(summary, materials) {
      const counts = summary && summary.status_counts;
      if (counts) {
        return {
          critical: Number(counts.critical || 0),
          low: Number(counts.low || 0),
          ok: Number(counts.ok || 0)
        };
      }
      return inventoryStatusCounts(materials);
    }

    function inventoryShortagesFromZusammenfassung(summary, materials) {
      if (summary && Array.isArray(summary.top_shortages)) {
        return summary.top_shortages;
      }
      return materials
        .slice()
        .sort((first, second) => Number(first.quantity || 0) - Number(second.quantity || 0))
        .slice(0, 3);
    }

    function renderInventoryZusammenfassung(summary) {
      if (!inventoryStats) return;
      dashboardState.inventory = summary || {};
      const materials = Array.isArray(summary.materials) ? summary.materials : [];
      const counts = inventoryCountsFromZusammenfassung(summary, materials);
      const shortages = inventoryShortagesFromZusammenfassung(summary, materials);
      inventoryStats.innerHTML = "";
      inventoryStats.append(
        inventoryMetric("Kritisch", String(counts.critical), "Artikel"),
        inventoryMetric("Niedrig", String(counts.low), "Artikel"),
        inventoryMetric("OK", String(counts.ok), "Artikel"),
        inventoryMetric("Gesamtwert", formatMoney(summary.total_value), "Lagerwert")
      );
      if (!inventoryShortages) return;
      inventoryShortages.innerHTML = "";
      shortages.forEach((material) => {
        const item = document.createElement("span");
        const amount = document.createElement("strong");
        amount.textContent = String(material.quantity || 0) + " Stk.";
        item.append(document.createTextNode(material.name || "Material"), amount);
        inventoryShortages.appendChild(item);
      });
      if (!shortages.length) {
        inventoryShortages.appendChild(emptyDashboardMessage("Keine Lagerdaten verfügbar."));
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
        setDashboardText("[data-dashboard-shift-status]", "--");
        setDashboardText("[data-dashboard-shift-meta]", calendar.message);
        setProgress("[data-dashboard-shift-progress]", 8);
        return;
      }
      const now = new Date();
      const entries = Array.isArray(calendar.entries) ? calendar.entries : [];
      const today = todayIso();
      const todayEntries = entries.filter((entry) => entry.work_date === today && entry.shift !== "Frei");
      setDashboardText("[data-dashboard-shift-status]", todayEntries.length ? todayEntries.length + "/3" : "--");
      setDashboardText(
        "[data-dashboard-shift-meta]",
        todayEntries.length ? todayEntries.length + " Schichtbelegungen heute" : "Keine Schichtdaten heute"
      );
      setProgress("[data-dashboard-shift-progress]", todayEntries.length ? Math.min(100, (todayEntries.length / 3) * 100) : 12);
      const byShift = new Map(todayEntries.map((entry) => [entry.shift, entry]));
      const activeShiftKey = currentShiftKey(now);
      shiftTimeline.append(
        timelineRow("Frühschicht", "Frueh", "06:00", "14:00", "is-green", byShift.get("Frueh"), activeShiftKey),
        timelineRow("Spätschicht", "Spaet", "14:00", "22:00", "is-blue", byShift.get("Spaet"), activeShiftKey),
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
        priorityList.appendChild(priorityInsightCard("KI-Priorisierung", "Nicht verfügbar", "is-muted"));
        return;
      }
      if (!priorities.length) {
        priorityList.appendChild(priorityInsightCard("KI-Priorisierung", "Keine offenen Aufgaben", "is-muted"));
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

    function isoDateDaysAgo(days) {
      const date = new Date();
      date.setDate(date.getDate() - Math.max(0, Number(days || 30) - 1));
      return date.toISOString().slice(0, 10);
    }

    function todayIsoDate() {
      return new Date().toISOString().slice(0, 10);
    }

    function formatMinutes(value) {
      const minutes = Number(value || 0);
      if (minutes >= 60) return (minutes / 60).toFixed(1).replace(".", ",") + " h";
      return Math.round(minutes) + " min";
    }

    function formatPercent(value) {
      return Math.round(Number(value || 0)) + "%";
    }

    function formatCompactNumber(value) {
      return new Intl.NumberFormat("de-DE", { maximumFractionDigits: 1 }).format(Number(value || 0));
    }

    function formatUsd(value) {
      return new Intl.NumberFormat("de-DE", { style: "currency", currency: "USD" }).format(Number(value || 0));
    }

    function operationsParams() {
      const params = new URLSearchParams();
      const days = operationsRangeFilter ? operationsRangeFilter.value : "30";
      params.set("from", isoDateDaysAgo(days));
      params.set("to", todayIsoDate());
      if (operationsSiteFilter && operationsSiteFilter.value) {
        params.set("site_id", operationsSiteFilter.value);
      }
      return params.toString();
    }

    function operationsCard(label, value, detail, variant) {
      const card = document.createElement("article");
      card.className = "ops-insight-card" + (variant ? " " + variant : "");
      const title = document.createElement("span");
      title.textContent = label;
      const amount = document.createElement("strong");
      amount.textContent = value;
      const meta = document.createElement("small");
      meta.textContent = detail;
      card.append(title, amount, meta);
      return card;
    }

    function renderOperationsCards(summary) {
      if (!operationsKpiGrid) return;
      dashboardState.operations = summary || {};
      const tasks = summary.tasks || {};
      const machines = summary.machines || {};
      const inventory = summary.inventory || {};
      const workforce = summary.workforce || {};
      const documents = summary.documents || {};
      const aiQuality = summary.ai_quality || {};
      setDashboardText("[data-dashboard-recurring-count]", Number(machines.repeat_faults || 0));
      setDashboardText("[data-dashboard-machine-status]", Number(machines.machines_down || 0) + "/" + Number(machines.machines_total || 0));
      renderExecutiveDashboard();
      setDashboardText(
        "[data-dashboard-machine-status-meta]",
        (machines.faults || 0) + " Störungen, " + formatMinutes(machines.downtime_minutes) + " Ausfall"
      );
      operationsKpiGrid.innerHTML = "";
      operationsKpiGrid.append(
        operationsCard("Offene Aufgaben", String(tasks.open || 0), (tasks.overdue || 0) + " überfällig", tasks.overdue ? "is-risk" : ""),
        operationsCard("MTTR", formatMinutes(machines.mttr_minutes), (machines.downtime_minutes || 0) + " min Ausfall", machines.mttr_minutes ? "is-warning" : ""),
        operationsCard("Wiederholstörungen", String(machines.repeat_faults || 0), (machines.faults || 0) + " Störungen", machines.repeat_faults ? "is-risk" : ""),
        operationsCard("Materialengpässe", String(inventory.critical_shortage_count || 0), (inventory.low_stock_count || 0) + " unter Mindestbestand", inventory.critical_shortage_count ? "is-risk" : ""),
        operationsCard("Schichtdeckung", formatPercent(workforce.avg_coverage_percent), (workforce.critical_conflicts || 0) + " kritische Konflikte", workforce.critical_conflicts ? "is-warning" : ""),
        operationsCard("Dokumentqualität", formatCompactNumber(documents.avg_quality_score), (documents.quality_checked || 0) + " geprüft", documents.avg_quality_score < 70 && documents.quality_checked ? "is-warning" : ""),
        operationsCard("KI-Feedback", String(aiQuality.feedback_count || 0), formatUsd(aiQuality.estimated_cost_usd || 0) + " geschätzt", ""),
        operationsCard("Events", String((summary.events || {}).total || 0), "pseudonymisiert erfasst", "")
      );
    }

    function operationsDrilldownRow(label, value, meta) {
      const rowElement = document.createElement("div");
      rowElement.className = "ops-drilldown-row";
      const title = document.createElement("strong");
      title.textContent = label;
      const amount = document.createElement("span");
      amount.textContent = value;
      const detail = document.createElement("small");
      detail.textContent = meta || "";
      rowElement.append(title, amount, detail);
      return rowElement;
    }

    function renderOperationsDrilldown(summary) {
      if (!operationsDrilldown) return;
      const inventory = summary.inventory || {};
      const machines = summary.machines || {};
      const events = summary.events || {};
      operationsDrilldown.innerHTML = "";
      const shortages = Array.isArray(inventory.top_shortages) ? inventory.top_shortages : [];
      if (shortages.length) {
        shortages.slice(0, 4).forEach((item) => {
          operationsDrilldown.appendChild(operationsDrilldownRow(
            item.name || "Material",
            String(item.quantity || 0) + " / " + String(item.min_quantity || 0),
            item.criticality || "normal"
          ));
        });
      }
      const causes = machines.top_cause_categories || {};
      Object.entries(causes).slice(0, 4).forEach(([cause, count]) => {
        operationsDrilldown.appendChild(operationsDrilldownRow(
          cause === "unknown" ? "Ursache offen" : cause,
          String(count),
          "Störungskategorie"
        ));
      });
      Object.entries(events.by_feature || {}).slice(0, 4).forEach(([feature, count]) => {
        operationsDrilldown.appendChild(operationsDrilldownRow(feature, String(count), "Events im Zeitraum"));
      });
      if (!operationsDrilldown.children.length) {
        operationsDrilldown.appendChild(emptyDashboardMessage("Noch keine Operations-Events im gewählten Zeitraum."));
      }
    }

    async function loadOperationsSites() {
      if (!operationsSiteFilter || operationsSiteFilter.dataset.loaded === "true") return;
      try {
        const sites = listData(await api("/api/v1/sites"));
        sites.forEach((site) => {
          const option = document.createElement("option");
          option.value = String(site.id);
          option.textContent = site.name || site.code || ("Werk " + site.id);
          operationsSiteFilter.appendChild(option);
        });
        operationsSiteFilter.dataset.loaded = "true";
      } catch (error) {
        operationsSiteFilter.hidden = true;
      }
    }

    async function loadOperationsInsights(triggerButton) {
      if (!operationsInsights || !canView("dashboard")) return;
      if (operationsStatus) {
        operationsStatus.textContent = "Kennzahlen werden geladen...";
        operationsStatus.classList.remove("is-error");
      }
      await runAction({
        button: triggerButton || operationsRefresh,
        busyText: "Lädt...",
        toast: false,
        rethrow: true,
        action: async () => {
          await loadOperationsSites();
          const summary = await api("/api/v1/operations/summary?" + operationsParams());
          renderOperationsCards(summary);
          renderOperationsDrilldown(summary);
          if (operationsStatus) {
            operationsStatus.textContent = "Aktualisiert: " + new Date().toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
          }
          return summary;
        }
      }).catch((error) => {
        if (operationsStatus) {
          operationsStatus.textContent = error.message || "Operations-KPIs konnten nicht geladen werden.";
          operationsStatus.classList.add("is-error");
        }
        if (operationsKpiGrid) {
          operationsKpiGrid.innerHTML = "";
          operationsKpiGrid.appendChild(operationsCard("Status", "Fehler", "Bitte später erneut versuchen", "is-risk"));
        }
      });
    }

    function renderDailyBriefing(briefing) {
      dashboardState.briefing = briefing || {};
      briefing.sections = Array.isArray(briefing.sections) ? briefing.sections : [];
      if (briefingZusammenfassung) briefingZusammenfassung.textContent = briefing.summary;
      briefingList.innerHTML = "";
      const briefingCount = briefing.sections.reduce((sum, section) => sum + (section.count || 0), 0);
      setText("[data-dashboard-briefing-count]", briefingCount);
      renderExecutiveDashboard();
      if (!briefing.sections.length) {
        briefingList.appendChild(rowLikeStat("Status", "Keine Hinweise"));
        return;
      }
      briefing.sections.forEach((section) => {
        briefingList.appendChild(rowLikeStat(section.title, String(section.count)));
        section.items.slice(0, 2).forEach((item) => {
          briefingList.appendChild(briefingItem(section, item));
        });
      });
    }

    async function loadDailyBriefing() {
      if (!briefingList) return;
      const pendingTimer = window.setTimeout(() => {
        if (briefingZusammenfassung) briefingZusammenfassung.textContent = "Briefing wird aktualisiert.";
        briefingList.innerHTML = "";
        briefingList.appendChild(rowLikeStat("Status", "Aktualisierung läuft"));
      }, 5000);
      try {
        const briefing = await api("/api/v1/ai/daily-briefing");
        window.clearTimeout(pendingTimer);
        renderDailyBriefing(briefing);
      } catch (error) {
        window.clearTimeout(pendingTimer);
        if (briefingZusammenfassung) briefingZusammenfassung.textContent = "Briefing konnte nicht geladen werden.";
        briefingList.innerHTML = "";
        briefingList.appendChild(rowLikeStat("Status", "Nicht verfügbar"));
      }
    }

    async function loadDashboardMachines() {
      if (!machineCards || !canView("machines")) return;
      try {
        dashboardState.machines = listData(await api("/api/v1/machines?limit=100"));
      } catch (error) {
        dashboardState.machines = [];
        machineCards.innerHTML = "";
        machineCards.appendChild(emptyRailMessage("Maschinenstatus konnte nicht geladen werden."));
      }
      renderMachineCards();
      renderCriticalToday();
    }

    async function loadDashboardHandovers() {
      if (!handoverList || !canView("shiftplans")) return;
      try {
        renderHandoverList(listData(await api("/api/v1/handover?date=" + todayIso())));
      } catch (error) {
        dashboardState.handovers = [];
        handoverList.innerHTML = "";
        handoverList.appendChild(emptyRailMessage("Schichtübergaben konnten nicht geladen werden."));
        setDashboardText("[data-dashboard-shift-status]", "--");
        setDashboardText("[data-dashboard-shift-meta]", "Übergaben nicht verfügbar");
        setProgress("[data-dashboard-shift-progress]", 8);
      }
    }

    async function loadDashboardVacations() {
      if (!peopleHints || !canView("employees")) return;
      try {
        dashboardState.vacations = listData(await api("/api/v1/vacations?status=pending"));
      } catch (error) {
        dashboardState.vacations = [];
      }
      renderPeopleHints();
      renderCriticalToday();
    }

    async function setupDashboardCalendarFilter() {
      if (!shiftCalendarEmployee || !canView("employees")) return;
      try {
        const employees = listData(await api("/api/v1/employees?limit=200"));
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
            ? "Kalender für " + calendar.employee.name
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
      dashboardJobs.push(loadDashboardAufgaben());
      dashboardJobs.push(loadDashboardPriorities());
    }

    if (operationsInsights && canView("dashboard")) {
      if (operationsRefresh && operationsRefresh.dataset.bound !== "true") {
        operationsRefresh.addEventListener("click", () => loadOperationsInsights(operationsRefresh));
        operationsRefresh.dataset.bound = "true";
      }
      if (operationsSiteFilter && operationsSiteFilter.dataset.bound !== "true") {
        operationsSiteFilter.addEventListener("change", () => loadOperationsInsights());
        operationsSiteFilter.dataset.bound = "true";
      }
      if (operationsRangeFilter && operationsRangeFilter.dataset.bound !== "true") {
        operationsRangeFilter.addEventListener("change", () => loadOperationsInsights());
        operationsRangeFilter.dataset.bound = "true";
      }
      dashboardJobs.push(loadOperationsInsights());
    } else if (operationsInsights) {
      operationsInsights.hidden = true;
    }

    if (aiSystemRail || aiRiskRadar || aiKnowledgeHealth) {
      dashboardJobs.push(loadAiOperationsSignals());
    }

    dashboardJobs.push(loadDailyBriefing());

    if (machineCards && canView("machines")) {
      dashboardJobs.push(loadDashboardMachines());
    } else if (machineCards) {
      machineCards.innerHTML = "";
      machineCards.appendChild(emptyRailMessage("Keine Berechtigung für Maschinenstatus."));
    }

    if (handoverList && canView("shiftplans")) {
      dashboardJobs.push(loadDashboardHandovers());
    } else if (handoverList) {
      handoverList.innerHTML = "";
      handoverList.appendChild(emptyRailMessage("Keine Berechtigung für Schichtübergaben."));
    }

    if (peopleHints && canView("employees")) {
      dashboardJobs.push(loadDashboardVacations());
    }

    if (errorStats && canView("errors")) {
      dashboardJobs.push((async () => {
        const errorPayload = await api("/api/v1/errors?limit=100&active=1");
        const errors = listData(errorPayload);
        setText("[data-dashboard-machine-issue-count]", paginationTotal(errorPayload, errors));
        renderIncidentRows(errors);
      })());
    } else if (errorStats) {
      errorStats.innerHTML = "";
      errorStats.appendChild(emptyDashboardMessage("Keine Berechtigung für Störungen."));
      renderFrequentCodes([]);
    }

    if (employeeOverview && canView("employees")) {
      dashboardJobs.push((async () => {
        try {
          renderEmployeeOverview(listData(await api("/api/v1/employees?limit=200")));
        } catch (error) {
          employeeOverview.innerHTML = "";
          employeeOverview.appendChild(emptyDashboardMessage("Mitarbeiterdaten konnten nicht geladen werden."));
          dashboardState.employees = [];
          renderPeopleHints();
        }
      })());
    }

    if (inventoryStats && canView("inventory")) {
      dashboardJobs.push((async () => {
        const summary = await api("/api/v1/inventory/summary?include_materials=0");
        renderInventoryZusammenfassung(summary);
      })());
    }

    const dashboardResults = await Promise.allSettled(dashboardJobs);
    dashboardResults
      .filter((result) => result.status === "rejected")
      .forEach((result) => console.warn(result.reason));
    applySloKpis();
    renderRiskRadar();
    renderAiSystemRail();
    renderKnowledgeHealth();
    renderPriorityRail();
    renderExecutiveDashboard();

  }

  async function initDocuments() {
    const list = document.querySelector("[data-document-list]");
    const form = document.querySelector("[data-document-filter-form]");
    const reset = document.querySelector("[data-document-filter-reset]");
    const reviewPanel = document.querySelector("[data-document-review-panel]");
    const reviewZusammenfassung = document.querySelector("[data-document-review-summary]");
    const reviewScore = document.querySelector("[data-document-review-score]");
    const reviewStatus = document.querySelector("[data-document-review-status]");
    const reviewStatusBadge = document.querySelector("[data-document-review-status-badge]");
    const reviewQuelle = document.querySelector("[data-document-review-source]");
    const reviewFindings = document.querySelector("[data-document-review-findings]");
    const reviewRecommendations = document.querySelector("[data-document-review-recommendations]");
    const summaryPanel = document.querySelector("[data-document-summary-panel]");
    const summaryTitle = document.querySelector("[data-document-summary-title]");
    const summaryStatus = document.querySelector("[data-document-summary-status]");
    const summaryText = document.querySelector("[data-document-summary-text]");
    const uploadCheckForm = document.querySelector("[data-document-upload-check-form]");
    const uploadCheckMessage = document.querySelector("[data-document-upload-check-message]");
    const uploadCheckFile = uploadCheckForm ? uploadCheckForm.querySelector("input[type='file']") : null;
    const documentMessage = document.querySelector("[data-document-message]");
    const manualForm = document.querySelector("[data-manual-upload-form]");
    const manualList = document.querySelector("[data-manual-list]");
    const manualMessage = document.querySelector("[data-manual-message]");
    const manualMachineSelect = document.querySelector("[data-manual-machine-select]");
    if (!list || !form) return;
    if (!token()) {
      setStatusMessage(documentMessage, "Sitzung wird geladen. Dokumentaktionen werden gleich aktiviert.");
      return;
    }
    if (uploadCheckFile && uploadCheckMessage) {
      if (!uploadCheckMessage.id) uploadCheckMessage.id = "document-upload-check-message";
      uploadCheckFile.setAttribute("aria-describedby", uploadCheckMessage.id);
    }

    function reviewStatusLabel(status) {
      if (status === "good") return "Gut";
      if (status === "needs_review") return "Prüfen";
      return "Unvollständig";
    }

    function reviewStatusClass(status) {
      if (status === "good") return "badge badge-status is-done";
      if (status === "needs_review") return "badge badge-status is-progress";
      return "badge badge-status is-open";
    }

    function renderTableMessage(tableBody, colspan, message, isError) {
      if (!tableBody) return;
      if (tableBody.tagName !== "TBODY") {
        tableBody.innerHTML = "";
        const empty = document.createElement("article");
        empty.className = isError ? "guided-empty-state empty-state is-error" : "guided-empty-state empty-state";
        const title = document.createElement("strong");
        title.textContent = message;
        const hint = document.createElement("p");
        if (isError || message.includes("werden geladen")) {
          hint.textContent = isError ? "Bitte erneut versuchen oder die Berechtigung prüfen." : "Die Wissensbasis wird aktualisiert.";
        } else {
          hint.textContent = message.includes("Handb")
            ? "Lade ein Maschinenhandbuch hoch und ordne es Maschine und Bereich zu, damit es als Quelle nutzbar wird."
            : "Nutze Filter, lade ein Dokument hoch oder prüfe abgeschlossene Aufgaben, wenn du einen Bericht erwartest.";
        }
        empty.append(title, hint);
        tableBody.appendChild(empty);
        return;
      }
      const cell = document.createElement("td");
      cell.colSpan = colspan;
      cell.className = isError ? "table-message is-error" : "table-message";
      if (isError || message.includes("werden geladen")) {
        cell.textContent = message;
      } else {
        const empty = document.createElement("div");
        empty.className = "guided-empty-state";
        const title = document.createElement("strong");
        title.textContent = message;
        const hint = document.createElement("p");
        hint.textContent = message.includes("Handbücher")
          ? "Lade ein Maschinenhandbuch hoch und ordne es Maschine und Bereich zu, damit die AI eine belastbare Quelle findet."
          : "Nutze Filter, lade ein Dokument hoch oder prüfe abgeschlossene Aufgaben, wenn du einen Bericht erwartest.";
        empty.append(title, hint);
        cell.appendChild(empty);
      }
      const tableRow = document.createElement("tr");
      tableRow.appendChild(cell);
      tableBody.innerHTML = "";
      tableBody.appendChild(tableRow);
    }

    function severityClass(severity) {
      const value = String(severity || "").toLowerCase();
      if (["critical", "error", "high"].includes(value)) return "is-critical";
      if (["warning", "warn", "medium", "needs_review"].includes(value)) return "is-warning";
      return "is-good";
    }

    function severityMarker(severity) {
      const value = severityClass(severity);
      if (value === "is-critical") return "!";
      if (value === "is-warning") return "?";
      return "OK";
    }

    function reviewFindingItem(finding) {
      const item = document.createElement("article");
      item.className = "review-check-item " + severityClass(finding && finding.severity);
      const marker = document.createElement("span");
      marker.className = "review-check-marker";
      marker.textContent = severityMarker(finding && finding.severity);
      const content = document.createElement("div");
      content.className = "review-check-content";
      const title = document.createElement("strong");
      title.textContent = (finding && finding.field) || "Prüfpunkt";
      const message = document.createElement("span");
      message.textContent = (finding && finding.message) || "Keine Details vorhanden.";
      const meta = document.createElement("small");
      meta.textContent = (finding && finding.severity) ? "Schweregrad: " + finding.severity : "Hinweis";
      content.appendChild(title);
      content.appendChild(message);
      content.appendChild(meta);
      item.appendChild(marker);
      item.appendChild(content);
      return item;
    }

    function allowedCheckFile(file) {
      if (!file) return false;
      const name = String(file.name || "").toLowerCase();
      const type = String(file.type || "").toLowerCase();
      return name.endsWith(".html")
        || name.endsWith(".htm")
        || name.endsWith(".txt")
        || type === "text/html"
        || type === "text/plain";
    }

    function validateUploadCheckFile(fileInput) {
      if (!fileInput || !fileInput.files || !fileInput.files.length) {
        if (fileInput) fileInput.setAttribute("aria-invalid", "true");
        setStatusMessage(uploadCheckMessage, "Bitte eine HTML- oder TXT-Datei auswählen.", true);
        return false;
      }
      const file = fileInput.files[0];
      if (!allowedCheckFile(file)) {
        fileInput.setAttribute("aria-invalid", "true");
        setStatusMessage(uploadCheckMessage, "Nur HTML-, HTM- oder TXT-Dateien können geprüft werden.", true);
        return false;
      }
      fileInput.removeAttribute("aria-invalid");
      return true;
    }

    function renderDocumentReview(review) {
      if (!reviewPanel || !reviewFindings) return;
      const documentMeta = (review && review.document) || {};
      const findings = Array.isArray(review && review.findings) ? review.findings : [];
      const recommendations = Array.isArray(review && review.recommendations) ? review.recommendations : [];
      reviewPanel.hidden = false;
      if (reviewZusammenfassung) {
        reviewZusammenfassung.textContent = "Prüfung für " + (documentMeta.title || documentMeta.filename || "Dokument");
      }
      if (reviewScore) reviewScore.textContent = String((review && review.quality_score) || 0);
      if (reviewStatus) reviewStatus.textContent = reviewStatusLabel(review && review.status);
      if (reviewStatusBadge) {
        reviewStatusBadge.className = reviewStatusClass(review && review.status);
        reviewStatusBadge.textContent = reviewStatusLabel(review && review.status);
      }
      if (reviewQuelle) {
        reviewQuelle.textContent = documentMeta.source || documentMeta.document_type || "Dokument";
      }
      reviewFindings.innerHTML = "";
      if (!findings.length) {
        reviewFindings.appendChild(reviewFindingItem({
          field: "Keine Findings",
          message: "Die Prüfung hat keine offenen Punkte gefunden.",
          severity: "good"
        }));
      } else {
        findings.forEach((finding) => {
          reviewFindings.appendChild(reviewFindingItem(finding));
        });
      }
      if (reviewRecommendations) {
        reviewRecommendations.textContent = recommendations.length
          ? "Empfehlungen: " + recommendations.join(" | ")
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

    async function downloadDocumentPdf(documentItem) {
      await downloadFile(
        "/api/v1/documents/" + documentItem.id + "/download.pdf",
        "maintenance_report_task_" + documentItem.task_id + ".pdf"
      );
    }

    function renderZusammenfassung(title, status, text) {
      if (!summaryPanel || !summaryText) return;
      summaryPanel.hidden = false;
      if (summaryTitle) summaryTitle.textContent = title;
      if (summaryStatus) summaryStatus.textContent = status || "-";
      summaryText.textContent = text || "Keine Zusammenfassung vorhanden.";
      summaryPanel.scrollIntoView({ behavior: "smooth", block: "start" });
    }

    async function summarizeDocument(documentItem) {
      const result = await api("/api/v1/documents/" + documentItem.id + "/summarize", {
        method: "POST"
      });
      renderZusammenfassung(result.title, result.summary_status, result.summary);
    }

    async function showVersions(documentItem) {
      const result = await api("/api/v1/documents/" + documentItem.id + "/versions");
      const versions = listData(result).map((version) => (
        "v" + version.version_number + " - " + new Date(version.created_at).toLocaleString("de-DE")
      ));
      await showInfoDialog({
        title: "Dokumentversionen",
        message: versions.length ? versions.join("\n") : "Keine Versionen vorhanden."
      });
    }

    async function changeDocumentStatus(documentItem, action) {
      const comment = await requestText({
        title: action === "approve" ? "Dokument freigeben" : "Dokument ablehnen",
        message: "Kommentar für " + (action === "approve" ? "Freigabe" : "Ablehnung") + ". Leerlassen ist erlaubt.",
        label: "Kommentar",
        multiline: true,
        defaultValue: "",
        confirmText: action === "approve" ? "Freigeben" : "Ablehnen"
      });
      if (comment === null) return;
      await api("/api/v1/documents/" + documentItem.id + "/" + action, {
        method: "POST",
        body: JSON.stringify({ comment })
      });
      await load();
    }

    function statusText(value) {
      if (value === "in_review") return "In Prüfung";
      if (value === "approved") return "Freigegeben";
      if (value === "rejected") return "Abgelehnt";
      return "Entwurf";
    }

    function documentStatusBadge(value) {
      if (value === "approved" || value === "ready") return badge(statusText(value), "badge badge-status is-done");
      if (value === "in_review" || value === "needs_review") return badge(statusText(value), "badge badge-status is-progress");
      if (value === "rejected" || value === "error") return badge(statusText(value), "badge badge-status is-open");
      return badge(statusText(value), "badge badge-status is-open");
    }

    function recordMetaItem(label, value) {
      const item = document.createElement("span");
      const itemLabel = document.createElement("small");
      const itemValue = document.createElement("strong");
      itemLabel.textContent = label;
      itemValue.textContent = value || "-";
      item.append(itemLabel, itemValue);
      return item;
    }

    function manualRecordCard(manual, actions) {
      const card = document.createElement("article");
      card.className = "record-card document-record-card";
      card.dataset.searchText = [
        manual.title,
        manual.original_filename,
        manual.department,
        manual.machine && manual.machine.name,
        manual.analysis_status,
        manual.summary_status
      ].filter(Boolean).join(" ");

      const header = document.createElement("div");
      header.className = "record-card-header";
      const titleBlock = document.createElement("div");
      const title = document.createElement("h3");
      title.className = "record-card-title";
      title.textContent = manual.title || manual.original_filename || "Handbuch";
      const subtitle = document.createElement("p");
      subtitle.className = "record-card-subtitle";
      subtitle.textContent = manual.machine && manual.machine.name ? manual.machine.name : "Keine Maschine zugeordnet";
      titleBlock.append(title, subtitle);
      header.append(titleBlock, badge(manual.analysis_status || "nicht geprüft", "badge badge-status is-progress"));

      const meta = document.createElement("div");
      meta.className = "record-card-meta";
      meta.append(
        recordMetaItem("Bereich", manual.department || "-"),
        recordMetaItem("Analyse", manual.analysis_status || "-"),
        recordMetaItem("Zusammenfassung", manual.summary_status || "-")
      );
      actions.classList.remove("table-actions");
      actions.classList.add("record-card-actions");
      card.append(header, meta, actions);
      return card;
    }

    function documentRecordCard(documentItem, actions) {
      const card = document.createElement("article");
      card.className = "record-card document-record-card";
      card.dataset.searchText = [
        documentItem.title,
        documentItem.task_id,
        documentItem.department,
        documentItem.machine,
        statusText(documentItem.status)
      ].filter(Boolean).join(" ");

      const header = document.createElement("div");
      header.className = "record-card-header";
      const titleBlock = document.createElement("div");
      const title = document.createElement("h3");
      title.className = "record-card-title";
      title.textContent = documentItem.title || "Wartungsbericht";
      const subtitle = document.createElement("p");
      subtitle.className = "record-card-subtitle";
      subtitle.textContent = "Aufgabe #" + documentItem.task_id + " · " + (documentItem.machine || "Keine Maschine");
      titleBlock.append(title, subtitle);
      header.append(titleBlock, documentStatusBadge(documentItem.status));

      const meta = document.createElement("div");
      meta.className = "record-card-meta";
      meta.append(
        recordMetaItem("Bereich", documentItem.department || "-"),
        recordMetaItem("Version", documentItem.version ? "v" + documentItem.version : "-"),
        recordMetaItem("Erstellt", documentItem.created_at ? new Date(documentItem.created_at).toLocaleString("de-DE") : "-")
      );
      actions.classList.remove("table-actions");
      actions.classList.add("record-card-actions");
      card.append(header, meta, actions);
      return card;
    }

    async function loadManualMachines() {
      if (!manualMachineSelect) return;
      try {
        const machines = listData(await api("/api/v1/machines?limit=200"));
        machines.forEach((machine) => {
          const option = document.createElement("option");
          option.value = String(machine.id);
          option.textContent = machine.name;
          manualMachineSelect.appendChild(option);
        });
      } catch (error) {
        if (manualMessage) manualMessage.textContent = "Maschinen konnten nicht geladen werden.";
      }
    }

    async function loadManuals() {
      if (!manualList) return [];
      renderTableMessage(manualList, 6, "Handbücher werden geladen...");
      let manualPayload;
      try {
        manualPayload = await api("/api/v1/documents/manuals?limit=100");
      } catch (error) {
        renderTableMessage(manualList, 6, "Handbücher konnten nicht geladen werden.", true);
        throw error;
      }
      const manuals = listData(manualPayload);
      manualList.innerHTML = "";
      document.querySelectorAll("[data-manual-count]").forEach((element) => {
        element.textContent = paginationTotal(manualPayload, manuals) + " Handbücher";
      });
      if (!manuals.length) {
        renderTableMessage(manualList, 6, "Keine Handbücher vorhanden.");
        return manuals;
      }
      manuals.forEach((manual) => {
        const actions = document.createElement("div");
        actions.className = "table-actions";
        actions.appendChild(actionButton("Download", async () => {
          await downloadFile(manual.download_url, manual.original_filename);
        }, { successMessage: "Herunterladen wurde gestartet." }));
        actions.appendChild(actionButton("Analysieren", async () => {
          const result = await api("/api/v1/documents/manuals/" + manual.id + "/analyze", { method: "POST" });
          renderZusammenfassung(result.title, result.analysis_status, result.analysis);
          await loadManuals();
        }, { busyText: "Analysiert...", successMessage: "Handbuchanalyse aktualisiert." }));
        actions.appendChild(actionButton("Zusammenfassen", async () => {
          const result = await api("/api/v1/documents/manuals/" + manual.id + "/summarize", { method: "POST" });
          renderZusammenfassung(result.title, result.summary_status, result.summary);
          await loadManuals();
        }, { busyText: "Fasst zusammen...", successMessage: "Handbuch-Zusammenfassung aktualisiert." }));
        if (canWrite("documents")) {
          actions.appendChild(actionButton("Löschen", async () => {
            if (!window.confirm(manual.title + " wirklich löschen?")) return;
            await api("/api/v1/documents/manuals/" + manual.id, { method: "DELETE" });
            await loadManuals();
          }, { danger: true, busyText: "Löscht...", successMessage: "Handbuch gelöscht." }));
        }
        manualList.appendChild(manualRecordCard(manual, actions));
      });
      return manuals;
    }

    function documentSearchParams() {
      const params = new URLSearchParams();
      new FormData(form).forEach((value, key) => {
        if (value) params.set(key, value);
      });
      params.set("limit", "100");
      return params;
    }

    async function load(params) {
      const queryParams = params || documentSearchParams();
      renderTableMessage(list, 8, "Dokumente werden geladen...");
      const suffix = "?" + queryParams.toString();
      let documentPayload;
      try {
        documentPayload = await api("/api/v1/documents" + suffix);
      } catch (error) {
        renderTableMessage(list, 8, "Dokumente konnten nicht geladen werden.", true);
        throw error;
      }
      const documents = listData(documentPayload);
      list.innerHTML = "";
      document.querySelectorAll("[data-document-count]").forEach((element) => {
        element.textContent = paginationTotal(documentPayload, documents) + " Dokumente";
      });
      if (!documents.length) {
        renderTableMessage(list, 8, "Keine Dokumente gefunden.");
        return documents;
      }
      documents.forEach((documentItem) => {
        const actions = document.createElement("div");
        actions.className = "table-actions";
        actions.appendChild(actionButton("Prüfen", async () => {
          await reviewDocument(documentItem);
        }, { busyText: "Prüft...", successMessage: "Dokumentprüfung aktualisiert." }));
        actions.appendChild(actionButton("HTML", async () => {
          await downloadDocument(documentItem);
        }, { successMessage: "HTML-Herunterladen wurde gestartet." }));
        actions.appendChild(actionButton("PDF", async () => {
          await downloadDocumentPdf(documentItem);
        }, { successMessage: "PDF-Herunterladen wurde gestartet." }));
        actions.appendChild(actionButton("Zusammenfassung", async () => {
          await summarizeDocument(documentItem);
        }, { busyText: "Fasst zusammen...", successMessage: "Zusammenfassung aktualisiert." }));
        actions.appendChild(actionButton("Versionen", async () => {
          await showVersions(documentItem);
        }, { successMessage: "Versionen geladen." }));
        if (canWrite("documents")) {
          actions.appendChild(actionButton("Prüfung", async () => {
            await changeDocumentStatus(documentItem, "submit-review");
          }, { busyText: "Sendet...", successMessage: "Dokument wurde zur Prüfung eingereicht." }));
          actions.appendChild(actionButton("Freigeben", async () => {
            await changeDocumentStatus(documentItem, "approve");
          }, { busyText: "Gibt frei...", successMessage: "Dokument freigegeben." }));
          actions.appendChild(actionButton("Ablehnen", async () => {
            await changeDocumentStatus(documentItem, "reject");
          }, { danger: true, busyText: "Lehnt ab...", successMessage: "Dokument abgelehnt." }));
        }
        list.appendChild(documentRecordCard(documentItem, actions));
      });
      return documents;
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const params = documentSearchParams();
      await runAction({
        action: async () => load(params),
        form,
        busyText: "Filtert...",
        errorMessage: "Dokumente konnten nicht geladen werden.",
        pendingMessage: "Dokumente werden geladen...",
        statusElement: documentMessage,
        successMessage: "Dokumentliste aktualisiert.",
        toast: false
      });
    });

    if (reset) {
      reset.addEventListener("click", async () => {
        form.reset();
        await runAction({
          action: async () => load(documentSearchParams()),
          button: reset,
          busyText: "Setzt zurück...",
          errorMessage: "Filter konnten nicht zurückgesetzt werden.",
          pendingMessage: "Filter werden zurückgesetzt...",
          statusElement: documentMessage,
          successMessage: "Filter zurückgesetzt."
        });
      });
    }

    if (uploadCheckFile) {
      uploadCheckFile.addEventListener("change", () => {
        if (!uploadCheckFile.files || !uploadCheckFile.files.length) {
          uploadCheckFile.removeAttribute("aria-invalid");
          setStatusMessage(uploadCheckMessage, "");
          return;
        }
        if (validateUploadCheckFile(uploadCheckFile)) {
          setStatusMessage(uploadCheckMessage, "Datei bereit: " + uploadCheckFile.files[0].name, false);
        }
      });
    }

    if (uploadCheckForm) {
      uploadCheckForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (!validateUploadCheckFile(uploadCheckFile)) {
          if (uploadCheckFile) uploadCheckFile.focus();
          return;
        }
        const payload = new FormData(uploadCheckForm);
        await runAction({
          action: async () => {
            const review = await api("/api/v1/documents/check", {
              method: "POST",
              body: payload
            });
            renderDocumentReview(review);
            return review;
          },
          busyText: "Prüft...",
          errorMessage: "Dokument konnte nicht geprüft werden.",
          form: uploadCheckForm,
          pendingMessage: "Dokument wird geprüft...",
          statusElement: uploadCheckMessage,
          successMessage: "Dokument geprüft."
        });
      });
    }

    if (manualForm) {
      manualForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const payload = new FormData(manualForm);
        await runAction({
          action: async () => {
            await api("/api/v1/documents/manuals", {
              method: "POST",
              body: payload
            });
            manualForm.reset();
            await loadManuals();
          },
          busyText: "Lädt...",
          errorMessage: "Hochladen fehlgeschlagen.",
          form: manualForm,
          pendingMessage: "Handbuch wird hochgeladen...",
          statusElement: manualMessage,
          successMessage: "Handbuch hochgeladen."
        });
      });
    }

    try {
      await loadManualMachines();
      await loadManuals();
      const documents = await load();
      setStatusMessage(documentMessage, "Dokumentaktionen bereit.", false);
      const documentPreview = consumeAiActionPreview("documents");
      if (documentPreview && documentPreview.payload) {
        const documentItem = documents.find((item) => item.id === documentPreview.payload.document_id);
        if (documentItem) await reviewDocument(documentItem);
      }
    } catch (error) {
      renderTableMessage(list, 8, "Dokumente konnten nicht geladen werden.", true);
      setStatusMessage(documentMessage, error.message || "Dokumente konnten nicht geladen werden.", true);
      showInterfaceToast("Dokumente konnten nicht geladen werden.", "error");
    }
  }

  function workflowInitializersForCurrentPage() {
    const feature = window.maintenanceFeatures && window.maintenanceFeatures.forPath
      ? window.maintenanceFeatures.forPath(window.location.pathname)
      : null;
    const availableInitializers = {
      initDashboardShiftRealtime,
      initCockpitShiftRealtime: initDashboardShiftRealtime,
      initDailyCockpit,
      initDepartments,
      initTasks: initAufgaben,
      initAufgaben,
      initErrors,
      initEmployees,
      initMachines,
      initMachineProfile,
      initInventory,
      initShiftPlans,
      initVacations,
      initDocuments,
      initUsers,
      initBenutzer: initUsers
    };
    const initializerNames = Array.isArray(feature && feature.initializers)
      ? feature.initializers
      : [];
    return initializerNames
      .map((name) => availableInitializers[name])
      .filter((initializer) => typeof initializer === "function");
  }

  async function initCurrentWorkflowPage() {
    if (!token()) {
      document.body.classList.remove("is-workflow-loading");
      if (window.maintenanceFrontend && window.maintenanceFrontend.setWorkflowStatus) {
        window.maintenanceFrontend.setWorkflowStatus("Sitzung wird geladen. Aktionen werden gleich aktiviert.", "info");
      }
      return;
    }
    try {
      if (window.maintenanceAuth && window.maintenanceAuth.ensureReady) {
        await window.maintenanceAuth.ensureReady();
      }
      await loadWorkflowShared();
      const initializers = workflowInitializersForCurrentPage();
      for (const initializer of initializers) {
        await initializer();
      }
    } catch (error) {
      console.warn(error);
      if (window.maintenanceFrontend && window.maintenanceFrontend.setWorkflowStatus) {
        window.maintenanceFrontend.setWorkflowStatus("Diese Seite konnte nicht vollständig initialisiert werden.", "error");
      }
      showInterfaceToast("Diese Seite konnte nicht vollständig initialisiert werden.", "error");
    } finally {
      document.body.classList.remove("is-workflow-loading");
      window.dispatchEvent(new Event("maintenance-workflow-ready"));
    }
  }

  window.maintenanceWorkflows = {
    initCurrentWorkflowPage,
    workflowInitializersForCurrentPage
  };
})();

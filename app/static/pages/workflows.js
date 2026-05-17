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

  function listData(result) {
    if (Array.isArray(result)) return result;
    if (result && Array.isArray(result.data)) return result.data;
    if (result && result.data && Array.isArray(result.data.items)) return result.data.items;
    if (result && Array.isArray(result.items)) return result.items;
    return [];
  }

  function paginationTotal(result, fallbackItems) {
    const pagination = result && (result.pagination || (result.data && result.data.pagination));
    if (pagination && Number.isFinite(Number(pagination.total))) return Number(pagination.total);
    return Array.isArray(fallbackItems) ? fallbackItems.length : 0;
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

  function showInterfaceToast(message, variant) {
    if (window.maintenanceFrontend && window.maintenanceFrontend.showInterfaceToast) {
      window.maintenanceFrontend.showInterfaceToast(message, variant);
      return;
    }
    let toast = document.querySelector("[data-interface-toast]");
    if (!toast) {
      toast = document.createElement("div");
      toast.className = "interface-toast";
      toast.dataset.interfaceToast = "true";
      toast.setAttribute("role", "status");
      toast.setAttribute("aria-live", "polite");
      document.body.appendChild(toast);
    }
    toast.textContent = message;
    toast.classList.toggle("is-error", variant === "error");
    toast.classList.toggle("is-success", variant === "success");
    toast.classList.toggle("is-info", !variant || variant === "info");
    toast.hidden = false;
    window.clearTimeout(showInterfaceToast.timeoutId);
    showInterfaceToast.timeoutId = window.setTimeout(() => {
      toast.hidden = true;
    }, 2600);

    const liveRegion = document.querySelector("[data-global-live-region]");
    if (liveRegion) liveRegion.textContent = message;
  }

  function sourceTypeLabel(source) {
    const key = String((source && (source.module || source.type)) || "knowledge");
    const labels = {
      tasks: "Task",
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

  function renderSourcePanel(container, sources, emptyText) {
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
    title.textContent = "RAG-Quellen";
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
    meta.textContent = "Aus der Analyse kann direkt ein Task vorbereitet werden.";
    copy.append(title, meta);
    const button = document.createElement("button");
    button.type = "button";
    button.className = "btn btn-primary btn-sm";
    button.textContent = "Task vorbereiten";
    button.addEventListener("click", () => applyAiActionPreview(preview));
    container.append(copy, button);
    container.hidden = false;
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
        : "Keine Mitarbeiterdaten für die Schichtübersicht.",
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
    element.classList.toggle("is-info", Boolean(message && isError === undefined));
    if (message) {
      element.setAttribute("role", isError ? "alert" : "status");
      element.setAttribute("aria-live", isError ? "assertive" : "polite");
      return;
    }
    element.removeAttribute("role");
    element.removeAttribute("aria-live");
  }

  function setButtonBusy(button, busy, busyText) {
    if (window.maintenanceFrontend && window.maintenanceFrontend.setButtonBusy) {
      window.maintenanceFrontend.setButtonBusy(button, busy, busyText);
      return;
    }
    if (!button) return;
    if (busy) {
      if (!button.dataset.originalText) {
        button.dataset.originalText = button.textContent;
      }
      if (!button.dataset.originalDisabled) {
        button.dataset.originalDisabled = button.disabled ? "true" : "false";
      }
      button.disabled = true;
      button.classList.add("is-busy");
      button.setAttribute("aria-busy", "true");
      if (busyText) {
        button.dataset.busyText = busyText;
        button.textContent = busyText;
      }
      return;
    }
    button.disabled = button.dataset.originalDisabled === "true";
    button.classList.remove("is-busy");
    button.removeAttribute("aria-busy");
    if (button.dataset.originalText) {
      if (!button.dataset.busyText || button.textContent === button.dataset.busyText) {
        button.textContent = button.dataset.originalText;
      }
      delete button.dataset.originalText;
      delete button.dataset.busyText;
      delete button.dataset.originalDisabled;
    }
  }

  function setFormBusy(form, busy, busyText) {
    if (window.maintenanceFrontend && window.maintenanceFrontend.setFormBusy) {
      window.maintenanceFrontend.setFormBusy(form, busy, busyText);
      return;
    }
    if (!form) return;
    const submitButton = form.querySelector("button[type='submit']");
    setButtonBusy(submitButton, busy, busyText);
    form.setAttribute("aria-busy", String(Boolean(busy)));
  }

  async function runAction(options) {
    const settings = options || {};
    if (window.maintenanceFrontend && window.maintenanceFrontend.runAction) {
      return window.maintenanceFrontend.runAction(settings);
    }
    const control = settings.button || settings.control || null;
    const form = settings.form || null;
    if (form) setFormBusy(form, true, settings.busyText || "Läuft...");
    else setButtonBusy(control, true, settings.busyText || "Läuft...");
    if (settings.pendingMessage) setStatusMessage(settings.statusElement, settings.pendingMessage);
    try {
      const result = await settings.action();
      if (settings.successMessage) {
        setStatusMessage(settings.statusElement, settings.successMessage, false);
        if (settings.toast !== false) showInterfaceToast(settings.successMessage, "success");
      }
      return result;
    } catch (error) {
      const message = error.message || settings.errorMessage || "Aktion fehlgeschlagen.";
      setStatusMessage(settings.statusElement, message, true);
      showInterfaceToast(message, "error");
      if (settings.rethrow) throw error;
      return null;
    } finally {
      if (form) setFormBusy(form, false);
      else setButtonBusy(control, false);
    }
  }

  async function requestText(options) {
    if (window.maintenanceFrontend && window.maintenanceFrontend.requestText) {
      return window.maintenanceFrontend.requestText(options);
    }
    showInterfaceToast("Eingabedialog konnte nicht geoeffnet werden.", "error");
    return null;
  }

  async function showInfoDialog(options) {
    if (window.maintenanceFrontend && window.maintenanceFrontend.showInfoDialog) {
      return window.maintenanceFrontend.showInfoDialog(options);
    }
    showInterfaceToast((options && options.message) || "Information nicht verfuegbar.", "info");
    return true;
  }

  async function confirmAction(options) {
    if (window.maintenanceFrontend && window.maintenanceFrontend.confirmAction) {
      return window.maintenanceFrontend.confirmAction(options);
    }
    showInterfaceToast("Bestaetigungsdialog konnte nicht geoeffnet werden.", "error");
    return false;
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
        payload.possible_cause ? "Mögliche Ursache: " + payload.possible_cause : "",
        payload.recommended_action ? "Nächste Aktion: " + payload.recommended_action : ""
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
        task.due_date ? "Fällig: " + task.due_date : "Keine Fälligkeit"
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
      const tasks = listData(await api("/api/v1/tasks?limit=100"));
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
      setFormBusy(form, true, wasEditing ? "Aktualisiert..." : "Speichert...");
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
      } finally {
        setFormBusy(form, false);
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
        btn.textContent = "Wird geladen…";
        try {
          await loadPriorities();
        } finally {
          btn.textContent = original;
          btn.disabled = false;
          setButtonBusy(btn, false);
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
    const analysisSources = document.querySelector("[data-error-rag-sources]");
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

    function updateErrorRagPanels(result) {
      currentAssistantResult = result || null;
      renderSourcePanel(analysisSources, result && result.sources);
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
            "Analyse erstellt. " + result.diagnostics.rag_source_count + " RAG-Quellen gefunden."
          );
        }
      } catch (error) {
        updateErrorRagPanels(null);
        if (message) {
          setStatusMessage(message, "Analyse erstellt. RAG-Kontext nicht verfügbar: " + error.message);
        }
      }
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
      if (errorCount) errorCount.textContent = filteredErrors.length + " Einträge";
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
          highlightedBlock("Lösung", entry.solution, "is-solution")
        ];
        if (canWrite("errors")) {
          const actions = document.createElement("div");
          actions.className = "table-actions";
          actions.appendChild(actionButton("Bearbeiten", () => openErrorEdit(entry)));
          actions.appendChild(actionButton("Löschen", async () => {
            if (!window.confirm("Fehler '" + entry.title + "' wirklich löschen?")) return;
            await api("/api/v1/errors/" + entry.id, { method: "DELETE" });
            await load();
          }, true));
          cells.push(actions);
        }
        list.appendChild(row(cells));
      });
    }

    async function load() {
      currentErrors = listData(await api("/api/v1/errors?limit=100"));
      renderErrors();
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const data = Object.fromEntries(new FormData(form).entries());
      data.description = data.title;
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
            field.value = currentAnalysis[field.dataset.errorAnalysisField] || "";
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
        form.elements.possible_causes.value = values.possible_causes || "";
        form.elements.solution.value = values.solution || "";
        if (currentAssistantResult) updateErrorRagPanels(currentAssistantResult);
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

    function permissionSummary(permission) {
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

    function permissionChangeSummary(payload) {
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
          dashboardLabel(dashboard) + ": " + permissionSummary(before)
            + " -> " + permissionSummary(after)
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
        editorTitle.textContent = item.username + " - Rechte je Dashboard";
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
          defaultHint.textContent = "Default: " + permissionSummary(defaultPermission);
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
        const changes = permissionChangeSummary(payload);
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
        employees = listData(await api("/api/v1/employees?limit=200"));
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
          + balance.available + " Tage verfügbar, "
          + days + " Tage angefragt.";
      } else if (balance) {
        balancePreview.textContent = selectedEmployeeName() + ": "
          + balance.available + " verfügbar, "
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
          renderEmpty(summaryList, "Keine Mitarbeiterdaten für dieses Jahr.");
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
        ? "Reserviert: " + vacation.days_used + " Tage, aktuell verfügbar: " + balance.available
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
        withdrawBtn.textContent = "Zurückziehen";
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
        setMessage("Antrag wird zurückgezogen...", "");
        await api(BASE_VAC + "/" + id, { method: "DELETE" });
        setMessage("Antrag wurde zurückgezogen.", "success");
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
    const assistantSources = document.querySelector("[data-machine-assistant-sources]");
    const assistantFocus = document.querySelector("[data-machine-assistant-focus]");
    const recommendationPanel = document.querySelector("[data-maintenance-recommendations-panel]");
    const recommendationList = document.querySelector("[data-maintenance-recommendations-list]");
    const recommendationSummary = document.querySelector("[data-maintenance-recommendations-summary]");
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
            ? "Fallback-Antwort: "
            : "";
          setStatusMessage(assistantAnswer, fallback + result.answer);
          renderSourcePanel(assistantSources, result.sources);
        } catch (error) {
          setStatusMessage(assistantAnswer, error.message, true);
          renderSourcePanel(assistantSources, []);
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
      subtitle.textContent = item.reason || "Historie und Wissensquellen prüfen.";
      titleBlock.append(title, subtitle);
      const badges = document.createElement("div");
      badges.className = "resource-card-badges";
      badges.appendChild(badge(recommendationRiskLabel(item.risk_level), "badge badge-ai"));
      header.append(titleBlock, badges);

      const metrics = document.createElement("div");
      metrics.className = "resource-meta-grid";
      [
        ["Score", String(item.score || 0)],
        ["Tasks", String((item.source_counts && item.source_counts.tasks) || 0)],
        ["Fehler", String((item.source_counts && item.source_counts.errors) || 0)],
        ["RAG", String((item.source_counts && item.source_counts.rag_sources) || 0)]
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
      if (recommendationSummary) {
        recommendationSummary.textContent = items.length
          ? items.length + " praeventive Hinweise aus Tasks, Fehlern und RAG-Quellen."
          : "Keine auffälligen Wartungssignale gefunden.";
      }
      if (!items.length) {
        const empty = document.createElement("p");
        empty.className = "panel-meta";
        empty.textContent = "Keine praeventiven Empfehlungen vorhanden.";
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
        if (recommendationSummary) {
          recommendationSummary.textContent = "Praeventive Wartung konnte nicht geladen werden: " + error.message;
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

    async function load() {
      const machinePayload = await api("/api/v1/machines?limit=200");
      const machines = listData(machinePayload);
      const machineCount = document.querySelector("[data-machine-count]");
      list.innerHTML = "";
      if (machineCount) {
        machineCount.textContent = paginationTotal(machinePayload, machines) + " Maschinen";
      }
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
          actions.appendChild(actionButton("Löschen", async () => {
            if (!window.confirm(machine.name + " wirklich löschen?")) return;
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
      const materialPayload = await api("/api/v1/inventory?limit=200");
      const materials = listData(materialPayload);
      list.innerHTML = "";
      materials.forEach((material) => {
        const actions = document.createElement("div");
        actions.className = "table-actions";
        if (canWrite("inventory")) {
          actions.appendChild(actionButton("Löschen", async () => {
            if (!window.confirm(material.name + " wirklich löschen?")) return;
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
    const inventoryStats = document.querySelector("[data-dashboard-inventory-stats]");
    const inventoryShortages = document.querySelector("[data-dashboard-inventory-shortages]");
    const employeeOverview = document.querySelector("[data-dashboard-employee-overview]");
    const priorityList = document.querySelector("[data-dashboard-priority-list]");
    const briefingSummary = document.querySelector("[data-daily-briefing-summary]");
    const briefingList = document.querySelector("[data-daily-briefing-list]");
    const operationsInsights = document.querySelector("[data-operations-insights]");
    const operationsStatus = document.querySelector("[data-operations-insights-status]");
    const operationsSiteFilter = document.querySelector("[data-operations-site-filter]");
    const operationsRangeFilter = document.querySelector("[data-operations-range-filter]");
    const operationsRefresh = document.querySelector("[data-operations-refresh]");
    const operationsKpiGrid = document.querySelector("[data-operations-kpi-grid]");
    const operationsDrilldown = document.querySelector("[data-operations-drilldown]");
    const shiftCalendar = document.querySelector("[data-dashboard-shift-calendar]");
    const shiftTimeline = document.querySelector("[data-dashboard-shift-timeline]");
    const shiftCalendarMessage = document.querySelector("[data-dashboard-calendar-message]");
    const shiftCalendarEmployee = document.querySelector("[data-dashboard-calendar-employee]");
    if ((!taskBoard && !errorStats && !inventoryStats && !briefingList && !employeeOverview && !shiftTimeline && !operationsInsights) || !token()) return;

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
          ? "Keine Tasks für heute."
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
      const tasks = listData(await api("/api/v1/tasks?limit=100"));
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
          announce("Task gespeichert.");
          await loadDashboardTasks();
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
        employeeOverview.appendChild(emptyDashboardMessage("Keine Mitarbeiterdaten verfügbar."));
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
        errorStats.appendChild(emptyDashboardMessage("Keine Störungen erfasst."));
        return;
      }
      errors.slice(0, 5).forEach((entry, index) => {
        const rowElement = document.createElement("div");
        rowElement.className = "incident-row";

        const title = document.createElement("strong");
        title.textContent = entry.title || entry.error_code || "Störung";

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

    function inventoryCountsFromSummary(summary, materials) {
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

    function inventoryShortagesFromSummary(summary, materials) {
      if (summary && Array.isArray(summary.top_shortages)) {
        return summary.top_shortages;
      }
      return materials
        .slice()
        .sort((first, second) => Number(first.quantity || 0) - Number(second.quantity || 0))
        .slice(0, 3);
    }

    function renderInventorySummary(summary) {
      if (!inventoryStats) return;
      const materials = Array.isArray(summary.materials) ? summary.materials : [];
      const counts = inventoryCountsFromSummary(summary, materials);
      const shortages = inventoryShortagesFromSummary(summary, materials);
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
        return;
      }
      const now = new Date();
      const entries = Array.isArray(calendar.entries) ? calendar.entries : [];
      const today = todayIso();
      const todayEntries = entries.filter((entry) => entry.work_date === today && entry.shift !== "Frei");
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
      const tasks = summary.tasks || {};
      const machines = summary.machines || {};
      const inventory = summary.inventory || {};
      const workforce = summary.workforce || {};
      const documents = summary.documents || {};
      const aiQuality = summary.ai_quality || {};
      operationsKpiGrid.innerHTML = "";
      operationsKpiGrid.append(
        operationsCard("Offene Tasks", String(tasks.open || 0), (tasks.overdue || 0) + " überfällig", tasks.overdue ? "is-risk" : ""),
        operationsCard("MTTR", formatMinutes(machines.mttr_minutes), (machines.downtime_minutes || 0) + " min Ausfall", machines.mttr_minutes ? "is-warning" : ""),
        operationsCard("Wiederholstörungen", String(machines.repeat_faults || 0), (machines.faults || 0) + " Störungen", machines.repeat_faults ? "is-risk" : ""),
        operationsCard("Materialengpässe", String(inventory.critical_shortage_count || 0), (inventory.low_stock_count || 0) + " unter Mindestbestand", inventory.critical_shortage_count ? "is-risk" : ""),
        operationsCard("Schichtdeckung", formatPercent(workforce.avg_coverage_percent), (workforce.critical_conflicts || 0) + " kritische Konflikte", workforce.critical_conflicts ? "is-warning" : ""),
        operationsCard("Dokumentqualität", formatCompactNumber(documents.avg_quality_score), (documents.quality_checked || 0) + " geprüft", documents.avg_quality_score < 70 && documents.quality_checked ? "is-warning" : ""),
        operationsCard("AI Feedback", String(aiQuality.feedback_count || 0), formatUsd(aiQuality.estimated_cost_usd || 0) + " geschätzt", ""),
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
          briefingList.appendChild(briefingItem(section, item));
        });
      });
    }

    async function loadDailyBriefing() {
      if (!briefingList) return;
      const pendingTimer = window.setTimeout(() => {
        if (briefingSummary) briefingSummary.textContent = "Briefing wird aktualisiert.";
        briefingList.innerHTML = "";
        briefingList.appendChild(rowLikeStat("Status", "Aktualisierung läuft"));
      }, 5000);
      try {
        const briefing = await api("/api/v1/ai/daily-briefing");
        window.clearTimeout(pendingTimer);
        renderDailyBriefing(briefing);
      } catch (error) {
        window.clearTimeout(pendingTimer);
        if (briefingSummary) briefingSummary.textContent = "Briefing konnte nicht geladen werden.";
        briefingList.innerHTML = "";
        briefingList.appendChild(rowLikeStat("Status", "Nicht verfügbar"));
      }
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
      dashboardJobs.push(loadDashboardTasks());
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

    dashboardJobs.push(loadDailyBriefing());

    if (errorStats && canView("errors")) {
      dashboardJobs.push((async () => {
        const errorPayload = await api("/api/v1/errors?limit=100");
        const errors = listData(errorPayload);
        setText("[data-dashboard-machine-issue-count]", paginationTotal(errorPayload, errors));
        renderIncidentRows(errors);
      })());
    } else if (errorStats) {
      errorStats.innerHTML = "";
      errorStats.appendChild(emptyDashboardMessage("Keine Berechtigung für Störungen."));
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
        const summary = await api("/api/v1/inventory/summary?include_materials=0");
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
    const reviewStatusBadge = document.querySelector("[data-document-review-status-badge]");
    const reviewSource = document.querySelector("[data-document-review-source]");
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
    const manualCount = document.querySelector("[data-manual-count]");
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
      const cell = document.createElement("td");
      cell.colSpan = colspan;
      cell.textContent = message;
      cell.className = isError ? "table-message is-error" : "table-message";
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
      if (reviewSummary) {
        reviewSummary.textContent = "Prüfung für " + (documentMeta.title || documentMeta.filename || "Dokument");
      }
      if (reviewScore) reviewScore.textContent = String((review && review.quality_score) || 0);
      if (reviewStatus) reviewStatus.textContent = reviewStatusLabel(review && review.status);
      if (reviewStatusBadge) {
        reviewStatusBadge.className = reviewStatusClass(review && review.status);
        reviewStatusBadge.textContent = reviewStatusLabel(review && review.status);
      }
      if (reviewSource) {
        reviewSource.textContent = documentMeta.source || documentMeta.document_type || "Dokument";
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

    function renderSummary(title, status, text) {
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
      renderSummary(result.title, result.summary_status, result.summary);
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
      if (value === "in_review") return "In Review";
      if (value === "approved") return "Freigegeben";
      if (value === "rejected") return "Abgelehnt";
      return "Entwurf";
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
      if (manualCount) {
        manualCount.textContent = paginationTotal(manualPayload, manuals) + " Handbücher";
      }
      if (!manuals.length) {
        renderTableMessage(manualList, 6, "Keine Handbücher vorhanden.");
        return manuals;
      }
      manuals.forEach((manual) => {
        const actions = document.createElement("div");
        actions.className = "table-actions";
        actions.appendChild(actionButton("Download", async () => {
          await downloadFile(manual.download_url, manual.original_filename);
        }, { successMessage: "Download wurde gestartet." }));
        actions.appendChild(actionButton("Analysieren", async () => {
          const result = await api("/api/v1/documents/manuals/" + manual.id + "/analyze", { method: "POST" });
          renderSummary(result.title, result.analysis_status, result.analysis);
          await loadManuals();
        }, { busyText: "Analysiert...", successMessage: "Handbuchanalyse aktualisiert." }));
        actions.appendChild(actionButton("Zusammenfassen", async () => {
          const result = await api("/api/v1/documents/manuals/" + manual.id + "/summarize", { method: "POST" });
          renderSummary(result.title, result.summary_status, result.summary);
          await loadManuals();
        }, { busyText: "Fasst zusammen...", successMessage: "Handbuch-Zusammenfassung aktualisiert." }));
        if (canWrite("documents")) {
          actions.appendChild(actionButton("Löschen", async () => {
            if (!window.confirm(manual.title + " wirklich löschen?")) return;
            await api("/api/v1/documents/manuals/" + manual.id, { method: "DELETE" });
            await loadManuals();
          }, { danger: true, busyText: "Löscht...", successMessage: "Handbuch gelöscht." }));
        }
        manualList.appendChild(row([
          manual.title,
          manual.machine ? manual.machine.name : "-",
          manual.department || "-",
          manual.analysis_status,
          manual.summary_status,
          actions
        ]));
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
      const documentCount = document.querySelector("[data-document-count]");
      list.innerHTML = "";
      if (documentCount) {
        documentCount.textContent = paginationTotal(documentPayload, documents) + " Dokumente";
      }
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
        }, { successMessage: "HTML-Download wurde gestartet." }));
        actions.appendChild(actionButton("PDF", async () => {
          await downloadDocumentPdf(documentItem);
        }, { successMessage: "PDF-Download wurde gestartet." }));
        actions.appendChild(actionButton("Summary", async () => {
          await summarizeDocument(documentItem);
        }, { busyText: "Fasst zusammen...", successMessage: "Zusammenfassung aktualisiert." }));
        actions.appendChild(actionButton("Versionen", async () => {
          await showVersions(documentItem);
        }, { successMessage: "Versionen geladen." }));
        if (canWrite("documents")) {
          actions.appendChild(actionButton("Review", async () => {
            await changeDocumentStatus(documentItem, "submit-review");
          }, { busyText: "Sendet...", successMessage: "Dokument wurde in Review gesetzt." }));
          actions.appendChild(actionButton("Freigeben", async () => {
            await changeDocumentStatus(documentItem, "approve");
          }, { busyText: "Gibt frei...", successMessage: "Dokument freigegeben." }));
          actions.appendChild(actionButton("Ablehnen", async () => {
            await changeDocumentStatus(documentItem, "reject");
          }, { danger: true, busyText: "Lehnt ab...", successMessage: "Dokument abgelehnt." }));
        }
        list.appendChild(row([
          documentItem.title,
          String(documentItem.task_id),
          documentItem.department,
          documentItem.machine,
          statusText(documentItem.status),
          documentItem.version ? "v" + documentItem.version : "-",
          new Date(documentItem.created_at).toLocaleString("de-DE"),
          actions
        ]));
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
          errorMessage: "Upload fehlgeschlagen.",
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
      initDailyCockpit,
      initDepartments,
      initTasks,
      initErrors,
      initEmployees,
      initMachines,
      initInventory,
      initShiftPlans,
      initVacations,
      initDocuments,
      initUsers
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
    initCurrentWorkflowPage
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initCurrentWorkflowPage, { once: true });
  } else {
    initCurrentWorkflowPage();
  }
})();

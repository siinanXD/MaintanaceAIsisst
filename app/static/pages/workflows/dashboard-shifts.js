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

export { initDashboardShiftRealtime };

registerWorkflowInitializers({
  initDashboardShiftRealtime: initDashboardShiftRealtime,
  initCockpitShiftRealtime: initDashboardShiftRealtime
});

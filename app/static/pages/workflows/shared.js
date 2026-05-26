export const SHARED_MODULE_URLS = [
  "/static/shared/dom.js",
  "/static/shared/forms.js",
  "/static/shared/ui.js",
  "/static/shared/status-badges.js"
];
export let sharedModulePromise = null;

/**
 * Load shared workflow helper scripts before page initializers run.
 *
 * @returns {Promise<void>} Resolves after all shared modules executed.
 */
export async function loadWorkflowShared() {
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
export function sharedNamespace(name) {
  return window.maintenanceShared && window.maintenanceShared[name]
    ? window.maintenanceShared[name]
    : {};
}

export function token() {
  return window.maintenanceAuth ? window.maintenanceAuth.token() : null;
}

export function user() {
  return window.maintenanceAuth ? window.maintenanceAuth.user() : null;
}

export function canView(dashboard) {
  return window.maintenanceAuth && window.maintenanceAuth.canView
    ? window.maintenanceAuth.canView(dashboard)
    : false;
}

export function canWrite(dashboard) {
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
export function keywordText(value) {
  return String(value || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/ue/g, "u")
    .replace(/ae/g, "a")
    .replace(/oe/g, "o");
}

export function employeeAccessLevel() {
  return window.maintenanceAuth && window.maintenanceAuth.employeeAccessLevel
    ? window.maintenanceAuth.employeeAccessLevel()
    : "none";
}

export const DASHBOARD_LABELS = {
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

export const DASHBOARD_KEYS = Object.keys(DASHBOARD_LABELS);
export const EMPLOYEE_ACCESS_LEVELS = ["none", "basic", "shift", "confidential"];
export const TASK_PRIORITIES = ["urgent", "soon", "normal"];
export const TASK_STATUSES = ["open", "in_progress", "done", "cancelled"];

/**
 * Normalize API list envelopes through the shared DOM helper.
 *
 * @param {unknown} result API response payload.
 * @returns {Array} Normalized list items.
 */
export function listData(result) {
  return sharedNamespace("dom").listData(result);
}

/**
 * Resolve a paginated API total through the shared DOM helper.
 *
 * @param {object|null|undefined} result API response payload.
 * @param {Array|null|undefined} fallbackItems Fallback list.
 * @returns {number} Total item count.
 */
export function paginationTotal(result, fallbackItems) {
  return sharedNamespace("dom").paginationTotal(result, fallbackItems);
}

/**
 * Create a table row through the shared DOM helper.
 *
 * @param {Array} cells Cell values.
 * @returns {HTMLTableRowElement} Table row.
 */
export function row(cells) {
  return sharedNamespace("dom").row(cells);
}

/**
 * Read form data through the shared forms helper.
 *
 * @param {HTMLFormElement} form Form to read.
 * @returns {object} Plain form payload.
 */
export function formDataToObject(form) {
  return sharedNamespace("forms").formDataToObject(form);
}

/**
 * Show a toast through the shared UI helper.
 *
 * @param {string} message Toast message.
 * @param {string|object} variant Toast variant or options.
 * @returns {void}
 */
export function showInterfaceToast(message, variant) {
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
export function setStatusMessage(element, message, isError) {
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
export function setButtonBusy(button, busy, busyText) {
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
export function setFormBusy(form, busy, busyText) {
  return sharedNamespace("ui").setFormBusy(form, busy, busyText);
}

/**
 * Run an action through the shared UI helper.
 *
 * @param {object} options Action options.
 * @returns {Promise<unknown|null>} Action result.
 */
export function runAction(options) {
  return sharedNamespace("ui").runAction(options);
}

/**
 * Request text through the shared UI helper.
 *
 * @param {object} options Dialog options.
 * @returns {Promise<string|null>} Entered text.
 */
export function requestText(options) {
  return sharedNamespace("ui").requestText(options);
}

/**
 * Show information through the shared UI helper.
 *
 * @param {object} options Dialog options.
 * @returns {Promise<boolean>} Acknowledgement state.
 */
export function showInfoDialog(options) {
  return sharedNamespace("ui").showInfoDialog(options);
}

/**
 * Confirm an action through the shared UI helper.
 *
 * @param {object} options Dialog options.
 * @returns {Promise<boolean>} Confirmation state.
 */
export function confirmAction(options) {
  return sharedNamespace("ui").confirmAction(options);
}

/**
 * Create a reusable guided empty-state element.
 *
 * @param {string} title Empty-state title.
 * @param {string} hint Supporting hint text.
 * @returns {HTMLElement} Empty-state element.
 */
export function emptyState(title, hint) {
  return sharedNamespace("ui").emptyState(title, hint);
}

/**
 * Create a badge through the shared status-badge helper.
 *
 * @param {string|number|null|undefined} text Badge text.
 * @param {string} className Badge class.
 * @returns {HTMLSpanElement} Badge element.
 */
export function badge(text, className) {
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
export function labeledBadge(value, className, labelFormatter) {
  return sharedNamespace("statusBadges").labeledBadge(value, className, labelFormatter);
}

/**
 * Resolve task priority badge classes through the shared status-badge helper.
 *
 * @param {string} priority Aufgabe priority.
 * @returns {string} Badge classes.
 */
export function priorityBadgeClass(priority) {
  return sharedNamespace("statusBadges").taskPriorityBadgeClass(priority);
}

/**
 * Resolve task status badge classes through the shared status-badge helper.
 *
 * @param {string} status Aufgabe status.
 * @returns {string} Badge classes.
 */
export function statusBadgeClass(status) {
  return sharedNamespace("statusBadges").taskStatusBadgeClass(status);
}

/**
 * Resolve generic status badge classes through the shared status-badge helper.
 *
 * @param {string} status Status value.
 * @returns {string} Badge classes.
 */
export function genericStatusBadgeClass(status) {
  return sharedNamespace("statusBadges").genericStatusBadgeClass(status);
}

export async function api(path, options) {
  return window.maintenanceApi.request(path, options);
}

export async function downloadFile(url, filename) {
  return window.maintenanceApi.downloadFile(url, filename);
}

export function fillDepartments(selects, departments) {
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

export function sourceTypeLabel(source) {
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

export function renderQuellePanel(container, sources, emptyText) {
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

export function applyAiActionPreview(preview) {
  if (!preview || !preview.target) return;
  window.sessionStorage.setItem("maintenance_ai_action_preview", JSON.stringify(preview));
  window.location.href = preview.url || "/";
}

export function renderInlineActionPreview(container, preview) {
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

export function formatMoney(value) {
  return new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR" }).format(Number(value || 0));
}

export function priorityLabel(priority) {
  const labels = {
    urgent: "Kritisch",
    soon: "Bald",
    normal: "Normal"
  };
  return labels[priority] || priority || "-";
}

export function statusLabel(status) {
  const labels = {
    open: "Offen",
    in_progress: "In Arbeit",
    done: "Erledigt",
    cancelled: "Abgebrochen"
  };
  return labels[status] || status || "-";
}

export function setText(selector, value) {
  document.querySelectorAll(selector).forEach((element) => {
    element.textContent = String(value);
  });
}

export function actionButton(label, onClick, dangerOrOptions) {
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

export function formatDate(value) {
  if (!value) return "-";
  return new Date(value + "T00:00:00").toLocaleDateString("de-DE", {
    weekday: "short",
    day: "2-digit",
    month: "2-digit"
  });
}

export function shiftLabel(shift) {
  const labels = {
    Frueh: "Frühschicht",
    Spaet: "Spätschicht",
    Nacht: "Nachtschicht",
    Frei: "Frei",
    Urlaub: "Urlaub"
  };
  return labels[shift] || shift || "-";
}

export function renderShiftCalendar(container, calendar) {
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

export function revealSurface(element) {
  const collapsible = element.closest("[data-mobile-collapsible]");
  if (collapsible) {
    collapsible.open = true;
    collapsible.dataset.mobileTouched = "true";
  }
  element.scrollIntoView({ behavior: "smooth", block: "start" });
}

export function setSelectOptions(select, options, selectedValue) {
  select.innerHTML = "";
  options.forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    select.appendChild(option);
  });
  select.value = selectedValue || options[0] || "";
}

export function taskFormPayload(form) {
  const data = formDataToObject(form);
  Object.keys(data).forEach((key) => {
    if (data[key] === "") delete data[key];
  });
  return data;
}

export function consumeAiActionPreview(target) {
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

export async function fillMachineSelects() {
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


/**
 * Register workflow initializers from a domain module.
 *
 * @param {Record<string, Function>} initializers Named initializer callbacks.
 * @returns {void}
 */
export function registerWorkflowInitializers(initializers) {
  window.maintenanceWorkflowInitializers = window.maintenanceWorkflowInitializers || {};
  Object.assign(window.maintenanceWorkflowInitializers, initializers);
}

/**
 * Resolve a registered workflow initializer by name.
 *
 * @param {string} initializerName Name from the feature registry.
 * @returns {Function|null} Registered initializer callback or null.
 */
export function resolveWorkflowInitializer(initializerName) {
  const registry = window.maintenanceWorkflowInitializers || {};
  return typeof registry[initializerName] === "function" ? registry[initializerName] : null;
}

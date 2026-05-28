(function () {
  "use strict";

  const BASE = "/api/v1/handover";
  const SHIFT_ORDER = ["Frueh", "Spaet", "Nacht"];
  const SHIFT_LABEL = {
    Frueh: "Frühschicht",
    Spaet: "Spätschicht",
    Nacht: "Nachtschicht"
  };
  const PRODUCTION_STATUS_LABEL = {
    running: "Läuft stabil",
    reduced: "Reduzierte Leistung",
    stopped: "Stillstand",
    quality_hold: "Qualitätssperre"
  };
  const MACHINE_STATUS_LABEL = {
    ok: "In Ordnung",
    watch: "Beobachten",
    maintenance: "Wartung erforderlich",
    fault: "Störung aktiv"
  };

  const state = {
    handovers: [],
    machines: []
  };
  let initialized = false;

  function token() {
    return (window.maintenanceAuth && window.maintenanceAuth.token)
      ? window.maintenanceAuth.token()
      : window.localStorage.getItem("maintenance_access_token");
  }

  function authHeader() {
    const accessToken = token();
    return accessToken ? { Authorization: "Bearer " + accessToken } : {};
  }

  async function api(url, opts) {
    const response = await fetch(url, {
      headers: { "Content-Type": "application/json", ...authHeader() },
      ...opts
    });
    if (response.status === 204) return null;
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.message || body.error || "Fehler " + response.status);
    return body && body.success && "data" in body ? body.data : body;
  }

  function canWrite() {
    return window.maintenanceAuth && window.maintenanceAuth.canWrite
      ? window.maintenanceAuth.canWrite("shiftplans")
      : false;
  }

  function listData(result) {
    if (Array.isArray(result)) return result;
    if (result && Array.isArray(result.data)) return result.data;
    if (result && result.success && Array.isArray(result.items)) return result.items;
    return [];
  }

  function byId(id) {
    return document.getElementById(id);
  }

  function escapeHtml(value) {
    return String(value || "").replace(/[&<>"']/g, (character) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      "\"": "&quot;",
      "'": "&#39;"
    }[character]));
  }

  function setText(selector, value) {
    document.querySelectorAll(selector).forEach((element) => {
      element.textContent = String(value);
    });
  }

  function setMessage(element, message, isError) {
    if (!element) return;
    element.textContent = message || "";
    element.classList.toggle("is-error", Boolean(isError));
  }

  function adjacentShift(shiftType, offset) {
    const index = SHIFT_ORDER.indexOf(shiftType);
    if (index < 0) return "";
    return SHIFT_ORDER[(index + offset + SHIFT_ORDER.length) % SHIFT_ORDER.length];
  }

  function shiftLabel(value) {
    return SHIFT_LABEL[value] || value || "-";
  }

  function productionStatusLabel(value) {
    return PRODUCTION_STATUS_LABEL[value] || "Nicht bewertet";
  }

  function machineStatusLabel(value) {
    return MACHINE_STATUS_LABEL[value] || "Nicht bewertet";
  }

  function formatDate(value) {
    if (!value) return "-";
    return new Date(value + "T00:00:00").toLocaleDateString("de-DE", {
      weekday: "short",
      day: "2-digit",
      month: "2-digit",
      year: "numeric"
    });
  }

  function formatDateTime(value) {
    if (!value) return "";
    return new Date(value).toLocaleString("de-DE", {
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit"
    });
  }

  function machineName(handover) {
    return handover.machine && handover.machine.name ? handover.machine.name : "";
  }

  function handoverSearchText(handover) {
    return [
      handover.department,
      handover.area,
      machineName(handover),
      shiftLabel(handover.shift_type),
      productionStatusLabel(handover.production_status),
      machineStatusLabel(handover.machine_status),
      handover.problem_category,
      handover.content,
      handover.open_tasks,
      handover.machine_notes,
      handover.next_notes,
      handover.safety_notes,
      handover.material_notes,
      handover.cause,
      handover.action_taken,
      handover.follow_up_task,
      handover.responsible_employee,
      handover.involved_employees
    ].filter(Boolean).join(" ").toLowerCase();
  }

  function formPayload(form) {
    const payload = Object.fromEntries(new FormData(form).entries());
    payload.confirmed = byId("ho-confirmed") ? byId("ho-confirmed").checked : false;
    Object.keys(payload).forEach((key) => {
      if (payload[key] === "") delete payload[key];
    });
    return payload;
  }

  function syncAdjacentShiftSelects() {
    const current = byId("ho-shift-type");
    const previous = byId("ho-previous-shift");
    const next = byId("ho-next-shift");
    if (!current || !previous || !next || !current.value) return;
    previous.value = adjacentShift(current.value, -1);
    next.value = adjacentShift(current.value, 1);
  }

  function setStats(items) {
    const openCount = items.filter((item) => item.status !== "completed").length;
    const completedCount = items.filter((item) => item.status === "completed").length;
    const safetyCount = items.filter((item) => Boolean(item.safety_notes)).length;
    const followupCount = items.filter((item) => Boolean(item.open_tasks || item.follow_up_task)).length;
    setText("[data-ho-open-count]", openCount);
    setText("[data-ho-completed-count]", completedCount);
    setText("[data-ho-safety-count]", safetyCount);
    setText("[data-ho-followup-count]", followupCount);
  }

  function statusBadge(handover) {
    const completed = handover.status === "completed";
    return `<span class="badge status-badge ${completed ? "is-done" : "is-open"}">${completed ? "Bestätigt" : "Offen"}</span>`;
  }

  function metric(label, value) {
    return `
      <span>
        <small>${escapeHtml(label)}</small>
        <strong>${escapeHtml(value || "-")}</strong>
      </span>
    `;
  }

  function block(label, value, variant) {
    if (!value) return "";
    return `
      <section class="handover-block ${variant || ""}">
        <span>${escapeHtml(label)}</span>
        <p>${escapeHtml(value)}</p>
      </section>
    `;
  }

  function cardHtml(handover) {
    const completed = handover.status === "completed";
    const critical = handover.safety_notes || handover.machine_status === "fault" || handover.production_status === "stopped";
    const className = [
      "handover-record-card",
      completed ? "is-completed" : "is-open",
      critical ? "is-critical" : ""
    ].filter(Boolean).join(" ");
    return `
      <article class="${className}" data-handover-card="${handover.id}">
        <header class="handover-record-header">
          <div>
            <h3>${escapeHtml(formatDate(handover.shift_date))} · ${escapeHtml(shiftLabel(handover.shift_type))}</h3>
            <p>${escapeHtml(handover.department || "Bereich offen")}${handover.area ? " · " + escapeHtml(handover.area) : ""}${machineName(handover) ? " · " + escapeHtml(machineName(handover)) : ""}</p>
          </div>
          <div class="handover-record-badges">
            ${statusBadge(handover)}
            ${handover.problem_category ? `<span class="badge priority-badge is-normal">${escapeHtml(handover.problem_category)}</span>` : ""}
          </div>
        </header>
        <div class="handover-shift-flow" aria-label="Schichtfolge">
          ${metric("Vorherige Schicht", shiftLabel(handover.previous_shift))}
          ${metric("Aktuelle Schicht", shiftLabel(handover.shift_type))}
          ${metric("Nächste Schicht", shiftLabel(handover.next_shift))}
        </div>
        <div class="handover-record-metrics">
          ${metric("Produktion", productionStatusLabel(handover.production_status))}
          ${metric("Maschine", machineStatusLabel(handover.machine_status))}
          ${metric("Dauer", Number(handover.duration_minutes || 0) + " min")}
          ${metric("Verantwortlich", handover.responsible_employee || handover.handed_over_by)}
        </div>
        <div class="handover-record-blocks">
          ${block("Schichtlage", handover.content, "is-status")}
          ${block("Maschinenhinweis", handover.machine_notes, "is-machine")}
          ${block("Ursache", handover.cause, "is-cause")}
          ${block("Maßnahme", handover.action_taken, "is-action")}
          ${block("Sicherheit", handover.safety_notes, "is-safety")}
          ${block("Material / Ersatzteile", handover.material_notes, "is-material")}
          ${block("Offene Tasks", handover.open_tasks, "is-open-items")}
          ${block("Folgeaufgabe", handover.follow_up_task, "is-open-items")}
          ${block("Nächste Schicht", handover.next_notes, "is-next")}
        </div>
        <footer class="handover-record-footer">
          <span>${handover.handed_over_at ? "Bestätigt am " + escapeHtml(formatDateTime(handover.handed_over_at)) : "Noch nicht bestätigt"}</span>
          <div class="toolbar">
            ${!completed && canWrite() ? `<button class="btn btn-outline btn-sm" type="button" data-edit="${handover.id}">Bearbeiten</button>` : ""}
            ${!completed && canWrite() ? `<button class="btn btn-primary btn-sm" type="button" data-complete="${handover.id}">Bestätigen</button>` : ""}
          </div>
        </footer>
      </article>
    `;
  }

  function filteredHandovers() {
    const search = byId("filter-search") ? byId("filter-search").value.trim().toLowerCase() : "";
    if (!search) return state.handovers;
    return state.handovers.filter((handover) => handoverSearchText(handover).includes(search));
  }

  function renderList(items) {
    const listWrap = byId("ho-list-wrap");
    const emptyEl = byId("ho-empty");
    if (!listWrap || !emptyEl) return;
    const visibleItems = items || filteredHandovers();
    listWrap.querySelectorAll("[data-handover-card]").forEach((element) => element.remove());
    emptyEl.hidden = visibleItems.length > 0;
    emptyEl.textContent = visibleItems.length ? "" : "Keine Übergaben gefunden.";
    const summary = byId("ho-filter-summary");
    if (summary) {
      summary.textContent = visibleItems.length + " von " + state.handovers.length + " Übergaben sichtbar";
    }
    visibleItems.forEach((handover) => {
      const wrapper = document.createElement("div");
      wrapper.innerHTML = cardHtml(handover).trim();
      const card = wrapper.firstElementChild;
      card.querySelector("[data-edit]")?.addEventListener("click", () => openEditDialog(handover));
      card.querySelector("[data-complete]")?.addEventListener("click", () => completeHandover(handover.id));
      listWrap.appendChild(card);
    });
  }

  async function loadMachines() {
    const selects = Array.from(document.querySelectorAll("[data-ho-machine-select], [data-ho-filter-machine]"));
    if (!selects.length || !token()) return;
    try {
      state.machines = listData(await api("/api/v1/machines?limit=100"));
    } catch (error) {
      state.machines = [];
    }
    selects.forEach((select) => {
      const initialLabel = select.id === "filter-machine" ? "Alle Maschinen" : "Keine Maschine zugeordnet";
      select.innerHTML = `<option value="">${initialLabel}</option>`;
      state.machines.forEach((machine) => {
        const option = document.createElement("option");
        option.value = String(machine.id);
        option.textContent = machine.name;
        select.appendChild(option);
      });
    });
  }

  async function loadHandovers() {
    const emptyEl = byId("ho-empty");
    if (!token()) {
      if (emptyEl) emptyEl.textContent = "Bitte anmelden, um Schichtübergaben zu sehen.";
      return;
    }
    const params = new URLSearchParams();
    const filters = {
      department: byId("filter-dept") && byId("filter-dept").value,
      date: byId("filter-date") && byId("filter-date").value,
      shift_type: byId("filter-shift") && byId("filter-shift").value,
      status: byId("filter-status") && byId("filter-status").value,
      machine_id: byId("filter-machine") && byId("filter-machine").value
    };
    Object.entries(filters).forEach(([key, value]) => {
      if (value) params.set(key, value);
    });
    try {
      state.handovers = listData(await api(BASE + "?" + params.toString()));
      setStats(state.handovers);
      renderList();
    } catch (error) {
      if (emptyEl) {
        emptyEl.hidden = false;
        emptyEl.textContent = "Fehler: " + error.message;
      }
    }
  }

  function openEditDialog(handover) {
    const dialog = byId("ho-dialog");
    if (!dialog) return;
    dialog.dataset.handoverId = String(handover.id);
    byId("dlg-ho-production").value = handover.production_status || "";
    byId("dlg-ho-machine-status").value = handover.machine_status || "";
    byId("dlg-ho-content").value = handover.content || "";
    byId("dlg-ho-open").value = handover.open_tasks || "";
    byId("dlg-ho-machine").value = handover.machine_notes || "";
    byId("dlg-ho-cause").value = handover.cause || "";
    byId("dlg-ho-action").value = handover.action_taken || "";
    byId("dlg-ho-safety").value = handover.safety_notes || "";
    byId("dlg-ho-material").value = handover.material_notes || "";
    byId("dlg-ho-next").value = handover.next_notes || "";
    setMessage(byId("dlg-ho-msg"), "");
    dialog.showModal();
  }

  async function saveDialog() {
    const dialog = byId("ho-dialog");
    const saveButton = byId("dlg-ho-save");
    const message = byId("dlg-ho-msg");
    const handoverId = dialog && dialog.dataset.handoverId;
    if (!handoverId) return;
    saveButton.disabled = true;
    setMessage(message, "Wird gespeichert...");
    try {
      await api(BASE + "/" + handoverId, {
        method: "PATCH",
        body: JSON.stringify({
          production_status: byId("dlg-ho-production").value,
          machine_status: byId("dlg-ho-machine-status").value,
          content: byId("dlg-ho-content").value,
          open_tasks: byId("dlg-ho-open").value,
          machine_notes: byId("dlg-ho-machine").value,
          cause: byId("dlg-ho-cause").value,
          action_taken: byId("dlg-ho-action").value,
          safety_notes: byId("dlg-ho-safety").value,
          material_notes: byId("dlg-ho-material").value,
          next_notes: byId("dlg-ho-next").value
        })
      });
      dialog.close();
      await loadHandovers();
    } catch (error) {
      setMessage(message, error.message, true);
    } finally {
      saveButton.disabled = false;
    }
  }

  async function completeHandover(id) {
    const summary = byId("ho-filter-summary");
    try {
      setMessage(summary, "Übergabe wird bestätigt...");
      await api(BASE + "/" + id + "/complete", { method: "POST" });
      await loadHandovers();
      setMessage(summary, "Übergabe bestätigt.");
    } catch (error) {
      setMessage(summary, error.message, true);
    }
  }

  async function submitForm(event) {
    event.preventDefault();
    const form = event.currentTarget || document.querySelector("[data-handover-form]") || byId("ho-form");
    const button = byId("ho-submit-btn");
    const message = byId("ho-msg");
    const payload = formPayload(form);
    if (!payload.department || !payload.shift_date || !payload.shift_type) {
      setMessage(message, "Bitte Bereich, Datum und aktuelle Schicht ausfüllen.", true);
      return;
    }
    button.disabled = true;
    setMessage(message, "Übergabe wird gespeichert...");
    try {
      await api(BASE, { method: "POST", body: JSON.stringify(payload) });
      form.reset();
      byId("ho-date").value = new Date().toISOString().slice(0, 10);
      setMessage(message, "Übergabe gespeichert.");
      await loadHandovers();
    } catch (error) {
      setMessage(message, "Fehler: " + error.message, true);
    } finally {
      button.disabled = false;
    }
  }

  function resetFilters() {
    ["filter-search", "filter-dept", "filter-date", "filter-shift", "filter-status", "filter-machine"].forEach((id) => {
      const element = byId(id);
      if (element) element.value = "";
    });
    loadHandovers();
  }

  function bindEvents() {
    const form = document.querySelector("[data-handover-form]") || byId("ho-form");
    if (form) form.addEventListener("submit", submitForm);
    byId("ho-filter-btn")?.addEventListener("click", loadHandovers);
    byId("ho-filter-reset")?.addEventListener("click", resetFilters);
    byId("filter-search")?.addEventListener("input", () => renderList());
    byId("dlg-ho-save")?.addEventListener("click", saveDialog);
    byId("dlg-ho-cancel")?.addEventListener("click", () => byId("ho-dialog").close());
    byId("ho-shift-type")?.addEventListener("change", syncAdjacentShiftSelects);
    document.querySelector("[data-handover-focus-list]")?.addEventListener("click", () => {
      byId("handover-list")?.scrollIntoView({ behavior: "smooth", block: "start" });
      byId("filter-search")?.focus();
    });
  }

  async function init() {
    if (initialized) return;
    initialized = true;
    if (byId("ho-date")) byId("ho-date").value = new Date().toISOString().slice(0, 10);
    bindEvents();
    await loadMachines();
    await loadHandovers();
  }

  window.MaintenanceHandoverRuntime = {
    initHandover: init,
    loadHandoverMachines: loadMachines,
    loadHandovers
  };

  window.addEventListener("maintenance-auth-ready", () => {
    loadMachines();
    loadHandovers();
  });
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }
})();

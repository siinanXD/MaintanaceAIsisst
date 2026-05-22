(function () {
  "use strict";

  const BASE = "/api/v1/shiftplans";
  const SHIFT_WINDOWS = { Frueh: ["06:00","14:00"], Spaet: ["14:00","22:00"], Nacht: ["22:00","06:00"] };
  const SHIFT_ORDER  = ["Frueh","Spaet","Nacht","Urlaub","Frei"];
  const SHIFT_LABEL  = { Frueh:"Frühschicht\n06:00–14:00", Spaet:"Spätschicht\n14:00–22:00", Nacht:"Nachtschicht\n22:00–06:00", Urlaub:"Urlaub", Frei:"Frei" };
  const DAYS_DE = ["So","Mo","Di","Mi","Do","Fr","Sa"];

  // Local ISO date string (avoids UTC/timezone shift from toISOString())
  function localISO(d) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
  }

  let allPlans = [];
  let machines = [];
  let machinesLoadPromise = null;
  let shiftModels = [];
  let shiftModelsLoadPromise = null;
  let currentPlan = null;
  let editEntryId = null;
  let initializedToken = null;
  let initializationPromise = null;

  // ── DOM ───────────────────────────────────────────────────────────────────
  const form        = document.getElementById("sp-form");
  const previewBtn  = document.getElementById("sp-preview-btn");
  const submitBtn   = document.getElementById("sp-submit-btn");
  const spMsg       = document.getElementById("sp-msg");
  const spSelector  = document.getElementById("sp-selector");
  const planSelect  = document.getElementById("sp-plan-select");
  const tableWrap   = document.getElementById("sp-table-wrap");
  const thead       = document.getElementById("sp-thead");
  const tbody       = document.getElementById("sp-tbody");
  const emptyMsg    = document.getElementById("sp-empty-msg");
  const statsEl     = document.getElementById("sp-stats");
  const statsBody   = document.getElementById("sp-stats-body");
  const warningsEl  = document.getElementById("sp-warnings");
  const warnSummary = document.getElementById("sp-warn-summary");
  const warnList    = document.getElementById("sp-warn-list");
  const changelogEl = document.getElementById("sp-changelog");
  const changelogBody = document.getElementById("sp-changelog-body");
  const deleteWrap  = document.getElementById("sp-delete-wrap");
  const deleteBtn   = document.getElementById("sp-delete-btn");
  const publishBtn  = document.getElementById("sp-publish-btn");
  const statusBadge = document.getElementById("sp-status-badge");
  const printBtn    = document.getElementById("sp-print-btn");
  const csvBtn      = document.getElementById("sp-csv-btn");
  const shiftModelSelect = document.getElementById("sp-shift-model");
  const shiftModelPreview = document.getElementById("sp-model-preview");
  const shiftModelTitle = document.getElementById("sp-model-title");
  const shiftModelDescription = document.getElementById("sp-model-description");
  const shiftModelShifts = document.getElementById("sp-model-shifts");
  const shiftModelTeamCount = document.getElementById("sp-model-team-count");
  const shiftModelWeekend = document.getElementById("sp-model-weekend");
  const shiftModelRotation = document.getElementById("sp-model-rotation");
  const shiftModelRest = document.getElementById("sp-model-rest");
  const machinePicker = document.getElementById("sp-machine-picker");
  const printTitle  = document.getElementById("print-title");
  const printMeta   = document.getElementById("print-meta");
  const dialog      = document.getElementById("sp-dialog");
  const dlgInfo     = document.getElementById("sp-dlg-info");
  const dlgShift    = document.getElementById("dlg-shift");
  const dlgStart    = document.getElementById("dlg-start");
  const dlgEnd      = document.getElementById("dlg-end");
  const dlgNotes    = document.getElementById("dlg-notes");
  const dlgTimes    = document.getElementById("dlg-times");
  const dlgSave     = document.getElementById("dlg-save");
  const dlgDelete   = document.getElementById("dlg-delete");
  const dlgCancel   = document.getElementById("dlg-cancel");
  const dlgMsg      = document.getElementById("dlg-msg");

  // ── Helpers ───────────────────────────────────────────────────────────────
  function token() {
    return (window.maintenanceAuth && window.maintenanceAuth.token)
      ? window.maintenanceAuth.token()
      : window.localStorage.getItem("maintenance_access_token");
  }
  function authHdr() {
    const t = token();
    return t ? { Authorization: "Bearer " + t } : {};
  }
  async function api(url, opts) {
    const res = await fetch(url, {
      headers: { "Content-Type": "application/json", ...authHdr() },
      ...opts,
    });
    if (res.status === 204) return null;
    const body = await res.json().catch(() => ({}));
    if (!res.ok) {
      const error = new Error(body.message || body.error || "Fehler " + res.status);
      error.payload = body;
      throw error;
    }
    return (body && body.success && "data" in body) ? body.data : body;
  }
  function isAdmin() {
    return window.maintenanceAuth && window.maintenanceAuth.isAdmin
      ? window.maintenanceAuth.isAdmin() : false;
  }
  function canWrite() {
    return window.maintenanceAuth && window.maintenanceAuth.canWrite
      ? window.maintenanceAuth.canWrite("shiftplans") : false;
  }

  function selectedMachineIds() {
    if (!machinePicker) return [];
    return Array.from(machinePicker.querySelectorAll("input[type='checkbox']:checked"))
      .map((input) => parseInt(input.value, 10))
      .filter((value) => Number.isInteger(value));
  }

  function renderMachines(items) {
    if (!machinePicker) return;
    machinePicker.innerHTML = "";
    if (!items.length) {
      machinePicker.innerHTML = "<p class='panel-meta'>Keine Maschinen vorhanden.</p>";
      return;
    }
    items.forEach((machine) => {
      const label = document.createElement("label");
      label.className = "sp-machine-option";
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.value = machine.id;
      checkbox.checked = true;
      const text = document.createElement("span");
      text.textContent = machine.name + " (" + (machine.required_employees || 1) + " MA)";
      label.appendChild(checkbox);
      label.appendChild(text);
      machinePicker.appendChild(label);
    });
  }

  async function loadMachines() {
    if (!machinePicker) return [];
    if (!token()) return machines;
    if (machinesLoadPromise) return machinesLoadPromise;
    machinesLoadPromise = api("/api/v1/machines")
      .then((items) => {
        machines = Array.isArray(items) ? items : (items.items || []);
        renderMachines(machines);
        return machines;
      })
      .catch((err) => {
        machinePicker.innerHTML = "<p class='panel-meta text-error'>Maschinen konnten nicht geladen werden.</p>";
        if (spMsg) spMsg.textContent = "Maschinen konnten nicht geladen werden: " + err.message;
        return machines;
      })
      .finally(() => {
        machinesLoadPromise = null;
      });
    return machinesLoadPromise;
  }

  // ── Load & select plans ───────────────────────────────────────────────────
  function beginnerModelLabel(model) {
    const labels = {
      one_shift: "Tagschicht",
      two_shift: "2-Schicht Fr\u00fch/Sp\u00e4t",
      three_shift: "3-Schicht Fr\u00fch/Sp\u00e4t/Nacht",
      teilkonti: "Teilkonti",
      vollkonti_4: "Vollkonti 4-Schicht",
      vollkonti_5: "Vollkonti 5-Schicht",
    };
    return labels[model.key] || model.display_name || model.name || model.key;
  }

  function formatShiftWindow(shift) {
    const name = shift.label || shift.name || shift.key;
    return name + " " + shift.start_time + "-" + shift.end_time;
  }

  function shiftSummary(model) {
    if (model.shifts_summary) return model.shifts_summary;
    return (model.shifts || []).map(formatShiftWindow).join(", ");
  }

  function rotationLabel(value) {
    if (value === "forward") return "Vorw\u00e4rtsrotation Fr\u00fch \u2192 Sp\u00e4t \u2192 Nacht";
    if (value === "fixed") return "Feste Tagschicht";
    return value || "-";
  }

  function updateHiddenRhythm(model) {
    const rhythmInput = document.getElementById("sp-rhythm");
    if (!rhythmInput) return;
    rhythmInput.value = model ? (model.display_name || model.name || model.key) : "";
  }

  function renderShiftModelPreview(model) {
    updateHiddenRhythm(model);
    if (!shiftModelPreview) return;
    if (!model) {
      shiftModelPreview.hidden = true;
      return;
    }
    shiftModelTitle.textContent = beginnerModelLabel(model);
    shiftModelDescription.textContent = model.description || "";
    shiftModelShifts.textContent = shiftSummary(model);
    shiftModelTeamCount.textContent = String(model.team_count || "-");
    shiftModelWeekend.textContent = model.weekend_label || (
      model.weekend_operation ? "Wochenendbetrieb aktiv" : "Montag bis Freitag"
    );
    shiftModelRotation.textContent = model.rotation_label || rotationLabel(model.rotation_direction);
    shiftModelRest.textContent = (model.recommended_rest_hours || 11) + " Stunden empfohlen";
    shiftModelPreview.hidden = false;
  }

  function selectedShiftModel() {
    if (!shiftModelSelect || !shiftModelSelect.value) return null;
    if (!shiftModels.length) shiftModels = readShiftModelsFromSelect();
    const cachedModel = shiftModels.find((model) => model.key === shiftModelSelect.value);
    if (cachedModel) return cachedModel;
    const selectedOption = shiftModelSelect.options[shiftModelSelect.selectedIndex];
    if (!selectedOption || !selectedOption.value) return null;
    return {
      key: selectedOption.value,
      display_name: selectedOption.dataset.displayName || selectedOption.textContent,
      name: selectedOption.dataset.displayName || selectedOption.textContent,
      description: selectedOption.dataset.description || "",
      shifts_summary: selectedOption.dataset.shiftsSummary || "",
      team_count: Number(selectedOption.dataset.teamCount || 0),
      weekend_operation: selectedOption.dataset.weekendOperation === "true",
      weekend_label: selectedOption.dataset.weekendLabel || "",
      rotation_direction: selectedOption.dataset.rotationDirection || "",
      rotation_label: selectedOption.dataset.rotationLabel || "",
      recommended_rest_hours: Number(selectedOption.dataset.restHours || 11),
    };
  }

  function readShiftModelsFromSelect() {
    if (!shiftModelSelect) return [];
    return Array.from(shiftModelSelect.options)
      .filter((option) => option.value)
      .map((option) => ({
        key: option.value,
        display_name: option.dataset.displayName || option.textContent,
        name: option.dataset.displayName || option.textContent,
        description: option.dataset.description || "",
        shifts_summary: option.dataset.shiftsSummary || "",
        team_count: Number(option.dataset.teamCount || 0),
        weekend_operation: option.dataset.weekendOperation === "true",
        weekend_label: option.dataset.weekendLabel || "",
        rotation_direction: option.dataset.rotationDirection || "",
        rotation_label: option.dataset.rotationLabel || "",
        recommended_rest_hours: Number(option.dataset.restHours || 11),
      }));
  }

  function populateShiftModelSelect(models) {
    if (!shiftModelSelect) return;
    const previousValue = shiftModelSelect.value;
    shiftModelSelect.innerHTML = "";
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.disabled = true;
    placeholder.textContent = "Bitte Schichtmodell w\u00e4hlen";
    shiftModelSelect.appendChild(placeholder);
    models.forEach((model) => {
      const option = document.createElement("option");
      option.value = model.key;
      option.textContent = beginnerModelLabel(model);
      shiftModelSelect.appendChild(option);
    });
    if (previousValue && models.some((model) => model.key === previousValue)) {
      shiftModelSelect.value = previousValue;
    } else {
      shiftModelSelect.value = "";
    }
    renderShiftModelPreview(selectedShiftModel());
  }

  async function loadShiftModels() {
    if (!shiftModelSelect) return [];
    if (!shiftModels.length) shiftModels = readShiftModelsFromSelect();
    if (!token()) return shiftModels;
    if (shiftModelsLoadPromise) return shiftModelsLoadPromise;
    shiftModelsLoadPromise = api(BASE + "/models")
      .then((models) => {
        shiftModels = models;
        populateShiftModelSelect(shiftModels);
        return shiftModels;
      })
      .catch((err) => {
        if (!shiftModels.length) {
          shiftModelSelect.innerHTML = "<option value=''>Modelle konnten nicht geladen werden</option>";
        }
        if (spMsg) spMsg.textContent = "Schichtmodelle konnten nicht geladen werden: " + err.message;
        return shiftModels;
      })
      .finally(() => {
        shiftModelsLoadPromise = null;
      });
    return shiftModelsLoadPromise;
  }

  if (shiftModelSelect) {
    shiftModelSelect.addEventListener("change", () => {
      renderShiftModelPreview(selectedShiftModel());
      if (spMsg) spMsg.textContent = "";
    });
  }

  async function loadPlans(selectId, fallbackPlan) {
    if (!token()) return;
    try {
      const res = await fetch(BASE, { headers: authHdr() });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        emptyMsg.textContent = "Fehler beim Laden der Pläne: " + (body.message || res.status);
        emptyMsg.hidden = false;
        return;
      }
      allPlans = await res.json();
    } catch (err) {
      allPlans = [];
      emptyMsg.textContent = "Netzwerkfehler: " + err.message;
      emptyMsg.hidden = false;
    }
    if (
      fallbackPlan &&
      selectId !== undefined &&
      !allPlans.some((plan) => plan.id === selectId)
    ) {
      allPlans.unshift(fallbackPlan);
    }

    if (!allPlans.length) {
      emptyMsg.hidden   = false;
      tableWrap.hidden  = true;
      spSelector.hidden = true;
      statsEl.hidden    = true;
      warningsEl.hidden = true;
      printBtn.hidden   = true;
      csvBtn.hidden     = true;
      publishBtn.hidden = true;
      deleteWrap.hidden = true;
      return;
    }

    emptyMsg.hidden   = true;
    spSelector.hidden = false;
    printBtn.hidden   = false;
    csvBtn.hidden     = false;

    planSelect.innerHTML = "";
    allPlans.forEach((p, i) => {
      const opt = document.createElement("option");
      opt.value = i;
      const statusMark = p.status === "published" ? " ✓" : " [Entwurf]";
      opt.textContent = p.title + (p.department ? " [" + p.department + "]" : "") + statusMark;
      planSelect.appendChild(opt);
    });

    const idx = selectedPlanIndex(selectId);
    planSelect.value = idx;
    renderPlan(allPlans[planSelect.value] || allPlans[0]);
  }

  function selectedPlanIndex(selectId) {
    if (selectId !== undefined) {
      const exactIndex = allPlans.findIndex((plan) => plan.id === selectId);
      if (exactIndex >= 0) return exactIndex;
    }
    const firstFilledIndex = allPlans.findIndex(
      (plan) => Array.isArray(plan.entries) && plan.entries.length > 0
    );
    return firstFilledIndex >= 0 ? firstFilledIndex : 0;
  }

  function renderPlan(plan) {
    currentPlan = plan;
    renderGrid(plan);
    renderStats(plan);
    if (plan.id) {
      loadConflicts(plan.id);
    } else {
      showWarnings(plan.warnings || []);
    }
    const admin = isAdmin();
    deleteWrap.hidden = !admin || !plan.id;
    if (changelogEl) changelogEl.hidden = !admin || !plan.id;
    if (admin && plan.id) loadChangelog(plan.id);

    // Publish button (admin only)
    publishBtn.hidden = !admin || !plan.id;
    if (admin) {
      const published = plan.status === "published";
      publishBtn.textContent = published ? "↩ Zurück zu Entwurf" : "✓ Veröffentlichen";
      publishBtn.className   = "btn btn-sm no-print " +
        (published ? "btn-warning" : "btn-success");
    }

    // Status-Badge
    statusBadge.hidden = false;
    if (plan.status === "preview") {
      statusBadge.textContent = "Vorschau";
      statusBadge.className   = "badge badge-info";
    } else if (plan.status === "published") {
      statusBadge.textContent = "✓ Veröffentlicht";
      statusBadge.className   = "badge badge-success";
    } else {
      statusBadge.textContent = "Entwurf";
      statusBadge.className   = "badge badge-ghost";
    }

    // Update print header
    printTitle.textContent = plan.title || "Schichtplan";
    printMeta.textContent  = "Abteilung: " + (plan.department || "–") +
      " | " + plan.start_date + " | " + plan.days + " Tage" +
      (plan.status === "published" ? " | ✓ Veröffentlicht" : " | Entwurf");
  }

  // ── Excel-Grid ────────────────────────────────────────────────────────────
  // Rows = Schichttyp, Cols = day, Cell = machine+employee list
  function renderGrid(plan) {
    tableWrap.hidden = false;
    thead.innerHTML  = "";
    tbody.innerHTML  = "";

    const start = new Date(plan.start_date + "T00:00:00");
    const dates = [];
    for (let i = 0; i < plan.days; i++) {
      const d = new Date(start);
      d.setDate(start.getDate() + i);
      dates.push(d);
    }

    // Index: shiftKey → dateStr → [entry]
    const idx = {};
    const usedShifts = new Set();
    plan.entries.forEach((e) => {
      const s = e.shift;
      usedShifts.add(s);
      if (!idx[s]) idx[s] = {};
      const ds = e.work_date;
      if (!idx[s][ds]) idx[s][ds] = [];
      idx[s][ds].push(e);
    });
    (plan.unassigned_slots || []).forEach((slot) => {
      const s = slot.shift;
      usedShifts.add(s);
      if (!idx[s]) idx[s] = {};
      if (!idx[s][slot.work_date]) idx[s][slot.work_date] = [];
      idx[s][slot.work_date].push({ ...slot, unassigned: true });
    });

    const activeShifts = SHIFT_ORDER.filter((s) => usedShifts.has(s));
    const canEdit = canWrite() && !plan.is_preview;

    // ── Header ──
    const hrow = document.createElement("tr");
    const th0 = document.createElement("th");
    th0.className = "sp-col-shift";
    th0.textContent = "Schicht";
    hrow.appendChild(th0);
    dates.forEach((d) => {
      const th = document.createElement("th");
      th.className = "sp-col-day";
      const dow = DAYS_DE[d.getDay()];
      const dd  = String(d.getDate()).padStart(2, "0");
      const mm  = String(d.getMonth() + 1).padStart(2, "0");
      th.innerHTML = "<span class='sp-dow'>" + dow + "</span><br><span class='sp-date'>" + dd + "." + mm + ".</span>";
      hrow.appendChild(th);
    });
    thead.appendChild(hrow);

    // ── Rows ──
    if (!activeShifts.length) {
      const tr = document.createElement("tr");
      const td = document.createElement("td");
      td.colSpan = dates.length + 1;
      td.className = "text-center";
      td.style.opacity = "0.5";
      td.textContent = "Keine Einträge im Plan.";
      tr.appendChild(td);
      tbody.appendChild(tr);
      return;
    }

    activeShifts.forEach((shiftKey) => {
      const tr = document.createElement("tr");

      // Schicht-Label (sticky)
      const thRow = document.createElement("th");
      thRow.className = "sp-col-shift sp-shift-label sp-shift-" + shiftKey.toLowerCase();
      thRow.textContent = SHIFT_LABEL[shiftKey] || shiftKey;
      tr.appendChild(thRow);

      // Day cells
      dates.forEach((d) => {
        const dateStr = localISO(d);
        const td = document.createElement("td");
        td.className = "sp-day-cell sp-cell-" + shiftKey.toLowerCase();

        if (canEdit) {
          td.addEventListener("dragover", (ev) => { ev.preventDefault(); td.classList.add("sp-drop-target"); });
          td.addEventListener("dragleave", () => td.classList.remove("sp-drop-target"));
          td.addEventListener("drop", async (ev) => {
            ev.preventDefault();
            td.classList.remove("sp-drop-target");
            const entryId = ev.dataTransfer.getData("entry_id");
            if (!entryId) return;
            try {
              await api(BASE + "/entries/" + entryId + "/move", {
                method: "PATCH",
                body: JSON.stringify({ target_date: dateStr, target_shift: shiftKey }),
              });
              await loadPlans(currentPlan ? currentPlan.id : undefined);
            } catch (err) { alert("Fehler beim Verschieben: " + err.message); }
          });
        }
        const dayEntries = (idx[shiftKey] || {})[dateStr] || [];
        if (!dayEntries.length) {
          td.innerHTML = "<span class='sp-empty'>–</span>";
        } else {
          dayEntries.forEach((entry) => {
            const machineName = entry.machine ? entry.machine.name : null;
            const slotMachineName = machineName || entry.machine_name || null;
            const empName     = entry.unassigned
              ? "Unbesetzt (" + (entry.missing || 1) + ")"
              : (entry.employee ? entry.employee.name : "?");
            const chip = document.createElement(canEdit && !entry.unassigned ? "button" : "div");
            chip.className = "sp-chip" + (entry.unassigned ? " sp-unassigned" : "");
            if (canEdit && !entry.unassigned) {
              chip.type = "button";
              chip.setAttribute("aria-label", "Bearbeiten: " + empName);
              chip.setAttribute("draggable", "true");
              chip.dataset.entryId = entry.id;
              chip.addEventListener("click", () => openDialog(entry));
              chip.addEventListener("dragstart", (ev) => {
                ev.dataTransfer.setData("entry_id", entry.id);
                ev.dataTransfer.effectAllowed = "move";
                chip.classList.add("sp-dragging");
              });
              chip.addEventListener("dragend", () => chip.classList.remove("sp-dragging"));
              chip.addEventListener("dragover", (ev) => {
                ev.preventDefault();
                ev.stopPropagation();
                if (ev.dataTransfer.getData("entry_id") !== String(entry.id))
                  chip.classList.add("sp-chip-drop-target");
              });
              chip.addEventListener("dragleave", () => chip.classList.remove("sp-chip-drop-target"));
              chip.addEventListener("drop", async (ev) => {
                ev.preventDefault();
                ev.stopPropagation();
                chip.classList.remove("sp-chip-drop-target");
                const entryId = ev.dataTransfer.getData("entry_id");
                if (!entryId || entryId === String(entry.id)) return;
                try {
                  await api(BASE + "/entries/" + entryId + "/move", {
                    method: "PATCH",
                    body: JSON.stringify({ target_entry_id: entry.id }),
                  });
                  await loadPlans(currentPlan ? currentPlan.id : undefined);
                } catch (err) { alert("Fehler beim Tauschen: " + err.message); }
              });
            }
            if (slotMachineName) {
              chip.innerHTML =
                "<span class='sp-machine'>" + slotMachineName + "</span>" +
                "<span class='sp-emp'>" + empName + "</span>";
            } else {
              chip.innerHTML = "<span class='sp-emp'>" + empName + "</span>";
            }
            td.appendChild(chip);
          });
        }
        tr.appendChild(td);
      });

      tbody.appendChild(tr);
    });
  }

  // ── Stats ─────────────────────────────────────────────────────────────────
  function renderStats(plan) {
    statsEl.hidden = false;
    statsBody.innerHTML = "";
    const emp = {};
    plan.entries.forEach((e) => {
      const id = e.employee ? e.employee.id : null;
      if (!id) return;
      if (!emp[id]) emp[id] = { name: e.employee.name, Frueh:0, Spaet:0, Nacht:0, Urlaub:0, h:0 };
      if (e.shift === "Frueh") emp[id].Frueh++;
      else if (e.shift === "Spaet") emp[id].Spaet++;
      else if (e.shift === "Nacht") emp[id].Nacht++;
      else if (e.shift === "Urlaub") emp[id].Urlaub++;
      if (e.start_time && e.end_time) emp[id].h += shiftH(e.start_time, e.end_time);
    });
    Object.values(emp).sort((a,b) => a.name.localeCompare(b.name)).forEach((s) => {
      const tr = document.createElement("tr");
      [s.name, s.Frueh, s.Spaet, s.Nacht, s.Urlaub, s.h.toFixed(1)+"h"].forEach((v, i) => {
        const td = i === 0 ? document.createElement("th") : document.createElement("td");
        if (i === 0) td.scope = "row";
        td.textContent = v;
        tr.appendChild(td);
      });
      statsBody.appendChild(tr);
    });
  }
  function shiftH(s, e) {
    const [sh,sm] = s.split(":").map(Number);
    const [eh,em] = e.split(":").map(Number);
    let d = (eh*60+em) - (sh*60+sm);
    if (d <= 0) d += 24*60;
    return d/60;
  }

  // ── Warnings ──────────────────────────────────────────────────────────────
  function showWarnings(list) {
    warnList.innerHTML = "";
    if (!list || !list.length) { warningsEl.hidden = true; return; }
    warnSummary.textContent = "⚠ Warnungen anzeigen (" + list.length + ")";
    list.forEach((w) => {
      const li = document.createElement("li");
      li.className = "panel-meta " + (w.severity === "critical" ? "text-error" : "text-warning");
      li.textContent = (w.severity === "critical" ? "⛔ " : "⚠ ") + w.message;
      warnList.appendChild(li);
    });
    warningsEl.hidden = false;
  }

  async function loadConflicts(planId) {
    try {
      const payload = await api(BASE + "/" + planId + "/conflicts");
      showWarnings(payload.conflicts || []);
    } catch (_) {
      showWarnings(currentPlan && currentPlan.warnings);
    }
  }

  // ── Changelog ─────────────────────────────────────────────────────────────
  async function loadChangelog(planId) {
    if (!isAdmin()) return;
    try {
      const logs = await api(BASE + "/" + planId + "/changelog");
      changelogBody.innerHTML = "";
      (logs || []).forEach((l) => {
        const tr = document.createElement("tr");
        [new Date(l.changed_at).toLocaleString("de-DE"), l.user||"–", l.action, l.field_name||"–", l.old_value||"–", l.new_value||"–"]
          .forEach((v) => { const td = document.createElement("td"); td.textContent = v; tr.appendChild(td); });
        changelogBody.appendChild(tr);
      });
    } catch (_) {}
  }

  // ── Edit dialog ───────────────────────────────────────────────────────────
  function openDialog(entry) {
    editEntryId = entry.id;
    dlgMsg.textContent = "";
    dlgShift.value = entry.shift;
    dlgStart.value = entry.start_time || "";
    dlgEnd.value   = entry.end_time   || "";
    dlgNotes.value = entry.notes      || "";
    dlgInfo.textContent = (entry.employee ? entry.employee.name : "") + " — " + entry.work_date;
    dlgTimes.hidden = ["Frei","Urlaub"].includes(entry.shift);
    dlgDelete.hidden = !isAdmin();
    dialog.showModal();
  }

  dlgShift.addEventListener("change", () => {
    const isWork = !["Frei","Urlaub"].includes(dlgShift.value);
    dlgTimes.hidden = !isWork;
    if (isWork && SHIFT_WINDOWS[dlgShift.value]) {
      dlgStart.value = SHIFT_WINDOWS[dlgShift.value][0];
      dlgEnd.value   = SHIFT_WINDOWS[dlgShift.value][1];
    }
  });

  dlgSave.addEventListener("click", async () => {
    if (!editEntryId) return;
    dlgMsg.textContent = "Wird gespeichert…";
    dlgSave.disabled = true;
    const payload = { shift: dlgShift.value, notes: dlgNotes.value };
    if (!["Frei","Urlaub"].includes(dlgShift.value)) {
      payload.start_time = dlgStart.value;
      payload.end_time   = dlgEnd.value;
    }
    try {
      await api(BASE + "/entries/" + editEntryId, { method: "PATCH", body: JSON.stringify(payload) });
      dialog.close();
      const pid = currentPlan ? currentPlan.id : undefined;
      await loadPlans(pid);
    } catch (err) { dlgMsg.textContent = err.message; }
    finally { dlgSave.disabled = false; }
  });

  dlgDelete.addEventListener("click", async () => {
    if (!editEntryId || !confirm("Eintrag wirklich löschen?")) return;
    dlgDelete.disabled = true;
    try {
      await api(BASE + "/entries/" + editEntryId, { method: "DELETE" });
      dialog.close();
      const pid = currentPlan ? currentPlan.id : undefined;
      await loadPlans(pid);
    } catch (err) { dlgMsg.textContent = err.message; }
    finally { dlgDelete.disabled = false; }
  });

  dlgCancel.addEventListener("click", () => dialog.close());
  dialog.addEventListener("keydown", (e) => { if (e.key === "Escape") dialog.close(); });

  // ── Plan selector ─────────────────────────────────────────────────────────
  planSelect.addEventListener("change", () => {
    const p = allPlans[parseInt(planSelect.value, 10)];
    if (p) renderPlan(p);
  });

  // ── Plan l?schen ───────────────────────────────────────────────────────────
  deleteBtn.addEventListener("click", async () => {
    if (!currentPlan || !confirm("Plan \"" + currentPlan.title + "\" wirklich löschen?")) return;
    deleteBtn.disabled = true;
    try {
      await api(BASE + "/" + currentPlan.id, { method: "DELETE" });
      currentPlan = null;
      await loadPlans();
    } catch (err) { alert(err.message); }
    finally { deleteBtn.disabled = false; }
  });

  // ── Publish plan ─────────────────────────────────────────────────────────
  publishBtn.addEventListener("click", async () => {
    if (!currentPlan) return;
    const willPublish = currentPlan.status !== "published";
    if (willPublish) {
      try {
        const validation = await api(BASE + "/" + currentPlan.id + "/conflicts");
        const critical = validation.summary ? validation.summary.critical : 0;
        if (critical > 0 && !confirm("Der Plan hat " + critical + " kritische Konflikte. Trotzdem veroeffentlichen?")) {
          showWarnings(validation.conflicts || []);
          return;
        }
      } catch (_) {}
    }
    const msg = willPublish
      ? "Plan \"" + currentPlan.title + "\" veröffentlichen? Mitarbeiter können ihn dann sehen."
      : "Plan zurück auf Entwurf setzen? Er wird für Mitarbeiter ausgeblendet.";
    if (!confirm(msg)) return;
    publishBtn.disabled = true;
    try {
      const updated = await api(BASE + "/" + currentPlan.id + "/publish", { method: "PATCH" });
      await loadPlans(updated.id || currentPlan.id);
    } catch (err) { alert("Fehler: " + err.message); }
    finally { publishBtn.disabled = false; }
  });

  // ── Print / CSV ───────────────────────────────────────────────────────────
  printBtn.addEventListener("click", () => window.print());

  csvBtn.addEventListener("click", () => {
    if (!currentPlan) return;
    const a = document.createElement("a");
    a.href = BASE + "/" + currentPlan.id + "/export.xlsx";
    a.download = (currentPlan.title||"schichtplan") + ".xlsx";
    a.click();
  });

  // ── Form submit ───────────────────────────────────────────────────────────
  function buildGenerationPayload() {
    const dept  = document.getElementById("sp-department").value;
    const start = document.getElementById("sp-start").value;
    const model = selectedShiftModel();
    const machineIds = selectedMachineIds();
    if (!dept) throw new Error("Bitte Abteilung w\u00e4hlen.");
    if (!start) throw new Error("Bitte Startdatum angeben.");
    if (!model) throw new Error("Bitte ein Schichtmodell w\u00e4hlen.");
    if (!machineIds.length) throw new Error("Bitte mindestens eine Maschine ausw\u00e4hlen.");
    const vacText = document.getElementById("sp-vacations").value || "";
    const vacations = vacText.split("\n").flatMap((line) => {
      const parts = line.split(",").map((s) => s.trim());
      if (parts.length >= 2 && parts[0] && parts[1]) {
        return [{ employee_id: parseInt(parts[0], 10), date: parts[1], notes: parts[2]||"" }];
      }
      return [];
    });
    return {
      department:   dept,
      title:        document.getElementById("sp-title").value,
      start_date:   start,
      days:         parseInt(document.getElementById("sp-days").value||"7", 10),
      shift_model_key: model.key,
      machine_ids:   machineIds,
      rhythm:       document.getElementById("sp-rhythm").value || model.display_name || model.key,
      preferences:  { text: document.getElementById("sp-preferences").value || "" },
      vacations,
    };
  }

  async function submitShiftPlanPreview() {
    let payload;
    try {
      payload = buildGenerationPayload();
    } catch (err) {
      spMsg.textContent = err.message;
      return;
    }
    previewBtn.disabled = true;
    spMsg.textContent = "Vorschau wird erstellt...";
    try {
      const result = await api(BASE + "/preview", { method: "POST", body: JSON.stringify(payload) });
      spMsg.textContent = "Vorschau erstellt. Noch nicht gespeichert.";
      currentPlan = result;
      renderPlan(result);
      showWarnings(result && result.warnings);
    } catch (err) {
      spMsg.textContent = "Fehler: " + err.message;
      if (err.payload && err.payload.warnings) showWarnings(err.payload.warnings);
    } finally {
      previewBtn.disabled = false;
    }
  }

  if (previewBtn) {
    previewBtn.addEventListener("click", submitShiftPlanPreview);
  }

  async function submitShiftPlanGeneration() {
    let payload;
    try {
      payload = buildGenerationPayload();
    } catch (err) {
      spMsg.textContent = err.message;
      return;
    }
    submitBtn.disabled = true;
    spMsg.textContent  = "Plan wird generiert...";
    try {
      const result = await api(BASE + "/generate", { method: "POST", body: JSON.stringify(payload) });
      spMsg.textContent = "Plan erfolgreich generiert.";
      showWarnings(result && result.warnings);
      if (result && result.entries) {
        currentPlan = result;
        renderPlan(result);
      }
      await loadPlans(result && result.id, result);
    } catch (err) {
      spMsg.textContent = "Fehler: " + err.message;
      if (err.payload && err.payload.warnings) showWarnings(err.payload.warnings);
    } finally {
      submitBtn.disabled = false;
    }
  }

  submitBtn.addEventListener("click", async () => {
    return submitShiftPlanGeneration();

    const dept  = document.getElementById("sp-department").value;
    const start = document.getElementById("sp-start").value;
    const model = selectedShiftModel();
    if (!dept)  { spMsg.textContent = "Bitte Abteilung wählen."; return; }
    if (!start) { spMsg.textContent = "Bitte Startdatum angeben."; return; }
    if (!model) { spMsg.textContent = "Bitte ein Schichtmodell w\u00e4hlen."; return; }
    if (!machineIds.length) { spMsg.textContent = "Bitte mindestens eine Maschine ausw\u00e4hlen."; return; }

    submitBtn.disabled = true;
    spMsg.textContent  = "Plan wird generiert…";

    // Parse vacation textarea
    const vacText = document.getElementById("sp-vacations").value || "";
    const vacations = vacText.split("\n").flatMap((line) => {
      const parts = line.split(",").map((s) => s.trim());
      if (parts.length >= 2 && parts[0] && parts[1]) {
        return [{ employee_id: parseInt(parts[0], 10), date: parts[1], notes: parts[2]||"" }];
      }
      return [];
    });

    const payload = {
      department:   dept,
      title:        document.getElementById("sp-title").value,
      start_date:   start,
      days:         parseInt(document.getElementById("sp-days").value||"7", 10),
      shift_model_key: model.key,
      rhythm:       document.getElementById("sp-rhythm").value || model.display_name || model.key,
      preferences:  { text: document.getElementById("sp-preferences").value || "" },
      vacations,
    };

    try {
      const result = await api(BASE + "/generate", { method: "POST", body: JSON.stringify(payload) });
      spMsg.textContent = "✓ Plan erfolgreich generiert.";

      // Show warnings (optional, collapsible)
      showWarnings(result && result.warnings);

      // Reload plan list and select the new plan by id
      if (result && result.entries) {
        currentPlan = result;
        renderPlan(result);
      }
      await loadPlans(result && result.id, result);

    } catch (err) {
      spMsg.textContent = "Fehler: " + err.message;
      if (err.payload && err.payload.warnings) showWarnings(err.payload.warnings);
    } finally {
      submitBtn.disabled = false;
    }
  });

  // ── Init ──────────────────────────────────────────────────────────────────
  function setDefaultStartDate() {
    const startInput = document.getElementById("sp-start");
    if (startInput && !startInput.value) startInput.value = new Date().toISOString().slice(0,10);
  }

  async function initializeShiftplansPage() {
    setDefaultStartDate();
    if (!shiftModels.length) shiftModels = readShiftModelsFromSelect();

    const currentToken = token();
    if (!currentToken) {
      initializedToken = null;
      return null;
    }
    if (initializationPromise) return initializationPromise;
    if (initializedToken === currentToken) return null;

    initializationPromise = Promise.all([
      loadShiftModels(),
      loadMachines(),
      loadPlans(),
    ]).finally(() => {
      initializedToken = currentToken;
      initializationPromise = null;
    });
    return initializationPromise;
  }

  function scheduleShiftplansInitialization() {
    initializeShiftplansPage().catch((err) => {
      if (spMsg) spMsg.textContent = "Schichtplanung konnte nicht geladen werden: " + err.message;
      console.warn(err);
    });
  }

  window.addEventListener("maintenance-auth-ready", scheduleShiftplansInitialization);
  window.addEventListener("maintenance-auth-changed", () => {
    initializedToken = null;
    scheduleShiftplansInitialization();
  });
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", scheduleShiftplansInitialization, { once: true });
  } else {
    scheduleShiftplansInitialization();
  }
})();

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
  let currentPlan = null;
  let editEntryId = null;

  // ── DOM ───────────────────────────────────────────────────────────────────
  const form        = document.getElementById("sp-form");
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
    if (!res.ok) throw new Error(body.message || body.error || "Fehler " + res.status);
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

  // ── Load & select plans ───────────────────────────────────────────────────
  async function loadPlans(selectId) {
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

    const idx = selectId !== undefined
      ? allPlans.findIndex((p) => p.id === selectId)
      : 0;
    planSelect.value = Math.max(0, idx);
    renderPlan(allPlans[planSelect.value] || allPlans[0]);
  }

  function renderPlan(plan) {
    currentPlan = plan;
    renderGrid(plan);
    renderStats(plan);
    loadConflicts(plan.id);
    const admin = isAdmin();
    deleteWrap.hidden = !admin;
    if (changelogEl) changelogEl.hidden = !admin;
    if (admin) loadChangelog(plan.id);

    // Publish button (admin only)
    publishBtn.hidden = !admin;
    if (admin) {
      const published = plan.status === "published";
      publishBtn.textContent = published ? "↩ Zurück zu Entwurf" : "✓ Veröffentlichen";
      publishBtn.className   = "btn btn-sm no-print " +
        (published ? "btn-warning" : "btn-success");
    }

    // Status-Badge
    statusBadge.hidden = false;
    if (plan.status === "published") {
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

    const activeShifts = SHIFT_ORDER.filter((s) => usedShifts.has(s));
    const canEdit = canWrite();

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
            const empName     = entry.employee ? entry.employee.name : "?";
            const chip = document.createElement(canEdit ? "button" : "div");
            chip.className = "sp-chip";
            if (canEdit) {
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
            if (machineName) {
              chip.innerHTML =
                "<span class='sp-machine'>" + machineName + "</span>" +
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
  submitBtn.addEventListener("click", async () => {
    const dept  = document.getElementById("sp-department").value;
    const start = document.getElementById("sp-start").value;
    if (!dept)  { spMsg.textContent = "Bitte Abteilung wählen."; return; }
    if (!start) { spMsg.textContent = "Bitte Startdatum angeben."; return; }

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
      rhythm:       document.getElementById("sp-rhythm").value || "2-Schicht Rhythmus",
      preferences:  document.getElementById("sp-preferences").value,
      vacations,
    };

    try {
      const result = await api(BASE + "/generate", { method: "POST", body: JSON.stringify(payload) });
      spMsg.textContent = "✓ Plan erfolgreich generiert.";

      // Show warnings (optional, collapsible)
      showWarnings(result && result.warnings);

      // Reload plan list and select the new plan by id
      await loadPlans(result && result.id);

    } catch (err) {
      spMsg.textContent = "Fehler: " + err.message;
    } finally {
      submitBtn.disabled = false;
    }
  });

  // ── Init ──────────────────────────────────────────────────────────────────
  window.addEventListener("maintenance-auth-ready", () => loadPlans());
  document.addEventListener("DOMContentLoaded", () => {
    // Set today as default start date
    const startInput = document.getElementById("sp-start");
    if (startInput && !startInput.value) startInput.value = new Date().toISOString().slice(0,10);
    if (token()) loadPlans();
  });
})();

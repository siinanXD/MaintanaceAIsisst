(function () {
  "use strict";
  const BASE = "/api/v1/handover";
  const SHIFT_LABEL = { Frueh: "Frühschicht", Spaet: "Spätschicht", Nacht: "Nachtschicht" };

  function token() {
    return (window.maintenanceAuth && window.maintenanceAuth.token)
      ? window.maintenanceAuth.token()
      : window.localStorage.getItem("maintenance_access_token");
  }
  function authHdr() { const t = token(); return t ? { Authorization: "Bearer " + t } : {}; }
  async function api(url, opts) {
    const res = await fetch(url, { headers: { "Content-Type": "application/json", ...authHdr() }, ...opts });
    if (res.status === 204) return null;
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(body.message || body.error || "Fehler " + res.status);
    return (body && body.success && "data" in body) ? body.data : body;
  }
  function canWrite() {
    return window.maintenanceAuth && window.maintenanceAuth.canWrite
      ? window.maintenanceAuth.canWrite("shiftplans") : false;
  }

  const listWrap  = document.getElementById("ho-list-wrap");
  const emptyEl   = document.getElementById("ho-empty");
  const hoMsg     = document.getElementById("ho-msg");
  const dialog    = document.getElementById("ho-dialog");
  const dlgSave   = document.getElementById("dlg-ho-save");
  const dlgCancel = document.getElementById("dlg-ho-cancel");
  const dlgMsg    = document.getElementById("dlg-ho-msg");
  let editId = null;

  async function loadHandovers() {
    if (!token()) return;
    const dept  = document.getElementById("filter-dept").value;
    const date  = document.getElementById("filter-date").value;
    const shift = document.getElementById("filter-shift").value;
    let url = BASE + "?";
    if (dept)  url += "department=" + encodeURIComponent(dept) + "&";
    if (date)  url += "date=" + date + "&";
    if (shift) url += "shift_type=" + encodeURIComponent(shift) + "&";
    try {
      const data = await api(url);
      renderList(Array.isArray(data) ? data : (data || []));
    } catch (err) {
      emptyEl.textContent = "Fehler: " + err.message;
      emptyEl.hidden = false;
    }
  }

  function renderList(items) {
    // Remove old cards
    listWrap.querySelectorAll(".ho-card").forEach(el => el.remove());
    emptyEl.hidden = items.length > 0;
    emptyEl.textContent = "Keine Übergaben gefunden.";

    items.forEach(h => {
      const card = document.createElement("article");
      card.className = "card app-card ho-card mb-3";
      const statusCls = h.status === "completed" ? "badge-success" : "badge-warning";
      const statusTxt = h.status === "completed" ? "✓ Abgeschlossen" : "Offen";
      const editable  = h.status === "open" && canWrite();
      card.innerHTML = `
        <div class="card-body">
          <div class="panel-header">
            <div>
              <h3 class="panel-title">${h.shift_date} · ${SHIFT_LABEL[h.shift_type] || h.shift_type} · ${h.department}</h3>
              <p class="panel-meta">Von: ${h.handed_over_by || "–"} ${h.handed_over_at ? "· " + new Date(h.handed_over_at).toLocaleString("de-DE") : ""}</p>
            </div>
            <div class="toolbar">
              <span class="badge ${statusCls}">${statusTxt}</span>
              ${editable ? `<button class="btn btn-ghost btn-xs" data-edit="${h.id}">✏ Bearbeiten</button>` : ""}
              ${editable ? `<button class="btn btn-success btn-xs" data-complete="${h.id}">✓ Abschließen</button>` : ""}
            </div>
          </div>
          ${h.content     ? `<div class="mt-2"><span class="stat-label">Erledigt:</span><p class="panel-meta mt-1" style="white-space:pre-wrap">${h.content}</p></div>` : ""}
          ${h.open_tasks  ? `<div class="mt-2"><span class="stat-label">Offen:</span><p class="panel-meta mt-1" style="white-space:pre-wrap">${h.open_tasks}</p></div>` : ""}
          ${h.machine_notes ? `<div class="mt-2"><span class="stat-label">Maschinen:</span><p class="panel-meta mt-1" style="white-space:pre-wrap">${h.machine_notes}</p></div>` : ""}
          ${h.next_notes  ? `<div class="mt-2"><span class="stat-label">Nächste Schicht:</span><p class="panel-meta mt-1" style="white-space:pre-wrap">${h.next_notes}</p></div>` : ""}
        </div>`;
      // Wire up buttons
      card.querySelector("[data-edit]")?.addEventListener("click", () => openEditDialog(h));
      card.querySelector("[data-complete]")?.addEventListener("click", () => completeHandover(h.id));
      listWrap.appendChild(card);
    });
  }

  function openEditDialog(h) {
    editId = h.id;
    document.getElementById("dlg-ho-content").value = h.content || "";
    document.getElementById("dlg-ho-open").value    = h.open_tasks || "";
    document.getElementById("dlg-ho-machine").value = h.machine_notes || "";
    document.getElementById("dlg-ho-next").value    = h.next_notes || "";
    dlgMsg.textContent = "";
    dialog.showModal();
  }

  dlgSave.addEventListener("click", async () => {
    if (!editId) return;
    dlgSave.disabled = true;
    dlgMsg.textContent = "Wird gespeichert…";
    try {
      await api(BASE + "/" + editId, { method: "PATCH", body: JSON.stringify({
        content:       document.getElementById("dlg-ho-content").value,
        open_tasks:    document.getElementById("dlg-ho-open").value,
        machine_notes: document.getElementById("dlg-ho-machine").value,
        next_notes:    document.getElementById("dlg-ho-next").value,
      })});
      dialog.close();
      await loadHandovers();
    } catch (err) { dlgMsg.textContent = err.message; }
    finally { dlgSave.disabled = false; }
  });

  dlgCancel.addEventListener("click", () => dialog.close());

  async function completeHandover(id) {
    if (!confirm("Übergabe wirklich abschließen? Danach nicht mehr bearbeitbar.")) return;
    try {
      await api(BASE + "/" + id + "/complete", { method: "POST" });
      await loadHandovers();
    } catch (err) { alert(err.message); }
  }

  document.getElementById("ho-submit-btn").addEventListener("click", async () => {
    const dept  = document.getElementById("ho-department").value;
    const date  = document.getElementById("ho-date").value;
    const shift = document.getElementById("ho-shift-type").value;
    if (!dept || !date || !shift) { hoMsg.textContent = "Bitte alle Pflichtfelder ausfüllen."; return; }
    const btn = document.getElementById("ho-submit-btn");
    btn.disabled = true;
    hoMsg.textContent = "Wird gespeichert…";
    try {
      await api(BASE, { method: "POST", body: JSON.stringify({
        department: dept, shift_date: date, shift_type: shift,
        content:       document.getElementById("ho-content").value,
        open_tasks:    document.getElementById("ho-open-tasks").value,
        machine_notes: document.getElementById("ho-machine-notes").value,
        next_notes:    document.getElementById("ho-next-notes").value,
      })});
      hoMsg.textContent = "✓ Übergabe gespeichert.";
      ["ho-content","ho-open-tasks","ho-machine-notes","ho-next-notes"].forEach(id => document.getElementById(id).value = "");
      await loadHandovers();
    } catch (err) { hoMsg.textContent = "Fehler: " + err.message; }
    finally { btn.disabled = false; }
  });

  document.getElementById("ho-filter-btn").addEventListener("click", loadHandovers);

  window.addEventListener("maintenance-auth-ready", loadHandovers);
  document.addEventListener("DOMContentLoaded", () => {
    document.getElementById("ho-date").value = new Date().toISOString().slice(0, 10);
    if (token()) loadHandovers();
  });
})();

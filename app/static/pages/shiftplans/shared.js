/**
 * Shift planning shared module.
 * Registers helpers on the current MaintenanceShiftplansRuntime object.
 */
(function registerShiftplansModule() {
  window.MaintenanceShiftplansModules = window.MaintenanceShiftplansModules || {};
  window.MaintenanceShiftplansModules["shared"] = function attachShiftplansShared(Shiftplans) {
    with (Shiftplans) {
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
      Object.assign(Shiftplans, { localISO, token, authHdr, api, isAdmin, canWrite, selectedMachineIds, renderMachines, loadMachines });
    }
  };
})();

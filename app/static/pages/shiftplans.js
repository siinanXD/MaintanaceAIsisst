(function bootstrapShiftplansPage() {
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

  const SHIFTPLAN_MODULES = [
    "shared",
    "models",
    "plans",
    "grid",
    "validation",
    "actions"
  ];

  const shiftplanModulePromises = new Map();

  function shiftplanModuleBaseUrl() {
    const currentScript = document.currentScript;
    if (!currentScript || !currentScript.src) return "/static/pages/shiftplans/";
    return currentScript.src.split("/static/pages/shiftplans.js")[0] + "/static/pages/shiftplans/";
  }

  function loadShiftplanModule(moduleName) {
    if (window.MaintenanceShiftplansModules && window.MaintenanceShiftplansModules[moduleName]) {
      return Promise.resolve();
    }
    if (!shiftplanModulePromises.has(moduleName)) {
      shiftplanModulePromises.set(moduleName, new Promise((resolve, reject) => {
        const script = document.createElement("script");
        const version = window.maintenanceStaticVersion || "dev";
        script.src = shiftplanModuleBaseUrl() + moduleName + ".js?v=" + version;
        script.defer = true;
        script.onload = resolve;
        script.onerror = () => reject(new Error("Schichtplan-Modul konnte nicht geladen werden: " + moduleName));
        document.head.appendChild(script);
      }));
    }
    return shiftplanModulePromises.get(moduleName);
  }

  async function startShiftplansPage() {
    const Shiftplans = {
      BASE,
      SHIFT_WINDOWS,
      SHIFT_ORDER,
      SHIFT_LABEL,
      DAYS_DE,
      allPlans,
      machines,
      machinesLoadPromise,
      shiftModels,
      shiftModelsLoadPromise,
      currentPlan,
      editEntryId,
      initializedToken,
      initializationPromise,
      form,
      previewBtn,
      submitBtn,
      spMsg,
      spSelector,
      planSelect,
      tableWrap,
      thead,
      tbody,
      emptyMsg,
      statsEl,
      statsBody,
      warningsEl,
      warnSummary,
      warnList,
      changelogEl,
      changelogBody,
      deleteWrap,
      deleteBtn,
      publishBtn,
      statusBadge,
      printBtn,
      csvBtn,
      shiftModelSelect,
      shiftModelPreview,
      shiftModelTitle,
      shiftModelDescription,
      shiftModelShifts,
      shiftModelTeamCount,
      shiftModelWeekend,
      shiftModelRotation,
      shiftModelRest,
      machinePicker,
      printTitle,
      printMeta,
      dialog,
      dlgInfo,
      dlgShift,
      dlgStart,
      dlgEnd,
      dlgNotes,
      dlgTimes,
      dlgSave,
      dlgDelete,
      dlgCancel,
      dlgMsg
    };
    window.MaintenanceShiftplansRuntime = Shiftplans;
    for (const moduleName of SHIFTPLAN_MODULES) {
      await loadShiftplanModule(moduleName);
    }
    SHIFTPLAN_MODULES.forEach((moduleName) => {
      window.MaintenanceShiftplansModules[moduleName](Shiftplans);
    });
    Shiftplans.bindShiftplanActions();
  }

  startShiftplansPage().catch((error) => {
    if (spMsg) spMsg.textContent = "Schichtplanung konnte nicht geladen werden: " + error.message;
    console.warn(error);
  });
})();

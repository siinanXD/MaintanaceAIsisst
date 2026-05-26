const STATIC_VERSION = window.maintenanceStaticVersion || "dev";
const WORKFLOW_MODULE_BASE = "/static/pages/workflows/";
const INITIALIZER_MODULES = {
  initAufgaben: "tasks",
  initBenutzer: "admin-users",
  initCockpitShiftRealtime: "dashboard-shifts",
  initDailyCockpit: "dashboard",
  initDashboardShiftRealtime: "dashboard-shifts",
  initDepartments: "tasks",
  initDocuments: "documents",
  initEmployees: "employees",
  initErrors: "errors",
  initInventory: "inventory",
  initMachineProfile: "machine-profile",
  initMachines: "machines",
  initShiftPlans: "legacy-shiftplans",
  initTasks: "tasks",
  initUsers: "admin-users",
  initVacations: "vacations"
};

let sharedModulePromise = null;
const domainModulePromises = new Map();

/**
 * Return the versioned URL for a workflow domain module.
 *
 * @param {string} moduleName Workflow domain module name.
 * @returns {string} Versioned static module URL.
 */
function workflowModuleUrl(moduleName) {
  return WORKFLOW_MODULE_BASE + moduleName + ".js?v=" + STATIC_VERSION;
}

/**
 * Load the workflow shared module once.
 *
 * @returns {Promise<object>} Shared workflow module exports.
 */
async function loadSharedModule() {
  if (!sharedModulePromise) {
    sharedModulePromise = import(workflowModuleUrl("shared"));
  }
  return sharedModulePromise;
}

/**
 * Return initializer names configured for the current route.
 *
 * @returns {string[]} Initializer names from the feature registry.
 */
function initializerNamesForCurrentPage() {
  const feature = window.maintenanceFeatures && window.maintenanceFeatures.forPath
    ? window.maintenanceFeatures.forPath(window.location.pathname)
    : null;
  return Array.isArray(feature && feature.initializers) ? feature.initializers : [];
}

/**
 * Load the domain modules that provide the requested initializers.
 *
 * @param {string[]} initializerNames Initializer names from the feature registry.
 * @returns {Promise<void>}
 */
async function loadInitializerModules(initializerNames) {
  const moduleNames = [...new Set(initializerNames.map((name) => INITIALIZER_MODULES[name]).filter(Boolean))];
  await Promise.all(moduleNames.map((moduleName) => {
    if (!domainModulePromises.has(moduleName)) {
      domainModulePromises.set(moduleName, import(workflowModuleUrl(moduleName)).catch((error) => {
        domainModulePromises.delete(moduleName);
        throw error;
      }));
    }
    return domainModulePromises.get(moduleName);
  }));
}

/**
 * Resolve route initializers that have already been registered by domain modules.
 *
 * @returns {Function[]} Workflow initializer callbacks.
 */
function workflowInitializersForCurrentPage() {
  const registry = window.maintenanceWorkflowInitializers || {};
  return initializerNamesForCurrentPage()
    .map((name) => registry[name])
    .filter((initializer) => typeof initializer === "function");
}

/**
 * Initialize the current workflow page through its domain modules.
 *
 * @returns {Promise<void>}
 */
async function initCurrentWorkflowPage() {
  const shared = await loadSharedModule();
  if (!shared.token()) {
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
    await shared.loadWorkflowShared();
    const initializerNames = initializerNamesForCurrentPage();
    await loadInitializerModules(initializerNames);
    const missingInitializers = initializerNames.filter((name) => !shared.resolveWorkflowInitializer(name));
    if (missingInitializers.length) {
      console.warn("Missing workflow initializers", missingInitializers);
      throw new Error("Missing workflow initializers: " + missingInitializers.join(", "));
    }
    for (const initializerName of initializerNames) {
      const initializer = shared.resolveWorkflowInitializer(initializerName);
      await initializer();
    }
  } catch (error) {
    console.warn(error);
    if (window.maintenanceFrontend && window.maintenanceFrontend.setWorkflowStatus) {
      window.maintenanceFrontend.setWorkflowStatus("Diese Seite konnte nicht vollst?ndig initialisiert werden.", "error");
    }
    shared.showInterfaceToast("Diese Seite konnte nicht vollst?ndig initialisiert werden.", "error");
  } finally {
    document.body.classList.remove("is-workflow-loading");
    window.dispatchEvent(new Event("maintenance-workflow-ready"));
  }
}

window.maintenanceWorkflows = {
  initCurrentWorkflowPage,
  workflowInitializersForCurrentPage
};

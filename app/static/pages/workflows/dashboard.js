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

const DASHBOARD_MODULES = [
  "state",
  "resources",
  "executive",
  "tasks",
  "operations",
  "shift-calendar",
  "actions"
];

const dashboardModulePromises = new Map();

function dashboardModuleUrl(moduleName) {
  const version = window.maintenanceStaticVersion || "dev";
  return new URL("./dashboard/" + moduleName + ".js?v=" + version, import.meta.url).href;
}

function loadDashboardModule(moduleName) {
  if (window.MaintenanceDashboardModules && window.MaintenanceDashboardModules[moduleName]) {
    return Promise.resolve();
  }
  if (!dashboardModulePromises.has(moduleName)) {
    dashboardModulePromises.set(moduleName, new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = dashboardModuleUrl(moduleName);
      script.defer = true;
      script.onload = resolve;
      script.onerror = () => reject(new Error("Dashboard-Modul konnte nicht geladen werden: " + moduleName));
      document.head.appendChild(script);
    }));
  }
  return dashboardModulePromises.get(moduleName);
}

async function loadDashboardModules() {
  for (const moduleName of DASHBOARD_MODULES) {
    await loadDashboardModule(moduleName);
  }
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
  const frequentCodes = document.querySelector("[data-dashboard-frequent-codes]");
  const inventoryStats = document.querySelector("[data-dashboard-inventory-stats]");
  const inventoryShortages = document.querySelector("[data-dashboard-inventory-shortages]");
  const employeeOverview = document.querySelector("[data-dashboard-employee-overview]");
  const priorityList = document.querySelector("[data-dashboard-priority-list]");
  const briefingZusammenfassung = document.querySelector("[data-daily-briefing-summary]");
  const briefingList = document.querySelector("[data-daily-briefing-list]");
  const operationsInsights = document.querySelector("[data-operations-insights]");
  const operationsStatus = document.querySelector("[data-operations-insights-status]");
  const operationsSiteFilter = document.querySelector("[data-operations-site-filter]");
  const operationsRangeFilter = document.querySelector("[data-operations-range-filter]");
  const operationsRefresh = document.querySelector("[data-operations-refresh]");
  const operationsKpiGrid = document.querySelector("[data-operations-kpi-grid]");
  const operationsDrilldown = document.querySelector("[data-operations-drilldown]");
  const aiOpsStatus = document.querySelector("[data-ai-ops-status]");
  const aiOpsUpdated = document.querySelector("[data-ai-ops-updated]");
  const aiOpsPriorityRail = document.querySelector("[data-ai-ops-priority-rail]");
  const aiSystemRail = document.querySelector("[data-ai-system-rail]");
  const aiRiskRadar = document.querySelector("[data-ai-risk-radar]");
  const aiKnowledgeHealth = document.querySelector("[data-ai-knowledge-health]");
  const executiveActivityFeed = document.querySelector("[data-dashboard-activity-feed]");
  const executiveWarningFeed = document.querySelector("[data-dashboard-warning-feed]");
  const executiveAiTrust = document.querySelector("[data-dashboard-ai-trust]");
  const executiveMachineStrip = document.querySelector("[data-dashboard-machine-strip]");
  const criticalTodayPanel = document.querySelector("[data-dashboard-critical-today]");
  const machineCards = document.querySelector("[data-dashboard-machine-cards]");
  const handoverList = document.querySelector("[data-dashboard-handover-list]");
  const peopleHints = document.querySelector("[data-dashboard-people-hints]");
  const quickAiButtons = document.querySelectorAll("[data-dashboard-quick-ai]");
  const shiftCalendar = document.querySelector("[data-dashboard-shift-calendar]");
  const shiftTimeline = document.querySelector("[data-dashboard-shift-timeline]");
  const shiftCalendarMessage = document.querySelector("[data-dashboard-calendar-message]");
  const shiftCalendarEmployee = document.querySelector("[data-dashboard-calendar-employee]");
  if ((!taskBoard && !errorStats && !inventoryStats && !briefingList && !employeeOverview && !shiftTimeline && !operationsInsights && !executiveActivityFeed) || !token()) return;

  let activeTask = null;
  let activeTaskId = null;
  const dashboardJobs = [];
  const dashboardState = {
    aiStatus: null,
    briefing: null,
    errors: [],
    handovers: [],
    employees: [],
    inventory: null,
    knowledgeGaps: null,
    knowledgeStatus: null,
    machines: [],
    operations: null,
    retrievalTelemetry: null,
    vacations: [],
    tasks: []
  };

  const Dashboard = {
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
    user,
    taskBoard,
    taskCountElements,
    taskDetailModal,
    taskDetailTitle,
    taskDetailSubtitle,
    taskDetailBody,
    taskDetailMessage,
    taskStartButton,
    taskCompleteButton,
    taskDetailClose,
    reportGenerate,
    cockpitSuggestForm,
    cockpitDraft,
    cockpitDraftCancel,
    cockpitMessage,
    globalLive,
    errorStats,
    frequentCodes,
    inventoryStats,
    inventoryShortages,
    employeeOverview,
    priorityList,
    briefingZusammenfassung,
    briefingList,
    operationsInsights,
    operationsStatus,
    operationsSiteFilter,
    operationsRangeFilter,
    operationsRefresh,
    operationsKpiGrid,
    operationsDrilldown,
    aiOpsStatus,
    aiOpsUpdated,
    aiOpsPriorityRail,
    aiSystemRail,
    aiRiskRadar,
    aiKnowledgeHealth,
    executiveActivityFeed,
    executiveWarningFeed,
    executiveAiTrust,
    executiveMachineStrip,
    criticalTodayPanel,
    machineCards,
    handoverList,
    peopleHints,
    quickAiButtons,
    shiftCalendar,
    shiftTimeline,
    shiftCalendarMessage,
    shiftCalendarEmployee,
    activeTask,
    activeTaskId,
    dashboardJobs,
    dashboardState
  };
  window.MaintenanceDashboardRuntime = Dashboard;
  await loadDashboardModules();
  DASHBOARD_MODULES.forEach((moduleName) => {
    window.MaintenanceDashboardModules[moduleName](Dashboard);
  });
  await Dashboard.runDashboardJobs();
}

export { initDailyCockpit };

registerWorkflowInitializers({
  initDailyCockpit: initDailyCockpit
});

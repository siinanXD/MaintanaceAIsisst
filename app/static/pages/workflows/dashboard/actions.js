/**
 * Dashboard actions module.
 * Registers helpers on the current MaintenanceDashboardRuntime object.
 */
(function registerDashboardModule() {
  window.MaintenanceDashboardModules = window.MaintenanceDashboardModules || {};
  window.MaintenanceDashboardModules["actions"] = function attachDashboardActions(Dashboard) {
    with (Dashboard) {
      async function runDashboardJobs() {
        dashboardJobs.push(loadDashboardPriorities());

      if (taskBoard && canView("tasks")) {
        dashboardJobs.push(loadDashboardAufgaben());
      } else if (taskBoard) {
        taskBoard.innerHTML = "";
        taskBoard.appendChild(emptyCockpitCard("Keine Berechtigung für Aufgaben."));
      }

      if (operationsInsights && canView("dashboard")) {
        if (operationsRefresh && operationsRefresh.dataset.bound !== "true") {
          operationsRefresh.addEventListener("click", () => loadOperationsInsights(operationsRefresh));
          operationsRefresh.dataset.bound = "true";
        }
        if (operationsSiteFilter && operationsSiteFilter.dataset.bound !== "true") {
          operationsSiteFilter.addEventListener("change", () => loadOperationsInsights());
          operationsSiteFilter.dataset.bound = "true";
        }
        if (operationsRangeFilter && operationsRangeFilter.dataset.bound !== "true") {
          operationsRangeFilter.addEventListener("change", () => loadOperationsInsights());
          operationsRangeFilter.dataset.bound = "true";
        }
        dashboardJobs.push(loadOperationsInsights());
      } else if (operationsInsights) {
        operationsInsights.hidden = true;
      }

      if (aiSystemRail || aiRiskRadar || aiKnowledgeHealth) {
        dashboardJobs.push(loadAiOperationsSignals());
      }

      dashboardJobs.push(loadDailyBriefing());

      if (machineCards && canView("machines")) {
        dashboardJobs.push(loadDashboardMachines());
      } else if (machineCards) {
        machineCards.innerHTML = "";
        machineCards.appendChild(emptyRailMessage("Keine Berechtigung für Maschinenstatus."));
      }

      if (handoverList && canView("shiftplans")) {
        dashboardJobs.push(loadDashboardHandovers());
      } else if (handoverList) {
        handoverList.innerHTML = "";
        handoverList.appendChild(emptyRailMessage("Keine Berechtigung für Schichtübergaben."));
      }

      if (peopleHints && canView("employees")) {
        dashboardJobs.push(loadDashboardVacations());
      }

      if (errorStats && canView("errors")) {
        dashboardJobs.push((async () => {
          const errorPayload = await api("/api/v1/errors?limit=100&active=1");
          const errors = listData(errorPayload);
          setText("[data-dashboard-machine-issue-count]", paginationTotal(errorPayload, errors));
          renderIncidentRows(errors);
        })());
      } else if (errorStats) {
        errorStats.innerHTML = "";
        errorStats.appendChild(emptyDashboardMessage("Keine Berechtigung für Störungen."));
        renderFrequentCodes([]);
      }

      if (employeeOverview && canView("employees")) {
        dashboardJobs.push((async () => {
          try {
            renderEmployeeOverview(listData(await api("/api/v1/employees?limit=200")));
          } catch (error) {
            employeeOverview.innerHTML = "";
            employeeOverview.appendChild(emptyDashboardMessage("Mitarbeiterdaten konnten nicht geladen werden."));
            dashboardState.employees = [];
            renderPeopleHints();
          }
        })());
      }

      if (inventoryStats && canView("inventory")) {
        dashboardJobs.push((async () => {
          const summary = await api("/api/v1/inventory/summary?include_materials=0");
          renderInventoryZusammenfassung(summary);
        })());
      }

      if (shiftCalendar && canView("shiftplans")) {
        dashboardJobs.push((async () => {
          await setupDashboardCalendarFilter();
          await loadShiftCalendar();
          startDashboardShiftRealtime();
        })());
      }

      const dashboardResults = await Promise.allSettled(dashboardJobs);
      dashboardResults
        .filter((result) => result.status === "rejected")
        .forEach((result) => console.warn(result.reason));
      }
      Object.assign(Dashboard, { runDashboardJobs });
    }
  };
})();

/**
 * Dashboard operations module.
 * Registers helpers on the current MaintenanceDashboardRuntime object.
 */
(function registerDashboardModule() {
  window.MaintenanceDashboardModules = window.MaintenanceDashboardModules || {};
  window.MaintenanceDashboardModules["operations"] = function attachDashboardOperations(Dashboard) {
    with (Dashboard) {
      async function loadAiOperationsSignals() {
        if (!aiSystemRail && !aiRiskRadar && !aiKnowledgeHealth) return;
        if (!currentUserIsMasterAdmin()) {
          renderAiSystemRail();
          renderRiskRadar();
          renderKnowledgeHealth();
          renderExecutiveDashboard();
          return;
        }
        const [aiStatusResult, telemetryResult, knowledgeStatusResult, gapResult] = await Promise.allSettled([
          api("/api/v1/ai/status"),
          api("/api/v1/admin/ai/retrieval-telemetry?days=7&limit=5"),
          api("/api/v1/admin/ai/knowledge/status"),
          api("/api/v1/admin/ai/knowledge-gaps?status=open&limit=5")
        ]);
        if (aiStatusResult.status === "fulfilled") dashboardState.aiStatus = aiStatusResult.value;
        if (telemetryResult.status === "fulfilled") dashboardState.retrievalTelemetry = telemetryResult.value;
        if (knowledgeStatusResult.status === "fulfilled") dashboardState.knowledgeStatus = knowledgeStatusResult.value;
        if (gapResult.status === "fulfilled") dashboardState.knowledgeGaps = gapResult.value;
        applySloKpis();
        renderAiSystemRail();
        renderRiskRadar();
        renderKnowledgeHealth();
        renderExecutiveDashboard();
      }

      function priorityInsightCard(label, value, variant) {
        const item = document.createElement("article");
        item.className = "priority-insight" + (variant ? " " + variant : "");
        const title = document.createElement("span");
        title.textContent = label;
        const score = document.createElement("strong");
        score.textContent = value;
        item.append(title, score);
        return item;
      }

      async function loadDashboardPriorities() {
        if (!priorityList || !canView("tasks")) return;
        priorityList.innerHTML = "";
        let priorities = [];
        try {
          priorities = listData(await api("/api/v1/tasks/prioritize", {
            method: "POST",
            body: JSON.stringify({ status: "open", limit: 3, mode: "local" })
          }));
        } catch (error) {
          priorityList.appendChild(priorityInsightCard("KI-Priorisierung", "Nicht verfügbar", "is-muted"));
          return;
        }
        if (!priorities.length) {
          priorityList.appendChild(priorityInsightCard("KI-Priorisierung", "Keine offenen Aufgaben", "is-muted"));
          return;
        }
        priorities.forEach((item) => {
          priorityList.appendChild(priorityInsightCard(
            item.task.title,
            item.score + " / " + item.risk_level,
            item.risk_level === "critical" || item.risk_level === "high" ? "is-critical" : ""
          ));
        });
      }

      function isoDateDaysAgo(days) {
        const date = new Date();
        date.setDate(date.getDate() - Math.max(0, Number(days || 30) - 1));
        return date.toISOString().slice(0, 10);
      }

      function todayIsoDate() {
        return new Date().toISOString().slice(0, 10);
      }

      function formatMinutes(value) {
        const minutes = Number(value || 0);
        if (minutes >= 60) return (minutes / 60).toFixed(1).replace(".", ",") + " h";
        return Math.round(minutes) + " min";
      }

      function formatPercent(value) {
        return Math.round(Number(value || 0)) + "%";
      }

      function formatCompactNumber(value) {
        return new Intl.NumberFormat("de-DE", { maximumFractionDigits: 1 }).format(Number(value || 0));
      }

      function formatUsd(value) {
        return new Intl.NumberFormat("de-DE", { style: "currency", currency: "USD" }).format(Number(value || 0));
      }

      function operationsParams() {
        const params = new URLSearchParams();
        const days = operationsRangeFilter ? operationsRangeFilter.value : "30";
        params.set("from", isoDateDaysAgo(days));
        params.set("to", todayIsoDate());
        if (operationsSiteFilter && operationsSiteFilter.value) {
          params.set("site_id", operationsSiteFilter.value);
        }
        return params.toString();
      }

      function operationsCard(label, value, detail, variant) {
        const card = document.createElement("article");
        card.className = "ops-insight-card" + (variant ? " " + variant : "");
        const title = document.createElement("span");
        title.textContent = label;
        const amount = document.createElement("strong");
        amount.textContent = value;
        const meta = document.createElement("small");
        meta.textContent = detail;
        card.append(title, amount, meta);
        return card;
      }

      function renderOperationsCards(summary) {
        if (!operationsKpiGrid) return;
        dashboardState.operations = summary || {};
        const tasks = summary.tasks || {};
        const machines = summary.machines || {};
        const inventory = summary.inventory || {};
        const workforce = summary.workforce || {};
        const documents = summary.documents || {};
        const aiQuality = summary.ai_quality || {};
        setDashboardText("[data-dashboard-recurring-count]", Number(machines.repeat_faults || 0));
        setDashboardText("[data-dashboard-machine-status]", Number(machines.machines_down || 0) + "/" + Number(machines.machines_total || 0));
        renderExecutiveDashboard();
        setDashboardText(
          "[data-dashboard-machine-status-meta]",
          (machines.faults || 0) + " Störungen, " + formatMinutes(machines.downtime_minutes) + " Ausfall"
        );
        operationsKpiGrid.innerHTML = "";
        operationsKpiGrid.append(
          operationsCard("Offene Aufgaben", String(tasks.open || 0), (tasks.overdue || 0) + " überfällig", tasks.overdue ? "is-risk" : ""),
          operationsCard("MTTR", formatMinutes(machines.mttr_minutes), (machines.downtime_minutes || 0) + " min Ausfall", machines.mttr_minutes ? "is-warning" : ""),
          operationsCard("Wiederholstörungen", String(machines.repeat_faults || 0), (machines.faults || 0) + " Störungen", machines.repeat_faults ? "is-risk" : ""),
          operationsCard("Materialengpässe", String(inventory.critical_shortage_count || 0), (inventory.low_stock_count || 0) + " unter Mindestbestand", inventory.critical_shortage_count ? "is-risk" : ""),
          operationsCard("Schichtdeckung", formatPercent(workforce.avg_coverage_percent), (workforce.critical_conflicts || 0) + " kritische Konflikte", workforce.critical_conflicts ? "is-warning" : ""),
          operationsCard("Dokumentqualität", formatCompactNumber(documents.avg_quality_score), (documents.quality_checked || 0) + " geprüft", documents.avg_quality_score < 70 && documents.quality_checked ? "is-warning" : ""),
          operationsCard("KI-Feedback", String(aiQuality.feedback_count || 0), formatUsd(aiQuality.estimated_cost_usd || 0) + " geschätzt", ""),
          operationsCard("Events", String((summary.events || {}).total || 0), "pseudonymisiert erfasst", "")
        );
      }

      function operationsDrilldownRow(label, value, meta) {
        const rowElement = document.createElement("div");
        rowElement.className = "ops-drilldown-row";
        const title = document.createElement("strong");
        title.textContent = label;
        const amount = document.createElement("span");
        amount.textContent = value;
        const detail = document.createElement("small");
        detail.textContent = meta || "";
        rowElement.append(title, amount, detail);
        return rowElement;
      }

      function renderOperationsDrilldown(summary) {
        if (!operationsDrilldown) return;
        const inventory = summary.inventory || {};
        const machines = summary.machines || {};
        const events = summary.events || {};
        operationsDrilldown.innerHTML = "";
        const shortages = Array.isArray(inventory.top_shortages) ? inventory.top_shortages : [];
        if (shortages.length) {
          shortages.slice(0, 4).forEach((item) => {
            operationsDrilldown.appendChild(operationsDrilldownRow(
              item.name || "Material",
              String(item.quantity || 0) + " / " + String(item.min_quantity || 0),
              item.criticality || "normal"
            ));
          });
        }
        const causes = machines.top_cause_categories || {};
        Object.entries(causes).slice(0, 4).forEach(([cause, count]) => {
          operationsDrilldown.appendChild(operationsDrilldownRow(
            cause === "unknown" ? "Ursache offen" : cause,
            String(count),
            "Störungskategorie"
          ));
        });
        Object.entries(events.by_feature || {}).slice(0, 4).forEach(([feature, count]) => {
          operationsDrilldown.appendChild(operationsDrilldownRow(feature, String(count), "Events im Zeitraum"));
        });
        if (!operationsDrilldown.children.length) {
          operationsDrilldown.appendChild(emptyDashboardMessage("Noch keine Operations-Events im gewählten Zeitraum."));
        }
      }

      async function loadOperationsSites() {
        if (!operationsSiteFilter || operationsSiteFilter.dataset.loaded === "true") return;
        try {
          const sites = listData(await api("/api/v1/sites"));
          sites.forEach((site) => {
            const option = document.createElement("option");
            option.value = String(site.id);
            option.textContent = site.name || site.code || ("Werk " + site.id);
            operationsSiteFilter.appendChild(option);
          });
          operationsSiteFilter.dataset.loaded = "true";
        } catch (error) {
          operationsSiteFilter.hidden = true;
        }
      }

      async function loadOperationsInsights(triggerButton) {
        if (!operationsInsights || !canView("dashboard")) return;
        if (operationsStatus) {
          operationsStatus.textContent = "Kennzahlen werden geladen...";
          operationsStatus.classList.remove("is-error");
        }
        await runAction({
          button: triggerButton || operationsRefresh,
          busyText: "Lädt...",
          toast: false,
          rethrow: true,
          action: async () => {
            await loadOperationsSites();
            const summary = await api("/api/v1/operations/summary?" + operationsParams());
            renderOperationsCards(summary);
            renderOperationsDrilldown(summary);
            if (operationsStatus) {
              operationsStatus.textContent = "Aktualisiert: " + new Date().toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
            }
            return summary;
          }
        }).catch((error) => {
          if (operationsStatus) {
            operationsStatus.textContent = error.message || "Operations-KPIs konnten nicht geladen werden.";
            operationsStatus.classList.add("is-error");
          }
          if (operationsKpiGrid) {
            operationsKpiGrid.innerHTML = "";
            operationsKpiGrid.appendChild(operationsCard("Status", "Fehler", "Bitte später erneut versuchen", "is-risk"));
          }
        });
      }

      function renderDailyBriefing(briefing) {
        dashboardState.briefing = briefing || {};
        briefing.sections = Array.isArray(briefing.sections) ? briefing.sections : [];
        if (briefingZusammenfassung) briefingZusammenfassung.textContent = briefing.summary;
        briefingList.innerHTML = "";
        const briefingCount = briefing.sections.reduce((sum, section) => sum + (section.count || 0), 0);
        setText("[data-dashboard-briefing-count]", briefingCount);
        renderExecutiveDashboard();
        if (!briefing.sections.length) {
          briefingList.appendChild(rowLikeStat("Status", "Keine Hinweise"));
          return;
        }
        briefing.sections.forEach((section) => {
          briefingList.appendChild(rowLikeStat(section.title, String(section.count)));
          section.items.slice(0, 2).forEach((item) => {
            briefingList.appendChild(briefingItem(section, item));
          });
        });
      }

      async function loadDailyBriefing() {
        if (!briefingList) return;
        const pendingTimer = window.setTimeout(() => {
          if (briefingZusammenfassung) briefingZusammenfassung.textContent = "Briefing wird aktualisiert.";
          briefingList.innerHTML = "";
          briefingList.appendChild(rowLikeStat("Status", "Aktualisierung läuft"));
        }, 5000);
        try {
          const briefing = await api("/api/v1/ai/daily-briefing");
          window.clearTimeout(pendingTimer);
          renderDailyBriefing(briefing);
        } catch (error) {
          window.clearTimeout(pendingTimer);
          if (briefingZusammenfassung) briefingZusammenfassung.textContent = "Briefing konnte nicht geladen werden.";
          briefingList.innerHTML = "";
          briefingList.appendChild(rowLikeStat("Status", "Nicht verfügbar"));
        }
      }
      Object.assign(Dashboard, { loadAiOperationsSignals, priorityInsightCard, loadDashboardPriorities, isoDateDaysAgo, todayIsoDate, formatMinutes, formatPercent, formatCompactNumber, formatUsd, operationsParams, operationsCard, renderOperationsCards, operationsDrilldownRow, renderOperationsDrilldown, loadOperationsSites, loadOperationsInsights, renderDailyBriefing, loadDailyBriefing });
    }
  };
})();

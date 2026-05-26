/**
 * Dashboard executive module.
 * Registers helpers on the current MaintenanceDashboardRuntime object.
 */
(function registerDashboardModule() {
  window.MaintenanceDashboardModules = window.MaintenanceDashboardModules || {};
  window.MaintenanceDashboardModules["executive"] = function attachDashboardExecutive(Dashboard) {
    with (Dashboard) {
      function cockpitSignal(label, value, detail, severity, href) {
        const element = document.createElement(href ? "a" : "article");
        element.className = "ai-signal-card " + dashboardSignalClass(severity);
        if (href) element.href = href;
        const marker = document.createElement("span");
        marker.className = "ai-signal-marker";
        marker.textContent = severity === "critical" ? "!" : (severity === "warning" ? "!" : "OK");
        const body = document.createElement("div");
        const title = document.createElement("strong");
        const amount = document.createElement("span");
        const meta = document.createElement("small");
        title.textContent = label;
        amount.textContent = String(value);
        meta.textContent = detail || "";
        body.append(title, meta);
        element.append(marker, body, amount);
        return element;
      }

      function systemStatusRow(label, value, detail, severity) {
        const rowElement = document.createElement("div");
        rowElement.className = "ai-system-row " + dashboardSignalClass(severity);
        const title = document.createElement("span");
        const amount = document.createElement("strong");
        const meta = document.createElement("small");
        title.textContent = label;
        amount.textContent = String(value == null || value === "" ? "-" : value);
        meta.textContent = detail || "";
        rowElement.append(title, amount, meta);
        return rowElement;
      }

      function retrievalSloValues() {
        const telemetry = dashboardState.retrievalTelemetry || {};
        const slo = telemetry.retrieval_slo || {};
        return slo.last_values || {};
      }

      function updateDashboardStatus(signals) {
        if (!aiOpsStatus) return;
        const severity = dashboardWorstSeverity(signals);
        aiOpsStatus.textContent = dashboardStatusLabel(severity);
        aiOpsStatus.className = "ops-status-pill " + dashboardSignalClass(severity);
        if (aiOpsUpdated) {
          aiOpsUpdated.textContent = "Aktualisiert " + new Date().toLocaleTimeString("de-DE", {
            hour: "2-digit",
            minute: "2-digit"
          });
        }
      }

      function renderPriorityRail() {
        if (!aiOpsPriorityRail) return;
        const signals = [];
        const activeTasks = dashboardState.tasks.filter((task) => task.status !== "done" && task.status !== "cancelled");
        const criticalTasks = activeTasks.filter((task) => task.priority === "urgent" || isOverdue(task));
        const operations = dashboardState.operations || {};
        const machines = operations.machines || {};
        const inventory = dashboardState.inventory || operations.inventory || {};
        const sloValues = retrievalSloValues();
        const gapCount = dashboardState.knowledgeGaps ? Number(dashboardState.knowledgeGaps.open_count || 0) : 0;
        const safetyRiskCount = Number(sloValues.safety_risk_count || 0);
        const lowConfidenceRate = Number(sloValues.low_confidence_rate || 0);
        const noQuelleRate = Number(sloValues.no_source_rate || 0);
        const staleIndexCount = Number(sloValues.stale_index_count || 0);

        if (criticalTasks.length) {
          signals.push({
            label: "Kritische Aufgaben",
            value: criticalTasks.length,
            detail: criticalTasks[0].title || "Sofort prüfen",
            severity: "critical",
            href: "/tasks"
          });
        }
        if (dashboardState.errors.length) {
          signals.push({
            label: "Offene Störungen",
            value: dashboardState.errors.length,
            detail: (dashboardState.errors[0].error_code || dashboardState.errors[0].title || "Fehlerliste"),
            severity: dashboardState.errors.length > 2 ? "critical" : "warning",
            href: "/errors"
          });
        }
        if (Number(machines.repeat_faults || 0)) {
          signals.push({
            label: "Wiederkehrende Probleme",
            value: machines.repeat_faults,
            detail: (machines.faults || 0) + " Störungen im Zeitraum",
            severity: "warning",
            href: "/errors"
          });
        }
        if (Number(inventory.critical_shortage_count || 0)) {
          signals.push({
            label: "Materialengpässe",
            value: inventory.critical_shortage_count,
            detail: (inventory.low_stock_count || 0) + " unter Mindestbestand",
            severity: "critical",
            href: "/inventory"
          });
        }
        if (safetyRiskCount) {
          signals.push({
            label: "Sicherheitsrisiken",
            value: safetyRiskCount,
            detail: "KI-Sicherheit Events im Fenster",
            severity: "critical",
            href: "/admin/ai"
          });
        }
        if (gapCount) {
          signals.push({
            label: "Wissenslücken",
            value: gapCount,
            detail: "offene Wissenslücken",
            severity: gapCount > 3 ? "critical" : "warning",
            href: "/admin/ai"
          });
        }
        if (lowConfidenceRate >= 0.15 || noQuelleRate >= 0.1) {
          signals.push({
            label: "Suchqualität",
            value: formatRatePercent(Math.max(lowConfidenceRate, noQuelleRate)),
            detail: "Niedrige Sicherheit oder fehlende Quellen",
            severity: lowConfidenceRate >= 0.25 || noQuelleRate >= 0.2 ? "critical" : "warning",
            href: "/admin/ai"
          });
        }
        if (staleIndexCount) {
          signals.push({
            label: "Veralteter Index",
            value: staleIndexCount,
            detail: "Dokumente sollten reindexiert werden",
            severity: "warning",
            href: "/admin/ai"
          });
        }

        signals.sort((first, second) => dashboardSignalRank(first.severity) - dashboardSignalRank(second.severity));
        aiOpsPriorityRail.innerHTML = "";
        if (!signals.length) {
          aiOpsPriorityRail.appendChild(emptyRailMessage("Keine kritischen Operations-Signale im aktuellen Datenfenster."));
        } else {
          signals.slice(0, 7).forEach((item) => {
            aiOpsPriorityRail.appendChild(cockpitSignal(
              item.label,
              item.value,
              item.detail,
              item.severity,
              item.href
            ));
          });
        }
        updateDashboardStatus(signals);
      }

      function renderRiskRadar() {
        if (!aiRiskRadar) return;
        const sloValues = retrievalSloValues();
        const rows = [
          ["Sicherheit", Number(sloValues.safety_risk_count || 0), "Sicherheitsereignisse", Number(sloValues.safety_risk_count || 0) ? "critical" : "good"],
          ["Niedrige Sicherheit", formatRatePercent(sloValues.low_confidence_rate), "Antworten unter Schwelle", Number(sloValues.low_confidence_rate || 0) >= 0.15 ? "warning" : "good"],
          ["Ohne Quellen", formatRatePercent(sloValues.no_source_rate), "Antworten ohne Quelle", Number(sloValues.no_source_rate || 0) >= 0.1 ? "warning" : "good"],
          ["Ausweichantworten", formatRatePercent(sloValues.fallback_rate), "KI-Anbieter oder Suche", Number(sloValues.fallback_rate || 0) >= 0.1 ? "warning" : "good"],
          ["Negatives Feedback", formatRatePercent(sloValues.negative_feedback_rate), "Nutzerrückmeldungen", Number(sloValues.negative_feedback_rate || 0) >= 0.1 ? "warning" : "good"],
          ["Berechtigungsfilter", Number(sloValues.permission_filtered_candidate_count || 0), "gefilterte Kandidaten", "muted"]
        ];
        aiRiskRadar.innerHTML = "";
        rows.forEach(([label, value, detail, severity]) => {
          aiRiskRadar.appendChild(systemStatusRow(label, value, detail, severity));
        });
      }

      function renderAiSystemRail() {
        if (!aiSystemRail) return;
        const aiStatus = dashboardState.aiStatus || {};
        const sloValues = retrievalSloValues();
        aiSystemRail.innerHTML = "";
        if (!currentUserIsMasterAdmin()) {
          aiSystemRail.appendChild(systemStatusRow(
            "Admin-Metriken",
            "eingeschränkt",
            "KI-Sicherheit, Quellenabruf und Indexdetails sind nur für Master-Admins sichtbar.",
            "muted"
          ));
          setDashboardText("[data-dashboard-ai-status]", "Basis");
          setDashboardText("[data-dashboard-ai-status-meta]", "Admin-Metriken eingeschränkt");
          return;
        }
        const ready = aiStatus.ready === true;
        aiSystemRail.append(
          systemStatusRow("KI-Anbieter", aiStatus.provider || "-", ready ? "bereit" : "prüfen", ready ? "good" : "warning"),
          systemStatusRow("Modell", aiStatus.model || "-", aiStatus.streaming_enabled ? "Streaming aktiv" : "Streaming aus", "muted"),
          systemStatusRow("Suchzeit P95", formatMilliseconds(sloValues.retrieval_p95_ms), "Antwortkontext", Number(sloValues.retrieval_p95_ms || 0) > 2500 ? "warning" : "good"),
          systemStatusRow("Ausweichantworten", formatRatePercent(sloValues.fallback_rate), "KI-Anbieter oder Suche", Number(sloValues.fallback_rate || 0) >= 0.1 ? "warning" : "good"),
          systemStatusRow("Index-Sync-Fehler", Number(sloValues.vector_sync_failure_count || 0), "Index-Synchronisation", Number(sloValues.vector_sync_failure_count || 0) ? "critical" : "good")
        );
        setDashboardText("[data-dashboard-ai-status]", ready ? "bereit" : "prüfen");
        setDashboardText("[data-dashboard-ai-status-meta]", aiStatus.provider || "KI-Anbieter unbekannt");
      }

      function renderKnowledgeHealth() {
        if (!aiKnowledgeHealth) return;
        const status = dashboardState.knowledgeStatus || {};
        const vectorStatus = status.vector_store || {};
        const gaps = dashboardState.knowledgeGaps || {};
        const indexed = Number(status.indexed || 0);
        const documents = Number(status.documents || 0);
        const chunks = Number(status.chunks || 0);
        const stale = Number(status.stale || 0);
        const missingTextabschnitte = Number(vectorStatus.missing_chunk_count || 0);
        const reindexNeeded = Boolean(vectorStatus.reindex_recommended);
        aiKnowledgeHealth.innerHTML = "";
        if (!currentUserIsMasterAdmin()) {
          aiKnowledgeHealth.appendChild(systemStatusRow(
            "Wissensstatus",
            "eingeschränkt",
            "Indexdetails sind im KI-Administration sichtbar.",
            "muted"
          ));
          return;
        }
        aiKnowledgeHealth.append(
          systemStatusRow("Dokumente indexiert", indexed + "/" + documents, chunks + " Textabschnitte", documents && indexed < documents ? "warning" : "good"),
          systemStatusRow("Veraltete Dokumente", stale, "Aging und Reindex", stale ? "warning" : "good"),
          systemStatusRow("Fehlende Textabschnitte", missingTextabschnitte, "DB zu Vektor Store", missingTextabschnitte ? "critical" : "good"),
          systemStatusRow("Reindex", reindexNeeded ? "empfohlen" : "nicht nötig", (vectorStatus.reindex_reasons || []).join(", "), reindexNeeded ? "warning" : "good"),
          systemStatusRow("Wissenslücken", Number(gaps.open_count || 0), "offene Lücken", Number(gaps.open_count || 0) ? "warning" : "good")
        );
        setDashboardText("[data-dashboard-index-status]", reindexNeeded ? "Reindex" : "OK");
        setDashboardText(
          "[data-dashboard-index-status-meta]",
          indexed + "/" + documents + " Dokumente, " + chunks + " Textabschnitte"
        );
        setDashboardText("[data-dashboard-knowledge-gap-count]", Number(gaps.open_count || 0));
        setDashboardText("[data-dashboard-knowledge-gap-meta]", "offene Lücken");
      }

      function applySloKpis() {
        const sloValues = retrievalSloValues();
        setDashboardText("[data-dashboard-safety-count]", Number(sloValues.safety_risk_count || 0));
        setDashboardText("[data-dashboard-low-confidence-count]", formatRatePercent(sloValues.low_confidence_rate));
        setDashboardText("[data-dashboard-retrieval-health]", formatMilliseconds(sloValues.retrieval_p95_ms));
        setDashboardText(
          "[data-dashboard-retrieval-health-meta]",
          formatRatePercent(sloValues.no_source_rate) + " ohne Quellen"
        );
      }

      function setProgress(selector, value) {
        document.querySelectorAll(selector).forEach((element) => {
          element.style.width = Math.max(0, Math.min(100, Number(value || 0))) + "%";
        });
      }

      function activityItem(kind, title, meta, severity, href) {
        const element = document.createElement(href ? "a" : "div");
        element.className = "activity-feed-item " + dashboardSignalClass(severity);
        if (href) element.href = href;
        const marker = document.createElement("span");
        marker.className = "activity-feed-marker";
        marker.textContent = kind;
        const body = document.createElement("div");
        const heading = document.createElement("strong");
        const detail = document.createElement("small");
        heading.textContent = title || "Hinweis";
        detail.textContent = meta || "";
        body.append(heading, detail);
        element.append(marker, body);
        return element;
      }

      function briefingSignalCount() {
        const briefing = dashboardState.briefing || {};
        const sections = Array.isArray(briefing.sections) ? briefing.sections : [];
        return sections.reduce((sum, section) => sum + Number(section.count || 0), 0);
      }

      function renderMachineStrip() {
        if (!executiveMachineStrip) return;
        const operations = dashboardState.operations || {};
        const machines = operations.machines || {};
        const inventory = dashboardState.inventory || operations.inventory || {};
        executiveMachineStrip.innerHTML = "";
        executiveMachineStrip.append(
          systemStatusRow("Maschinen down", Number(machines.machines_down || 0) + "/" + Number(machines.machines_total || 0), (machines.faults || dashboardState.errors.length || 0) + " Störungen", Number(machines.machines_down || 0) ? "critical" : "good"),
          systemStatusRow("Wiederholungen", Number(machines.repeat_faults || 0), "Fehlertrend im Zeitraum", Number(machines.repeat_faults || 0) ? "warning" : "good"),
          systemStatusRow("MTTR", formatMinutes(machines.mttr_minutes), formatMinutes(machines.downtime_minutes) + " Ausfallzeit", Number(machines.mttr_minutes || 0) > 0 ? "warning" : "good"),
          systemStatusRow("Lager kritisch", Number(inventory.critical_shortage_count || 0), (inventory.low_stock_count || 0) + " niedrig", Number(inventory.critical_shortage_count || 0) ? "critical" : "good")
        );
      }

      function renderAiTrustPanel() {
        if (!executiveAiTrust) return;
        const sloValues = retrievalSloValues();
        const gapCount = dashboardState.knowledgeGaps ? Number(dashboardState.knowledgeGaps.open_count || 0) : 0;
        executiveAiTrust.innerHTML = "";
        executiveAiTrust.append(
          systemStatusRow("Niedrige Sicherheit", formatRatePercent(sloValues.low_confidence_rate), "Antworten unter Schwelle", Number(sloValues.low_confidence_rate || 0) >= 0.15 ? "warning" : "good"),
          systemStatusRow("Suchzeit P95", formatMilliseconds(sloValues.retrieval_p95_ms), formatRatePercent(sloValues.no_source_rate) + " ohne Quellen", Number(sloValues.retrieval_p95_ms || 0) > 2500 || Number(sloValues.no_source_rate || 0) >= 0.1 ? "warning" : "good"),
          systemStatusRow("Sicherheit", Number(sloValues.safety_risk_count || 0), "Sicherheitsereignisse im Fenster", Number(sloValues.safety_risk_count || 0) ? "critical" : "good"),
          systemStatusRow("Wissenslücken", gapCount, "offene Wissenslücken", gapCount ? "warning" : "good")
        );
      }

      function renderExecutiveWarnings() {
        if (!executiveWarningFeed) return;
        const activeTasks = dashboardState.tasks.filter((task) => task.status !== "done" && task.status !== "cancelled");
        const criticalTasks = activeTasks.filter((task) => task.priority === "urgent" || isOverdue(task));
        const sloValues = retrievalSloValues();
        const gapCount = dashboardState.knowledgeGaps ? Number(dashboardState.knowledgeGaps.open_count || 0) : 0;
        const items = [];
        if (criticalTasks.length) items.push(activityItem("KR", criticalTasks.length + " kritische Aufgaben", "Sofort priorisieren", "critical", "/tasks"));
        if (dashboardState.errors.length) items.push(activityItem("ST", dashboardState.errors.length + " offene Störungen", "Maschinenlage prüfen", dashboardState.errors.length > 2 ? "critical" : "warning", "/errors"));
        if (Number(sloValues.safety_risk_count || 0)) items.push(activityItem("SF", Number(sloValues.safety_risk_count || 0) + " Sicherheitsrisiken", "AI Antworten prüfen", "critical", "/admin/ai"));
        if (gapCount) items.push(activityItem("KG", gapCount + " Wissenslücken", "Wissensbasis ergänzen", "warning", "/admin/ai"));
        if (Number(sloValues.stale_index_count || 0)) items.push(activityItem("IX", Number(sloValues.stale_index_count || 0) + " veraltete Indexeinträge", "Reindex empfohlen", "warning", "/admin/ai"));
        executiveWarningFeed.innerHTML = "";
        if (!items.length) {
          executiveWarningFeed.appendChild(emptyRailMessage("Keine kritischen Warnungen im aktuellen Datenfenster."));
          return;
        }
        items.slice(0, 6).forEach((item) => executiveWarningFeed.appendChild(item));
      }

      function renderActivityFeed() {
        if (!executiveActivityFeed) return;
        const items = [];
        dashboardState.tasks.slice(0, 3).forEach((task) => {
          items.push(activityItem("TA", task.title || "Aufgabe", (task.priority || "normal") + " - " + (task.status || "offen"), task.priority === "urgent" || isOverdue(task) ? "warning" : "muted", "/tasks"));
        });
        dashboardState.errors.slice(0, 3).forEach((entry) => {
          items.push(activityItem("FE", entry.title || entry.error_code || "Störung", ((entry.machine_obj && entry.machine_obj.name) || entry.machine || "Maschine") + " - " + formatDashboardTime(entry.created_at), "warning", "/errors"));
        });
        const briefing = dashboardState.briefing || {};
        const sections = Array.isArray(briefing.sections) ? briefing.sections : [];
        sections.slice(0, 2).forEach((section) => {
          items.push(activityItem("AI", section.title || "Briefing", Number(section.count || 0) + " Hinweise", "muted", "#daily-briefing"));
        });
        const sloValues = retrievalSloValues();
        if (Number(sloValues.no_source_rate || 0) >= 0.1) {
          items.push(activityItem("RG", "Antworten ohne Quellen", formatRatePercent(sloValues.no_source_rate), "warning", "/admin/ai"));
        }
        executiveActivityFeed.innerHTML = "";
        if (!items.length) {
          executiveActivityFeed.appendChild(emptyRailMessage("Noch keine Aktivitäten im aktuellen Datenfenster."));
          return;
        }
        items.slice(0, 8).forEach((item) => executiveActivityFeed.appendChild(item));
      }

      function renderExecutiveKpis() {
        const activeTasks = dashboardState.tasks.filter((task) => task.status !== "done" && task.status !== "cancelled");
        const doneTasks = dashboardState.tasks.filter((task) => task.status === "done");
        const criticalTasks = activeTasks.filter((task) => task.priority === "urgent" || isOverdue(task));
        const activityCount = dashboardState.errors.length + dashboardState.tasks.length + briefingSignalCount();
        const sloValues = retrievalSloValues();
        const hasRisk = Boolean(criticalTasks.length || dashboardState.errors.length || Number(sloValues.safety_risk_count || 0) || Number(sloValues.vector_sync_failure_count || 0) || Number(sloValues.stale_index_count || 0));
        setDashboardText("[data-dashboard-unresolved-errors]", dashboardState.errors.length);
        setDashboardText("[data-dashboard-today-activity-count]", activityCount);
        setDashboardText("[data-dashboard-active-integrations]", currentUserIsMasterAdmin() ? "Assistenz" : "Basis");
        setDashboardText("[data-dashboard-system-status]", hasRisk ? "Prüfen" : "Stabil");
        setDashboardText("[data-dashboard-system-meta]", hasRisk ? "Warnungen aktiv" : "Keine kritischen Signale");
        setProgress("[data-dashboard-open-progress]", activeTasks.length ? Math.min(100, activeTasks.length * 8) : 4);
        setProgress("[data-dashboard-critical-progress]", criticalTasks.length ? Math.min(100, criticalTasks.length * 20) : 4);
        setProgress("[data-dashboard-done-progress]", dashboardState.tasks.length ? (doneTasks.length / dashboardState.tasks.length) * 100 : 4);
        setProgress("[data-dashboard-error-progress]", dashboardState.errors.length ? Math.min(100, dashboardState.errors.length * 18) : 4);
        setProgress("[data-dashboard-activity-progress]", activityCount ? Math.min(100, activityCount * 6) : 4);
        setProgress("[data-dashboard-ai-progress]", Number(sloValues.low_confidence_rate || 0) >= 0.15 ? 45 : 88);
        setProgress("[data-dashboard-integration-progress]", currentUserIsMasterAdmin() ? 75 : 35);
        setProgress("[data-dashboard-system-progress]", hasRisk ? 48 : 92);
      }

      function renderExecutiveDashboard() {
        renderExecutiveKpis();
        renderCriticalToday();
        renderMachineCards();
        renderPeopleHints();
        renderMachineStrip();
        renderAiTrustPanel();
        renderExecutiveWarnings();
        renderActivityFeed();
      }
      Object.assign(Dashboard, { cockpitSignal, systemStatusRow, retrievalSloValues, updateDashboardStatus, renderPriorityRail, renderRiskRadar, renderAiSystemRail, renderKnowledgeHealth, applySloKpis, setProgress, activityItem, briefingSignalCount, renderMachineStrip, renderAiTrustPanel, renderExecutiveWarnings, renderActivityFeed, renderExecutiveKpis, renderExecutiveDashboard });
    }
  };
})();

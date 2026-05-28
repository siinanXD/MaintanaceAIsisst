/**
 * Dashboard resources module.
 * Registers helpers on the current MaintenanceDashboardRuntime object.
 */
(function registerDashboardModule() {
  window.MaintenanceDashboardModules = window.MaintenanceDashboardModules || {};
  window.MaintenanceDashboardModules["resources"] = function attachDashboardResources(Dashboard) {
    with (Dashboard) {
      function activeDashboardErrors(errors) {
        const recentWindowDays = 30;
        return listData(errors)
          .filter((entry) => {
            const status = String(entry.status || "").toLowerCase();
            if (status === "closed") return false;
            if (!entry.last_seen_at) return false;
            const seenDate = isoDateOnly(entry.last_seen_at);
            return !seenDate || dateDiffDays(seenDate, todayIso()) <= recentWindowDays;
          })
          .sort((first, second) => {
            const severityRank = { critical: 0, high: 1, medium: 2, low: 3 };
            const firstRank = severityRank[String(first.severity || "").toLowerCase()] ?? 4;
            const secondRank = severityRank[String(second.severity || "").toLowerCase()] ?? 4;
            if (firstRank !== secondRank) return firstRank - secondRank;
            return String(second.last_seen_at || second.created_at || "").localeCompare(
              String(first.last_seen_at || first.created_at || "")
            );
          });
      }

      function renderCriticalToday() {
        if (window.maintenanceDashboardReactTasksOwned === true || window.maintenanceDashboardReactAssetsOwned === true) return;
        if (!criticalTodayPanel) return;
        const activeTasks = dashboardState.tasks.filter((task) => task.status !== "done" && task.status !== "cancelled");
        const criticalTasks = activeTasks.filter((task) => task.priority === "urgent" || isOverdue(task));
        const activeErrors = activeDashboardErrors(dashboardState.errors);
        const inventory = dashboardState.inventory || (dashboardState.operations && dashboardState.operations.inventory) || {};
        const machines = (dashboardState.operations && dashboardState.operations.machines) || {};
        const items = [];
        criticalTasks.slice(0, 4).forEach((task) => {
          items.push(controlCenterLinkCard("TA", task.title, taskMetaLine(task), "critical", "/tasks", task.status === "open" ? "Starten" : "Prüfen"));
        });
        activeErrors.slice(0, 4).forEach((entry) => {
          const machine = (entry.machine_obj && entry.machine_obj.name) || entry.machine || "Maschine offen";
          const meta = [machine, entry.error_code || "ohne Code", relativeSeenLabel(entry.last_seen_at) || "aktiv"].filter(Boolean).join(" · ");
          const severity = entry.severity === "critical" || entry.severity === "high" ? "critical" : "warning";
          items.push(controlCenterLinkCard("ST", entry.title || entry.error_code || "Störung", meta, severity, "/errors?status=open", "Störung prüfen"));
        });
        if (Number(machines.machines_down || 0)) {
          items.push(controlCenterLinkCard("MA", machines.machines_down + " Maschinen down", (machines.faults || 0) + " Störungen im Zeitraum", "critical", "/machines", "Maschinen"));
        }
        if (Number(inventory.critical_shortage_count || 0)) {
          items.push(controlCenterLinkCard("LG", inventory.critical_shortage_count + " kritische Lagerengpässe", (inventory.low_stock_count || 0) + " Artikel unter Mindestbestand", "critical", "/inventory", "Lager"));
        }
        criticalTodayPanel.innerHTML = "";
        if (!items.length) {
          criticalTodayPanel.appendChild(emptyRailMessage("Keine kritischen Punkte für heute. Beobachte neue Störungen, Fälligkeiten und Engpässe."));
          return;
        }
        items.slice(0, 8).forEach((item) => criticalTodayPanel.appendChild(item));
      }

      function machineStatusSeverity(machine) {
        const status = keywordText(machine.status);
        if (status.includes("down") || status.includes("stor") || status.includes("error") || status.includes("stop")) {
          return "critical";
        }
        if (status.includes("wart") || status.includes("maintenance") || status.includes("pause") || status.includes("pruf")) {
          return "warning";
        }
        if (status.includes("run") || status.includes("aktiv") || status.includes("ok") || status.includes("bereit")) {
          return "good";
        }
        return "muted";
      }

      function machineStatusText(machine) {
        const status = String(machine.status || "unbekannt");
        if (status === "running") return "Läuft";
        if (status === "down") return "Stillstand";
        if (status === "maintenance") return "Wartung";
        return status;
      }

      function updateMachineKpis() {
        if (window.maintenanceDashboardReactAssetsOwned === true) return;
        const operations = dashboardState.operations || {};
        const machineMetrics = operations.machines || {};
        const machines = dashboardState.machines || [];
        const total = Number(machineMetrics.machines_total || machines.length || 0);
        const down = Number(machineMetrics.machines_down || machines.filter((machine) => machineStatusSeverity(machine) === "critical").length || 0);
        const warning = machines.filter((machine) => machineStatusSeverity(machine) === "warning").length;
        const healthy = Math.max(0, total - down - warning);
        setDashboardText("[data-dashboard-machine-status]", total ? (healthy + "/" + total) : "--");
        setDashboardText(
          "[data-dashboard-machine-kpi-meta]",
          total ? down + " kritisch, " + warning + " beobachten" : "Keine Maschinen geladen"
        );
        setProgress("[data-dashboard-machine-progress]", total ? (healthy / total) * 100 : 4);
      }

      function renderMachineCards() {
        if (window.maintenanceDashboardReactAssetsOwned === true) return;
        if (!machineCards) {
          updateMachineKpis();
          return;
        }
        machineCards.innerHTML = "";
        const machines = dashboardState.machines || [];
        if (!machines.length) {
          machineCards.appendChild(emptyRailMessage("Keine Maschinen im aktuellen Zugriff."));
          updateMachineKpis();
          return;
        }
        machines.slice(0, 6).forEach((machine) => {
          const severity = machineStatusSeverity(machine);
          const card = document.createElement("a");
          card.className = "machine-status-card " + dashboardSignalClass(severity);
          card.href = "/machines";
          const title = document.createElement("strong");
          title.textContent = machine.name || "Maschine";
          const meta = document.createElement("small");
          meta.textContent = machine.produced_item || "Produktionsdaten offen";
          const footer = document.createElement("div");
          footer.append(
            controlCenterBadge(machineStatusText(machine), severity),
            controlCenterBadge(machine.criticality || "normal", machine.criticality === "critical" ? "critical" : "muted")
          );
          card.append(title, meta, footer);
          machineCards.appendChild(card);
        });
        updateMachineKpis();
      }

      function formatDashboardDate(value) {
        if (!value) return "-";
        return new Date(value).toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" });
      }

      function renderHandoverList(handovers) {
        if (window.maintenanceDashboardReactPeopleOwned === true) {
          dashboardState.handovers = handovers || [];
          return;
        }
        if (!handoverList) return;
        dashboardState.handovers = handovers || [];
        handoverList.innerHTML = "";
        setDashboardText("[data-dashboard-shift-status]", dashboardState.handovers.length || "--");
        setDashboardText(
          "[data-dashboard-shift-meta]",
          dashboardState.handovers.length ? dashboardState.handovers.length + " Übergaben heute" : "Keine Übergabe heute"
        );
        setProgress("[data-dashboard-shift-progress]", dashboardState.handovers.length ? 72 : 18);
        if (!dashboardState.handovers.length) {
          handoverList.appendChild(emptyRailMessage("Heute gibt es noch keine gespeicherte Schichtübergabe."));
          return;
        }
        dashboardState.handovers.slice(0, 4).forEach((handover) => {
          const card = document.createElement("a");
          card.className = "handover-card " + (handover.status === "completed" ? "is-good" : "is-warning");
          card.href = "/handover";
          const title = document.createElement("strong");
          title.textContent = (handover.shift_type || "Schicht") + " · " + (handover.department || "Bereich");
          const meta = document.createElement("small");
          meta.textContent = [
            formatDashboardDate(handover.shift_date),
            handover.open_tasks ? "offene Punkte vorhanden" : "keine offenen Punkte erfasst",
            handover.machine_notes ? "Maschinenhinweise" : ""
          ].filter(Boolean).join(" · ");
          card.append(title, meta, controlCenterBadge(handover.status === "completed" ? "Bestätigt" : "Offen", handover.status === "completed" ? "good" : "warning"));
          handoverList.appendChild(card);
        });
      }

      function renderPeopleHints() {
        if (window.maintenanceDashboardReactPeopleOwned === true) return;
        if (!peopleHints) return;
        const vacations = dashboardState.vacations || [];
        const employees = dashboardState.employees || [];
        const absent = employees.filter((employee) => employeeStatus(employee) === "Abwesend");
        const hints = [];
        if (vacations.length) {
          hints.push(controlCenterLinkCard("UR", vacations.length + " offene Urlaubsanträge", "Genehmigen oder ablehnen", "warning", "/vacations", "Urlaub"));
        }
        if (absent.length) {
          hints.push(controlCenterLinkCard("AB", absent.length + " abwesend markiert", absent.slice(0, 2).map((employee) => employee.name).join(", "), "warning", "/employees", "Team"));
        }
        if (employees.length && !hints.length) {
          hints.push(controlCenterLinkCard("PE", employees.length + " Mitarbeitende sichtbar", "Keine offenen Personalwarnungen", "good", "/employees", "Personal"));
        }
        peopleHints.innerHTML = "";
        if (!hints.length) {
          peopleHints.appendChild(emptyRailMessage("Keine Personalhinweise im aktuellen Zugriff."));
        } else {
          hints.forEach((hint) => peopleHints.appendChild(hint));
        }
        setDashboardText("[data-dashboard-people-status]", vacations.length || absent.length || employees.length || "--");
        setDashboardText(
          "[data-dashboard-people-meta]",
          vacations.length ? vacations.length + " offene Urlaubsanträge" : (absent.length ? absent.length + " abwesend" : "Keine offenen Personalwarnungen")
        );
        setProgress("[data-dashboard-people-progress]", vacations.length || absent.length ? 45 : 88);
      }

      function rowLikeStat(label, value) {
        const item = document.createElement("div");
        item.className = "stat-row";
        item.innerHTML = `<span>${label}</span><strong>${value}</strong>`;
        return item;
      }

      function briefingClass(severity) {
        if (severity === "critical" || severity === "urgent") return "is-critical";
        if (severity === "warning" || severity === "soon" || severity === "high") return "is-warning";
        return "is-success";
      }

      function briefingIcon(section, item) {
        if (section && section.type === "knowledge") return "AI";
        if (item && (item.severity === "critical" || item.severity === "urgent")) return "!";
        if (item && (item.severity === "warning" || item.severity === "soon")) return "!";
        return "OK";
      }

      function briefingItem(section, item) {
        const element = document.createElement(item && item.url ? "a" : "div");
        element.className = "briefing-item " + briefingClass(item && item.severity);
        if (item && item.url) element.href = item.url;
        const icon = document.createElement("span");
        icon.textContent = briefingIcon(section, item);
        const title = document.createElement("strong");
        title.textContent = (item && item.title) || "Hinweis";
        const meta = document.createElement("small");
        meta.textContent = (item && (item.summary || item.severity)) || "";
        element.append(icon, title, meta);
        return element;
      }

      function emptyDashboardMessage(message) {
        const empty = document.createElement("div");
        empty.className = "guided-empty-state";
        empty.textContent = message;
        return empty;
      }

      function initials(name) {
        return String(name || "?")
          .split(/\s+/)
          .filter(Boolean)
          .slice(0, 2)
          .map((part) => part[0].toUpperCase())
          .join("") || "?";
      }

      function formatDashboardTime(value) {
        if (!value) return "-";
        return new Date(value).toLocaleTimeString("de-DE", {
          hour: "2-digit",
          minute: "2-digit"
        });
      }

      function firstQualification(employee) {
        return String(employee.qualifications || "")
          .split(/[,\n;]/)
          .map((part) => part.trim())
          .filter(Boolean)[0] || employee.department || "Mitarbeiter";
      }

      function employeeStatus(employee) {
        const shift = String(employee.current_shift || employee.shift_model || "").toLowerCase();
        if (shift.includes("urlaub") || shift.includes("frei")) return "Abwesend";
        if (!shift) return "Geplant";
        return "Anwesend";
      }

      function employeeRow(employee, isHeader) {
        const rowElement = document.createElement("div");
        rowElement.className = isHeader ? "employee-row is-head" : "employee-row";
        rowElement.setAttribute("role", "row");
        if (isHeader) {
          ["Mitarbeiter", "Rolle", "Schicht", "Status"].forEach((label) => {
            const cell = document.createElement("span");
            cell.textContent = label;
            rowElement.appendChild(cell);
          });
          return rowElement;
        }

        const name = document.createElement("span");
        const avatar = document.createElement("span");
        avatar.className = "mini-avatar";
        avatar.textContent = initials(employee.name);
        name.append(avatar, document.createTextNode(employee.name || "Unbekannt"));

        const role = document.createElement("span");
        role.textContent = firstQualification(employee);

        const shift = document.createElement("span");
        shift.textContent = employee.current_shift || employee.shift_model || "-";

        const status = document.createElement("strong");
        status.textContent = employeeStatus(employee);
        status.classList.toggle("is-warning", status.textContent !== "Anwesend");

        rowElement.append(name, role, shift, status);
        return rowElement;
      }

      function renderEmployeeOverview(employees) {
        if (window.maintenanceDashboardReactPeopleOwned === true) {
          dashboardState.employees = employees || [];
          return;
        }
        if (!employeeOverview) return;
        dashboardState.employees = employees;
        employeeOverview.innerHTML = "";
        employeeOverview.appendChild(employeeRow(null, true));
        if (!employees.length) {
          employeeOverview.appendChild(emptyDashboardMessage("Keine Mitarbeiterdaten verfügbar."));
          renderPeopleHints();
          return;
        }
        employees.slice(0, 5).forEach((employee) => {
          employeeOverview.appendChild(employeeRow(employee));
        });
        renderPeopleHints();
      }

      function incidentBadge(entry) {
        const severity = String(entry && entry.severity || "").toLowerCase();
        if (severity === "critical" || severity === "high") {
          return badge("Aktiv", "badge badge-priority is-urgent");
        }
        return badge("Aktiv", "badge badge-priority is-soon");
      }

      function renderFrequentCodes(errors) {
        if (window.maintenanceDashboardReactAssetsOwned === true) return;
        if (!frequentCodes) return;
        const counts = errors.reduce((items, entry) => {
          const code = entry.error_code || entry.code || "ohne Code";
          items[code] = (items[code] || 0) + 1;
          return items;
        }, {});
        frequentCodes.innerHTML = "";
        const sortedCodes = Object.entries(counts)
          .sort((first, second) => second[1] - first[1])
          .slice(0, 5);
        if (!sortedCodes.length) {
          frequentCodes.appendChild(emptyDashboardMessage("Keine Fehlercodes im aktuellen Fenster."));
          return;
        }
        sortedCodes.forEach(([code, count]) => {
          const item = document.createElement("span");
          const amount = document.createElement("strong");
          item.textContent = code;
          amount.textContent = String(count);
          item.appendChild(amount);
          frequentCodes.appendChild(item);
        });
      }

      function renderIncidentRows(errors) {
        if (window.maintenanceDashboardReactAssetsOwned === true) {
          dashboardState.errors = activeDashboardErrors(errors);
          return;
        }
        if (!errorStats) return;
        const activeErrors = activeDashboardErrors(errors);
        dashboardState.errors = activeErrors;
        renderFrequentCodes(activeErrors);
        errorStats.innerHTML = "";
        if (!activeErrors.length) {
          errorStats.appendChild(emptyDashboardMessage("Keine aktiven Störungen im aktuellen Fenster."));
          setDashboardText("[data-dashboard-machine-status]", "0");
          renderExecutiveDashboard();
          setDashboardText("[data-dashboard-machine-status-meta]", "keine aktiven Störungen");
          return;
        }
        activeErrors.slice(0, 5).forEach((entry) => {
          const rowElement = document.createElement("div");
          rowElement.className = "incident-row";

          const title = document.createElement("strong");
          title.textContent = entry.title || entry.error_code || "Störung";

          const machine = document.createElement("span");
          machine.textContent = (entry.machine_obj && entry.machine_obj.name) || entry.machine || "-";

          const time = document.createElement("span");
          time.textContent = relativeSeenLabel(entry.last_seen_at) || formatDashboardTime(entry.created_at);

          const status = badge(statusLabel(entry.status), "badge badge-status is-progress");
          rowElement.append(incidentBadge(entry), title, machine, time, status);
          errorStats.appendChild(rowElement);
        });
        setDashboardText("[data-dashboard-machine-status]", String(activeErrors.length));
        renderExecutiveDashboard();
        setDashboardText("[data-dashboard-machine-status-meta]", "aktive Störungen");
      }

      function inventoryStatusCounts(materials) {
        return materials.reduce((counts, material) => {
          const quantity = Number(material.quantity || 0);
          if (quantity <= 3) counts.critical += 1;
          else if (quantity <= 10) counts.low += 1;
          else counts.ok += 1;
          return counts;
        }, { critical: 0, low: 0, ok: 0 });
      }

      function inventoryMetric(label, value, detail) {
        const item = document.createElement("div");
        const title = document.createElement("strong");
        title.textContent = label;
        const amount = document.createElement("span");
        amount.textContent = value;
        const meta = document.createElement("small");
        meta.textContent = detail;
        item.append(title, amount, meta);
        return item;
      }

      function inventoryCountsFromZusammenfassung(summary, materials) {
        const counts = summary && summary.status_counts;
        if (counts) {
          return {
            critical: Number(counts.critical || 0),
            low: Number(counts.low || 0),
            ok: Number(counts.ok || 0)
          };
        }
        return inventoryStatusCounts(materials);
      }

      function inventoryShortagesFromZusammenfassung(summary, materials) {
        if (summary && Array.isArray(summary.top_shortages)) {
          return summary.top_shortages;
        }
        return materials
          .slice()
          .sort((first, second) => Number(first.quantity || 0) - Number(second.quantity || 0))
          .slice(0, 3);
      }

      function renderInventoryZusammenfassung(summary) {
        if (window.maintenanceDashboardReactSideOwned === true) {
          dashboardState.inventory = summary || {};
          return;
        }
        if (!inventoryStats) return;
        dashboardState.inventory = summary || {};
        const materials = Array.isArray(summary.materials) ? summary.materials : [];
        const counts = inventoryCountsFromZusammenfassung(summary, materials);
        const shortages = inventoryShortagesFromZusammenfassung(summary, materials);
        inventoryStats.innerHTML = "";
        inventoryStats.append(
          inventoryMetric("Kritisch", String(counts.critical), "Artikel"),
          inventoryMetric("Niedrig", String(counts.low), "Artikel"),
          inventoryMetric("OK", String(counts.ok), "Artikel"),
          inventoryMetric("Gesamtwert", formatMoney(summary.total_value), "Lagerwert")
        );
        if (!inventoryShortages) return;
        inventoryShortages.innerHTML = "";
        shortages.forEach((material) => {
          const item = document.createElement("span");
          const amount = document.createElement("strong");
          amount.textContent = String(material.quantity || 0) + " Stk.";
          item.append(document.createTextNode(material.name || "Material"), amount);
          inventoryShortages.appendChild(item);
        });
        if (!shortages.length) {
          inventoryShortages.appendChild(emptyDashboardMessage("Keine Lagerdaten verfügbar."));
        }
      }

      async function loadDashboardMachines() {
        if (window.maintenanceDashboardReactAssetsOwned === true) return;
        if (!machineCards || !canView("machines")) return;
        try {
          dashboardState.machines = listData(await api("/api/v1/machines?limit=100"));
        } catch (error) {
          dashboardState.machines = [];
          machineCards.innerHTML = "";
          machineCards.appendChild(emptyRailMessage("Maschinenstatus konnte nicht geladen werden."));
        }
        renderMachineCards();
        renderCriticalToday();
      }

      async function loadDashboardHandovers() {
        if (window.maintenanceDashboardReactPeopleOwned === true) return;
        if (!handoverList || !canView("shiftplans")) return;
        try {
          renderHandoverList(listData(await api("/api/v1/handover?date=" + todayIso())));
        } catch (error) {
          dashboardState.handovers = [];
          handoverList.innerHTML = "";
          handoverList.appendChild(emptyRailMessage("Schichtübergaben konnten nicht geladen werden."));
          setDashboardText("[data-dashboard-shift-status]", "--");
          setDashboardText("[data-dashboard-shift-meta]", "Übergaben nicht verfügbar");
          setProgress("[data-dashboard-shift-progress]", 8);
        }
      }

      async function loadDashboardVacations() {
        if (window.maintenanceDashboardReactPeopleOwned === true) return;
        if (!peopleHints || !canView("employees")) return;
        try {
          dashboardState.vacations = listData(await api("/api/v1/vacations?limit=100"));
        } catch (error) {
          dashboardState.vacations = [];
        }
        renderPeopleHints();
      }
      Object.assign(Dashboard, { activeDashboardErrors, renderCriticalToday, machineStatusSeverity, machineStatusText, updateMachineKpis, renderMachineCards, formatDashboardDate, renderHandoverList, renderPeopleHints, rowLikeStat, briefingClass, briefingIcon, briefingItem, emptyDashboardMessage, initials, formatDashboardTime, firstQualification, employeeStatus, employeeRow, renderEmployeeOverview, incidentBadge, renderFrequentCodes, renderIncidentRows, inventoryStatusCounts, inventoryMetric, inventoryCountsFromZusammenfassung, inventoryShortagesFromZusammenfassung, renderInventoryZusammenfassung, loadDashboardMachines, loadDashboardHandovers, loadDashboardVacations });
    }
  };
})();

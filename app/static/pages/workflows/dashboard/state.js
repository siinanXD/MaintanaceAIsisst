/**
 * Dashboard state module.
 * Registers helpers on the current MaintenanceDashboardRuntime object.
 */
(function registerDashboardModule() {
  window.MaintenanceDashboardModules = window.MaintenanceDashboardModules || {};
  window.MaintenanceDashboardModules["state"] = function attachDashboardState(Dashboard) {
    with (Dashboard) {
      function announce(message, isError) {
        if (globalLive) globalLive.textContent = message;
        if (cockpitMessage) {
          cockpitMessage.textContent = message;
          cockpitMessage.classList.toggle("is-error", Boolean(isError));
          cockpitMessage.classList.toggle("is-success", Boolean(message && !isError));
        }
      }

      function todayIso() {
        const now = new Date();
        const month = String(now.getMonth() + 1).padStart(2, "0");
        const day = String(now.getDate()).padStart(2, "0");
        return now.getFullYear() + "-" + month + "-" + day;
      }

      function isOverdue(task) {
        return task.due_date && task.due_date < todayIso() && task.status !== "done";
      }

      function isoDateOnly(value) {
        const text = String(value || "").slice(0, 10);
        return /^\d{4}-\d{2}-\d{2}$/.test(text) ? text : "";
      }

      function dateDiffDays(fromIso, toIso) {
        const from = isoDateOnly(fromIso).split("-").map(Number);
        const to = isoDateOnly(toIso).split("-").map(Number);
        if (from.length !== 3 || to.length !== 3 || from.some(Number.isNaN) || to.some(Number.isNaN)) {
          return 0;
        }
        const fromTime = Date.UTC(from[0], from[1] - 1, from[2]);
        const toTime = Date.UTC(to[0], to[1] - 1, to[2]);
        return Math.round((toTime - fromTime) / 86400000);
      }

      function relativeDateLabel(dateValue) {
        const target = isoDateOnly(dateValue);
        if (!target) return "";
        const diff = dateDiffDays(todayIso(), target);
        if (diff === 0) return "heute faellig";
        if (diff === 1) return "morgen faellig";
        if (diff === -1) return "seit gestern überfällig";
        if (diff < 0) return "seit " + Math.abs(diff) + " Tagen überfällig";
        return "in " + diff + " Tagen faellig";
      }

      function setDashboardText(selector, value) {
        setText(selector, value == null || value === "" ? "-" : value);
      }

      function formatRatePercent(value) {
        return Math.round(Number(value || 0) * 100) + "%";
      }

      function formatMilliseconds(value) {
        return Math.round(Number(value || 0)) + " ms";
      }

      function currentUserIsMasterAdmin() {
        const currentUser = user();
        return Boolean(currentUser && currentUser.role === "master_admin");
      }

      function dashboardSignalClass(severity) {
        if (severity === "critical") return "is-critical";
        if (severity === "warning") return "is-warning";
        if (severity === "good") return "is-good";
        return "is-muted";
      }

      function dashboardSignalRank(severity) {
        const ranks = { critical: 0, warning: 1, good: 2, muted: 3 };
        return ranks[severity] == null ? 3 : ranks[severity];
      }

      function dashboardWorstSeverity(signals) {
        if (signals.some((item) => item.severity === "critical")) return "critical";
        if (signals.some((item) => item.severity === "warning")) return "warning";
        return signals.length ? "good" : "muted";
      }

      function dashboardStatusLabel(severity) {
        if (severity === "critical") return "Kritische Lage";
        if (severity === "warning") return "Prüfen";
        if (severity === "good") return "Stabil";
        return "Noch keine Daten";
      }

      function emptyRailMessage(message) {
        const empty = document.createElement("div");
        empty.className = "empty-state";
        empty.textContent = message;
        return empty;
      }

      function controlCenterBadge(label, severity) {
        return badge(label, "badge badge-status " + (
          severity === "critical" ? "is-open" :
            severity === "warning" ? "is-progress" :
              severity === "good" ? "is-done" : "is-neutral"
        ));
      }

      function controlCenterLinkCard(kind, title, meta, severity, href, actionLabel) {
        const card = document.createElement(href ? "a" : "article");
        card.className = "control-center-item " + dashboardSignalClass(severity);
        if (href) card.href = href;
        const marker = document.createElement("span");
        marker.className = "control-center-item-marker";
        marker.textContent = kind;
        const body = document.createElement("div");
        const heading = document.createElement("strong");
        const detail = document.createElement("small");
        heading.textContent = title || "Hinweis";
        detail.textContent = meta || "";
        body.append(heading, detail);
        const action = document.createElement("span");
        action.className = "control-center-item-action";
        action.textContent = actionLabel || (href ? "Öffnen" : "Status");
        card.append(marker, body, action);
        return card;
      }

      function taskMachineHint(task) {
        const text = [task.title, task.description].filter(Boolean).join(" ");
        const match = text.match(/\b(Maschine|Anlage|Presse|Linie)\s*[A-Za-z0-9\-_.]*/i);
        return match ? match[0] : ((task.department && task.department.name) || "Bereich offen");
      }

      function taskMetaLine(task) {
        const parts = [
          priorityLabel(task.priority),
          statusLabel(task.status),
          relativeDateLabel(task.due_date),
          taskMachineHint(task)
        ].filter(Boolean);
        return parts.join(" · ");
      }
      Object.assign(Dashboard, { announce, todayIso, isOverdue, isoDateOnly, dateDiffDays, relativeDateLabel, setDashboardText, formatRatePercent, formatMilliseconds, currentUserIsMasterAdmin, dashboardSignalClass, dashboardSignalRank, dashboardWorstSeverity, dashboardStatusLabel, emptyRailMessage, controlCenterBadge, controlCenterLinkCard, taskMachineHint, taskMetaLine });
    }
  };
})();

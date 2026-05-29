import { type DashboardRuntimeData } from "./dashboardApi";
import { activeDashboardIncidents, assetText } from "./dashboardAssetModel";
import {
  dashboardSignalClass,
  dashboardStatusLabel,
  formatRatePercent,
  knowledgeGapCount,
  numberValue,
  objectValue,
  retrievalSloValues
} from "./dashboardTechnicalHelpers";
import type { DashboardHeroStatus, DashboardSeverity, DashboardSignalItem } from "./dashboardTechnicalTypes";
import { taskIsOverdue, taskText } from "./dashboardTaskModel";

/**
 * Build the hero status text from React-owned dashboard data.
 */
export function dashboardHeroStatus(data: DashboardRuntimeData, isLoading: boolean, errorMessage: string): DashboardHeroStatus {
  if (isLoading) {
    return {
      className: "is-loading",
      label: "Daten werden geladen",
      meta: "Schicht- und Systemdaten werden geladen",
      updated: "Aktualisierung läuft"
    };
  }

  if (errorMessage) {
    return {
      className: "is-warning",
      label: "Teilweise geladen",
      meta: errorMessage,
      updated: new Date().toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })
    };
  }

  const signals = prioritySignals(data);
  return {
    className: dashboardSignalClass(signals[0]?.severity ?? "good"),
    label: dashboardStatusLabel(signals),
    meta: signals.length ? `${signals.length} aktive Hinweise` : "Keine kritischen Signale",
    updated: `Aktualisiert ${new Date().toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })}`
  };
}

/**
 * Build priority signals for the AI operations rail.
 */
export function prioritySignals(data: DashboardRuntimeData): readonly DashboardSignalItem[] {
  const activeTasks = data.tasks.filter((task) => taskText(task, "status") !== "done" && taskText(task, "status") !== "cancelled");
  const criticalTasks = activeTasks.filter((task) => taskText(task, "priority") === "urgent" || taskIsOverdue(task));
  const operations = data.operationsSummary ?? {};
  const machines = objectValue(operations, "machines");
  const inventory = data.inventorySummary ?? objectValue(operations, "inventory");
  const sloValues = retrievalSloValues(data);
  const signals: DashboardSignalItem[] = [];

  if (criticalTasks.length) {
    signals.push({
      detail: taskText(criticalTasks[0], "title", "Sofort prüfen"),
      href: "/tasks",
      label: "Kritische Aufgaben",
      severity: "critical",
      value: String(criticalTasks.length)
    });
  }

  if (data.errors.length) {
    const incidents = activeDashboardIncidents(data.errors);
    signals.push({
      detail: assetText(incidents[0], "error_code", assetText(incidents[0], "title", "Fehlerliste")),
      href: "/errors",
      label: "Offene Störungen",
      severity: incidents.length > 2 ? "critical" : "warning",
      value: String(incidents.length)
    });
  }

  if (numberValue(machines, "repeat_faults")) {
    signals.push({
      detail: `${numberValue(machines, "faults")} Störungen im Zeitraum`,
      href: "/errors",
      label: "Wiederkehrende Probleme",
      severity: "warning",
      value: String(numberValue(machines, "repeat_faults"))
    });
  }

  if (numberValue(inventory, "critical_shortage_count")) {
    signals.push({
      detail: `${numberValue(inventory, "low_stock_count")} unter Mindestbestand`,
      href: "/inventory",
      label: "Materialengpässe",
      severity: "critical",
      value: String(numberValue(inventory, "critical_shortage_count"))
    });
  }

  if (numberValue(sloValues, "safety_risk_count")) {
    signals.push({
      detail: "KI-Sicherheit Events im Fenster",
      href: "/admin/ai",
      label: "Sicherheitsrisiken",
      severity: "critical",
      value: String(numberValue(sloValues, "safety_risk_count"))
    });
  }

  const gapCount = knowledgeGapCount(data);
  if (gapCount) {
    signals.push({
      detail: "offene Wissenslücken",
      href: "/admin/ai",
      label: "Wissenslücken",
      severity: gapCount > 3 ? "critical" : "warning",
      value: String(gapCount)
    });
  }

  const lowConfidenceRate = numberValue(sloValues, "low_confidence_rate");
  const noSourceRate = numberValue(sloValues, "no_source_rate");
  if (lowConfidenceRate >= 0.15 || noSourceRate >= 0.1) {
    signals.push({
      detail: "Niedrige Sicherheit oder fehlende Quellen",
      href: "/admin/ai",
      label: "Suchqualität",
      severity: lowConfidenceRate >= 0.25 || noSourceRate >= 0.2 ? "critical" : "warning",
      value: formatRatePercent(Math.max(lowConfidenceRate, noSourceRate))
    });
  }

  if (numberValue(sloValues, "stale_index_count")) {
    signals.push({
      detail: "Dokumente sollten reindexiert werden",
      href: "/admin/ai",
      label: "Veralteter Index",
      severity: "warning",
      value: String(numberValue(sloValues, "stale_index_count"))
    });
  }

  const severityRank: Record<DashboardSeverity, number> = { critical: 0, warning: 1, good: 2, muted: 3 };
  return signals.sort((first, second) => severityRank[first.severity] - severityRank[second.severity]).slice(0, 7);
}

/**
 * Build warning feed items from dashboard and AI signals.
 */
export function warningSignals(data: DashboardRuntimeData): readonly DashboardSignalItem[] {
  return prioritySignals(data).filter((signal) => signal.severity === "critical" || signal.severity === "warning").slice(0, 6);
}

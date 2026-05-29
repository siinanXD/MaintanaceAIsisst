/**
 * Normalize German maintenance text for simple search and keyword detection.
 */
export function keywordText(value: unknown): string {
  return String(value || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/ue/g, "u")
    .replace(/ae/g, "a")
    .replace(/oe/g, "o");
}

/**
 * Return the German priority label used by the legacy workflow.
 */
export function priorityLabel(priority: string | null | undefined): string {
  const labels: Record<string, string> = {
    urgent: "Kritisch",
    soon: "Bald",
    normal: "Normal"
  };
  return labels[priority || ""] || priority || "-";
}

/**
 * Return the German task status label used by the legacy workflow.
 */
export function statusLabel(status: string | null | undefined): string {
  const labels: Record<string, string> = {
    open: "Offen",
    in_progress: "In Arbeit",
    done: "Erledigt",
    cancelled: "Abgebrochen"
  };
  return labels[status || ""] || status || "-";
}

/**
 * Return the task priority badge classes from the existing visual language.
 */
export function priorityBadgeClass(priority: string | null | undefined): string {
  if (priority === "urgent") return "badge priority-badge is-urgent";
  if (priority === "soon") return "badge priority-badge is-soon";
  return "badge priority-badge is-normal";
}

/**
 * Return the task status badge classes from the existing visual language.
 */
export function statusBadgeClass(status: string | null | undefined): string {
  if (status === "in_progress") return "badge status-badge is-progress";
  if (status === "done" || status === "cancelled") return "badge status-badge is-done";
  return "badge status-badge is-open";
}

/**
 * Return the priority score risk badge classes from the existing UI.
 */
export function riskBadgeClass(riskLevel: string): string {
  if (riskLevel === "critical") return "badge badge-error text-white";
  if (riskLevel === "high") return "badge badge-warning text-slate-900";
  if (riskLevel === "medium") return "badge badge-info text-white";
  return "badge badge-success text-white";
}

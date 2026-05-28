import { formatGermanDateTime, todayIsoDate } from "../utils/date";
import { type DashboardPayload, type DashboardRuntimeData } from "./dashboardApi";

export type DashboardTaskGroupKey = "urgent" | "today" | "progress";

export type DashboardTaskGroups = Record<DashboardTaskGroupKey, readonly DashboardPayload[]>;

const GROUP_EMPTY_TEXT: Record<DashboardTaskGroupKey, string> = {
  progress: "Keine Aufgaben in Arbeit. Starte offene Aufgaben, sobald Verantwortung und Material klar sind.",
  today: "Keine Aufgaben für heute. Neue Arbeit kannst du direkt aus dem Cockpit anlegen.",
  urgent: "Keine kritischen Aufgaben. Beobachte neue Störungen und überfällige Arbeit."
};

const TASK_STATUS_LABELS: Record<string, string> = {
  cancelled: "Abgebrochen",
  done: "Erledigt",
  in_progress: "In Arbeit",
  open: "Offen"
};

const TASK_PRIORITY_LABELS: Record<string, string> = {
  low: "Niedrig",
  normal: "Normal",
  soon: "Bald",
  urgent: "Dringend"
};

/**
 * Return a string field from a flexible task payload.
 */
export function taskText(task: DashboardPayload | null | undefined, key: string, fallback = ""): string {
  const value = task?.[key];
  return typeof value === "string" && value.trim() ? value : fallback;
}

/**
 * Return a numeric ID from a flexible task payload.
 */
export function taskId(task: DashboardPayload): number {
  const value = task.id;
  const parsed = typeof value === "number" ? value : Number(value || 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

/**
 * Return a nested department name from a task payload.
 */
export function taskDepartmentName(task: DashboardPayload | null | undefined): string {
  const department = task?.department;
  if (typeof department === "object" && department !== null && !Array.isArray(department)) {
    const name = (department as Record<string, unknown>).name;
    return typeof name === "string" ? name : "-";
  }

  return taskText(task, "department", "-");
}

/**
 * Return a nested user label from a task payload.
 */
export function taskUserLabel(value: unknown): string {
  if (typeof value === "object" && value !== null && !Array.isArray(value)) {
    const user = value as Record<string, unknown>;
    return taskText(user, "username") || taskText(user, "email") || `User #${String(user.id || "-")}`;
  }

  return "-";
}

/**
 * Return a localized task status label.
 */
export function taskStatusLabel(status: unknown): string {
  const key = String(status || "open");
  return TASK_STATUS_LABELS[key] || key;
}

/**
 * Return a localized task priority label.
 */
export function taskPriorityLabel(priority: unknown): string {
  const key = String(priority || "normal");
  return TASK_PRIORITY_LABELS[key] || key;
}

/**
 * Return the dashboard badge class for a task status.
 */
export function taskStatusBadgeClass(status: unknown): string {
  const key = String(status || "open");
  if (key === "done") return "badge badge-status is-done";
  if (key === "in_progress") return "badge badge-status is-progress";
  if (key === "cancelled") return "badge badge-status is-neutral";
  return "badge badge-status is-open";
}

/**
 * Return the dashboard badge class for a task priority.
 */
export function taskPriorityBadgeClass(priority: unknown): string {
  const key = String(priority || "normal");
  if (key === "urgent") return "badge badge-priority is-urgent";
  if (key === "soon") return "badge badge-priority is-soon";
  if (key === "low") return "badge badge-priority is-low";
  return "badge badge-priority is-normal";
}

/**
 * Return true when a dashboard task is not closed.
 */
export function taskIsActive(task: DashboardPayload): boolean {
  const status = taskText(task, "status");
  return status !== "done" && status !== "cancelled";
}

/**
 * Return true when a dashboard task is overdue.
 */
export function taskIsOverdue(task: DashboardPayload): boolean {
  const dueDate = taskText(task, "due_date");
  return Boolean(dueDate && dueDate < todayIsoDate() && taskIsActive(task));
}

/**
 * Return a compact relative due-date label.
 */
export function taskRelativeDateLabel(task: DashboardPayload): string {
  const dueDate = taskText(task, "due_date");
  if (!dueDate) return "";
  if (dueDate === todayIsoDate()) return "heute fällig";
  if (taskIsOverdue(task)) return "überfällig";
  return dueDate;
}

/**
 * Group active dashboard tasks for the cockpit board.
 */
export function dashboardTaskGroups(tasks: readonly DashboardPayload[]): DashboardTaskGroups {
  const groups: Record<DashboardTaskGroupKey, DashboardPayload[]> = {
    progress: [],
    today: [],
    urgent: []
  };

  tasks.filter(taskIsActive).forEach((task) => {
    if (taskText(task, "status") === "in_progress") {
      groups.progress.push(task);
    } else if (taskText(task, "priority") === "urgent" || taskIsOverdue(task)) {
      groups.urgent.push(task);
    } else if (taskText(task, "due_date") === todayIsoDate()) {
      groups.today.push(task);
    }
  });

  return groups;
}

/**
 * Return tasks that belong in the critical-today panel.
 */
export function dashboardCriticalTasks(data: DashboardRuntimeData): readonly DashboardPayload[] {
  return data.tasks
    .filter((task) => taskIsActive(task) && (taskText(task, "priority") === "urgent" || taskIsOverdue(task)))
    .slice(0, 5);
}

/**
 * Return a user-facing empty text for one cockpit group.
 */
export function dashboardTaskGroupEmptyText(groupKey: DashboardTaskGroupKey): string {
  return GROUP_EMPTY_TEXT[groupKey];
}

/**
 * Return a detail field value for the dashboard task modal.
 */
export function dashboardTaskDetailValue(task: DashboardPayload, key: string): string {
  if (key === "department") return taskDepartmentName(task);
  if (key === "creator") return taskUserLabel(task.creator);
  if (key === "current_worker") return taskUserLabel(task.current_worker);
  if (key === "completed_by_user") return taskUserLabel(task.completed_by_user);
  if (key.endsWith("_at") || key === "created_at") return formatGermanDateTime(task[key]);
  if (key === "priority") return taskPriorityLabel(task.priority);
  if (key === "status") return taskStatusLabel(task.status);
  return taskText(task, key, "-");
}

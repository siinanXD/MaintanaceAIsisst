import { formatGermanDate, formatGermanDateTime, todayIsoDate } from "../utils/date";
import type { Task, TaskDueState } from "./taskTypes";

/**
 * Return today's local ISO date.
 */
export function taskTodayIso(): string {
  return todayIsoDate();
}

/**
 * Return the visible due-state bucket for one task.
 */
export function taskDueState(task: Task): TaskDueState {
  if (task.status === "done" || task.status === "cancelled") return "closed";
  if (!task.due_date) return "planned";
  const today = taskTodayIso();
  if (task.due_date < today) return "overdue";
  if (task.due_date === today) return "today";
  return "planned";
}

/**
 * Format an ISO date value like the legacy task cards.
 */
export function formatDate(value: string | null | undefined): string {
  if (!value) return "-";
  return formatGermanDate(`${value}T00:00:00`, {
    weekday: "short",
    day: "2-digit",
    month: "2-digit",
    dateOnly: true,
    fallback: "-"
  });
}

/**
 * Format a timestamp value like the legacy task timeline.
 */
export function formatDateTimeValue(value: string | null | undefined): string {
  if (!value) return "-";
  return formatGermanDateTime(value, {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    fallback: "-"
  });
}

/**
 * Return the human-readable due label for one task.
 */
export function taskDueLabel(task: Task): string {
  const state = taskDueState(task);
  if (state === "overdue") return `Überfällig seit ${formatDate(task.due_date)}`;
  if (state === "today") return "Heute fällig";
  if (state === "closed" && task.completed_at) return `Erledigt ${formatDateTimeValue(task.completed_at)}`;
  return task.due_date ? `Fällig ${formatDate(task.due_date)}` : "Keine Fälligkeit";
}

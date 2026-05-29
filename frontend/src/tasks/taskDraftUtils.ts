import { safeErrorMessage } from "../utils/errors";
import type { Task, TaskDraft, TaskFilters, TaskPriority, TaskStatus, TaskSuggestion } from "./taskTypes";

export const EMPTY_TASK_DRAFT: TaskDraft = {
  title: "",
  department: "",
  priority: "normal",
  status: "open",
  due_date: "",
  description: ""
};

export const EMPTY_TASK_FILTERS: TaskFilters = {
  search: "",
  status: "",
  priority: "",
  department: "",
  due: ""
};

/**
 * Return a task draft prefilled with default values.
 */
export function createEmptyTaskDraft(): TaskDraft {
  return { ...EMPTY_TASK_DRAFT };
}

/**
 * Convert unknown API errors into a safe UI message.
 */
export function taskErrorMessage(error: unknown): string {
  return safeErrorMessage(error, "Die Anfrage konnte nicht verarbeitet werden.");
}

/**
 * Convert one task into a form draft for edit mode.
 */
export function draftFromTask(task: Task): TaskDraft {
  return {
    title: task.title || "",
    department: task.department?.name || "",
    priority: task.priority || "normal",
    status: task.status || "open",
    due_date: task.due_date || "",
    description: task.description || ""
  };
}

/**
 * Normalize a raw suggestion payload into editable form data.
 */
export function normalizeSuggestion(value: Record<string, unknown>): TaskSuggestion {
  return {
    title: typeof value.title === "string" ? value.title : "",
    department: typeof value.department === "string" ? value.department : "",
    priority: normalizePriority(value.priority),
    status: normalizeStatus(value.status),
    due_date: "",
    description: typeof value.description === "string" ? value.description : "",
    possible_cause: typeof value.possible_cause === "string" ? value.possible_cause : "",
    recommended_action: typeof value.recommended_action === "string" ? value.recommended_action : ""
  };
}

/**
 * Convert a suggestion into the main task form draft.
 */
export function draftFromSuggestion(suggestion: TaskSuggestion): TaskDraft {
  return {
    title: suggestion.title,
    department: suggestion.department,
    priority: suggestion.priority,
    status: suggestion.status,
    due_date: "",
    description: [
      suggestion.description,
      suggestion.possible_cause ? `Mögliche Ursache: ${suggestion.possible_cause}` : "",
      suggestion.recommended_action ? `Nächste Aktion: ${suggestion.recommended_action}` : ""
    ].filter(Boolean).join("\n\n")
  };
}

/**
 * Consume the AI action preview session payload for tasks.
 */
export function consumeTaskActionPreview(): TaskDraft | null {
  try {
    const raw = window.sessionStorage.getItem("maintenance_ai_action_preview");
    if (!raw) return null;
    const preview = JSON.parse(raw) as { readonly target?: string; readonly payload?: Record<string, unknown> };
    if (!preview || preview.target !== "tasks" || !preview.payload?.title) return null;
    window.sessionStorage.removeItem("maintenance_ai_action_preview");
    return draftFromSuggestion(normalizeSuggestion(preview.payload));
  } catch {
    window.sessionStorage.removeItem("maintenance_ai_action_preview");
    return null;
  }
}

/**
 * Read the initial task search query from the current URL.
 */
export function initialTaskSearchQuery(): string {
  const query = new URLSearchParams(window.location.search);
  return query.get("search") || query.get("q") || "";
}

/**
 * Normalize an unknown priority value.
 */
function normalizePriority(value: unknown): TaskPriority {
  return value === "urgent" || value === "soon" || value === "normal" ? value : "normal";
}

/**
 * Normalize an unknown status value.
 */
function normalizeStatus(value: unknown): TaskStatus {
  return value === "open" || value === "in_progress" || value === "done" || value === "cancelled"
    ? value
    : "open";
}

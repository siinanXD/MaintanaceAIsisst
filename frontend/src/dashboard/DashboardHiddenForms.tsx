import { type ReactNode } from "react";

const DASHBOARD_HIDDEN_COUNTERS = [
  { hookName: "data-dashboard-task-count", value: "0" },
  { hookName: "data-dashboard-progress-count", value: "0" },
  { hookName: "data-dashboard-recurring-count", value: "0" },
  { hookName: "data-dashboard-safety-count", value: "0" },
  { hookName: "data-dashboard-briefing-count", value: "0" },
] as const;

/**
 * Convert a dashboard data attribute name into a JSX-compatible prop object.
 */
function createDataHook(hookName: string): Record<string, string> {
  return { [hookName]: "" };
}

/**
 * Render hidden dashboard forms and counters required by the legacy runtime.
 */
export function DashboardHiddenForms(): ReactNode {
  return (
    <>
      <form data-cockpit-suggest-form="" hidden>
        <textarea name="text" />
      </form>
      <form data-cockpit-draft="" hidden>
        <input name="title" />
        <input name="department" />
        <select name="priority">
          <option value="urgent">urgent</option>
          <option value="soon">soon</option>
          <option value="normal">normal</option>
        </select>
        <select name="status">
          <option value="open">open</option>
          <option value="in_progress">in_progress</option>
        </select>
        <textarea name="description" />
        <button type="button" data-cockpit-draft-cancel="">
          Verwerfen
        </button>
      </form>
      <span data-cockpit-message="" hidden />
      {DASHBOARD_HIDDEN_COUNTERS.map((counter) => (
        <span key={counter.hookName} {...createDataHook(counter.hookName)} hidden>
          {counter.value}
        </span>
      ))}
    </>
  );
}

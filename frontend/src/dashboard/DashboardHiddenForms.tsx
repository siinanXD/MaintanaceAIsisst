import { type FormEvent, type ReactNode } from "react";

import { type DashboardTaskMutation } from "./dashboardApi";

type DashboardHiddenFormsProps = {
  readonly cockpitMessage: string;
  readonly draftTask: DashboardTaskMutation | null;
  readonly isDraftBusy: boolean;
  readonly onDraftCancel: () => void;
  readonly onDraftChange: (payload: DashboardTaskMutation | null) => void;
  readonly onDraftSubmit: (payload: DashboardTaskMutation) => void;
  readonly onSuggestSubmit: (text: string) => void;
  readonly suggestText: string;
  readonly onSuggestTextChange: (text: string) => void;
};

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
 * Render hidden dashboard forms and counters required by legacy-compatible hooks.
 */
export function DashboardHiddenForms({
  cockpitMessage,
  draftTask,
  isDraftBusy,
  onDraftCancel,
  onDraftChange,
  onDraftSubmit,
  onSuggestSubmit,
  suggestText,
  onSuggestTextChange
}: DashboardHiddenFormsProps): ReactNode {
  /**
   * Submit the hidden suggestion form through React-owned task APIs.
   */
  function handleSuggestSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    onSuggestSubmit(suggestText);
  }

  /**
   * Submit the hidden draft form through React-owned task APIs.
   */
  function handleDraftSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    onDraftSubmit(draftTask ?? {});
  }

  /**
   * Merge one hidden draft-field update into the current draft.
   */
  function updateDraft(partialPayload: DashboardTaskMutation): void {
    onDraftChange({ ...(draftTask ?? {}), ...partialPayload });
  }

  return (
    <>
      <form data-cockpit-suggest-form="" hidden onSubmit={handleSuggestSubmit}>
        <textarea
          name="text"
          value={suggestText}
          onChange={(event) => onSuggestTextChange(event.currentTarget.value)}
        />
      </form>
      <form data-cockpit-draft="" hidden={!draftTask} onSubmit={handleDraftSubmit}>
        <input
          name="title"
          value={draftTask?.title ?? ""}
          onChange={(event) => updateDraft({ title: event.currentTarget.value })}
        />
        <input
          name="department"
          value={draftTask?.department ?? ""}
          onChange={(event) => updateDraft({ department: event.currentTarget.value })}
        />
        <select
          name="priority"
          value={draftTask?.priority ?? "normal"}
          onChange={(event) => updateDraft({ priority: event.currentTarget.value })}
        >
          <option value="urgent">urgent</option>
          <option value="soon">soon</option>
          <option value="normal">normal</option>
        </select>
        <select
          name="status"
          value={draftTask?.status ?? "open"}
          onChange={(event) => updateDraft({ status: event.currentTarget.value })}
        >
          <option value="open">open</option>
          <option value="in_progress">in_progress</option>
        </select>
        <textarea
          name="description"
          value={draftTask?.description ?? ""}
          onChange={(event) => updateDraft({ description: event.currentTarget.value })}
        />
        <button disabled={isDraftBusy} type="button" data-cockpit-draft-cancel="" onClick={onDraftCancel}>
          Verwerfen
        </button>
      </form>
      <span data-cockpit-message="" hidden>
        {cockpitMessage}
      </span>
      {DASHBOARD_HIDDEN_COUNTERS.map((counter) => (
        <span key={counter.hookName} {...createDataHook(counter.hookName)} hidden>
          {counter.value}
        </span>
      ))}
    </>
  );
}

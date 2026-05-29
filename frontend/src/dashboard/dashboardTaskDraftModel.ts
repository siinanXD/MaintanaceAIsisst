import type { DashboardPayload, DashboardTaskMutation } from "./dashboardApi";

/**
 * Convert a task suggestion API response into the hidden cockpit draft shape.
 */
export function taskDraftFromSuggestion(suggestion: DashboardPayload): DashboardTaskMutation {
  const descriptionParts = [
    typeof suggestion.description === "string" ? suggestion.description : "",
    typeof suggestion.possible_cause === "string" ? `Mögliche Ursache: ${suggestion.possible_cause}` : "",
    typeof suggestion.recommended_action === "string" ? `Nächste Aktion: ${suggestion.recommended_action}` : ""
  ].filter(Boolean);

  return {
    department: typeof suggestion.department === "string" ? suggestion.department : "",
    description: descriptionParts.join("\n\n"),
    priority: typeof suggestion.priority === "string" ? suggestion.priority : "normal",
    status: typeof suggestion.status === "string" ? suggestion.status : "open",
    title: typeof suggestion.title === "string" ? suggestion.title : ""
  };
}

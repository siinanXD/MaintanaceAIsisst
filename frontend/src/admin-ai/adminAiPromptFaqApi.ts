import { adminAiData, type AdminAiPayload } from "./adminAiApiCore";

/**
 * Load prompt templates and versions for the Prompt & FAQ view.
 */
export async function loadPromptTemplates(signal?: AbortSignal): Promise<AdminAiPayload> {
  return adminAiData("/api/v1/admin/ai/prompts", { signal });
}

/**
 * Create a new draft version for one prompt template.
 */
export async function createPromptVersion(
  templateId: number,
  payload: Record<string, unknown>
): Promise<AdminAiPayload> {
  return adminAiData(`/api/v1/admin/ai/prompts/${templateId}/versions`, {
    body: payload,
    method: "POST"
  });
}

/**
 * Load FAQ entries for the Prompt & FAQ view.
 */
export async function loadFaqEntries(signal?: AbortSignal): Promise<AdminAiPayload> {
  return adminAiData("/api/v1/admin/ai/faq?limit=50", { signal });
}

/**
 * Create a manual FAQ draft.
 */
export async function createFaqEntry(payload: Record<string, unknown>): Promise<AdminAiPayload> {
  return adminAiData("/api/v1/admin/ai/faq", {
    body: payload,
    method: "POST"
  });
}

/**
 * Approve one FAQ draft and make it indexable.
 */
export async function approveFaqEntry(entryId: number): Promise<AdminAiPayload> {
  return adminAiData(`/api/v1/admin/ai/faq/${entryId}/approve`, { method: "POST" });
}

/**
 * Load FAQ suggestions from recent chat and knowledge-gap signals.
 */
export async function loadFaqSuggestions(signal?: AbortSignal): Promise<AdminAiPayload> {
  return adminAiData("/api/v1/admin/ai/faq/suggestions?days=30&limit=10", { signal });
}

/**
 * Load reusable response snippets for the Prompt & FAQ view.
 */
export async function loadResponseSnippets(signal?: AbortSignal): Promise<AdminAiPayload> {
  return adminAiData("/api/v1/admin/ai/response-snippets", { signal });
}

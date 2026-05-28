import { apiRequest } from "../api/client";
import { unwrapData } from "../api/payload";

export type AdminAiPayload = Record<string, unknown>;

/**
 * Load the active AI provider and model status.
 */
export async function loadAiStatus(signal?: AbortSignal): Promise<AdminAiPayload> {
  return unwrapData<AdminAiPayload>(await apiRequest("/api/v1/ai/status", { signal }));
}

/**
 * Load the Admin-AI monitoring summary used by the overview cockpit.
 */
export async function loadAdminAiSummary(signal?: AbortSignal): Promise<AdminAiPayload> {
  return unwrapData<AdminAiPayload>(
    await apiRequest("/api/v1/admin/ai/summary?days=7", { signal })
  );
}

/**
 * Load prompt templates and versions for the Prompt & FAQ view.
 */
export async function loadPromptTemplates(signal?: AbortSignal): Promise<AdminAiPayload> {
  return unwrapData<AdminAiPayload>(await apiRequest("/api/v1/admin/ai/prompts", { signal }));
}

/**
 * Create a new draft version for one prompt template.
 */
export async function createPromptVersion(
  templateId: number,
  payload: Record<string, unknown>
): Promise<AdminAiPayload> {
  return unwrapData<AdminAiPayload>(
    await apiRequest(`/api/v1/admin/ai/prompts/${templateId}/versions`, {
      body: payload,
      method: "POST"
    })
  );
}

/**
 * Load FAQ entries for the Prompt & FAQ view.
 */
export async function loadFaqEntries(signal?: AbortSignal): Promise<AdminAiPayload> {
  return unwrapData<AdminAiPayload>(
    await apiRequest("/api/v1/admin/ai/faq?limit=50", { signal })
  );
}

/**
 * Create a manual FAQ draft.
 */
export async function createFaqEntry(payload: Record<string, unknown>): Promise<AdminAiPayload> {
  return unwrapData<AdminAiPayload>(
    await apiRequest("/api/v1/admin/ai/faq", {
      body: payload,
      method: "POST"
    })
  );
}

/**
 * Approve one FAQ draft and make it indexable.
 */
export async function approveFaqEntry(entryId: number): Promise<AdminAiPayload> {
  return unwrapData<AdminAiPayload>(
    await apiRequest(`/api/v1/admin/ai/faq/${entryId}/approve`, { method: "POST" })
  );
}

/**
 * Load FAQ suggestions from recent chat and knowledge-gap signals.
 */
export async function loadFaqSuggestions(signal?: AbortSignal): Promise<AdminAiPayload> {
  return unwrapData<AdminAiPayload>(
    await apiRequest("/api/v1/admin/ai/faq/suggestions?days=30&limit=10", { signal })
  );
}

/**
 * Load reusable response snippets for the Prompt & FAQ view.
 */
export async function loadResponseSnippets(signal?: AbortSignal): Promise<AdminAiPayload> {
  return unwrapData<AdminAiPayload>(
    await apiRequest("/api/v1/admin/ai/response-snippets", { signal })
  );
}

/**
 * Load per-user AI costs for the effectiveness view.
 */
export async function loadAdminAiUserCosts(signal?: AbortSignal): Promise<AdminAiPayload> {
  return unwrapData<AdminAiPayload>(
    await apiRequest("/api/v1/admin/ai/users?days=30&limit=50", { signal })
  );
}

/**
 * Load retrieval SLO metrics used by quality and risk panels.
 */
export async function loadRetrievalTelemetry(signal?: AbortSignal): Promise<AdminAiPayload> {
  return unwrapData<AdminAiPayload>(
    await apiRequest("/api/v1/admin/ai/retrieval-telemetry?days=30&limit=5", { signal })
  );
}

/**
 * Load operations health metrics for the Admin-AI queue card.
 */
export async function loadOperationsHealth(signal?: AbortSignal): Promise<AdminAiPayload> {
  return unwrapData<AdminAiPayload>(await apiRequest("/api/v1/health/operations", { signal }));
}

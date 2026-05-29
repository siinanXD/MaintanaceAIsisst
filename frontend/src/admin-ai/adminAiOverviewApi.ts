import { adminAiData, type AdminAiPayload } from "./adminAiApiCore";

/**
 * Load the active AI provider and model status.
 */
export async function loadAiStatus(signal?: AbortSignal): Promise<AdminAiPayload> {
  return adminAiData("/api/v1/ai/status", { signal });
}

/**
 * Load the Admin-AI monitoring summary used by the overview cockpit.
 */
export async function loadAdminAiSummary(signal?: AbortSignal): Promise<AdminAiPayload> {
  return adminAiData("/api/v1/admin/ai/summary?days=7", { signal });
}

/**
 * Load prompt-safe AI audit events for the Admin-AI overview table.
 */
export async function loadAdminAiEvents(errorFilter: string, signal?: AbortSignal): Promise<AdminAiPayload> {
  return adminAiData(`/api/v1/admin/ai/events?limit=20&error=${encodeURIComponent(errorFilter)}`, { signal });
}

/**
 * Load prompt-safe AI chat references for the Admin-AI overview list.
 */
export async function loadAdminAiChats(query: string, signal?: AbortSignal): Promise<AdminAiPayload> {
  return adminAiData(`/api/v1/admin/ai/chats?limit=20&q=${encodeURIComponent(query)}`, { signal });
}

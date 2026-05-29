import { adminAiData, type AdminAiPayload } from "./adminAiApiCore";

/**
 * Load per-user AI costs for the effectiveness view.
 */
export async function loadAdminAiUserCosts(signal?: AbortSignal): Promise<AdminAiPayload> {
  return adminAiData("/api/v1/admin/ai/users?days=30&limit=50", { signal });
}

/**
 * Load retrieval SLO metrics used by quality and risk panels.
 */
export async function loadRetrievalTelemetry(signal?: AbortSignal): Promise<AdminAiPayload> {
  return adminAiData("/api/v1/admin/ai/retrieval-telemetry?days=30&limit=5", { signal });
}

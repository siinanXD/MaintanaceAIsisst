import { adminAiData, type AdminAiPayload } from "./adminAiApiCore";

/**
 * Load prompt-safe retrieval debug records for the Technical view.
 */
export async function loadRetrievalDebug(queryString: string, signal?: AbortSignal): Promise<AdminAiPayload> {
  return adminAiData(`/api/v1/admin/ai/retrieval-debug?${queryString}`, { signal });
}

/**
 * Load AI observability metrics and debug metadata for the Technical view.
 */
export async function loadAiObservability(queryString: string, signal?: AbortSignal): Promise<AdminAiPayload> {
  return adminAiData(`/api/v1/admin/ai/observability?${queryString}`, { signal });
}

/**
 * Load open AI knowledge gaps for the Technical view.
 */
export async function loadAdminAiKnowledgeGaps(signal?: AbortSignal): Promise<AdminAiPayload> {
  return adminAiData("/api/v1/admin/ai/knowledge-gaps?status=open&limit=5", { signal });
}

/**
 * Run the bounded golden retrieval evaluation.
 */
export async function runRetrievalEvaluation(): Promise<AdminAiPayload> {
  return adminAiData("/api/v1/admin/ai/retrieval-evaluations/run", { method: "POST" });
}

/**
 * Load operations health metrics for the Admin-AI queue card.
 */
export async function loadOperationsHealth(signal?: AbortSignal): Promise<AdminAiPayload> {
  return adminAiData("/api/v1/health/operations", { signal });
}

import { adminAiData, type AdminAiPayload } from "./adminAiApiCore";

/**
 * Load RAG index health and lifecycle diagnostics for the RAG Board view.
 */
export async function loadKnowledgeStatus(signal?: AbortSignal): Promise<AdminAiPayload> {
  return adminAiData("/api/v1/admin/ai/knowledge/status", { signal });
}

/**
 * Load knowledge documents for the RAG Board knowledge table.
 */
export async function loadKnowledgeDocuments(queryString: string, signal?: AbortSignal): Promise<AdminAiPayload> {
  return adminAiData(`/api/v1/admin/ai/knowledge?${queryString}`, { signal });
}

/**
 * Load manual training entries for the RAG Board training editor.
 */
export async function loadTrainingEntries(queryString: string, signal?: AbortSignal): Promise<AdminAiPayload> {
  return adminAiData(`/api/v1/admin/ai/training?${queryString}`, { signal });
}

/**
 * Save a manual training entry.
 */
export async function saveTrainingEntry(
  payload: Record<string, unknown>,
  entryId?: number
): Promise<AdminAiPayload> {
  return adminAiData(entryId ? `/api/v1/admin/ai/training/${entryId}` : "/api/v1/admin/ai/training", {
    body: payload,
    method: entryId ? "PUT" : "POST"
  });
}

/**
 * Delete a manual training entry.
 */
export async function deleteTrainingEntry(entryId: number): Promise<AdminAiPayload> {
  return adminAiData(`/api/v1/admin/ai/training/${entryId}`, { method: "DELETE" });
}

/**
 * Load prompt-safe knowledge network metadata.
 */
export async function loadKnowledgeNetwork(queryString: string, signal?: AbortSignal): Promise<AdminAiPayload> {
  return adminAiData(`/api/v1/admin/ai/knowledge-network?${queryString}`, { signal });
}

/**
 * Load RAG background jobs.
 */
export async function loadAdminJobs(signal?: AbortSignal): Promise<AdminAiPayload> {
  return adminAiData("/api/v1/admin/jobs?job_type=rag_reindex&limit=10", { signal });
}

/**
 * Queue a RAG reindex job.
 */
export async function queueKnowledgeReindexJob(payload: Record<string, unknown>): Promise<AdminAiPayload> {
  return adminAiData("/api/v1/admin/ai/knowledge/reindex/jobs", {
    body: payload,
    method: "POST"
  });
}

/**
 * Run a synchronous RAG reindex.
 */
export async function runKnowledgeReindex(queryString = ""): Promise<AdminAiPayload> {
  return adminAiData(`/api/v1/admin/ai/knowledge/reindex${queryString}`, { method: "POST" });
}

/**
 * Reindex one knowledge document.
 */
export async function reindexKnowledgeDocument(documentId: number): Promise<AdminAiPayload> {
  return adminAiData(`/api/v1/admin/ai/knowledge/${documentId}/reindex`, { method: "POST" });
}

/**
 * Update one knowledge document quality status.
 */
export async function updateKnowledgeQualityStatus(
  documentId: number,
  qualityStatus: string
): Promise<AdminAiPayload> {
  return adminAiData(`/api/v1/admin/ai/knowledge/${documentId}/quality-status`, {
    body: { quality_status: qualityStatus },
    method: "PUT"
  });
}

/**
 * Delete one knowledge document.
 */
export async function deleteKnowledgeDocument(documentId: number): Promise<AdminAiPayload> {
  return adminAiData(`/api/v1/admin/ai/knowledge/${documentId}`, { method: "DELETE" });
}

/**
 * Upload a local knowledge document.
 */
export async function uploadKnowledgeDocument(formData: FormData): Promise<AdminAiPayload> {
  return adminAiData("/api/v1/admin/ai/knowledge/upload", {
    body: formData,
    method: "POST"
  });
}

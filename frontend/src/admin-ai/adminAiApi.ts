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
 * Run a prompt dry-run preview for the Source Check view.
 */
export async function testPromptDryRun(
  payload: Record<string, unknown>
): Promise<AdminAiPayload> {
  return unwrapData<AdminAiPayload>(
    await apiRequest("/api/v1/admin/ai/prompts/test", {
      body: payload,
      method: "POST"
    })
  );
}

/**
 * Run a live AI chat call for the Source Check view.
 */
export async function runAiChat(payload: Record<string, unknown>): Promise<AdminAiPayload> {
  return unwrapData<AdminAiPayload>(
    await apiRequest("/api/v1/ai/chat", {
      body: payload,
      method: "POST"
    })
  );
}

/**
 * Store quality feedback for a Source Check result.
 */
export async function submitAiFeedback(
  payload: Record<string, unknown>
): Promise<AdminAiPayload> {
  return unwrapData<AdminAiPayload>(
    await apiRequest("/api/v1/ai/feedback", {
      body: payload,
      method: "POST"
    })
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
 * Load prompt-safe retrieval debug records for the Technical view.
 */
export async function loadRetrievalDebug(
  queryString: string,
  signal?: AbortSignal
): Promise<AdminAiPayload> {
  return unwrapData<AdminAiPayload>(
    await apiRequest(`/api/v1/admin/ai/retrieval-debug?${queryString}`, { signal })
  );
}

/**
 * Load AI observability metrics and debug metadata for the Technical view.
 */
export async function loadAiObservability(
  queryString: string,
  signal?: AbortSignal
): Promise<AdminAiPayload> {
  return unwrapData<AdminAiPayload>(
    await apiRequest(`/api/v1/admin/ai/observability?${queryString}`, { signal })
  );
}

/**
 * Run the bounded golden retrieval evaluation.
 */
export async function runRetrievalEvaluation(): Promise<AdminAiPayload> {
  return unwrapData<AdminAiPayload>(
    await apiRequest("/api/v1/admin/ai/retrieval-evaluations/run", { method: "POST" })
  );
}

/**
 * Load operations health metrics for the Admin-AI queue card.
 */
export async function loadOperationsHealth(signal?: AbortSignal): Promise<AdminAiPayload> {
  return unwrapData<AdminAiPayload>(await apiRequest("/api/v1/health/operations", { signal }));
}

/**
 * Load RAG index health and lifecycle diagnostics for the RAG Board view.
 */
export async function loadKnowledgeStatus(signal?: AbortSignal): Promise<AdminAiPayload> {
  return unwrapData<AdminAiPayload>(
    await apiRequest("/api/v1/admin/ai/knowledge/status", { signal })
  );
}

/**
 * Load knowledge documents for the RAG Board knowledge table.
 */
export async function loadKnowledgeDocuments(
  queryString: string,
  signal?: AbortSignal
): Promise<AdminAiPayload> {
  return unwrapData<AdminAiPayload>(
    await apiRequest(`/api/v1/admin/ai/knowledge?${queryString}`, { signal })
  );
}

/**
 * Load manual training entries for the RAG Board training editor.
 */
export async function loadTrainingEntries(
  queryString: string,
  signal?: AbortSignal
): Promise<AdminAiPayload> {
  return unwrapData<AdminAiPayload>(
    await apiRequest(`/api/v1/admin/ai/training?${queryString}`, { signal })
  );
}

/**
 * Save a manual training entry.
 */
export async function saveTrainingEntry(
  payload: Record<string, unknown>,
  entryId?: number
): Promise<AdminAiPayload> {
  return unwrapData<AdminAiPayload>(
    await apiRequest(entryId ? `/api/v1/admin/ai/training/${entryId}` : "/api/v1/admin/ai/training", {
      body: payload,
      method: entryId ? "PUT" : "POST"
    })
  );
}

/**
 * Delete a manual training entry.
 */
export async function deleteTrainingEntry(entryId: number): Promise<AdminAiPayload> {
  return unwrapData<AdminAiPayload>(
    await apiRequest(`/api/v1/admin/ai/training/${entryId}`, { method: "DELETE" })
  );
}

/**
 * Load prompt-safe knowledge network metadata.
 */
export async function loadKnowledgeNetwork(
  queryString: string,
  signal?: AbortSignal
): Promise<AdminAiPayload> {
  return unwrapData<AdminAiPayload>(
    await apiRequest(`/api/v1/admin/ai/knowledge-network?${queryString}`, { signal })
  );
}

/**
 * Load RAG background jobs.
 */
export async function loadAdminJobs(signal?: AbortSignal): Promise<AdminAiPayload> {
  return unwrapData<AdminAiPayload>(
    await apiRequest("/api/v1/admin/jobs?job_type=rag_reindex&limit=10", { signal })
  );
}

/**
 * Queue a RAG reindex job.
 */
export async function queueKnowledgeReindexJob(
  payload: Record<string, unknown>
): Promise<AdminAiPayload> {
  return unwrapData<AdminAiPayload>(
    await apiRequest("/api/v1/admin/ai/knowledge/reindex/jobs", {
      body: payload,
      method: "POST"
    })
  );
}

/**
 * Run a synchronous RAG reindex.
 */
export async function runKnowledgeReindex(queryString = ""): Promise<AdminAiPayload> {
  return unwrapData<AdminAiPayload>(
    await apiRequest(`/api/v1/admin/ai/knowledge/reindex${queryString}`, { method: "POST" })
  );
}

/**
 * Reindex one knowledge document.
 */
export async function reindexKnowledgeDocument(documentId: number): Promise<AdminAiPayload> {
  return unwrapData<AdminAiPayload>(
    await apiRequest(`/api/v1/admin/ai/knowledge/${documentId}/reindex`, { method: "POST" })
  );
}

/**
 * Update one knowledge document quality status.
 */
export async function updateKnowledgeQualityStatus(
  documentId: number,
  qualityStatus: string
): Promise<AdminAiPayload> {
  return unwrapData<AdminAiPayload>(
    await apiRequest(`/api/v1/admin/ai/knowledge/${documentId}/quality-status`, {
      body: { quality_status: qualityStatus },
      method: "PUT"
    })
  );
}

/**
 * Delete one knowledge document.
 */
export async function deleteKnowledgeDocument(documentId: number): Promise<AdminAiPayload> {
  return unwrapData<AdminAiPayload>(
    await apiRequest(`/api/v1/admin/ai/knowledge/${documentId}`, { method: "DELETE" })
  );
}

/**
 * Upload a local knowledge document.
 */
export async function uploadKnowledgeDocument(formData: FormData): Promise<AdminAiPayload> {
  return unwrapData<AdminAiPayload>(
    await apiRequest("/api/v1/admin/ai/knowledge/upload", {
      body: formData,
      method: "POST"
    })
  );
}

import { apiRequest } from "../api/client";
import { listData, unwrapData } from "../api/payload";
import type {
  Department,
  ErrorAssistantResult,
  ErrorDraft,
  ErrorEntry,
  SimilarErrorResult
} from "./errorTypes";

/**
 * Load errors visible to the current user.
 */
export async function loadErrors(): Promise<ErrorEntry[]> {
  const response = await apiRequest<unknown>("/api/v1/errors?limit=100");
  return listData<ErrorEntry>(response);
}

/**
 * Load departments for error create and edit forms.
 */
export async function loadDepartments(): Promise<Department[]> {
  const response = await apiRequest<unknown>("/api/v1/departments");
  return listData<Department>(response);
}

/**
 * Persist a new error entry through the existing API.
 */
export async function createErrorEntry(draft: ErrorDraft): Promise<ErrorEntry> {
  return apiRequest<ErrorEntry>("/api/v1/errors", {
    method: "POST",
    body: { ...draft, description: draft.symptoms || draft.title }
  });
}

/**
 * Update an existing error entry through the existing API.
 */
export async function updateErrorEntry(errorId: number, draft: ErrorDraft): Promise<ErrorEntry> {
  return apiRequest<ErrorEntry>(`/api/v1/errors/${errorId}`, {
    method: "PUT",
    body: { ...draft, description: draft.symptoms || draft.title }
  });
}

/**
 * Close an existing error entry.
 */
export async function closeErrorEntry(errorId: number): Promise<ErrorEntry> {
  return unwrapData<ErrorEntry>(
    await apiRequest<unknown>(`/api/v1/errors/${errorId}/close`, { method: "POST" })
  );
}

/**
 * Delete an existing error entry.
 */
export async function deleteErrorEntry(errorId: number): Promise<void> {
  await apiRequest<null>(`/api/v1/errors/${errorId}`, { method: "DELETE" });
}

/**
 * Request an AI-generated non-persisted error analysis.
 */
export async function analyzeErrorDescription(description: string): Promise<Partial<ErrorDraft>> {
  return unwrapData<Partial<ErrorDraft>>(
    await apiRequest<unknown>("/api/v1/errors/analyze", {
      method: "POST",
      body: { description }
    })
  );
}

/**
 * Find similar catalog errors for a text and optional machine.
 */
export async function loadSimilarErrors(text: string, machine = ""): Promise<SimilarErrorResult> {
  return unwrapData<SimilarErrorResult>(
    await apiRequest<unknown>("/api/v1/errors/similar", {
      method: "POST",
      body: { text, machine, limit: 5 }
    })
  );
}

/**
 * Enrich an error description with RAG source context.
 */
export async function loadErrorAssistantContext(query: string): Promise<ErrorAssistantResult> {
  return unwrapData<ErrorAssistantResult>(
    await apiRequest<unknown>("/api/v1/ai/error-assistant", {
      method: "POST",
      body: { query, limit: 5 }
    })
  );
}

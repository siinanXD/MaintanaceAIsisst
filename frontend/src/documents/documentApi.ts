import { apiRequest } from "../api/client";
import { listData, unwrapData } from "../api/payload";
import type {
  DocumentFilters,
  DocumentReview,
  DocumentSummary,
  DocumentVersion,
  GeneratedDocument,
  Machine,
  MachineManual
} from "./documentTypes";

/**
 * Load generated documents using the existing filter API.
 */
export async function loadGeneratedDocuments(filters: DocumentFilters): Promise<GeneratedDocument[]> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value) params.set(key, value);
  });
  params.set("limit", "100");
  return listData<GeneratedDocument>(await apiRequest<unknown>(`/api/v1/documents?${params.toString()}`));
}

/**
 * Load machine manuals visible to the current user.
 */
export async function loadMachineManuals(): Promise<MachineManual[]> {
  return listData<MachineManual>(await apiRequest<unknown>("/api/v1/documents/manuals?limit=100"));
}

/**
 * Load machines for manual assignment.
 */
export async function loadMachines(): Promise<Machine[]> {
  return listData<Machine>(await apiRequest<unknown>("/api/v1/machines?limit=200"));
}

/**
 * Review a generated document.
 */
export async function reviewGeneratedDocument(documentId: number): Promise<DocumentReview> {
  return unwrapData<DocumentReview>(
    await apiRequest<unknown>(`/api/v1/documents/${documentId}/review`, { method: "POST" })
  );
}

/**
 * Summarize a generated document.
 */
export async function summarizeGeneratedDocument(documentId: number): Promise<DocumentSummary> {
  return unwrapData<DocumentSummary>(
    await apiRequest<unknown>(`/api/v1/documents/${documentId}/summarize`, { method: "POST" })
  );
}

/**
 * Load generated document versions.
 */
export async function loadDocumentVersions(documentId: number): Promise<DocumentVersion[]> {
  return unwrapData<DocumentVersion[]>(
    await apiRequest<unknown>(`/api/v1/documents/${documentId}/versions`)
  );
}

/**
 * Change the approval state for a generated document.
 */
export async function changeDocumentStatus(documentId: number, action: "submit-review" | "approve" | "reject"): Promise<GeneratedDocument> {
  return unwrapData<GeneratedDocument>(
    await apiRequest<unknown>(`/api/v1/documents/${documentId}/${action}`, {
      method: "POST",
      body: { comment: "" }
    })
  );
}

/**
 * Check an uploaded document without persisting it.
 */
export async function checkUploadedDocument(formData: FormData): Promise<DocumentReview> {
  return unwrapData<DocumentReview>(
    await apiRequest<unknown>("/api/v1/documents/check", {
      method: "POST",
      body: formData
    })
  );
}

/**
 * Upload a machine manual.
 */
export async function uploadMachineManual(formData: FormData): Promise<MachineManual> {
  return unwrapData<MachineManual>(
    await apiRequest<unknown>("/api/v1/documents/manuals", {
      method: "POST",
      body: formData
    })
  );
}

/**
 * Analyze a machine manual.
 */
export async function analyzeMachineManual(manualId: number): Promise<DocumentSummary> {
  return unwrapData<DocumentSummary>(
    await apiRequest<unknown>(`/api/v1/documents/manuals/${manualId}/analyze`, { method: "POST" })
  );
}

/**
 * Summarize a machine manual.
 */
export async function summarizeMachineManual(manualId: number): Promise<DocumentSummary> {
  return unwrapData<DocumentSummary>(
    await apiRequest<unknown>(`/api/v1/documents/manuals/${manualId}/summarize`, { method: "POST" })
  );
}

/**
 * Delete a machine manual.
 */
export async function deleteMachineManual(manualId: number): Promise<void> {
  await apiRequest<null>(`/api/v1/documents/manuals/${manualId}`, { method: "DELETE" });
}

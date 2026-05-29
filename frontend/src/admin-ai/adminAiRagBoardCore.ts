import { listData } from "../api/payload";
import { safeErrorMessage } from "../utils/errors";
import { type AdminAiPayload } from "./adminAiApi";
import type { AdminAiRagBoardFilters, AdminAiRagBoardState } from "./AdminAiRagBoardTypes";

/**
 * Return an object from an unknown payload.
 */
export function objectPayload(value: unknown): AdminAiPayload {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as AdminAiPayload)
    : {};
}

/**
 * Return a string fallback for visible UI values.
 */
export function ragText(value: unknown, fallback = "-"): string {
  if (value === null || value === undefined || value === "") return fallback;
  return String(value);
}

/**
 * Return list items from an Admin-AI response.
 */
export function ragItems(payload: unknown): AdminAiPayload[] {
  return listData<AdminAiPayload>(payload);
}

/**
 * Resolve a safe RAG Board error state.
 */
export function failedRagBoardState(error: unknown): Pick<AdminAiRagBoardState, "errorMessage"> {
  return { errorMessage: safeErrorMessage(error, "RAG Board konnte nicht geladen werden.") };
}

/**
 * Build the query string for knowledge documents.
 */
export function knowledgeQueryString(filters: AdminAiRagBoardFilters): string {
  return new URLSearchParams({
    limit: "50",
    q: filters.knowledgeQuery,
    quality_status: filters.knowledgeQuality,
    source_type: filters.knowledgeSource,
    status: filters.knowledgeStatus
  }).toString();
}

/**
 * Build the query string for manual training entries.
 */
export function trainingQueryString(filters: AdminAiRagBoardFilters): string {
  return new URLSearchParams({
    active: filters.trainingActive,
    limit: "50",
    q: filters.trainingQuery
  }).toString();
}

/**
 * Build the query string for the knowledge network.
 */
export function networkQueryString(filters: AdminAiRagBoardFilters): string {
  return new URLSearchParams({
    focus: filters.networkFocus,
    focus_type: filters.networkFocusType,
    limit: "120",
    q: filters.networkQuery,
    quality_status: filters.networkQuality,
    source_type: filters.networkSource
  }).toString();
}

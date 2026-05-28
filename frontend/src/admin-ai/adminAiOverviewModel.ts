import { safeErrorMessage } from "../utils/errors";
import { type AdminAiPayload } from "./adminAiApi";

export type AdminAiOverviewLoadState = {
  readonly aiStatus: AdminAiPayload | null;
  readonly summary: AdminAiPayload | null;
  readonly operations: AdminAiPayload | null;
  readonly errorMessage: string;
  readonly isLoading: boolean;
};

export type AdminAiStatusCard = {
  readonly key: string;
  readonly label: string;
  readonly value: string;
  readonly detail: string;
  readonly tone: "is-active" | "is-stale" | "is-error" | "is-muted";
};

export type AdminAiHealthCard = {
  readonly key: string;
  readonly label: string;
  readonly detail: string;
  readonly tone: "is-active" | "is-stale" | "is-error" | "is-muted";
};

export type AdminAiProviderField = {
  readonly key: string;
  readonly label: string;
  readonly value: string;
  readonly detail: string;
};

export type AdminAiStatRow = {
  readonly label: string;
  readonly value: string;
};

export const EMPTY_ADMIN_AI_OVERVIEW_STATE: AdminAiOverviewLoadState = {
  aiStatus: null,
  summary: null,
  operations: null,
  errorMessage: "",
  isLoading: true
};

/**
 * Return true when a value is a non-array object.
 */
function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/**
 * Read a nested object field safely.
 */
function recordField(source: AdminAiPayload | null, key: string): AdminAiPayload {
  const value = source?.[key];
  return isRecord(value) ? value : {};
}

/**
 * Read a string-like field with a fallback.
 */
function stringField(source: AdminAiPayload | null, key: string, fallback = "-"): string {
  const value = source?.[key];
  if (typeof value === "string" && value.trim()) return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return fallback;
}

/**
 * Read a numeric field with a fallback.
 */
function numberField(source: AdminAiPayload | null, key: string, fallback = 0): number {
  const value = source?.[key];
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

/**
 * Format a number with the German frontend locale.
 */
function numberText(value: unknown): string {
  const parsed = Number(value ?? 0);
  if (!Number.isFinite(parsed)) return String(value ?? "-");
  return parsed.toLocaleString("de-DE");
}

/**
 * Format a ratio as whole percent.
 */
function percentText(value: unknown): string {
  const parsed = Number(value ?? 0);
  return `${Math.round((Number.isFinite(parsed) ? parsed : 0) * 100)}%`;
}

/**
 * Format a USD cost value like the legacy Admin-AI runtime.
 */
function moneyText(value: unknown): string {
  const parsed = Number(value ?? 0);
  return `$${(Number.isFinite(parsed) ? parsed : 0).toLocaleString("de-DE", {
    maximumFractionDigits: 6,
    minimumFractionDigits: 0
  })}`;
}

/**
 * Map Admin-AI health status values to existing CSS tone classes.
 */
function toneForStatus(status: unknown): AdminAiStatusCard["tone"] {
  const value = String(status ?? "").toLowerCase();
  if (["ok", "ready", "healthy", "active", "success"].includes(value)) return "is-active";
  if (["critical", "error", "failed", "unhealthy"].includes(value)) return "is-error";
  if (["warning", "stale", "degraded", "pending"].includes(value)) return "is-stale";
  return "is-muted";
}

/**
 * Build the main overview status badge text from partial API payloads.
 */
export function overviewBadge(state: AdminAiOverviewLoadState): AdminAiStatusCard {
  const ready = state.aiStatus ? state.aiStatus.ready !== false : true;
  const summaryReadiness = recordField(state.summary, "readiness");
  const readinessStatus = stringField(summaryReadiness, "status", ready ? "ok" : "critical");
  const tone = state.errorMessage ? "is-stale" : toneForStatus(readinessStatus);
  const label = state.errorMessage
    ? "Teilweise geladen"
    : tone === "is-error"
      ? "Handlungsbedarf"
      : tone === "is-stale"
        ? "Beobachten"
        : state.isLoading
          ? "Wird geladen"
          : "Betriebsbereit";
  return {
    key: "overview",
    label,
    value: label,
    detail: state.errorMessage || "AI-Status, Summary und Operations-Metriken",
    tone: state.isLoading ? "is-muted" : tone
  };
}

/**
 * Build the five compact status cards from the overview payloads.
 */
export function overviewStatusCards(state: AdminAiOverviewLoadState): AdminAiStatusCard[] {
  const aiReady = state.aiStatus ? state.aiStatus.ready !== false : false;
  const provider = stringField(state.aiStatus, "provider", "lokal");
  const model = stringField(state.aiStatus, "model", "lokal");
  const fallbackRate = numberField(state.summary, "fallback_rate");
  const operationsJobs = recordField(state.operations, "background_jobs");
  const queuedJobs = numberField(operationsJobs, "queue_length");
  const failedJobs = numberField(operationsJobs, "failed");

  return [
    {
      key: "ai",
      label: "AI",
      value: state.aiStatus ? (aiReady ? "aktiv" : "inaktiv") : "Wird geladen",
      detail: state.aiStatus ? "Anbieterstatus aus /api/v1/ai/status" : "Status wird geladen",
      tone: state.aiStatus ? (aiReady ? "is-active" : "is-error") : "is-muted"
    },
    {
      key: "openai",
      label: "OpenAI",
      value: provider.toLowerCase().includes("openai") || model.toLowerCase().includes("gpt")
        ? "konfiguriert"
        : "nicht konfiguriert",
      detail: `${provider} / ${model}`,
      tone: state.aiStatus ? (aiReady ? "is-active" : "is-error") : "is-muted"
    },
    {
      key: "fallback",
      label: "Lokaler Ausweichbetrieb",
      value: fallbackRate > 0 || !aiReady ? "aktiv" : "inaktiv",
      detail: `Fallback-Rate ${percentText(fallbackRate)}`,
      tone: fallbackRate > 0 || !aiReady ? "is-stale" : "is-active"
    },
    {
      key: "rag",
      label: "RAG",
      value: stringField(recordField(state.summary, "readiness"), "status", "wird geladen"),
      detail: "Bereitschaft aus Admin-AI-Summary",
      tone: toneForStatus(recordField(state.summary, "readiness").status)
    },
    {
      key: "reindex",
      label: "Letzter Reindex",
      value: failedJobs ? "Jobs kritisch" : queuedJobs ? "Jobs laufen" : "Queue ruhig",
      detail: `${numberText(queuedJobs)} wartend / ${numberText(failedJobs)} fehlgeschlagen`,
      tone: failedJobs ? "is-error" : queuedJobs ? "is-stale" : "is-active"
    }
  ];
}

/**
 * Build health cards for the status panel.
 */
export function overviewHealthCards(state: AdminAiOverviewLoadState): AdminAiHealthCard[] {
  const readiness = recordField(state.summary, "readiness");
  const operationsJobs = recordField(state.operations, "background_jobs");
  const provider = stringField(state.aiStatus, "provider", "lokal");
  const model = stringField(state.aiStatus, "model", "lokal");
  const ready = state.aiStatus ? state.aiStatus.ready !== false : false;
  const queuedJobs = numberField(operationsJobs, "queue_length");
  const failedJobs = numberField(operationsJobs, "failed");

  return [
    {
      key: "ai",
      label: ready ? "bereit" : "checken",
      detail: `${provider} / ${model}`,
      tone: state.aiStatus ? (ready ? "is-active" : "is-error") : "is-muted"
    },
    {
      key: "rag",
      label: stringField(readiness, "status", "offen"),
      detail: stringField(readiness, "reasons", "Summary geladen"),
      tone: toneForStatus(readiness.status)
    },
    {
      key: "queue",
      label: failedJobs ? "kritisch" : queuedJobs ? "aktiv" : "ruhig",
      detail: `${numberText(queuedJobs)} wartend / ${numberText(failedJobs)} fehlgeschlagen`,
      tone: failedJobs ? "is-error" : queuedJobs ? "is-stale" : "is-active"
    }
  ];
}

/**
 * Build the model status card from `/api/v1/ai/status`.
 */
export function modelHealthCard(state: AdminAiOverviewLoadState): AdminAiHealthCard {
  const ready = state.aiStatus ? state.aiStatus.ready !== false : false;
  const model = stringField(state.aiStatus, "model", "lokal");
  return {
    key: "model",
    label: ready ? "bereit" : "Fallback / Kontrolle",
    detail: model,
    tone: state.aiStatus ? (ready ? "is-active" : "is-stale") : "is-muted"
  };
}

/**
 * Format a KPI value from Admin-AI summary payloads.
 */
export function kpiValue(summary: AdminAiPayload | null, key: string): string {
  const value = summary?.[key];
  if (key.includes("rate")) return percentText(value);
  if (key.includes("cost") || key.includes("usd")) return moneyText(value);
  if (key.includes("latency")) return `${numberText(value)} ms`;
  return numberText(value);
}

/**
 * Build provider field cards from AI status payloads.
 */
export function providerFields(state: AdminAiOverviewLoadState): AdminAiProviderField[] {
  const ready = state.aiStatus ? state.aiStatus.ready !== false : false;
  return [
    {
      key: "provider",
      label: "Anbieter",
      value: stringField(state.aiStatus, "provider", "lokal"),
      detail: "Aktiver AI-Backend-Anbieter."
    },
    {
      key: "model",
      label: "Modell",
      value: stringField(state.aiStatus, "model", "lokal"),
      detail: "Modell fuer generative Antworten."
    },
    {
      key: "mode",
      label: "Betriebsmodus",
      value: ready ? "Modellbetrieb" : "Fallback / Kontrolle",
      detail: "Externes Modell oder lokaler Ausweichbetrieb."
    },
    {
      key: "streaming",
      label: "Streaming",
      value: state.aiStatus?.streaming_enabled ? "aktiv" : "aus",
      detail: "Antwortausgabe im Chat-Frontend."
    }
  ];
}

/**
 * Build provider diagnostic rows without exposing secrets.
 */
export function providerDetailRows(state: AdminAiOverviewLoadState): AdminAiStatRow[] {
  return [
    { label: "Provider", value: stringField(state.aiStatus, "provider", "lokal") },
    { label: "Modell", value: stringField(state.aiStatus, "model", "lokal") },
    {
      label: "Streaming",
      value: state.aiStatus?.streaming_enabled ? "aktiv" : "aus"
    },
    {
      label: "Letzter Fehler",
      value: stringField(state.aiStatus, "last_error", "kein letzter Fehler")
    }
  ];
}

/**
 * Build provider action rows that point operators to the stable backend contract.
 */
export function providerActionRows(state: AdminAiOverviewLoadState): AdminAiStatRow[] {
  const ready = state.aiStatus ? state.aiStatus.ready !== false : false;
  return [
    { label: "Aendern", value: ".env / Runtime-Konfiguration" },
    { label: "Endpoint", value: "/api/v1/ai/status" },
    { label: "Service", value: "app.ai.services.ai_status" },
    {
      label: "Admin-Hinweis",
      value: ready ? "Keine Aktion erforderlich" : "Key, Modell und Provider kontrollieren"
    }
  ];
}

/**
 * Convert a partial load failure into a stable Admin-AI overview state.
 */
export function failedOverviewState(error: unknown): Pick<AdminAiOverviewLoadState, "errorMessage"> {
  return {
    errorMessage: safeErrorMessage(error, "AI-Admin Overview konnte nicht komplett geladen werden.")
  };
}

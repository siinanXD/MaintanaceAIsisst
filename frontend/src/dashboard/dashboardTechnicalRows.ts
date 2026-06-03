import { type DashboardRuntimeData } from "./dashboardApi";
import { assetText } from "./dashboardAssetModel";
import {
  formatMilliseconds,
  formatRatePercent,
  knowledgeGapCount,
  numberValue,
  objectValue,
  retrievalSloValues
} from "./dashboardTechnicalHelpers";
import type { DashboardStatusRow } from "./dashboardTechnicalTypes";

/**
 * Build AI system rows.
 */
export function aiSystemRows(data: DashboardRuntimeData): readonly DashboardStatusRow[] {
  const aiStatus = data.aiStatus ?? {};
  const sloValues = retrievalSloValues(data);
  const ready = aiStatus.ready === true;

  return [
    {
      detail: ready ? "bereit" : "prüfen",
      label: "KI-Anbieter",
      severity: ready ? "good" : "warning",
      value: assetText(aiStatus, "provider", "-")
    },
    {
      detail: aiStatus.streaming_available
        ? "Streaming aktiv"
        : aiStatus.streaming_configured
          ? "Konfiguriert, API noch nicht freigegeben"
          : "Streaming aus",
      label: "Modell",
      severity: "muted",
      value: assetText(aiStatus, "model", "-")
    },
    {
      detail: "Antwortkontext",
      label: "Suchzeit P95",
      severity: numberValue(sloValues, "retrieval_p95_ms") > 2500 ? "warning" : "good",
      value: formatMilliseconds(sloValues.retrieval_p95_ms)
    },
    {
      detail: "KI-Anbieter oder Suche",
      label: "Ausweichantworten",
      severity: numberValue(sloValues, "fallback_rate") >= 0.1 ? "warning" : "good",
      value: formatRatePercent(sloValues.fallback_rate)
    },
    {
      detail: "Index-Synchronisation",
      label: "Index-Sync-Fehler",
      severity: numberValue(sloValues, "vector_sync_failure_count") ? "critical" : "good",
      value: String(numberValue(sloValues, "vector_sync_failure_count"))
    }
  ];
}

/**
 * Build risk radar rows.
 */
export function riskRows(data: DashboardRuntimeData): readonly DashboardStatusRow[] {
  const sloValues = retrievalSloValues(data);
  return [
    {
      detail: "Sicherheitsereignisse",
      label: "Sicherheit",
      severity: numberValue(sloValues, "safety_risk_count") ? "critical" : "good",
      value: String(numberValue(sloValues, "safety_risk_count"))
    },
    {
      detail: "Antworten unter Schwelle",
      label: "Niedrige Sicherheit",
      severity: numberValue(sloValues, "low_confidence_rate") >= 0.15 ? "warning" : "good",
      value: formatRatePercent(sloValues.low_confidence_rate)
    },
    {
      detail: "Antworten ohne Quelle",
      label: "Ohne Quellen",
      severity: numberValue(sloValues, "no_source_rate") >= 0.1 ? "warning" : "good",
      value: formatRatePercent(sloValues.no_source_rate)
    },
    {
      detail: "KI-Anbieter oder Suche",
      label: "Ausweichantworten",
      severity: numberValue(sloValues, "fallback_rate") >= 0.1 ? "warning" : "good",
      value: formatRatePercent(sloValues.fallback_rate)
    },
    {
      detail: "Nutzerrückmeldungen",
      label: "Negatives Feedback",
      severity: numberValue(sloValues, "negative_feedback_rate") >= 0.1 ? "warning" : "good",
      value: formatRatePercent(sloValues.negative_feedback_rate)
    },
    {
      detail: "gefilterte Kandidaten",
      label: "Berechtigungsfilter",
      severity: "muted",
      value: String(numberValue(sloValues, "permission_filtered_candidate_count"))
    }
  ];
}

/**
 * Build knowledge health rows.
 */
export function knowledgeRows(data: DashboardRuntimeData): readonly DashboardStatusRow[] {
  const status = data.knowledgeStatus ?? {};
  const vectorStatus = objectValue(status, "vector_store");
  const indexed = numberValue(status, "indexed");
  const documents = numberValue(status, "documents");
  const chunks = numberValue(status, "chunks");
  const stale = numberValue(status, "stale");
  const missingChunks = numberValue(vectorStatus, "missing_chunk_count");
  const reindexNeeded = vectorStatus.reindex_recommended === true;
  const reasons = Array.isArray(vectorStatus.reindex_reasons) ? vectorStatus.reindex_reasons.join(", ") : "";
  const gapCount = knowledgeGapCount(data);

  return [
    {
      detail: `${chunks} Textabschnitte`,
      label: "Dokumente indexiert",
      severity: documents && indexed < documents ? "warning" : "good",
      value: `${indexed}/${documents}`
    },
    {
      detail: "Aging und Reindex",
      label: "Veraltete Dokumente",
      severity: stale ? "warning" : "good",
      value: String(stale)
    },
    {
      detail: "DB zu Vektor Store",
      label: "Fehlende Textabschnitte",
      severity: missingChunks ? "critical" : "good",
      value: String(missingChunks)
    },
    {
      detail: reasons,
      label: "Reindex",
      severity: reindexNeeded ? "warning" : "good",
      value: reindexNeeded ? "empfohlen" : "nicht nötig"
    },
    {
      detail: "offene Lücken",
      label: "Wissenslücken",
      severity: gapCount ? "warning" : "good",
      value: String(gapCount)
    }
  ];
}

/**
 * Build technical index rows.
 */
export function technicalIndexRows(data: DashboardRuntimeData): readonly DashboardStatusRow[] {
  const status = data.knowledgeStatus ?? {};
  const sloValues = retrievalSloValues(data);
  const vectorStatus = objectValue(status, "vector_store");
  const reindexNeeded = vectorStatus.reindex_recommended === true;
  const indexed = numberValue(status, "indexed");
  const documents = numberValue(status, "documents");
  const chunks = numberValue(status, "chunks");

  return [
    {
      detail: `${indexed}/${documents} Dokumente, ${chunks} Textabschnitte`,
      label: "Dokument-/Index-Status",
      severity: reindexNeeded ? "warning" : "good",
      value: reindexNeeded ? "Reindex" : "OK"
    },
    {
      detail: "Offene Lücken",
      label: "Wissenslücken",
      severity: knowledgeGapCount(data) ? "warning" : "good",
      value: String(knowledgeGapCount(data))
    },
    {
      detail: `${formatRatePercent(sloValues.no_source_rate)} ohne Quellen`,
      label: "Suchzeit P95",
      severity: numberValue(sloValues, "retrieval_p95_ms") > 2500 ? "warning" : "good",
      value: formatMilliseconds(sloValues.retrieval_p95_ms)
    },
    {
      detail: "Antwortqualität",
      label: "Niedrige Sicherheit",
      severity: numberValue(sloValues, "low_confidence_rate") >= 0.15 ? "warning" : "good",
      value: formatRatePercent(sloValues.low_confidence_rate)
    }
  ];
}

import { type ReactNode } from "react";

import {
  type AdminAiTechnicalFilters,
  type AdminAiTechnicalState,
  flowStatusLabel,
  metricLabel,
  monitoringValue,
  objectPayload,
  retrievalSloValue,
  retrievalSloValues,
  selectedRetrievalDebugItem,
  technicalDateTime,
  technicalItems,
  technicalJobRows,
  technicalReference
} from "./adminAiTechnicalModel";
import { numberText, percentText } from "./adminAiEffectivenessModel";
import { ragText } from "./adminAiRagBoardModel";
import {
  DataTable,
  debugRequests,
  debugSteps,
  filterChange,
  isPayload,
  MetricCard,
  MetricRow,
  StatsList,
  topList
} from "./AdminAiTechnicalShared";

const RETRIEVAL_SLO_KPIS = [
  ["retrieval_p95_ms", "P95 Suchzeit", "0 ms"],
  ["no_source_rate", "Antworten ohne Quellen", "0%"],
  ["low_confidence_rate", "Niedrige Sicherheit", "0%"],
  ["permission_filtered_candidate_count", "Berechtigungsfilter", "0"],
  ["negative_feedback_rate", "Negatives Feedback", "0%"],
  ["safety_risk_count", "Sicherheitsrisiken", "0"],
  ["fallback_rate", "Ausweichantworten", "0%"],
  ["index_sync_risks", "Index/Sync Risiken", "0"]
] as const;

const MONITORING_KPIS = [
  ["average_response_ms", "Antwortzeit Ø", "0 ms"],
  ["average_retrieval_ms", "Quellenabruf Ø", "0 ms"],
  ["total_tokens", "Tokenverbrauch", "0"],
  ["error_rate", "Fehlerquote", "0%"],
  ["structured_answer_count", "Strukturierte Antworten", "0"],
  ["rag_answer_count", "RAG-Antworten", "0"],
  ["no_source_count", "Ohne Quellen", "0"],
  ["source_count_average", "Quellen Ø", "0"],
  ["empty_retrieval_rate", "Leere Abrufe", "0%"],
  ["hallucination_warning_count", "Halluzinationswarnungen", "0"],
  ["retrieval_hit_rate", "Trefferquote", "0%"],
  ["average_similarity_score", "Similarity Ø", "0%"]
] as const;

type AdminAiTechnicalProps = {
  readonly onFilterChange: (key: keyof AdminAiTechnicalFilters, value: string) => void;
  readonly onQueueStale: () => void;
  readonly onRefresh: () => void;
  readonly onReindexAll: () => void;
  readonly onReindexStale: () => void;
  readonly onRunEvaluation: () => void;
  readonly technicalState: AdminAiTechnicalState;
};

/**
 * Render the technical Admin-AI diagnostics areas.
 */
export function AdminAiTechnical(props: AdminAiTechnicalProps): ReactNode {
  const { technicalState } = props;

  return (
    <>
      <section className="ai-admin-area" id="ai-technical" data-ai-admin-area="technical">
        <div className="ai-admin-area-header">
          <div>
            <span className="section-kicker">7. Technische Diagnose</span>
            <h3>Retrieval, Protokolle, Reindex und SLOs</h3>
            <p className="panel-meta">
              Die bisherigen technischen Detailansichten bleiben erhalten und sind hier gebündelt
              verlinkt.
            </p>
          </div>
          <span className="badge badge-ai" data-ai-section-status="technical">
            {technicalState.isLoading ? "Diagnose lädt" : "Diagnose bereit"}
          </span>
        </div>
        <div className="document-card-grid">
          <a className="document-card" href="#ai-retrieval"><span>Retrieval</span><strong>Quellenabruf analysieren</strong><small>Debug, SLO und Golden Eval.</small></a>
          <a className="document-card" href="#ai-diagnostics"><span>Protokolle</span><strong>AI-Logs und Wissenslücken</strong><small>Observability, Fehler und Debug-Blueprints.</small></a>
          <a className="document-card" href="#ai-indexing-status"><span>Index</span><strong>Reindex und Jobs</strong><small>Queue, Vektor-Sync und Drift.</small></a>
          <a className="document-card" href="/admin/ai#ai-models"><span>Modelle</span><strong>Provider und Laufzeit</strong><small>Status, Fallbacks und Modellprofile.</small></a>
        </div>
      </section>
      <CollapsedTechnicalPanel
        detail="Recall@K, MRR, NDCG, Antworten ohne Quellen, Similarity und Quellenabruf-Ablauf."
        title="Retrieval-Qualität und Evaluation"
      >
        <RetrievalSection {...props} />
      </CollapsedTechnicalPanel>
      <CollapsedTechnicalPanel
        detail="Monitoring, Fehler, Prompt-Debug, Chunk-Nutzung, Top-Fragen und Wissensluecken."
        title="Interne Diagnose und Prompt-Debug"
      >
        <DiagnosticsSection {...props} />
      </CollapsedTechnicalPanel>
      <CollapsedTechnicalPanel
        detail="Reindex-Kommandos, Background-Jobs, Vektor-Sync, Queue und Operationsdaten."
        title="Index, Jobs und Operations"
      >
        <IndexingSection {...props} />
      </CollapsedTechnicalPanel>
    </>
  );
}

/**
 * Render a collapsed technical diagnostics group.
 */
function CollapsedTechnicalPanel({
  children,
  detail,
  title
}: {
  readonly children: ReactNode;
  readonly detail: string;
  readonly title: string;
}): ReactNode {
  return (
    <details className="panel admin-ai-technical-disclosure">
      <summary>
        <span>
          <strong>{title}</strong>
          <small>{detail}</small>
        </span>
        <span className="status-pill is-muted">aufklappen</span>
      </summary>
      <div className="admin-ai-technical-disclosure-body">{children}</div>
    </details>
  );
}

/**
 * Render retrieval debug, SLO and golden-eval panels.
 */
function RetrievalSection({
  onFilterChange,
  onRefresh,
  onRunEvaluation,
  technicalState
}: AdminAiTechnicalProps): ReactNode {
  const sloValues = retrievalSloValues(technicalState.telemetry);
  const slo = objectPayload(technicalState.telemetry?.retrieval_slo);
  const trends = objectPayload(slo.trends);
  const warnings = Array.isArray(slo.warnings) ? slo.warnings.filter(isPayload) : [];
  const evaluationHistory = objectPayload(technicalState.telemetry?.retrieval_evaluation_history);
  const latestEvaluation = objectPayload(evaluationHistory.latest);
  const evaluationRuns = Array.isArray(evaluationHistory.runs) ? evaluationHistory.runs.filter(isPayload) : [];
  const regressionSignals = Array.isArray(evaluationHistory.regression_signals)
    ? evaluationHistory.regression_signals.filter(isPayload)
    : [];
  const selectedDebug = selectedRetrievalDebugItem(technicalState.retrievalDebug);

  return (
    <section className="ai-admin-area" id="ai-retrieval" data-ai-admin-area="retrieval">
      <div className="ai-admin-area-header">
        <div>
          <span className="section-kicker">2. Quellenabruf</span>
          <h3>Warum wurden Quellen gefunden, gefiltert oder verworfen?</h3>
          <p className="panel-meta">Prompt-sichere Analyse für Abfrage-Klassifizierung, SQL-Ausweichbetrieb, Keyword-Suche, Vektorsuche, Bewertungen und finale Quellen.</p>
        </div>
        <span className="badge badge-ai" data-ai-section-status="retrieval">Quellenabruf geladen</span>
      </div>
      <section className="panel" data-retrieval-slo-panel>
        <div className="panel-header">
          <div><h3>Suchqualität SLO</h3><p className="panel-meta">Qualitäts- und Betriebsmetriken für AI-Antworten.</p></div>
          <span className="badge badge-ai" data-retrieval-slo-status>{ragText(slo.status, "Noch nicht geladen")}</span>
        </div>
        <div className="dashboard-grid dashboard-grid-4">
          {RETRIEVAL_SLO_KPIS.map(([key, label, fallback]) => (
            <article className="metric-card" key={key}>
              <span>{label}</span>
              <strong data-retrieval-slo-kpi={key}>{sloValues[key] == null ? fallback : retrievalSloValue(key, sloValues[key])}</strong>
            </article>
          ))}
        </div>
        <div className="content-grid two-columns mt-4">
          <StatsList dataAttr="data-retrieval-slo-trends" rows={Object.entries(trends).map(([key, value]) => [metricLabel(key), retrievalSloValue(key, objectPayload(value).current)] as const)} empty={["Trends", "noch keine SLO-Trends"]} />
          <StatsList dataAttr="data-retrieval-slo-warnings" rows={warnings.map((warning) => [metricLabel(ragText(warning.metric)), `${ragText(warning.status)} ab ${retrievalSloValue(ragText(warning.metric), warning.threshold)}`] as const)} empty={["Warnungen", "keine aktiven SLO-Warnungen"]} />
        </div>
      </section>

      <section className="panel" data-retrieval-debug-panel>
        <div className="panel-header">
          <div><h3>Quellenabruf Analyse</h3><p className="panel-meta">Nur-Lese Nachvollziehbarkeit ohne Roh-Prompts, Antworten oder Textabschnitt-Volltexte.</p></div>
          <div className="toolbar admin-ai-toolbar">
            <input className="input input-bordered" data-retrieval-debug-search placeholder="Quellenabruf-Fälle filtern" value={technicalState.filters.debugQuery} onChange={filterChange(onFilterChange, "debugQuery")} />
            <select className="input input-bordered" data-retrieval-debug-type aria-label="Nach Abfrage-Typ filtern" value={technicalState.filters.debugType} onChange={filterChange(onFilterChange, "debugType")}>
              <option value="">Alle Abfrage-Typen</option>
              <option value="error_analysis">Fehleranalyse</option>
              <option value="machine_question">Maschinenfrage</option>
              <option value="inventory_question">Inventarfrage</option>
              <option value="task_question">Aufgabefrage</option>
              <option value="document_question">Dokumentfrage</option>
              <option value="safety_question">Sicherheitsfrage</option>
              <option value="knowledge_gap">Wissenslücke</option>
              <option value="trend_history_question">Trend/Historie</option>
              <option value="general_question">Allgemein</option>
            </select>
            <button className="btn btn-secondary" type="button" data-retrieval-debug-refresh onClick={onRefresh}>Aktualisieren</button>
          </div>
        </div>
        <div className="ai-retrieval-inspector" data-retrieval-inspector>
          <div className="ai-retrieval-metrics" data-retrieval-analysis>
            <MetricRow label="Quellen" value={selectedDebug?.source_count || 0} />
            <MetricRow label="Gefiltert" value={selectedDebug?.filtered_candidate_count || 0} />
            <MetricRow label="Dauer" value={`${numberText(selectedDebug?.retrieval_duration_ms || 0)} ms`} />
          </div>
          <section className="retrieval-flow-panel" data-retrieval-flow-panel aria-label="AI Quellenabruf Ablauf">
            <div className="retrieval-flow-header">
              <div><span className="section-kicker">Warum diese Antwort?</span><h4>AI Quellenabruf Ablauf</h4><p className="panel-meta">Prompt-sichere Timeline vom Abfrage-Verständnis bis zur finalen Antwort.</p></div>
              <div className="retrieval-flow-header-actions"><span className="badge badge-ai" data-retrieval-flow-status>{selectedDebug ? "geladen" : "Noch nicht geladen"}</span><span className="panel-meta" data-retrieval-flow-duration>{selectedDebug ? `${numberText(selectedDebug.retrieval_duration_ms || 0)} ms` : "-"}</span></div>
            </div>
            <div className="retrieval-flow-summary" data-retrieval-flow-summary>{selectedDebug ? technicalReference("Chat", selectedDebug.chat_message_id || selectedDebug.id) : "Kein Debug-Datensatz ausgewählt."}</div>
            <div className="retrieval-flow-timeline" data-retrieval-flow-timeline>
              {debugSteps(selectedDebug).map((step, index) => <MetricRow key={index} label={ragText(step.step || step.label, `Schritt ${index + 1}`)} value={flowStatusLabel(step.status)} />)}
            </div>
            <div className="content-grid two-columns mt-4">
              <div className="retrieval-flow-source-map" data-retrieval-flow-source-map><MetricRow label="Finale Quellen" value={selectedDebug?.final_visible_sources || selectedDebug?.source_count || 0} /></div>
              <div className="retrieval-flow-answer" data-retrieval-flow-answer><MetricRow label="Antwort" value={ragText(selectedDebug?.answer_preview, "metadata-only")} /></div>
            </div>
          </section>
        </div>
        <DataTable caption="Prompt-sichere Quellenabruf-Debug-Daten mit Abfrage-Typ, Quellen, Sicherheit und Konflikten" headers={["Zeit", "Referenz", "Typ", "Quellen", "Sicherheit", "Konflikte", "Dauer", "Ablauf"]} dataAttr="data-retrieval-debug-rows" rows={technicalState.retrievalDebug.map((item) => [
          technicalDateTime(item.created_at),
          technicalReference("Chat", item.chat_message_id || item.id),
          item.query_type,
          item.source_count || item.final_visible_sources || 0,
          item.confidence_level || item.confidence_score || "-",
          item.conflict_count || 0,
          `${numberText(item.retrieval_duration_ms || 0)} ms`,
          "anzeigen"
        ])} />
      </section>

      <section className="panel" data-retrieval-evaluation-history-panel>
        <div className="panel-header">
          <div><h3>Golden Eval Historie</h3><p className="panel-meta">Regressionen und Qualitätstrends für bekannte Quellenabruf-Fragen.</p></div>
          <div className="toolbar"><span className="badge badge-ai" data-retrieval-evaluation-status>{evaluationRuns.length ? "Historie geladen" : "Noch nicht geladen"}</span><button className="btn btn-secondary" disabled={technicalState.isSaving} type="button" data-retrieval-evaluation-run onClick={onRunEvaluation}>Golden Eval ausführen</button></div>
        </div>
        <div className="dashboard-grid dashboard-grid-4">
          {[
            ["recall_at_k", "Recall@K"],
            ["mrr", "MRR"],
            ["ndcg_at_k", "NDCG"],
            ["no_result_count", "Keine Treffer"]
          ].map(([key, label]) => <article className="metric-card" key={key}><span>{label}</span><strong data-retrieval-evaluation-kpi={key}>{key.endsWith("count") ? numberText(latestEvaluation[key] || 0) : percentText(latestEvaluation[key] || 0)}</strong></article>)}
        </div>
        <div className="content-grid two-columns mt-4">
          <StatsList dataAttr="data-retrieval-evaluation-regression" rows={regressionSignals.map((signal) => [ragText(signal.metric), percentText(signal.current || 0)] as const)} empty={["Golden Eval", "noch keine Runs gespeichert"]} />
          <StatsList dataAttr="data-retrieval-evaluation-runs" rows={evaluationRuns.slice(0, 5).map((run) => [technicalReference("Run", run.id), `${percentText(run.recall_at_k || 0)} Recall / ${percentText(run.mrr || 0)} MRR`] as const)} empty={["Runs", "keine Historie"]} />
        </div>
      </section>
    </section>
  );
}

/**
 * Render observability, workflow and prompt-debug panels.
 */
function DiagnosticsSection({ onRefresh, technicalState }: AdminAiTechnicalProps): ReactNode {
  const observability = technicalState.observability || {};
  const metrics = objectPayload(observability.metrics);
  const quality = objectPayload(observability.quality_metrics);
  const retrieval = objectPayload(observability.retrieval_monitoring);
  const debugTools = objectPayload(observability.debug_tools);
  const logs = Array.isArray(observability.logs) ? observability.logs.filter(isPayload) : technicalItems(observability);
  const workflows = Array.isArray(observability.workflows) ? observability.workflows.filter(isPayload) : [];
  const topErrors = Array.isArray(observability.top_errors) ? observability.top_errors.filter(isPayload) : [];
  const gaps = Array.isArray(observability.knowledge_gaps) ? observability.knowledge_gaps.filter(isPayload) : [];
  const topQuestions = observability.top_questions || metrics.top_questions || metrics.frequent_questions;
  const sourceDistribution = observability.source_distribution || metrics.source_distribution_rows;
  const structuredModules = Array.isArray(metrics.top_structured_modules)
    ? metrics.top_structured_modules.filter(isPayload)
    : [];
  const structuredDomainRows = Array.isArray(metrics.structured_domain_distribution_rows)
    ? metrics.structured_domain_distribution_rows.filter(isPayload)
    : structuredModules;
  const frequentSearchTerms = Array.isArray(metrics.frequent_search_terms)
    ? metrics.frequent_search_terms.filter(isPayload)
    : [];
  const noSourceRows = [
    ["Fehlende Berechtigung", metrics.no_source_permission_denied_count || 0],
    ["Keine Daten gefunden", metrics.no_source_no_data_count || 0],
    ["Beantwortet ohne Quellen", metrics.no_source_answer_count || 0],
    ["Quellen je beantworteter Frage", monitoringValue("source_count_average_answered", metrics.source_count_average_answered)]
  ] as const;

  return (
    <section className="ai-admin-area" id="ai-diagnostics" data-ai-admin-area="answers">
      <div className="ai-admin-area-header">
        <div><span className="section-kicker">5. Diagnose</span><h3>Fehler, Protokolle, Prompt-Debugging und Wissenslücken</h3><p className="panel-meta">Admins sehen prompt-sichere Betriebsdiagnosen, letzte fehlgeschlagene Abfragen, Workflows, Wissenslücken und Debug-Blueprints.</p></div>
        <div className="toolbar"><span className="badge badge-ai" data-ai-observability-status>{technicalState.isLoading ? "lädt" : "geladen"}</span><button className="btn btn-secondary" type="button" data-ai-observability-refresh onClick={onRefresh}>Monitoring aktualisieren</button></div>
      </div>
      <section className="panel"><div className="panel-header"><div><h3>Letzte fehlgeschlagene AI-Abfragen</h3><p className="panel-meta">Aus bestehenden Audit-Ereignissen abgeleitet; ohne Rohfrage oder Antworttext.</p></div></div><div className="ai-failed-query-list" data-ai-failed-queries>{logs.slice(0, 5).map((item) => <MetricRow key={ragText(item.id)} label={technicalReference("Audit", item.id)} value={ragText(item.status || item.error_category, "ok")} />)}</div></section>
      <section className="panel ai-answer-quality-panel"><div className="panel-header"><h3>Antwortqualität im Chat</h3><span className="panel-meta">Jede Antwort zeigt Quellen, Sicherheit, Unsicherheit und verwendete Dokumente.</span></div><div className="ai-answer-quality-grid" data-ai-answer-quality-guide><MetricRow label="Quellen" value="sichtbar" /><MetricRow label="Sicherheit" value="bewertet" /></div></section>
      <section className="panel ai-observability-panel">
        <div className="panel-header"><div><h3>KI-Metrik-Cockpit</h3><p className="panel-meta">Latenz, Tokens, Fehler, leere Abrufe und Halluzinationswarnungen.</p></div></div>
        <div className="dashboard-grid dashboard-grid-4">{MONITORING_KPIS.map(([key, label, fallback]) => <article className="metric-card" key={key}><span>{label}</span><strong data-ai-monitoring-kpi={key}>{metrics[key] == null && quality[key] == null ? fallback : monitoringValue(key, metrics[key] ?? quality[key])}</strong></article>)}</div>
        <div className="content-grid two-columns mt-4"><StatsList dataAttr="data-ai-top-questions" rows={topList(topQuestions)} empty={["Fragen", "keine Daten"]} /><StatsList dataAttr="data-ai-source-distribution" rows={topList(sourceDistribution)} empty={["Quellen", "keine Daten"]} /></div>
        <div className="content-grid two-columns mt-4"><StatsList dataAttr="data-ai-top-structured-modules" rows={structuredDomainRows.map((item) => [item.label || item.module, item.count] as const)} empty={["Strukturierte Bereiche", "keine Daten"]} /><StatsList dataAttr="data-ai-frequent-search-terms" rows={frequentSearchTerms.map((item) => [item.term, item.count] as const)} empty={["Suchbegriffe", "keine Daten"]} /></div>
        <div className="content-grid two-columns mt-4"><StatsList dataAttr="data-ai-no-source-breakdown" rows={noSourceRows} empty={["Antworten ohne Quellen", "keine Daten"]} /><StatsList dataAttr="data-ai-answer-source-average" rows={[["Alle Antworten", monitoringValue("source_count_average", metrics.source_count_average)], ["Beantwortete Fragen", monitoringValue("source_count_average_answered", metrics.source_count_average_answered)]]} empty={["Quellen", "keine Daten"]} /></div>
      </section>
      <section className="panel"><div className="panel-header"><h3>Quellenabruf Monitoring</h3><span className="panel-meta">Top Treffer, schlechte Treffer, Textabschnitt-Nutzung und Dokumentverteilung.</span></div><div className="content-grid two-columns"><StatsList dataAttr="data-ai-top-hits" rows={topList(retrieval.top_hits)} empty={["Treffer", "keine Daten"]} /><StatsList dataAttr="data-ai-poor-hits" rows={topList(retrieval.poor_hits)} empty={["Schlechte Treffer", "keine Daten"]} /></div><div className="content-grid two-columns mt-4"><StatsList dataAttr="data-ai-chunk-usage" rows={topList(retrieval.chunk_usage)} empty={["Textabschnitte", "keine Daten"]} /><StatsList dataAttr="data-ai-quality-metrics" rows={Object.entries(quality).slice(0, 6).map(([key, value]) => [metricLabel(key), monitoringValue(key, value)] as const)} empty={["Qualität", "keine Daten"]} /></div></section>
      <section className="panel"><div className="panel-header"><h3>Workflow-Kosten und Fehler</h3><span className="panel-meta">Metadata-only Auswertung ohne Prompt- oder Antworttexte</span></div><div className="content-grid two-columns"><DataTable caption="AI-Workflows nach Ereignissen, Fehlern, Ausweichbetrieb, Tokens und Kosten" headers={["Workflow", "Ereignisse", "Ausweichbetrieb", "Fehler", "Tokens", "Kosten", "Latenz"]} dataAttr="data-ai-workflows" rows={workflows.map((item) => [item.workflow, item.events, percentText(item.fallback_rate || 0), item.errors, item.total_tokens, item.estimated_cost_usd, `${numberText(item.average_latency_ms || 0)} ms`])} /><StatsList dataAttr="data-ai-top-errors" rows={topErrors.map((item) => [item.error_category, item.count] as const)} empty={["AI Fehler", "keine Fehler im Zeitraum"]} /></div></section>
      <section className="panel"><div className="panel-header"><h3>Wissenslücken</h3><span className="panel-meta" data-ai-knowledge-gap-count>{numberText(gaps.length)} offen</span></div><DataTable caption="Offene Wissenslücken aus KI-Fragen ohne belastbare Quellen" headers={["Referenz", "Bereich", "Maschine", "Status", "Treffer", "Zuletzt"]} dataAttr="data-ai-knowledge-gaps" rows={gaps.map((gap) => [technicalReference("Gap", gap.id), gap.department, gap.machine, gap.status, gap.occurrence_count, technicalDateTime(gap.last_seen_at)])} /></section>
      <section className="panel"><div className="panel-header"><h3>KI-Protokolle</h3><span className="panel-meta">Prompt-sichere Referenz, Quellen, Sicherheit, Antwortqualität, Fehler und Dauer.</span></div><DataTable caption="AI-Monitoring-Protokolle mit Antwortqualität, Sicherheit und Quellen" headers={["Zeit", "Referenz", "Qualität", "Sicherheit", "Quellen", "Dauer", "Debug"]} dataAttr="data-ai-observability-logs" rows={logs.map((item) => [technicalDateTime(item.created_at), technicalReference("AI", item.id), item.quality_status || item.status, item.confidence_level || "-", item.source_count || 0, `${numberText(item.response_duration_ms || item.retrieval_duration_ms || 0)} ms`, "Debug"])} /></section>
      <section className="panel"><div className="panel-header"><h3>Debug Tools</h3><div className="toolbar"><select className="input input-bordered" data-ai-debug-request aria-label="AI-Anfrage analysieren">{debugRequests(debugTools).map((item) => <option key={ragText(item.id)} value={ragText(item.id)}>{technicalReference("Chat", item.id)}</option>)}</select></div></div><div className="content-grid two-columns"><div className="ai-monitor-list" data-ai-debug-analysis><MetricRow label="Quellen" value={objectPayload(debugTools.request_analysis).source_count || 0} /></div><pre className="ai-debug-prompt" data-ai-debug-prompt>{ragText(objectPayload(debugTools.prompt_blueprint).system_prompt, "Kein Prompt-Blueprint geladen.")}</pre></div></section>
    </section>
  );
}

/**
 * Render reindex command, background job and operations panels.
 */
function IndexingSection({
  onQueueStale,
  onReindexAll,
  onReindexStale,
  technicalState
}: AdminAiTechnicalProps): ReactNode {
  const operations = technicalState.operations || {};
  const database = objectPayload(operations.database);
  const backgroundJobs = objectPayload(operations.background_jobs);
  const ai = objectPayload(operations.ai);
  const rag = objectPayload(operations.rag);
  const requests = objectPayload(operations.requests);
  const slowEndpoints = Array.isArray(requests.slow_endpoints) ? requests.slow_endpoints.filter(isPayload) : [];
  const jobRows = technicalJobRows(technicalState.jobs);
  const statusCounts = technicalState.jobs.reduce<Record<string, number>>((counts, job) => {
    const key = ragText(job.status, "unknown");
    counts[key] = (counts[key] || 0) + 1;
    return counts;
  }, {});

  return (
    <section className="ai-admin-area" id="ai-indexing-status" data-ai-admin-area="jobs">
      <div className="ai-admin-area-header"><div><span className="section-kicker">7. Indexstatus</span><h3>Index-Aufbau, Textabschnitte, Vektoren und Verarbeitung-Jobs</h3><p className="panel-meta">Reindex-Aktionen, Queue, Vektor-Sync und Textabschnitt-Abdeckung sichtbar getrennt vom normalen Antwortverhalten.</p></div><span className="badge badge-ai" data-ai-section-status="jobs">{technicalState.isLoading ? "Jobs werden geladen" : "Jobs geladen"}</span></div>
      <section className="panel ai-reindex-command-panel"><div className="panel-header"><div><h3>Reindex-Kommandos</h3><p className="panel-meta">Direkter Reindex blockiert den Request; Job einplanen nutzt die Background-Queue.</p></div><span className="panel-meta" data-ai-reindex-message>{technicalState.statusMessage}</span></div><div className="ai-admin-actions"><button className="btn btn-primary" disabled={technicalState.isSaving} type="button" data-ai-reindex onClick={onReindexAll}>Wissen neu indexieren</button><button className="btn btn-secondary" disabled={technicalState.isSaving} type="button" data-ai-reindex-stale onClick={onReindexStale}>Nur veraltete indexieren</button><button className="btn btn-ghost" disabled={technicalState.isSaving} type="button" data-ai-queue-stale onClick={onQueueStale}>Job einplanen</button></div></section>
      <section className="panel"><div className="panel-header"><div><h3>Background Jobs</h3><p className="panel-meta">RAG-Reindex und Wartungsdiagnose-Aufgaben mit Status und Ergebnis.</p></div><span className="panel-meta" data-ai-job-count>{technicalState.jobs.length} Jobs</span></div><DataTable caption="Background-Jobs für RAG-Reindex und Wartungsdiagnose" headers={["ID", "Typ", "Status", "Versuche", "Ergebnis"]} dataAttr="data-ai-jobs" rows={jobRows} /></section>
      <section className="panel"><div className="panel-header"><div><h3>Operationsdiagnose</h3><p className="panel-meta">Queue, DB-Latenz, AI-Latenz, Jobdauer und langsame Endpoints.</p></div><span className="panel-meta" data-ops-generated>{technicalDateTime(operations.generated_at)}</span></div><div className="dashboard-grid dashboard-grid-4">
        <MetricCard label="DB Latenz" hook="database_latency_ms" value={`${numberText(database.latency_ms || 0)} ms`} />
        <MetricCard label="Queue" hook="queue_length" value={backgroundJobs.queue_length || 0} />
        <MetricCard label="Laufend" hook="running_jobs" value={backgroundJobs.running || 0} />
        <MetricCard label="Fehlgeschlagen" hook="failed_jobs" value={backgroundJobs.failed || 0} />
        <MetricCard label="AI Latenz" hook="ai_latency_ms" value={`${numberText(ai.avg_latency_ms || 0)} ms`} />
        <MetricCard label="RAG stale" hook="rag_stale_ratio" value={percentText(rag.stale_ratio || 0)} />
        <MetricCard label="Ältester Job" hook="oldest_queued_age" value={`${numberText(backgroundJobs.oldest_queued_age_seconds || 0)} s`} />
        <MetricCard label="Job Dauer" hook="job_avg_duration" value={`${numberText(backgroundJobs.recent_avg_duration_seconds || 0)} s`} />
      </div><div className="content-grid two-columns mt-4"><StatsList dataAttr="data-ai-job-status" rows={[["Queued", statusCounts.queued || 0], ["Running", statusCounts.running || 0], ["Failed", statusCounts.failed || 0], ["Done", statusCounts.done || 0]]} /><StatsList dataAttr="data-ops-slow-endpoints" rows={slowEndpoints.map((item) => [item.endpoint, `${ragText(item.avg_duration_ms)} ms avg / ${ragText(item.slow_count)} slow`] as const)} empty={["Slow Endpoints", "noch keine Messwerte"]} /></div></section>
    </section>
  );
}

import { type ReactNode } from "react";

const RETRIEVAL_SLO_KPIS = [
  ["retrieval_p95_ms", "P95 Suchzeit", "0 ms"],
  ["no_source_rate", "Ohne Quellen", "0%"],
  ["low_confidence_rate", "Niedrige Sicherheit", "0%"],
  ["permission_filtered_candidate_count", "Berechtigungsfilter", "0"],
  ["negative_feedback_rate", "Negatives Feedback", "0%"],
  ["safety_risk_count", "Sicherheitsrisiken", "0"],
  ["fallback_rate", "Ausweichantworten", "0%"],
  ["index_sync_risks", "Index/Sync Risiken", "0"],
] as const;

const MONITORING_KPIS = [
  ["average_response_ms", "Antwortzeit Ø", "0 ms"],
  ["average_retrieval_ms", "Quellenabruf Ø", "0 ms"],
  ["total_tokens", "Tokenverbrauch", "0"],
  ["error_rate", "Fehlerquote", "0%"],
  ["empty_retrieval_rate", "Leere Abrufe", "0%"],
  ["hallucination_warning_count", "Halluzinationswarnungen", "0"],
  ["retrieval_hit_rate", "Trefferquote", "0%"],
  ["average_similarity_score", "Similarity Ø", "0%"],
] as const;

/**
 * Render the technical Admin-AI diagnostics areas.
 */
export function AdminAiTechnical(): ReactNode {
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
            Diagnose bereit
          </span>
        </div>
        <div className="document-card-grid">
          <a className="document-card" href="#ai-retrieval">
            <span>Retrieval</span>
            <strong>Quellenabruf analysieren</strong>
            <small>Debug, SLO und Golden Eval.</small>
          </a>
          <a className="document-card" href="#ai-diagnostics">
            <span>Protokolle</span>
            <strong>AI-Logs und Wissenslücken</strong>
            <small>Observability, Fehler und Debug-Blueprints.</small>
          </a>
          <a className="document-card" href="#ai-indexing-status">
            <span>Index</span>
            <strong>Reindex und Jobs</strong>
            <small>Queue, Vektor-Sync und Drift.</small>
          </a>
          <a className="document-card" href="/admin/ai#ai-models">
            <span>Modelle</span>
            <strong>Provider und Laufzeit</strong>
            <small>Status, Fallbacks und Modellprofile.</small>
          </a>
        </div>
      </section>
      <RetrievalSection />
      <DiagnosticsSection />
      <IndexingSection />
    </>
  );
}

/**
 * Render retrieval debug, SLO and golden-eval hooks.
 */
function RetrievalSection(): ReactNode {
  return (
    <section className="ai-admin-area" id="ai-retrieval" data-ai-admin-area="retrieval">
      <div className="ai-admin-area-header">
        <div>
          <span className="section-kicker">2. Quellenabruf</span>
          <h3>Warum wurden Quellen gefunden, gefiltert oder verworfen?</h3>
          <p className="panel-meta">
            Prompt-sichere Analyse für Abfrage-Klassifizierung, SQL-Ausweichbetrieb,
            Keyword-Suche, Vektorsuche, Bewertungen und finale Quellen.
          </p>
        </div>
        <span className="badge badge-ai" data-ai-section-status="retrieval">
          Quellenabruf wird geladen
        </span>
      </div>

      <section className="panel" data-retrieval-slo-panel>
        <div className="panel-header">
          <div>
            <h3>Suchqualität SLO</h3>
            <p className="panel-meta">Qualitäts- und Betriebsmetriken für AI-Antworten.</p>
          </div>
          <span className="badge badge-ai" data-retrieval-slo-status>
            Noch nicht geladen
          </span>
        </div>
        <div className="dashboard-grid dashboard-grid-4">
          {RETRIEVAL_SLO_KPIS.map(([key, label, value]) => (
            <article className="metric-card" key={key}>
              <span>{label}</span>
              <strong data-retrieval-slo-kpi={key}>{value}</strong>
            </article>
          ))}
        </div>
        <div className="content-grid two-columns mt-4">
          <div className="stats-list" data-retrieval-slo-trends />
          <div className="stats-list" data-retrieval-slo-warnings />
        </div>
      </section>

      <section className="panel" data-retrieval-debug-panel>
        <div className="panel-header">
          <div>
            <h3>Quellenabruf Analyse</h3>
            <p className="panel-meta">
              Nur-Lese Nachvollziehbarkeit ohne Roh-Prompts, Antworten oder Textabschnitt-Volltexte.
            </p>
          </div>
          <div className="toolbar admin-ai-toolbar">
            <input className="input input-bordered" data-retrieval-debug-search placeholder="Quellenabruf-Fälle filtern" />
            <select className="input input-bordered" data-retrieval-debug-type aria-label="Nach Abfrage-Typ filtern">
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
            <button className="btn btn-secondary" type="button" data-retrieval-debug-refresh>
              Aktualisieren
            </button>
          </div>
        </div>

        <div className="ai-retrieval-inspector" data-retrieval-inspector>
          <div className="ai-retrieval-metrics" data-retrieval-analysis />
          <section className="retrieval-flow-panel" data-retrieval-flow-panel aria-label="AI Quellenabruf Ablauf">
            <div className="retrieval-flow-header">
              <div>
                <span className="section-kicker">Warum diese Antwort?</span>
                <h4>AI Quellenabruf Ablauf</h4>
                <p className="panel-meta">
                  Prompt-sichere Timeline vom Abfrage-Verständnis bis zur finalen Antwort.
                </p>
              </div>
              <div className="retrieval-flow-header-actions">
                <span className="badge badge-ai" data-retrieval-flow-status>
                  Noch nicht geladen
                </span>
                <span className="panel-meta" data-retrieval-flow-duration>
                  -
                </span>
              </div>
            </div>
            <div className="retrieval-flow-summary" data-retrieval-flow-summary />
            <div className="retrieval-flow-timeline" data-retrieval-flow-timeline />
            <div className="content-grid two-columns mt-4">
              <div className="retrieval-flow-source-map" data-retrieval-flow-source-map />
              <div className="retrieval-flow-answer" data-retrieval-flow-answer />
            </div>
          </section>
        </div>

        <div className="table-wrap">
          <table className="data-table">
            <caption>Prompt-sichere Quellenabruf-Debug-Daten mit Abfrage-Typ, Quellen, Sicherheit und Konflikten</caption>
            <thead>
              <tr>
                <th scope="col">Zeit</th>
                <th scope="col">Referenz</th>
                <th scope="col">Typ</th>
                <th scope="col">Quellen</th>
                <th scope="col">Sicherheit</th>
                <th scope="col">Konflikte</th>
                <th scope="col">Dauer</th>
                <th scope="col">Ablauf</th>
              </tr>
            </thead>
            <tbody data-retrieval-debug-rows />
          </table>
        </div>
      </section>

      <section className="panel" data-retrieval-evaluation-history-panel>
        <div className="panel-header">
          <div>
            <h3>Golden Eval Historie</h3>
            <p className="panel-meta">Regressionen und Qualitätstrends für bekannte Quellenabruf-Fragen.</p>
          </div>
          <div className="toolbar">
            <span className="badge badge-ai" data-retrieval-evaluation-status>
              Noch nicht geladen
            </span>
            <button className="btn btn-secondary" type="button" data-retrieval-evaluation-run>
              Golden Eval ausführen
            </button>
          </div>
        </div>
        <div className="dashboard-grid dashboard-grid-4">
          <article className="metric-card">
            <span>Recall@K</span>
            <strong data-retrieval-evaluation-kpi="recall_at_k">0%</strong>
          </article>
          <article className="metric-card">
            <span>MRR</span>
            <strong data-retrieval-evaluation-kpi="mrr">0%</strong>
          </article>
          <article className="metric-card">
            <span>nDCG@K</span>
            <strong data-retrieval-evaluation-kpi="ndcg_at_k">0%</strong>
          </article>
          <article className="metric-card">
            <span>Keine Treffer</span>
            <strong data-retrieval-evaluation-kpi="no_result_count">0</strong>
          </article>
        </div>
        <div className="content-grid two-columns mt-4">
          <div className="stats-list" data-retrieval-evaluation-regression />
          <div className="stats-list" data-retrieval-evaluation-runs />
        </div>
      </section>
    </section>
  );
}

/**
 * Render observability, workflow and prompt-debug hooks.
 */
function DiagnosticsSection(): ReactNode {
  return (
    <section className="ai-admin-area" id="ai-diagnostics" data-ai-admin-area="answers">
      <div className="ai-admin-area-header">
        <div>
          <span className="section-kicker">5. Diagnose</span>
          <h3>Fehler, Protokolle, Prompt-Debugging und Wissenslücken</h3>
          <p className="panel-meta">
            Admins sehen prompt-sichere Betriebsdiagnosen, letzte fehlgeschlagene Abfragen,
            Workflows, Wissenslücken und Debug-Blueprints.
          </p>
        </div>
        <div className="toolbar">
          <span className="badge badge-ai" data-ai-observability-status>
            Noch nicht geladen
          </span>
          <button className="btn btn-secondary" type="button" data-ai-observability-refresh>
            Monitoring aktualisieren
          </button>
        </div>
      </div>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h3>Letzte fehlgeschlagene AI-Abfragen</h3>
            <p className="panel-meta">Aus bestehenden Audit-Ereignissen abgeleitet; ohne Rohfrage oder Antworttext.</p>
          </div>
        </div>
        <div className="ai-failed-query-list" data-ai-failed-queries />
      </section>

      <section className="panel ai-answer-quality-panel">
        <div className="panel-header">
          <h3>Antwortqualität im Chat</h3>
          <span className="panel-meta">
            Jede Antwort zeigt Quellen, Sicherheit, Unsicherheit und verwendete Dokumente.
          </span>
        </div>
        <div className="ai-answer-quality-grid" data-ai-answer-quality-guide />
      </section>

      <section className="panel ai-observability-panel">
        <div className="panel-header">
          <div>
            <h3>KI-Metrik-Cockpit</h3>
            <p className="panel-meta">Latenz, Tokens, Fehler, leere Abrufe und Halluzinationswarnungen.</p>
          </div>
        </div>
        <div className="dashboard-grid dashboard-grid-4">
          {MONITORING_KPIS.map(([key, label, value]) => (
            <article className="metric-card" key={key}>
              <span>{label}</span>
              <strong data-ai-monitoring-kpi={key}>{value}</strong>
            </article>
          ))}
        </div>
        <div className="content-grid two-columns mt-4">
          <div className="ai-monitor-list" data-ai-top-questions />
          <div className="ai-monitor-list" data-ai-source-distribution />
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <h3>Quellenabruf Monitoring</h3>
          <span className="panel-meta">Top Treffer, schlechte Treffer, Textabschnitt-Nutzung und Dokumentverteilung.</span>
        </div>
        <div className="content-grid two-columns">
          <div className="ai-monitor-list" data-ai-top-hits />
          <div className="ai-monitor-list" data-ai-poor-hits />
        </div>
        <div className="content-grid two-columns mt-4">
          <div className="ai-monitor-list" data-ai-chunk-usage />
          <div className="ai-monitor-list" data-ai-quality-metrics />
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <h3>Workflow-Kosten und Fehler</h3>
          <span className="panel-meta">Metadata-only Auswertung ohne Prompt- oder Antworttexte</span>
        </div>
        <div className="content-grid two-columns">
          <div className="table-wrap">
            <table className="data-table">
              <caption>AI-Workflows nach Ereignissen, Fehlern, Ausweichbetrieb, Tokens und Kosten</caption>
              <thead>
                <tr>
                  <th scope="col">Workflow</th>
                  <th scope="col">Ereignisse</th>
                  <th scope="col">Ausweichbetrieb</th>
                  <th scope="col">Fehler</th>
                  <th scope="col">Tokens</th>
                  <th scope="col">Kosten</th>
                  <th scope="col">Latenz</th>
                </tr>
              </thead>
              <tbody data-ai-workflows />
            </table>
          </div>
          <div className="stats-list" data-ai-top-errors />
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <h3>Wissenslücken</h3>
          <span className="panel-meta" data-ai-knowledge-gap-count>
            0 offen
          </span>
        </div>
        <div className="table-wrap">
          <table className="data-table">
            <caption>Offene Wissenslücken aus KI-Fragen ohne belastbare Quellen</caption>
            <thead>
              <tr>
                <th scope="col">Referenz</th>
                <th scope="col">Bereich</th>
                <th scope="col">Maschine</th>
                <th scope="col">Status</th>
                <th scope="col">Treffer</th>
                <th scope="col">Zuletzt</th>
              </tr>
            </thead>
            <tbody data-ai-knowledge-gaps />
          </table>
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <h3>KI-Protokolle</h3>
          <span className="panel-meta">
            Prompt-sichere Referenz, Quellen, Sicherheit, Antwortqualität, Fehler und Dauer.
          </span>
        </div>
        <div className="table-wrap">
          <table className="data-table">
            <caption>AI-Monitoring-Protokolle mit Antwortqualität, Sicherheit und Quellen</caption>
            <thead>
              <tr>
                <th scope="col">Zeit</th>
                <th scope="col">Referenz</th>
                <th scope="col">Qualität</th>
                <th scope="col">Sicherheit</th>
                <th scope="col">Quellen</th>
                <th scope="col">Dauer</th>
                <th scope="col">Debug</th>
              </tr>
            </thead>
            <tbody data-ai-observability-logs />
          </table>
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <h3>Debug Tools</h3>
          <div className="toolbar">
            <select className="input input-bordered" data-ai-debug-request aria-label="AI-Anfrage analysieren" />
          </div>
        </div>
        <div className="content-grid two-columns">
          <div className="ai-monitor-list" data-ai-debug-analysis />
          <pre className="ai-debug-prompt" data-ai-debug-prompt>
            Kein Prompt-Blueprint geladen.
          </pre>
        </div>
      </section>
    </section>
  );
}

/**
 * Render reindex command, background job and operations hooks.
 */
function IndexingSection(): ReactNode {
  return (
    <section className="ai-admin-area" id="ai-indexing-status" data-ai-admin-area="jobs">
      <div className="ai-admin-area-header">
        <div>
          <span className="section-kicker">7. Indexstatus</span>
          <h3>Index-Aufbau, Textabschnitte, Vektoren und Verarbeitung-Jobs</h3>
          <p className="panel-meta">
            Reindex-Aktionen, Queue, Vektor-Sync und Textabschnitt-Abdeckung sichtbar getrennt vom
            normalen Antwortverhalten.
          </p>
        </div>
        <span className="badge badge-ai" data-ai-section-status="jobs">
          Jobs werden geladen
        </span>
      </div>

      <section className="panel ai-reindex-command-panel">
        <div className="panel-header">
          <div>
            <h3>Reindex-Kommandos</h3>
            <p className="panel-meta">Direkter Reindex blockiert den Request; Job einplanen nutzt die Background-Queue.</p>
          </div>
          <span className="panel-meta" data-ai-reindex-message />
        </div>
        <div className="ai-admin-actions">
          <button className="btn btn-primary" type="button" data-ai-reindex>
            Wissen neu indexieren
          </button>
          <button className="btn btn-secondary" type="button" data-ai-reindex-stale>
            Nur veraltete indexieren
          </button>
          <button className="btn btn-ghost" type="button" data-ai-queue-stale>
            Job einplanen
          </button>
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h3>Background Jobs</h3>
            <p className="panel-meta">RAG-Reindex und Wartungsdiagnose-Aufgaben mit Status und Ergebnis.</p>
          </div>
          <span className="panel-meta" data-ai-job-count>
            0 Jobs
          </span>
        </div>
        <div className="table-wrap">
          <table className="data-table">
            <caption>Background-Jobs für RAG-Reindex und Wartungsdiagnose</caption>
            <thead>
              <tr>
                <th scope="col">ID</th>
                <th scope="col">Typ</th>
                <th scope="col">Status</th>
                <th scope="col">Versuche</th>
                <th scope="col">Ergebnis</th>
              </tr>
            </thead>
            <tbody data-ai-jobs />
          </table>
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h3>Operationsdiagnose</h3>
            <p className="panel-meta">Queue, DB-Latenz, AI-Latenz, Jobdauer und langsame Endpoints.</p>
          </div>
          <span className="panel-meta" data-ops-generated>
            -
          </span>
        </div>
        <div className="dashboard-grid dashboard-grid-4">
          <article className="metric-card">
            <span>DB Latenz</span>
            <strong data-ops-kpi="database_latency_ms">0 ms</strong>
          </article>
          <article className="metric-card">
            <span>Queue</span>
            <strong data-ops-kpi="queue_length">0</strong>
          </article>
          <article className="metric-card">
            <span>Laufend</span>
            <strong data-ops-kpi="running_jobs">0</strong>
          </article>
          <article className="metric-card">
            <span>Fehlgeschlagen</span>
            <strong data-ops-kpi="failed_jobs">0</strong>
          </article>
          <article className="metric-card">
            <span>AI Latenz</span>
            <strong data-ops-kpi="ai_latency_ms">0 ms</strong>
          </article>
          <article className="metric-card">
            <span>RAG stale</span>
            <strong data-ops-kpi="rag_stale_ratio">0%</strong>
          </article>
          <article className="metric-card">
            <span>Ältester Job</span>
            <strong data-ops-kpi="oldest_queued_age">0 s</strong>
          </article>
          <article className="metric-card">
            <span>Job Dauer</span>
            <strong data-ops-kpi="job_avg_duration">0 s</strong>
          </article>
        </div>
        <div className="content-grid two-columns mt-4">
          <div className="stats-list" data-ai-job-status />
          <div className="stats-list" data-ops-slow-endpoints />
        </div>
      </section>
    </section>
  );
}

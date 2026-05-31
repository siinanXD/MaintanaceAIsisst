import { type ReactNode } from "react";

import {
  adminActionItems,
  businessMetricRows,
  kpiValue,
  modelHealthCard,
  overviewBadge,
  overviewHealthCards,
  overviewStatusCards,
  type AdminAiOverviewLoadState
} from "./adminAiOverviewModel";
import { HealthMetricCard, healthCard } from "./AdminAiOverviewShared";

const KPI_ITEMS = [
  ["events_total", "Ereignisse"],
  ["fallback_rate", "Ausweichantworten"],
  ["error_rate", "Fehler-Rate"],
  ["average_latency_ms", "AI Latenz"],
  ["total_tokens", "Tokens"],
  ["estimated_cost_usd", "Kosten USD"],
  ["cache_rate", "Cache-Rate"],
  ["cost_per_1k_tokens", "Kosten / 1k"]
] as const;

/**
 * Render the explanatory Admin-AI overview intro.
 */
export function AdminAiOverviewIntro(): ReactNode {
  return (
    <section className="context-help ai-workflow-help" aria-label="So arbeitet die KI">
      <strong>So arbeitet die KI</strong>
      <ol className="next-step-list">
        <li><strong>Frage verstehen:</strong> Absicht, Maschine, Fehlercode und Bereich erkennen.</li>
        <li><strong>Daten suchen:</strong> Strukturierte App-Daten und freigegebene Dokument-Textabschnitte abrufen.</li>
        <li><strong>Kontext bauen:</strong> Quellen sortieren, kürzen und mit Sicherheit bewerten.</li>
        <li><strong>Sicherheit prüfen:</strong> riskante Aussagen markieren oder entschärfen.</li>
        <li><strong>Antwort liefern:</strong> Ergebnis mit Quellen, Unsicherheit und nächsten Schritten anzeigen.</li>
      </ol>
      <details className="help-disclosure">
        <summary>Was bedeuten RAG, Embeddings und Quellenabruf?</summary>
        <p>
          Quellenabruf ist die Suche nach passenden Quellen. RAG bedeutet, dass diese Quellen in
          die Antwort einfließen. Embeddings sind technische Suchvektoren; sie müssen vorhanden
          sein, damit Dokumente semantisch gefunden werden.
        </p>
      </details>
    </section>
  );
}

/**
 * Render status, clarity, health and KPI panels for the overview.
 */
export function AdminAiOverviewStatus({ overviewState }: { readonly overviewState: AdminAiOverviewLoadState }): ReactNode {
  const statusBadge = overviewBadge(overviewState);
  const healthCards = overviewHealthCards(overviewState);
  const modelCard = modelHealthCard(overviewState);
  const actionItems = adminActionItems(overviewState);
  const businessMetrics = businessMetricRows(overviewState);

  return (
    <>
      <div className="ai-admin-area-header">
        <div>
          <span className="section-kicker">1. Modelle</span>
          <h3>Welche Modelle, Anbieter und Betriebsmodi sind aktiv?</h3>
          <p className="panel-meta">
            Status, Modellkonfiguration, lokaler Ausweichbetrieb, Kosten- und Laufzeitmetriken in
            einer kompakten Betriebsansicht.
          </p>
        </div>
        <span className={`badge badge-ai ${statusBadge.tone}`} data-ai-section-status="status">
          {statusBadge.label}
        </span>
      </div>

      <div className="ai-section-guide" aria-label="Status und Betriebsmodus Hinweise">
        <article><span>Was beeinflusst das?</span><strong>Generierte Antworten, Kosten, Latenz, Streaming, lokale Ausweichbetriebe und Modellfehler.</strong></article>
        <article><span>Wann prüfen?</span><strong>Wenn Anbieter nicht bereit ist, Latenz steigt, Ausweichbetriebe zunehmen oder Modellfreigaben fehlen.</strong></article>
        <article><span>Betroffen</span><strong><code>/api/v1/ai/status</code> <code>/api/v1/admin/ai/summary</code>{" "}<code>/api/v1/health/operations</code></strong></article>
      </div>
      <p className="ai-section-explain">
        Modelle ist der schnelle Betriebscheck: Erst wenn Anbieter, Modellstatus und
        Ausweichbetrieb-Verhalten plausibel sind, lohnt sich Detailanalyse in Quellenabruf,
        Quellen und Indexierung.
      </p>

      <div className="ai-status-overview" data-ai-status-overview aria-label="AI Funktionsstatus">
        {overviewStatusCards(overviewState).map(({ detail, key, label, tone, value }) => (
          <article className={`ai-status-overview-card ${tone}`} data-ai-status-overview-item={key} key={key}>
            <span>{label}</span>
            <strong data-ai-status-overview-label>{value}</strong>
            <small data-ai-status-overview-detail>{detail}</small>
          </article>
        ))}
      </div>

      <section className="panel ai-clarity-panel admin-control-action-summary" data-ai-admin-control-center>
        <div className="panel-header">
          <div>
            <h3>Handlungsbedarf</h3>
            <p className="panel-meta">
              Admin-Aktionen aus vorhandenen Status-, Kosten-, Feedback-, Quellen- und Jobdaten.
            </p>
          </div>
          <span className={`status-pill ${actionItems[0]?.tone || "is-muted"}`}>
            {actionItems[0]?.key === "none" ? "Keine Aktion" : `${actionItems.length} offen`}
          </span>
        </div>
        <div className="document-card-grid">
          {actionItems.map((item) => (
            <article className={`document-card ${item.tone}`} key={item.key}>
              <span>{item.label}</span>
              <strong>{item.key === "none" ? "OK" : "Prüfen"}</strong>
              <small>{item.detail}</small>
            </article>
          ))}
        </div>
      </section>

      <section className="panel ai-status-panel" data-ai-business-metrics>
        <div className="panel-header">
          <div>
            <h3>Business metrics</h3>
            <p className="panel-meta">
              Source health, Antworten ohne Quellen, Low Confidence, Feedback, Tokens, Kosten und Nutzung.
            </p>
          </div>
        </div>
        <div className="dashboard-grid dashboard-grid-4">
          {businessMetrics.map((item) => (
            <article className="metric-card" key={item.label}>
              <span>{item.label}</span>
              <strong>{item.value}</strong>
            </article>
          ))}
        </div>
      </section>

      <section className="panel ai-clarity-panel">
        <div className="panel-header">
          <div>
            <h3>KI-Administration Überblick</h3>
            <p className="panel-meta">Die wichtigsten Betriebsfragen auf einen Blick: Quellen, Textabschnitte, Training, fehlgeschlagene Fragen, geblockte Quellen und Feedback.</p>
          </div>
          <span className={`status-pill ${statusBadge.tone}`} data-ai-clarity-state>{statusBadge.label}</span>
        </div>
        <div className="ai-clarity-grid" data-ai-clarity-summary aria-label="KI-Administration Überblick" />
        <div className="ai-clarity-detail-grid mt-4">
          <div className="stats-list" data-ai-indexed-source-summary />
          <div className="stats-list" data-ai-active-chunk-summary />
          <div className="stats-list" data-ai-training-summary />
          <div className="stats-list" data-ai-failure-summary />
          <div className="stats-list" data-ai-blocked-source-summary />
          <div className="stats-list" data-ai-feedback-summary />
        </div>
      </section>

      <section className="panel ai-status-panel" data-ai-health-panel>
        <div className="panel-header"><h3>Systemstatus</h3><span className="panel-meta">KI-Anbieter, Modell, Dokumentensuche und Queue</span></div>
        <div className="dashboard-grid dashboard-grid-4">
          <HealthMetricCard card={healthCard(healthCards, "ai")} title="AI Betrieb" />
          <HealthMetricCard card={healthCard(healthCards, "rag")} title="Dokumentensuche" />
          <HealthMetricCard card={healthCard(healthCards, "queue")} title="Job Queue" />
          <article className={`metric-card ai-status-card ${modelCard.tone}`} data-ai-model-card>
            <span>Modellstatus</span>
            <strong data-ai-model-status>{modelCard.label}</strong>
            <small data-ai-model-detail>{modelCard.detail}</small>
          </article>
        </div>
      </section>

      <div className="dashboard-grid dashboard-grid-4 ai-admin-kpi-grid" data-ai-kpis>
        {KPI_ITEMS.map(([key, label]) => (
          <article className="metric-card" key={key}>
            <span>{label}</span>
            <strong data-ai-kpi={key}>{kpiValue(overviewState.summary, key)}</strong>
          </article>
        ))}
      </div>
    </>
  );
}

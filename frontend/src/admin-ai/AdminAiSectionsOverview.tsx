import { type ReactNode } from "react";

import {
  kpiValue,
  modelHealthCard,
  overviewBadge,
  overviewHealthCards,
  overviewStatusCards,
  providerActionRows,
  providerDetailRows,
  providerFields,
  type AdminAiHealthCard,
  type AdminAiOverviewLoadState,
  type AdminAiStatRow
} from "./adminAiOverviewModel";

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

type AdminAiOverviewProps = {
  readonly onChatQueryChange: (value: string) => void;
  readonly onEventErrorChange: (value: string) => void;
  readonly overviewChatQuery: string;
  readonly overviewEventError: string;
  readonly overviewState: AdminAiOverviewLoadState;
};

/**
 * Render the Admin-AI overview cockpit markup.
 */
export function AdminAiOverview({
  onChatQueryChange,
  onEventErrorChange,
  overviewChatQuery,
  overviewEventError,
  overviewState
}: AdminAiOverviewProps): ReactNode {
  const statusBadge = overviewBadge(overviewState);
  const healthCards = overviewHealthCards(overviewState);
  const modelCard = modelHealthCard(overviewState);
  const providerSummaryTone =
    overviewState.aiStatus && overviewState.aiStatus.ready !== false ? "is-active" : "is-stale";

  return (
    <>
      <section className="context-help ai-workflow-help" aria-label="So arbeitet die KI">
        <strong>So arbeitet die KI</strong>
        <ol className="next-step-list">
          <li>
            <strong>Frage verstehen:</strong> Absicht, Maschine, Fehlercode und Bereich erkennen.
          </li>
          <li>
            <strong>Daten suchen:</strong> Strukturierte App-Daten und freigegebene
            Dokument-Textabschnitte abrufen.
          </li>
          <li>
            <strong>Kontext bauen:</strong> Quellen sortieren, kürzen und mit Sicherheit bewerten.
          </li>
          <li>
            <strong>Sicherheit prüfen:</strong> riskante Aussagen markieren oder entschärfen.
          </li>
          <li>
            <strong>Antwort liefern:</strong> Ergebnis mit Quellen, Unsicherheit und nächsten
            Schritten anzeigen.
          </li>
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

      <section className="ai-admin-area" id="ai-models" data-ai-admin-area="overview">
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
          <article>
            <span>Was beeinflusst das?</span>
            <strong>
              Generierte Antworten, Kosten, Latenz, Streaming, lokale Ausweichbetriebe und
              Modellfehler.
            </strong>
          </article>
          <article>
            <span>Wann prüfen?</span>
            <strong>
              Wenn Anbieter nicht bereit ist, Latenz steigt, Ausweichbetriebe zunehmen oder
              Modellfreigaben fehlen.
            </strong>
          </article>
          <article>
            <span>Betroffen</span>
            <strong>
              <code>/api/v1/ai/status</code> <code>/api/v1/admin/ai/summary</code>{" "}
              <code>/api/v1/health/operations</code>
            </strong>
          </article>
        </div>
        <p className="ai-section-explain">
          Modelle ist der schnelle Betriebscheck: Erst wenn Anbieter, Modellstatus und
          Ausweichbetrieb-Verhalten plausibel sind, lohnt sich Detailanalyse in Quellenabruf,
          Quellen und Indexierung.
        </p>

        <div className="ai-status-overview" data-ai-status-overview aria-label="AI Funktionsstatus">
          {overviewStatusCards(overviewState).map(({ detail, key, label, tone, value }) => (
            <article
              className={`ai-status-overview-card ${tone}`}
              data-ai-status-overview-item={key}
              key={key}
            >
              <span>{label}</span>
              <strong data-ai-status-overview-label>{value}</strong>
              <small data-ai-status-overview-detail>{detail}</small>
            </article>
          ))}
        </div>

        <section className="panel ai-clarity-panel">
          <div className="panel-header">
            <div>
              <h3>KI-Administration Überblick</h3>
              <p className="panel-meta">
                Die wichtigsten Betriebsfragen auf einen Blick: Quellen, Textabschnitte, Training,
                fehlgeschlagene Fragen, geblockte Quellen und Feedback.
              </p>
            </div>
            <span className={`status-pill ${statusBadge.tone}`} data-ai-clarity-state>
              {statusBadge.label}
            </span>
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
          <div className="panel-header">
            <h3>Systemstatus</h3>
            <span className="panel-meta">KI-Anbieter, Modell, Dokumentensuche und Queue</span>
          </div>
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

        <div className="content-grid two-columns">
          <section className="panel">
            <div className="panel-header">
              <div>
                <h3>Letzte AI-Fehler</h3>
                <p className="panel-meta">
                  Metadata-only Audit-Ereignisse zum Eingrenzen von Anbieter-, Modell- und
                  Timeout-Problemen.
                </p>
              </div>
              <select className="input input-bordered" data-ai-event-error value={overviewEventError} onChange={(event) => onEventErrorChange(event.target.value)}>
                <option value="">Alle Fehler</option>
                <option value="rate_limit">Rate Limit</option>
                <option value="model_not_allowed">Modell nicht erlaubt</option>
                <option value="authentication_error">Key ungültig</option>
                <option value="connection_error">Verbindung</option>
                <option value="timeout">Timeout</option>
              </select>
            </div>
            <div className="table-wrap">
              <table className="data-table">
                <caption>Letzte KI-Ereignisse mit Status, Fehlerart und Tokenverbrauch</caption>
                <thead>
                  <tr>
                    <th scope="col">Zeit</th>
                    <th scope="col">Workflow</th>
                    <th scope="col">Status</th>
                    <th scope="col">Fehler</th>
                    <th scope="col">Tokens</th>
                  </tr>
                </thead>
                <tbody data-ai-events>
                  {overviewState.events.length ? overviewState.events.map((eventItem) => (
                    <tr key={displayText(eventItem.id || `${eventItem.created_at}-${eventItem.workflow}`)}>
                      <td>{displayText(eventItem.created_at)}</td>
                      <td>{displayText(eventItem.workflow)}</td>
                      <td>{displayText(eventItem.status)}</td>
                      <td>{displayText(eventItem.error_category)}</td>
                      <td>{numberText(eventItem.total_tokens)}</td>
                    </tr>
                  )) : (
                    <tr>
                      <td colSpan={5}>
                        <span className="empty-state">Keine AI-Fehler für diesen Filter.</span>
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>

          <section className="panel">
            <div className="panel-header">
              <div>
                <h3>Letzte AI-Anfragen</h3>
                <p className="panel-meta">
                  Schneller Blick auf reale Chat-Nutzung und betroffene Workflows.
                </p>
              </div>
              <input className="input input-bordered" data-ai-chat-search placeholder="Chats durchsuchen" value={overviewChatQuery} onChange={(event) => onChatQueryChange(event.target.value)} />
            </div>
            <div className="stack" data-ai-chats>
              {overviewState.chats.length ? overviewState.chats.map((chat) => (
                <article className="list-card" key={displayText(chat.id)}>
                  <strong>{recordReference("Chat", chat.id)}</strong>
                  <p>{displayText(chat.message, "Frage und Antwort sind in dieser Übersicht ausgeblendet.")}</p>
                  <small>
                    {[
                      `Typ ${displayText(chat.response_type)}`,
                      `Quellen ${numberText(chat.source_count)}`,
                      `Workflow ${displayText(chat.workflow)}`
                    ].join(" / ")}
                  </small>
                </article>
              )) : <p className="empty-state">Keine AI-Anfragen für diese Suche.</p>}
            </div>
          </section>
        </div>

        <section className="panel ai-provider-panel">
          <div className="panel-header">
            <div>
              <h3>Anbieter- und Modell-Momentaufnahme</h3>
              <p className="panel-meta">
                Diese Ansicht ändert keine Secrets. Anbieter- und Modellwechsel laufen über
                Umgebungskonfiguration.
              </p>
            </div>
            <span className={`status-pill ${providerSummaryTone}`} data-ai-provider-summary>
              {overviewState.aiStatus && overviewState.aiStatus.ready !== false
                ? "Provider bereit"
                : "Provider checken"}
            </span>
          </div>
          <div className="dashboard-grid dashboard-grid-4">
            {providerFields(overviewState).map(({ detail, key, label, value }) => (
              <article className="metric-card ai-provider-card" key={key}>
                <span>{label}</span>
                <strong data-ai-provider-field={key}>{value}</strong>
                <small>{detail}</small>
              </article>
            ))}
          </div>
          <div className="content-grid two-columns mt-4">
            <StatRows rows={providerDetailRows(overviewState)} target="details" />
            <StatRows rows={providerActionRows(overviewState)} target="actions" />
          </div>
        </section>
      </section>
    </>
  );
}

/**
 * Return a safe display string for Admin-AI overview cells.
 */
function displayText(value: unknown, fallback = "-"): string {
  if (typeof value === "string" && value.trim()) return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return fallback;
}

/**
 * Format numeric Admin-AI overview values.
 */
function numberText(value: unknown): string {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed.toLocaleString("de-DE") : displayText(value);
}

/**
 * Return a prompt-safe record reference label.
 */
function recordReference(prefix: string, id: unknown): string {
  const value = displayText(id, "");
  return value ? `${prefix} #${value}` : prefix;
}

/**
 * Return a health card by key with the legacy loading fallback.
 */
function healthCard(cards: readonly AdminAiHealthCard[], key: string): AdminAiHealthCard {
  return (
    cards.find((card) => card.key === key) ?? {
      key,
      label: "--",
      detail: "Noch nicht geladen",
      tone: "is-muted"
    }
  );
}

/**
 * Render one existing health metric card.
 */
function HealthMetricCard({
  card,
  title
}: {
  readonly card: AdminAiHealthCard;
  readonly title: string;
}): ReactNode {
  return (
    <article className={`metric-card ai-status-card ${card.tone}`} data-ai-health={card.key}>
      <span>{title}</span>
      <strong data-ai-health-label>{card.label}</strong>
      <small data-ai-health-detail>{card.detail}</small>
    </article>
  );
}

/**
 * Render Admin-AI stat rows into the existing stats-list markup.
 */
function StatRows({
  rows,
  target
}: {
  readonly rows: readonly AdminAiStatRow[];
  readonly target: "actions" | "details";
}): ReactNode {
  return (
    <div
      className="stats-list"
      data-ai-provider-actions={target === "actions" ? true : undefined}
      data-ai-provider-details={target === "details" ? true : undefined}
    >
      {rows.map((row) => (
        <div className="stat-row" key={`${row.label}:${row.value}`}>
          <span>{row.label}</span>
          <strong>{row.value}</strong>
        </div>
      ))}
    </div>
  );
}

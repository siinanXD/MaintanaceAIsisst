import { type ReactNode } from "react";

type TechnicalSignalCardProps = {
  readonly className: string;
  readonly contentClassName: string;
  readonly description: string;
  readonly emptyText: string;
  readonly hookName: string;
  readonly title: string;
  readonly action?: ReactNode;
};

type IndexStatusRowProps = {
  readonly label: string;
  readonly value: string;
  readonly meta: string;
  readonly valueHook: string;
  readonly metaHook?: string;
};

const AI_SIGNAL_CARDS: readonly TechnicalSignalCardProps[] = [
  {
    className: "ai-priority-panel",
    contentClassName: "ai-priority-rail",
    description: "Kritische Fehler, Sicherheit, Gaps und Quellenrisiken.",
    emptyText: "AI Operations Signale werden geladen.",
    hookName: "data-ai-ops-priority-rail",
    title: "Prioritätslage",
  },
  {
    className: "ai-system-panel",
    contentClassName: "ai-system-rail",
    description: "Nur-Lese Betriebszustand ohne Promptinhalte.",
    emptyText: "Systemstatus wird geladen.",
    hookName: "data-ai-system-rail",
    title: "AI Systemstatus",
    action: (
      <a data-dashboard-nav="admin_users" hidden href="/admin/ai">
        Details
      </a>
    ),
  },
  {
    className: "ai-risk-panel",
    contentClassName: "ai-risk-grid",
    description: "Sicherheit, Fallbacks und Feedback.",
    emptyText: "Risk Radar wird geladen.",
    hookName: "data-ai-risk-radar",
    title: "AI Risk Radar",
  },
  {
    className: "ai-knowledge-panel",
    contentClassName: "ai-knowledge-health",
    description: "Index, Quellen und Wissenslücken.",
    emptyText: "Wissensstatus wird geladen.",
    hookName: "data-ai-knowledge-health",
    title: "Quellen & Wissensstatus",
  },
];

const INDEX_STATUS_ROWS: readonly IndexStatusRowProps[] = [
  {
    label: "Dokument-/Index-Status",
    value: "--",
    meta: "Index-Sync",
    valueHook: "data-dashboard-index-status",
    metaHook: "data-dashboard-index-status-meta",
  },
  {
    label: "Wissenslücken",
    value: "0",
    meta: "Offene Lücken",
    valueHook: "data-dashboard-knowledge-gap-count",
    metaHook: "data-dashboard-knowledge-gap-meta",
  },
  {
    label: "Suchzeit P95",
    value: "--",
    meta: "P95 und Quellenrate",
    valueHook: "data-dashboard-retrieval-health",
    metaHook: "data-dashboard-retrieval-health-meta",
  },
  {
    label: "Niedrige Sicherheit",
    value: "0%",
    meta: "Antwortqualität",
    valueHook: "data-dashboard-low-confidence-count",
  },
];

/**
 * Convert a data attribute name into a React-compatible dynamic prop.
 */
function createDataHook(hookName: string): Record<string, string> {
  return { [hookName]: "" };
}

/**
 * Render one AI signal panel while preserving the legacy data hook.
 */
function TechnicalSignalCard({
  action,
  className,
  contentClassName,
  description,
  emptyText,
  hookName,
  title,
}: TechnicalSignalCardProps): ReactNode {
  return (
    <article className={`ops-panel app-card ${className}`}>
      <header className="ops-panel-header">
        <div>
          <h2>{title}</h2>
          <p className="panel-meta">{description}</p>
        </div>
        {action}
      </header>
      <div className={contentClassName} {...createDataHook(hookName)}>
        <div className="empty-state">{emptyText}</div>
      </div>
    </article>
  );
}

/**
 * Render one document and retrieval health row with its runtime hook.
 */
function IndexStatusRow({ label, meta, metaHook, value, valueHook }: IndexStatusRowProps): ReactNode {
  return (
    <div className="ai-system-row is-muted">
      <span>{label}</span>
      <strong {...createDataHook(valueHook)}>{value}</strong>
      {metaHook ? <small {...createDataHook(metaHook)}>{meta}</small> : <small>{meta}</small>}
    </div>
  );
}

/**
 * Render the collapsible technical dashboard status area.
 */
export function DashboardTechnicalDetails(): ReactNode {
  return (
    <details className="section-disclosure control-center-technical">
      <summary>
        <span>
          <strong>Technische Details und Quellenstatus</strong>
          <small>AI-, Index- und Admin-Signale bleiben sichtbar, dominieren aber nicht die operative Lage.</small>
        </span>
      </summary>
      <section className="ai-ops-command-grid" aria-label="AI Operations Signale">
        {AI_SIGNAL_CARDS.map((card) => (
          <TechnicalSignalCard key={card.hookName} {...card} />
        ))}
      </section>

      <section className="ops-dashboard-grid" aria-label="Weitere Statusdetails">
        <article className="ops-panel app-card">
          <header className="ops-panel-header">
            <h2>Warnsignale</h2>
            <a data-dashboard-nav="errors" hidden href="/errors">
              Störungen
            </a>
          </header>
          <div className="activity-feed is-warning-feed" data-dashboard-warning-feed="">
            <div className="empty-state">Warnsignale werden geladen.</div>
          </div>
        </article>
        <article className="ops-panel app-card">
          <header className="ops-panel-header">
            <h2>Dokument-/Indexstatus</h2>
            <a data-dashboard-nav="documents" hidden href="/documents">
              Dokumente
            </a>
          </header>
          <div className="ai-knowledge-health">
            {INDEX_STATUS_ROWS.map((row) => (
              <IndexStatusRow key={row.valueHook} {...row} />
            ))}
          </div>
        </article>
      </section>
    </details>
  );
}

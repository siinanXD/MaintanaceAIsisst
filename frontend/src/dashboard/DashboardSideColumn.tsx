import { type ReactNode } from "react";

/**
 * Render the daily briefing card with the existing dashboard runtime hooks.
 */
function DailyBriefingCard(): ReactNode {
  return (
    <article className="ops-panel app-card daily-briefing" id="daily-briefing" data-daily-briefing-card="">
      <header className="ops-panel-header">
        <div>
          <p className="section-kicker">Kurzlage</p>
          <h2>Tagesbriefing</h2>
          <p className="panel-meta">Automatisch verdichtete Lage.</p>
        </div>
        <span className="ai-label">AI</span>
      </header>
      <p className="briefing-summary" data-daily-briefing-summary="">
        Kurzlage wird geladen.
      </p>
      <div className="briefing-list" data-daily-briefing-list="">
        <div className="briefing-item is-warning">
          <span>AI</span>
          <strong>Kurzlage wird geladen</strong>
          <small>Bitte kurz warten.</small>
        </div>
      </div>
    </article>
  );
}

/**
 * Render the activity feed card with the existing dashboard runtime hook.
 */
function ActivityFeedCard(): ReactNode {
  return (
    <article className="ops-panel app-card">
      <header className="ops-panel-header">
        <div>
          <p className="section-kicker">Verlauf</p>
          <h2>Aktivit&auml;tsverlauf</h2>
          <p className="panel-meta">Neue Aufgaben, Fehler und Briefing-Signale.</p>
        </div>
      </header>
      <div className="activity-feed" data-dashboard-activity-feed="">
        <div className="empty-state">Aktivit&auml;ten werden geladen.</div>
      </div>
    </article>
  );
}

/**
 * Render the inventory hints card with the existing dashboard runtime hooks.
 */
function InventoryHintsCard(): ReactNode {
  return (
    <article className="ops-panel app-card">
      <header className="ops-panel-header">
        <div>
          <p className="section-kicker">Material</p>
          <h2>Lagerhinweise</h2>
          <p className="panel-meta">
            Kritische Teile und Engp&auml;sse f&uuml;r laufende Arbeit.
          </p>
        </div>
        <a data-dashboard-nav="inventory" hidden href="/inventory">
          Lager
        </a>
      </header>
      <div className="inventory-stats" data-dashboard-inventory-stats="">
        <div>
          <strong>Kritisch</strong>
          <span>--</span>
          <small>Artikel</small>
        </div>
      </div>
      <div
        className="shortage-tags"
        aria-label="Top Engp&auml;sse"
        data-dashboard-inventory-shortages=""
      >
        <span>Lagerdaten werden geladen.</span>
      </div>
    </article>
  );
}

/**
 * Render the dashboard side column as React-owned markup.
 */
export function DashboardSideColumn(): ReactNode {
  return (
    <aside className="control-center-side-column" aria-label="Briefing und Aktivitaet">
      <DailyBriefingCard />
      <ActivityFeedCard />
      <InventoryHintsCard />
    </aside>
  );
}

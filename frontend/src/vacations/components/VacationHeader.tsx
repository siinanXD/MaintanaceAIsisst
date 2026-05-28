import type { ReactNode } from "react";

import type { VacationRequest, VacationSummary } from "../vacationTypes";

type VacationHeaderProps = {
  readonly requests: readonly VacationRequest[];
  readonly selectedBalance: VacationSummary | null;
  readonly summaries: readonly VacationSummary[];
};

/**
 * Render the vacations page hero.
 */
export function VacationHeader(): ReactNode {
  return (
    <section className="page-hero vacation-hero">
      <div>
        <p className="page-kicker">Personalplanung</p>
        <h1 className="page-title">Urlaubsplanung</h1>
        <p className="page-description">Anträge, Vertreter, Schichtbezug und Auswirkungen auf den Betrieb in einer gemeinsamen Planungsansicht.</p>
      </div>
      <div className="vacation-hero-actions" aria-label="Schnellaktionen">
        <a className="btn btn-primary btn-sm" href="#vacation-request">Urlaub beantragen</a>
        <a className="btn btn-outline btn-sm" href="#vacation-decisions">Offene Anträge prüfen</a>
      </div>
    </section>
  );
}

/**
 * Render vacation KPI cards.
 */
export function VacationStats({ requests, selectedBalance, summaries }: VacationHeaderProps): ReactNode {
  const pendingRequests = requests.filter((request) => request.status === "pending");
  const riskyRequests = requests.filter((request) => ["pending", "approved"].includes(request.status || "") && ["warning", "critical"].includes(request.impact_level || ""));
  const usedTotal = summaries.reduce((sum, summary) => sum + Number(summary.used || 0), 0);
  const pendingTotal = summaries.reduce((sum, summary) => sum + Number(summary.pending || 0), 0);

  return (
    <section className="vacation-control-strip" aria-label="Urlaubskennzahlen">
      <article className="vacation-control-stat is-warning">
        <span>Ausstehend</span>
        <strong data-vac-pending-count>{pendingRequests.length}</strong>
        <small>Anträge zur Entscheidung</small>
      </article>
      <article className="vacation-control-stat is-risk">
        <span>Konflikte</span>
        <strong data-vac-conflict-count>{riskyRequests.length}</strong>
        <small>Unterbesetzung oder Schichttreffer</small>
      </article>
      <article className="vacation-control-stat is-good">
        <span>Verfügbar</span>
        <strong data-vac-selected-available>{selectedBalance ? String(selectedBalance.available || 0) : "-"}</strong>
        <small>für ausgewählte Person</small>
      </article>
      <article className="vacation-control-stat is-info">
        <span>Genehmigt</span>
        <strong data-vac-used-total>{usedTotal || "-"}</strong>
        <small>genutzte Tage im Jahr</small>
      </article>
      <article className="vacation-control-stat is-muted">
        <span>Reserviert</span>
        <strong data-vac-pending-total>{pendingTotal || "-"}</strong>
        <small>durch offene Anträge</small>
      </article>
    </section>
  );
}

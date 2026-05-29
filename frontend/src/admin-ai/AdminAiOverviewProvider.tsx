import { type ReactNode } from "react";

import {
  providerActionRows,
  providerDetailRows,
  providerFields,
  type AdminAiOverviewLoadState
} from "./adminAiOverviewModel";
import { StatRows } from "./AdminAiOverviewShared";

/**
 * Render the provider and model configuration snapshot panel.
 */
export function AdminAiOverviewProvider({ overviewState }: { readonly overviewState: AdminAiOverviewLoadState }): ReactNode {
  const providerSummaryTone = overviewState.aiStatus && overviewState.aiStatus.ready !== false ? "is-active" : "is-stale";

  return (
    <section className="panel ai-provider-panel">
      <div className="panel-header">
        <div>
          <h3>Anbieter- und Modell-Momentaufnahme</h3>
          <p className="panel-meta">Diese Ansicht ändert keine Secrets. Anbieter- und Modellwechsel laufen über Umgebungskonfiguration.</p>
        </div>
        <span className={`status-pill ${providerSummaryTone}`} data-ai-provider-summary>
          {overviewState.aiStatus && overviewState.aiStatus.ready !== false ? "Provider bereit" : "Provider checken"}
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
  );
}

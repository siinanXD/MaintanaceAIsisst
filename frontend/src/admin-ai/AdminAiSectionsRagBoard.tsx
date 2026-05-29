import { type ChangeEvent, type FormEvent, type MouseEvent, type ReactNode } from "react";

import { type AdminAiPayload } from "./adminAiApi";
import {
  AdminAiSourceTestPanel,
  type AdminAiSourceCheckProps
} from "./AdminAiSectionsSourceCheck";
import {
  type AdminAiRagBoardFilters,
  type AdminAiRagBoardState,
  type AdminAiTrainingForm,
  EMPTY_TRAINING_FORM,
  QUALITY_STATUSES,
  RAG_SOURCE_DEFINITIONS,
  lifecycleKpiValue,
  lifecycleStatus,
  networkTypeLabel,
  objectPayload,
  qualityStatusClass,
  qualityStatusLabel,
  ragDateTime,
  ragReadinessLabel,
  ragText,
  sourceHealth,
  sourceMetrics,
  sourceTypeLabel,
  truncateLabel,
  vectorStatus
} from "./adminAiRagBoardModel";
import { numberText } from "./adminAiEffectivenessModel";

const QUALITY_OPTIONS = [
  ["", "Alle Qualitätsstatus"],
  ...QUALITY_STATUSES.map((status) => [status, qualityStatusLabel(status)] as const)
] as const;

const SOURCE_OPTIONS = [
  ["", "Alle Quellen"],
  ["upload", "Hochladungen"],
  ["manual_training", "Manuelles Training"],
  ["generated_document", "Berichte"],
  ["error_entry", "Fehlerkatalog"],
  ["task", "Aufgaben"],
  ["machine", "Maschinen"],
  ["inventory_material", "Inventar"],
  ["maintenance_plan", "Wartungspläne"],
  ["machine_manual", "Maschinenhandbücher"],
  ["shift_handover", "Schichtübergaben"]
] as const;

type AdminAiRagBoardProps = AdminAiSourceCheckProps & {
  readonly onDeleteKnowledge: (documentId: number) => void;
  readonly onDeleteTraining: (entryId: number) => void;
  readonly onKnowledgeFilterChange: (key: keyof AdminAiRagBoardFilters, value: string) => void;
  readonly onKnowledgeUpload: (form: HTMLFormElement) => void;
  readonly onNetworkFilterChange: (key: keyof AdminAiRagBoardFilters, value: string) => void;
  readonly onQueueDocument: (documentId: number) => void;
  readonly onQueueStale: () => void;
  readonly onReindexAll: () => void;
  readonly onReindexDocument: (documentId: number) => void;
  readonly onReindexStale: () => void;
  readonly onSaveTraining: (form: AdminAiTrainingForm) => void;
  readonly onSelectTraining: (entry: AdminAiPayload) => void;
  readonly onTrainingFilterChange: (key: keyof AdminAiRagBoardFilters, value: string) => void;
  readonly onTrainingFormChange: (form: AdminAiTrainingForm) => void;
  readonly onUpdateKnowledgeQuality: (documentId: number, qualityStatus: string) => void;
  readonly ragBoardState: AdminAiRagBoardState;
};

/**
 * Render the RAG board, knowledge, training and source maintenance areas.
 */
export function AdminAiRagBoard(props: AdminAiRagBoardProps): ReactNode {
  const { ragBoardState } = props;

  return (
    <>
      <section className="ai-admin-area rag-board-area rag-game-shell" id="ai-rag-board" data-ai-admin-area="rag-board">
        <RagHealthStrip state={ragBoardState} />
        <SourceHealthBoard state={ragBoardState} />
        <section className="panel mt-4">
          <div className="panel-header">
            <div>
              <h3>RAG-Pflegeaktionen</h3>
              <p className="panel-meta" data-ai-reindex-message>
                {ragBoardState.statusMessage || "Quelle -> Textabschnitte -> Vektoren -> Suchbar -> Getestet"}
              </p>
            </div>
            <div className="toolbar">
              <button
                className="btn btn-secondary btn-sm"
                disabled={ragBoardState.isSaving}
                type="button"
                data-ai-queue-stale
                onClick={props.onQueueStale}
              >
                Job planen
              </button>
              <button
                className="btn btn-primary btn-sm"
                disabled={ragBoardState.isSaving}
                type="button"
                data-ai-reindex-stale
                onClick={props.onReindexStale}
              >
                Reindex
              </button>
            </div>
          </div>
          {ragBoardState.errorMessage ? <p className="panel-meta text-error">{ragBoardState.errorMessage}</p> : null}
        </section>
        <section className="panel mt-4">
          <div className="panel-header">
            <h3>Quellen-Arena</h3>
            <span className="panel-meta">Testfrage direkt gegen aktuelle Quellen prüfen</span>
          </div>
          <AdminAiSourceTestPanel {...props} />
        </section>
      </section>

      <section className="ai-admin-area" id="ai-knowledge-sources" data-ai-admin-area="data-sources">
        <div className="ai-admin-area-header">
          <div>
            <span className="section-kicker">3. Wissensquellen</span>
            <h3>Welche Quellen speisen SQL, Keyword-Suche und RAG?</h3>
            <p className="panel-meta">
              Fehlerkatalog, Dokumente, Aufgaben, Maschinen, Material, Wartungspläne und
              Schichtdaten mit Status und Freigaben bewerten.
            </p>
          </div>
          <span className="badge badge-ai" data-ai-section-status="knowledge">
            {ragBoardState.isLoading ? "Wissen wird geladen" : "Wissen geladen"}
          </span>
        </div>
        <section className="panel">
          <div className="panel-header">
            <div>
              <h3>Quelle Health Matrix</h3>
              <p className="panel-meta">Einträge, Textabschnitte, RAG-Aktivierung und Health je Quelle.</p>
            </div>
          </div>
          <SourceHealthBoard state={ragBoardState} compact />
        </section>
        <RagStatusPanel state={ragBoardState} />
        <KnowledgeLifecyclePanel state={ragBoardState} />
        <KnowledgeNetworkPanel {...props} />
        <TrainingPanel {...props} />
        <KnowledgeDatabasePanel {...props} />
      </section>
    </>
  );
}

/**
 * Render the top RAG health strip.
 */
function RagHealthStrip({ state }: { readonly state: AdminAiRagBoardState }): ReactNode {
  const status = state.knowledgeStatus;
  const score = Number(status?.readiness_score || 0);
  const jobsQueued = state.jobs.filter((job) => job.status === "queued").length;
  const jobsFailed = state.jobs.filter((job) => job.status === "failed").length;

  return (
    <div className="rag-game-status">
      <article className="rag-health-item is-good" data-ai-health="ai">
        <span>AI</span>
        <strong data-ai-health-label>bereit</strong>
        <em data-ai-health-detail>Systemstatus</em>
      </article>
      <article className={`rag-health-item ${score >= 80 ? "is-good" : "is-watch"}`} data-ai-health="rag">
        <span>RAG</span>
        <strong data-ai-health-label>{score}/100</strong>
        <em data-ai-health-detail>RAG-Bereitschaft</em>
      </article>
      <article className={`rag-health-item ${jobsFailed ? "is-error" : "is-good"}`} data-ai-health="queue">
        <span>Queue</span>
        <strong data-ai-job-count>{state.jobs.length} Jobs</strong>
        <em data-ai-health-detail>{jobsQueued} queued / {jobsFailed} failed</em>
      </article>
      <article className="rag-health-item">
        <span>Kosten</span>
        <strong data-ai-kpi="estimated_cost_usd">$0</strong>
        <em data-ai-price-status>über Effektivität sichtbar</em>
      </article>
    </div>
  );
}

/**
 * Render source health cards from the knowledge status payload.
 */
function SourceHealthBoard({
  compact = false,
  state
}: {
  readonly compact?: boolean;
  readonly state: AdminAiRagBoardState;
}): ReactNode {
  const diagnostics = objectPayload(state.knowledgeStatus?.diagnostics);
  const ragEnabled = Boolean(diagnostics.rag_enabled);
  const vector = vectorStatus(state.knowledgeStatus);
  const lastUpdate = vector.latest_indexed_at || objectPayload(vector.last_successful_sync).synced_at || "";

  return (
    <div className={compact ? "ai-source-grid" : "rag-game-board"} data-ai-source-health aria-label="RAG Quellen-Spielbrett">
      {RAG_SOURCE_DEFINITIONS.map((definition) => {
        const metrics = sourceMetrics(state.knowledgeStatus, definition.types);
        const health = sourceHealth(metrics, ragEnabled);
        const scorePercent = Math.round((health.ratio || 0) * 100);

        return (
          <article className={`ai-source-card ${health.className}`} key={definition.key}>
            <div className="ai-source-card-header">
              <strong>{definition.label}</strong>
              <span className={`status-pill ${health.className}`}>{health.label}</span>
            </div>
            <div className="ai-source-score">
              <strong>{numberText(scorePercent)}%</strong>
              <small>Gesundheit</small>
            </div>
            <p>{definition.description}</p>
            <div className="ai-source-stats">
              <span><small>Quellen</small><strong>{numberText(metrics.documents)}</strong></span>
              <span><small>Chunks</small><strong>{numberText(metrics.chunks)}</strong></span>
              <span><small>Suchbar</small><strong>{numberText(metrics.searchable)}</strong></span>
            </div>
            <small>
              Embedding: {ragText(diagnostics.embedding_provider)} · RAG: {metrics.active ? "aktiv genutzt" : "nicht aktiv"} ·
              Letzte Aktualisierung: {lastUpdate ? ragDateTime(lastUpdate) : "nicht verfügbar"} · Health: {health.detail}
            </small>
          </article>
        );
      })}
    </div>
  );
}

/**
 * Render RAG readiness and vector sync status.
 */
function RagStatusPanel({ state }: { readonly state: AdminAiRagBoardState }): ReactNode {
  const status = state.knowledgeStatus;
  const diagnostics = objectPayload(status?.diagnostics);
  const vector = vectorStatus(status);
  const sourceTypes = Array.isArray(status?.source_types) ? status.source_types.filter(isPayload) : [];
  const problems = Array.isArray(status?.problem_documents) ? status.problem_documents.filter(isPayload) : [];
  const reasons = Array.isArray(status?.readiness_reasons) ? status.readiness_reasons : [];
  const syncRows: readonly (readonly [unknown, unknown])[] = [
    ["Suchindex Backend", vector.store],
    ["Konfiguriert", vector.configured_store],
    ["Ausweichbetrieb", vector.fallback_active ? "aktiv" : "nein"],
    ["Soll Vektoren", numberText(vector.expected_vector_count || 0)],
    ["Ist Vektoren", vector.actual_vector_count == null ? "-" : numberText(vector.actual_vector_count)],
    ["Letzter Index", ragDateTime(vector.latest_indexed_at)]
  ];
  const issueRows: readonly (readonly [unknown, unknown])[] = [
    ["Reindex empfohlen", vector.reindex_recommended ? "ja" : "nein"],
    ["Stale Dokumente", numberText(vector.stale_document_count || 0)],
    ["Fehlende Textabschnitte", numberText(vector.missing_chunk_count || 0)],
    ["Textabschnitt Mismatch", numberText(vector.chunk_mismatch_count || 0)],
    ["Sync-Fehler", numberText(vector.vector_sync_failure_count || 0)]
  ];

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h3>RAG-Index Status</h3>
          <p className="panel-meta">Bereitschaft, Vektor-Sync, Problemquellen und Indexabdeckung.</p>
        </div>
        <span className="badge badge-ai" data-rag-readiness>{ragReadinessLabel(status)}</span>
      </div>
      <div className="dashboard-grid dashboard-grid-4">
        {["documents", "indexed", "stale", "pending", "searchable_documents", "chunks"].map((key) => (
          <article className="metric-card" key={key}>
            <span>{key}</span>
            <strong data-rag-kpi={key}>{numberText(status?.[key] || 0)}</strong>
          </article>
        ))}
        <article className="metric-card">
          <span>Bereitschaft</span>
          <strong data-rag-readiness-score>{numberText(status?.readiness_score || 0)}/100</strong>
        </article>
      </div>
      <div className="content-grid two-columns mt-4">
        <StatsList rows={sourceTypes.map((item) => [
          sourceTypeLabel(item.source_type),
          `${numberText(item.searchable_documents || 0)}/${numberText(item.documents || 0)} durchsuchbar, ${numberText(item.chunks || 0)} Textabschnitte`
        ] as const)} empty={["Quellen", "Noch keine Daten indexiert"]} target="source-status" />
        <StatsList rows={[
          ["RAG aktiv", diagnostics.rag_enabled ? "ja" : "nein"],
          ["Suchindex", diagnostics.vector_store],
          ["Embedding-Anbieter", diagnostics.embedding_provider],
          ["Textabschnitting", `${ragText(diagnostics.chunk_size)} / ${ragText(diagnostics.chunk_overlap)}`],
          ["Top K", diagnostics.top_k],
          ["Scan Limit", diagnostics.scan_limit]
        ]} target="diagnostics" />
      </div>
      <div className="content-grid two-columns mt-4">
        <StatsList rows={reasons.map((reason) => ["Bereitschaft", reason] as const)} empty={["Bereitschaft", "Keine Bereitschaft-Daten vorhanden."]} target="reasons" />
        <StatsList rows={problems.map((documentItem) => [
          `#${ragText(documentItem.id)} ${sourceTypeLabel(documentItem.source_type)}`,
          `${ragText(documentItem.status)} - ${ragText(documentItem.title)}`
        ] as const)} empty={["Problemdokumente", "keine offenen Quellen"]} target="problems" />
      </div>
      <div className="content-grid two-columns mt-4">
        <StatsList rows={syncRows} target="vector-sync" />
        <StatsList rows={issueRows} target="vector-issues" />
      </div>
    </section>
  );
}

/**
 * Render knowledge lifecycle review.
 */
function KnowledgeLifecyclePanel({ state }: { readonly state: AdminAiRagBoardState }): ReactNode {
  const lifecycle = lifecycleStatus(state.knowledgeStatus);
  const reviewQueue = objectPayload(lifecycle.review_queue);
  const qualityGate = objectPayload(lifecycle.rag_quality_gate);
  const nextActions = Array.isArray(lifecycle.next_actions) ? lifecycle.next_actions : [];
  const steps = Array.isArray(lifecycle.steps) ? lifecycle.steps.filter(isPayload) : [];
  const hasProblems = Number(lifecycle.problem_documents || 0) > 0;
  const hasReview = Object.values(reviewQueue).some((value) => Number(value || 0) > 0);

  return (
    <section className="panel" data-knowledge-lifecycle-panel>
      <div className="panel-header">
        <div>
          <h3>Wissens-Lebenszyklus</h3>
          <p className="panel-meta">Qualitätsstatus, Prüf-Gates und Freigaben der indexierbaren Wissensbasis.</p>
        </div>
        <span className={`badge badge-ai ${hasProblems ? "is-error" : hasReview ? "is-stale" : "is-active"}`} data-knowledge-lifecycle-state>
          {hasProblems ? "kritisch" : hasReview ? "Review offen" : "bereit"}
        </span>
      </div>
      <div className="dashboard-grid dashboard-grid-4">
        {[
          "drafts",
          "technician_confirmed",
          "admin_approved",
          "problem_documents",
          "feedback_open",
          "knowledge_gaps_open",
          "needs_admin_approval",
          "non_approved_indexed_documents"
        ].map((key) => (
          <article className="metric-card" key={key}>
            <span>{key}</span>
            <strong data-lifecycle-kpi={key}>{lifecycleKpiValue(lifecycle, key)}</strong>
          </article>
        ))}
      </div>
      <div className="content-grid two-columns mt-4">
        <StatsList rows={[
          ["Techniker-Review", reviewQueue.needs_technician_review || 0],
          ["Admin-Freigabe", reviewQueue.needs_admin_approval || 0],
          ["Quality-Review", reviewQueue.needs_quality_review || 0],
          ["Low Quality", reviewQueue.low_quality || 0],
          ["Duplikate", reviewQueue.duplicate || 0],
          ["Refresh", reviewQueue.needs_refresh || 0],
          ["Abgelehnt", reviewQueue.rejected || 0]
        ]} target="lifecycle-review" />
        <StatsList rows={[
          ["Quality Gate", qualityGate.enabled ? "aktiv" : "diagnostisch"],
          ["Freigegeben indexiert", qualityGate.approved_indexed_documents || 0],
          ["Nicht freigegeben indexiert", qualityGate.non_approved_indexed_documents || 0],
          ["Hinweis", qualityGate.reason || "-"]
        ]} target="lifecycle-gate" />
      </div>
      <div className="content-grid two-columns mt-4">
        <StatsList rows={nextActions.slice(0, 6).map((action, index) => [`Aktion ${index + 1}`, action])} empty={["Aktionen", "Keine offenen Lifecycle-Aktionen."]} target="lifecycle-actions" />
        <StatsList rows={steps.slice(0, 9).map((step) => [ragText(step.label), ragText(step.status)])} empty={["Lifecycle", "keine Diagnostik vorhanden"]} target="lifecycle-steps" />
      </div>
    </section>
  );
}

/**
 * Render the knowledge network inspector.
 */
function KnowledgeNetworkPanel({ onNetworkFilterChange, ragBoardState }: AdminAiRagBoardProps): ReactNode {
  const network = ragBoardState.network || {};
  const stats = objectPayload(network.stats);
  const groups = Array.isArray(network.groups) ? network.groups.filter(isPayload) : [];
  const nodes = Array.isArray(network.nodes) ? network.nodes.filter(isPayload) : [];
  const edges = Array.isArray(network.edges) ? network.edges.filter(isPayload) : [];
  const filters = ragBoardState.filters;

  return (
    <section className="panel" data-knowledge-network-panel>
      <div className="panel-header">
        <div>
          <h3>Wissensnetz</h3>
          <p className="panel-meta">Nur-Lese Sicht auf Maschinen, Fehler, Dokumente, Inventar, Trends und Wissenslücken.</p>
        </div>
        <div className="toolbar admin-ai-toolbar">
          <input className="input input-bordered" data-knowledge-network-search placeholder="Netzwerk durchsuchen" value={filters.networkQuery} onChange={filterChange(onNetworkFilterChange, "networkQuery")} />
          <SelectFilter ariaLabel="Netzwerk nach Quelle filtern" dataAttr="data-knowledge-network-source" value={filters.networkSource} onChange={filterChange(onNetworkFilterChange, "networkSource")} options={SOURCE_OPTIONS} />
          <SelectFilter ariaLabel="Netzwerk nach Qualität filtern" dataAttr="data-knowledge-network-quality" value={filters.networkQuality} onChange={filterChange(onNetworkFilterChange, "networkQuality")} options={QUALITY_OPTIONS} />
          <select className="input input-bordered" data-knowledge-network-focus-type aria-label="Wissensnetz Ansicht" value={filters.networkFocusType} onChange={filterChange(onNetworkFilterChange, "networkFocusType")}>
            <option value="">Gesamtnetz</option>
            <option value="machine">Maschinenzentriert</option>
            <option value="error">Fehlerzentriert</option>
            <option value="task">Aufgabezentriert</option>
            <option value="knowledge_gap">Gapzentriert</option>
          </select>
          <input className="input input-bordered" data-knowledge-network-focus placeholder="Fokus optional" value={filters.networkFocus} onChange={filterChange(onNetworkFilterChange, "networkFocus")} />
          <button className="btn btn-secondary" type="button" data-knowledge-network-refresh onClick={() => onNetworkFilterChange("networkQuery", filters.networkQuery)}>
            Aktualisieren
          </button>
        </div>
      </div>
      <div className="dashboard-grid dashboard-grid-4" data-knowledge-network-stats>
        {([
          ["Nodes", stats.node_count || 0],
          ["Edges", stats.edge_count || 0],
          ["Roh-Nodes", stats.raw_node_count || 0],
          ["Zeitraum", `${ragText(stats.window_days, "30")} Tage`]
        ] as const).map(([label, value]) => (
          <article className="metric-card" key={label}><span>{label}</span><strong>{ragText(value)}</strong></article>
        ))}
      </div>
      <div className="knowledge-network-groups mt-4" data-knowledge-network-groups aria-label="Gruppierte Wissensknoten">
        {groups.length ? groups.map((group) => (
          <article className="knowledge-network-group-card" key={ragText(group.type)}>
            <div className="knowledge-network-group-header">
              <strong>{ragText(group.label) || networkTypeLabel(group.type)}</strong>
              <span>{numberText(group.count || 0)} Nodes / {numberText(group.edge_count || 0)} Links</span>
            </div>
            <div className="knowledge-network-group-nodes">
              {(Array.isArray(group.top_nodes) ? group.top_nodes.filter(isPayload) : []).map((node) => (
                <button className="knowledge-network-node-chip" type="button" data-network-group-node={ragText(node.id)} key={ragText(node.id)}>
                  {truncateLabel(node.label, 34)}
                </button>
              ))}
            </div>
          </article>
        )) : <StatRow label="Gruppen" value="Keine gruppierten Nodes vorhanden" />}
      </div>
      <div className="knowledge-network-layout mt-4">
        <div className="stats-list" data-knowledge-network-canvas aria-label="Wissensnetz Visualisierung">
          {nodes.slice(0, 20).map((node) => (
            <StatRow key={ragText(node.id)} label={networkTypeLabel(node.type)} value={truncateLabel(node.label || node.title, 80)} />
          ))}
          {!nodes.length ? <StatRow label="Wissensnetz" value="Keine Daten für diesen Filter." /> : null}
        </div>
        <aside className="stats-list" data-knowledge-network-detail aria-label="Wissensnetz Details">
          {nodes[0] ? (
            <>
              <StatRow label="Titel" value={ragText(nodes[0].title || nodes[0].label)} />
              <StatRow label="Typ" value={networkTypeLabel(nodes[0].type)} />
              <StatRow label="Gewicht" value={Number(nodes[0].weight || 0).toFixed(1)} />
              <StatRow label="Quelle" value={sourceTypeLabel(nodes[0].source_type)} />
            </>
          ) : <StatRow label="Auswahl" value="Node anklicken" />}
        </aside>
      </div>
      <div className="knowledge-network-relations mt-4" data-knowledge-network-relations aria-label="Klickbare Wissensverbindungen">
        <div className="knowledge-network-relations-header">
          <strong>Klickbare Verbindungen</strong>
          <span>{edges.length ? `${Math.min(edges.length, 16)} wichtigste Beziehungen` : "Keine sichtbaren Beziehungen"}</span>
        </div>
        {edges.slice(0, 16).map((edge) => (
          <button className="knowledge-network-relation-card" data-network-relation={ragText(edge.id)} type="button" key={ragText(edge.id)}>
            <span>{ragText(edge.label || edge.type)}</span>
            <strong>{truncateLabel(edge.source, 34)} -&gt; {truncateLabel(edge.target, 34)}</strong>
            <small>Gewicht {Number(edge.weight || 0).toFixed(1)} / Evidenz {numberText(edge.evidence_count || 0)}</small>
          </button>
        ))}
      </div>
      <div className="stats-list mt-4" data-knowledge-network-legend aria-label="Wissensnetz Legende">
        {Object.entries(objectPayload(stats.nodes_by_type)).map(([type, count]) => (
          <StatRow key={type} label={networkTypeLabel(type)} value={`${numberText(count)} Nodes`} />
        ))}
        <StatRow label="Privacy" value={ragText(objectPayload(network.privacy).mode, "metadata_only")} />
      </div>
    </section>
  );
}

/**
 * Render manual training list and editor.
 */
function TrainingPanel(props: AdminAiRagBoardProps): ReactNode {
  const { onDeleteTraining, onSaveTraining, onSelectTraining, onTrainingFilterChange, onTrainingFormChange, ragBoardState } = props;
  const form = ragBoardState.trainingForm;

  return (
    <section className="panel admin-training-panel" id="ai-training-data" data-ai-admin-area="training">
      <div className="panel-header">
        <div>
          <span className="section-kicker">4. Trainingsdaten</span>
          <h3>Manuelles Wissen gezielt pflegen</h3>
          <p className="panel-meta">Freigegebene Trainingseinträge ergänzen die strukturierten Quellen.</p>
        </div>
        <div className="admin-filterbar">
          <input className="input input-bordered" data-ai-training-search placeholder="Training durchsuchen" value={ragBoardState.filters.trainingQuery} onChange={filterChange(onTrainingFilterChange, "trainingQuery")} />
          <select className="input input-bordered" data-ai-training-active aria-label="Training nach Status filtern" value={ragBoardState.filters.trainingActive} onChange={filterChange(onTrainingFilterChange, "trainingActive")}>
            <option value="">Alle Trainings</option>
            <option value="true">Nur aktiv</option>
            <option value="false">Nur inaktiv</option>
          </select>
        </div>
      </div>
      <div className="admin-training-workflow">
        <aside className="admin-training-list" data-ai-training aria-label="Trainingseinträge">
          {ragBoardState.training.length ? ragBoardState.training.map((entry) => (
            <article className={`training-card ${form.id === String(entry.id) ? "is-selected" : ""}`} data-training-id={ragText(entry.id)} key={ragText(entry.id)}>
              <strong>{ragText(entry.title)}</strong>
              <p>{ragText(entry.question)}</p>
              <div className="training-card-meta">
                <span className={`status-pill ${entry.is_active ? "is-active" : "is-muted"}`}>{entry.is_active ? "aktiv" : "inaktiv"}</span>
                <span className="status-pill">Priorität {ragText(entry.priority)}</span>
                <span className="status-pill">{ragText(entry.category)}</span>
                <span className="status-pill">{ragText(entry.department, "alle Abteilungen")}</span>
              </div>
              <div className="training-card-actions">
                <button className="btn btn-secondary btn-sm" type="button" onClick={() => onSelectTraining(entry)}>Bearbeiten</button>
                <button className="btn btn-ghost btn-sm" type="button" data-delete-training={ragText(entry.id)} onClick={() => onDeleteTraining(Number(entry.id))}>Löschen</button>
              </div>
            </article>
          )) : <div className="guided-empty-state"><strong>Keine passenden Trainingseinträge gefunden.</strong><p>Passe Suche oder Statusfilter an.</p></div>}
        </aside>
        <form className="admin-training-editor" data-ai-training-form onSubmit={(event) => submitTraining(event, onSaveTraining, form)}>
          <input type="hidden" name="id" value={form.id} />
          <div className="training-editor-header">
            <div><span className="section-kicker">Editor</span><h4 data-ai-training-editor-title>{form.id ? "Training bearbeiten" : "Neuer Trainingseintrag"}</h4></div>
            <span className={`status-pill ${form.isActive ? "is-active" : "is-stale"}`} data-ai-training-editor-status>
              {form.isActive ? "Aktiv im RAG-Index" : "Nach dem Speichern neu indexieren"}
            </span>
          </div>
          <div className="training-status-strip">
            <label className="inline-form training-active-toggle"><span>Aktiv</span><input name="is_active" type="checkbox" checked={form.isActive} onChange={(event) => onTrainingFormChange({ ...form, isActive: event.target.checked })} /></label>
            <label className="inline-form training-priority-field"><span>Priorität</span><input className="input input-bordered" name="priority" type="number" min="0" max="100" value={form.priority} onChange={formChange(form, onTrainingFormChange, "priority")} /></label>
          </div>
          <div className="content-grid two-columns">
            <input className="input input-bordered" name="title" maxLength={220} placeholder="Titel" value={form.title} onChange={formChange(form, onTrainingFormChange, "title")} />
            <input className="input input-bordered" name="category" maxLength={80} placeholder="Kategorie, z. B. Wartung" value={form.category} onChange={formChange(form, onTrainingFormChange, "category")} />
            <input className="input input-bordered" name="department" maxLength={120} placeholder="Abteilung optional" value={form.department} onChange={formChange(form, onTrainingFormChange, "department")} />
            <input className="input input-bordered" name="keywords" maxLength={1000} placeholder="Keywords, Synonyme, Fehlercodes" value={form.keywords} onChange={formChange(form, onTrainingFormChange, "keywords")} />
          </div>
          <textarea className="input input-bordered" name="question" maxLength={1000} rows={3} placeholder="Typische Frage oder Situation" value={form.question} onChange={formChange(form, onTrainingFormChange, "question")} />
          <textarea className="input input-bordered" name="answer" maxLength={6000} rows={6} placeholder="Freigegebene Antwort, Regel oder Wartungshinweis" value={form.answer} onChange={formChange(form, onTrainingFormChange, "answer")} />
          <p className="panel-meta">Aktuelle strukturierte Daten bleiben führend; Training ergänzt nur freigegebenes Erfahrungswissen.</p>
          <div className="toolbar training-editor-actions">
            <button className="btn btn-primary" disabled={ragBoardState.isSaving} type="submit">Training speichern</button>
            <button className="btn btn-ghost" type="button" data-ai-training-reset onClick={() => onTrainingFormChange(EMPTY_TRAINING_FORM)}>Neu</button>
          </div>
        </form>
      </div>
    </section>
  );
}

/**
 * Render the knowledge database filters and table.
 */
function KnowledgeDatabasePanel(props: AdminAiRagBoardProps): ReactNode {
  const { onDeleteKnowledge, onKnowledgeFilterChange, onKnowledgeUpload, onQueueDocument, onReindexDocument, onUpdateKnowledgeQuality, ragBoardState } = props;
  const filters = ragBoardState.filters;

  return (
    <section className="panel">
      <div className="panel-header">
        <div><h3>Wissensdatenbank</h3><p className="panel-meta">Dokumente, Trainingseinträge und automatisch erzeugte Quellen verwalten.</p></div>
        <div className="toolbar admin-ai-toolbar">
          <input className="input input-bordered" data-ai-knowledge-search placeholder="Wissen durchsuchen" value={filters.knowledgeQuery} onChange={filterChange(onKnowledgeFilterChange, "knowledgeQuery")} />
          <SelectFilter dataAttr="data-ai-knowledge-source" value={filters.knowledgeSource} onChange={filterChange(onKnowledgeFilterChange, "knowledgeSource")} options={SOURCE_OPTIONS} />
          <select className="input input-bordered" data-ai-knowledge-status aria-label="Wissen nach Indexstatus filtern" value={filters.knowledgeStatus} onChange={filterChange(onKnowledgeFilterChange, "knowledgeStatus")}>
            <option value="">Alle Status</option><option value="indexed">Indexiert</option><option value="stale">Veraltet</option><option value="pending">Ausstehend</option><option value="error">Fehler</option><option value="no_text">Ohne Text</option>
          </select>
          <SelectFilter ariaLabel="Wissen nach Qualitätsstatus filtern" dataAttr="data-ai-knowledge-quality" value={filters.knowledgeQuality} onChange={filterChange(onKnowledgeFilterChange, "knowledgeQuality")} options={QUALITY_OPTIONS} />
          <form className="inline-form" data-ai-knowledge-upload onSubmit={(event) => submitUpload(event, onKnowledgeUpload)}>
            <input className="input input-bordered" name="department" placeholder="Abteilung optional" />
            <input className="input input-bordered" name="file" type="file" accept=".pdf,.txt,.html,.htm" />
            <button className="btn btn-secondary" disabled={ragBoardState.isSaving} type="submit">Hochladen</button>
          </form>
        </div>
        <div className="knowledge-origin-legend" data-knowledge-origin-legend aria-label="Herkunft der Wissensquellen">
          <span className="status-pill is-source-automatic">Automatisch</span>
          <span className="status-pill is-source-manual">Manuell</span>
          <span className="status-pill is-source-prebuilt">Vorgefertigt</span>
        </div>
      </div>
      <div className="table-wrap">
        <table className="data-table">
          <caption>Wissensdatenbank mit Quelle, Indexstatus, Qualität, Textabschnitte und Abteilung</caption>
          <thead><tr><th scope="col">Titel</th><th scope="col">Quelle</th><th scope="col">Index</th><th scope="col">Qualität</th><th scope="col">Textabschnitte</th><th scope="col">Abteilung</th><th scope="col">Aktionen</th></tr></thead>
          <tbody data-ai-knowledge>
            {ragBoardState.knowledge.length ? ragBoardState.knowledge.map((documentItem) => (
              <tr data-knowledge-status={ragText(documentItem.status)} data-knowledge-quality-status={ragText(documentItem.quality_status, "draft")} key={ragText(documentItem.id)}>
                <td>{ragText(documentItem.title)}</td>
                <td className="knowledge-source-cell"><span className="status-pill is-muted">{sourceTypeLabel(documentItem.source_type)}</span></td>
                <td>{ragText(documentItem.status)}</td>
                <td><span className={`status-pill ${qualityStatusClass(documentItem.quality_status)}`}>{qualityStatusLabel(documentItem.quality_status)}</span></td>
                <td>{numberText(documentItem.chunk_count || 0)}</td>
                <td>{ragText(documentItem.department)}</td>
                <td className="table-actions">
                  <button className="btn btn-secondary btn-sm" type="button" data-reindex-knowledge={ragText(documentItem.id)} onClick={() => onReindexDocument(Number(documentItem.id))}>Indexieren</button>
                  <button className="btn btn-ghost btn-sm" type="button" data-queue-knowledge={ragText(documentItem.id)} onClick={() => onQueueDocument(Number(documentItem.id))}>Job planen</button>
                  <select className="input input-bordered" data-knowledge-quality-select={ragText(documentItem.id)} aria-label="Wissens-Qualitätsstatus setzen" defaultValue={ragText(documentItem.quality_status, "draft")}>
                    {QUALITY_STATUSES.map((status) => <option value={status} key={status}>{qualityStatusLabel(status)}</option>)}
                  </select>
                  <button className="btn btn-secondary btn-sm" type="button" data-update-knowledge-quality={ragText(documentItem.id)} onClick={(event) => onUpdateQualityClick(event, onUpdateKnowledgeQuality, Number(documentItem.id))}>Status setzen</button>
                  <button className="btn btn-ghost btn-sm" type="button" data-delete-knowledge={ragText(documentItem.id)} onClick={() => onDeleteKnowledge(Number(documentItem.id))}>Löschen</button>
                </td>
              </tr>
            )) : <tr><td colSpan={7}>Keine Wissensquellen für diesen Filter.</td></tr>}
          </tbody>
        </table>
      </div>
    </section>
  );
}

/**
 * Render an Admin-AI stats list with existing hooks.
 */
function StatsList({
  empty,
  rows,
  target
}: {
  readonly empty?: readonly [unknown, unknown];
  readonly rows: readonly (readonly [unknown, unknown])[];
  readonly target: string;
}): ReactNode {
  const dataAttributes: Record<string, boolean> = {
    "lifecycle-actions": true,
    "lifecycle-gate": true,
    "lifecycle-review": true,
    "lifecycle-steps": true,
    "source-status": true,
    diagnostics: true,
    problems: true,
    reasons: true,
    "vector-issues": true,
    "vector-sync": true
  };
  const hookMap: Record<string, string> = {
    "lifecycle-actions": "data-knowledge-lifecycle-actions",
    "lifecycle-gate": "data-knowledge-lifecycle-gate",
    "lifecycle-review": "data-knowledge-lifecycle-review",
    "lifecycle-steps": "data-knowledge-lifecycle-steps",
    "source-status": "data-rag-source-status",
    diagnostics: "data-rag-diagnostics",
    problems: "data-rag-problem-documents",
    reasons: "data-rag-readiness-reasons",
    "vector-issues": "data-rag-vector-issues",
    "vector-sync": "data-rag-vector-sync"
  };
  const visibleRows = rows.length ? rows : empty ? [empty] : [];
  const hookName = hookMap[target];
  const hookProps = dataAttributes[target] && hookName ? { [hookName]: true } : {};

  return (
    <div className="stats-list" {...hookProps}>
      {visibleRows.map(([label, value], index) => (
        <StatRow key={`${ragText(label)}-${index}`} label={label} value={value} />
      ))}
    </div>
  );
}

/**
 * Render a stats list row.
 */
function StatRow({ label, value }: { readonly label: unknown; readonly value: unknown }): ReactNode {
  return <div className="stat-row"><span>{ragText(label)}</span><strong>{ragText(value)}</strong></div>;
}

/**
 * Return true when an unknown value is an object payload.
 */
function isPayload(value: unknown): value is AdminAiPayload {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/**
 * Return an input change handler for filter state.
 */
function filterChange(
  onChange: (key: keyof AdminAiRagBoardFilters, value: string) => void,
  key: keyof AdminAiRagBoardFilters
) {
  return (event: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => onChange(key, event.target.value);
}

/**
 * Return an input change handler for the training form.
 */
function formChange(
  form: AdminAiTrainingForm,
  onChange: (form: AdminAiTrainingForm) => void,
  key: keyof AdminAiTrainingForm
) {
  return (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    onChange({ ...form, [key]: event.target.value });
  };
}

/**
 * Submit the training editor form through the React handler.
 */
function submitTraining(
  event: FormEvent<HTMLFormElement>,
  onSaveTraining: (form: AdminAiTrainingForm) => void,
  form: AdminAiTrainingForm
): void {
  event.preventDefault();
  onSaveTraining(form);
}

/**
 * Submit the knowledge upload form through the React handler.
 */
function submitUpload(
  event: FormEvent<HTMLFormElement>,
  onKnowledgeUpload: (form: HTMLFormElement) => void
): void {
  event.preventDefault();
  onKnowledgeUpload(event.currentTarget);
}

/**
 * Read the selected quality status next to the clicked button.
 */
function onUpdateQualityClick(
  event: MouseEvent<HTMLButtonElement>,
  onUpdateKnowledgeQuality: (documentId: number, qualityStatus: string) => void,
  documentId: number
): void {
  const row = event.currentTarget.closest("tr");
  const select = row?.querySelector<HTMLSelectElement>("[data-knowledge-quality-select]");
  onUpdateKnowledgeQuality(documentId, select?.value || "draft");
}

/**
 * Render a select filter with an optional data hook.
 */
function SelectFilter({
  ariaLabel,
  dataAttr,
  onChange,
  options,
  value
}: {
  readonly ariaLabel?: string;
  readonly dataAttr: string;
  readonly onChange: (event: ChangeEvent<HTMLSelectElement>) => void;
  readonly options: readonly (readonly [string, string])[];
  readonly value: string;
}): ReactNode {
  return (
    <select className="input input-bordered" {...{ [dataAttr]: true }} aria-label={ariaLabel} value={value} onChange={onChange}>
      {options.map(([optionValue, label]) => (
        <option key={optionValue} value={optionValue}>{label}</option>
      ))}
    </select>
  );
}

import { type ReactNode } from "react";

import { AdminAiSourceTestPanel } from "./AdminAiSectionsSourceCheck";

const QUALITY_OPTIONS = [
  ["", "Alle Qualitätsstatus"],
  ["draft", "Draft"],
  ["ai_suggested", "AI-Vorschlag"],
  ["technician_confirmed", "Techniker bestätigt"],
  ["admin_approved", "Admin freigegeben"],
  ["low_quality", "Niedrige Qualität"],
  ["duplicate", "Duplikat"],
  ["outdated", "Veraltet"],
  ["rejected", "Abgelehnt"],
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
  ["shift_handover", "Schichtübergaben"],
] as const;

/**
 * Render the RAG board, knowledge, training and source maintenance areas.
 */
export function AdminAiRagBoard(): ReactNode {
  return (
    <>
      <section className="ai-admin-area rag-board-area rag-game-shell" id="ai-rag-board" data-ai-admin-area="rag-board">
        <div className="rag-game-status">
          <article className="rag-health-item is-good" data-ai-health="ai">
            <span>AI</span>
            <strong data-ai-health-label>Wird geladen</strong>
            <em data-ai-health-detail>Systemstatus</em>
          </article>
          <article className="rag-health-item is-watch" data-ai-health="rag">
            <span>RAG</span>
            <strong data-ai-health-label>Wird geladen</strong>
            <em data-ai-health-detail>RAG-Bereitschaft</em>
          </article>
          <article className="rag-health-item is-good" data-ai-health="queue">
            <span>Queue</span>
            <strong data-ai-job-count>0 Jobs</strong>
            <em data-ai-health-detail>Queue und stale Quellen</em>
          </article>
          <article className="rag-health-item">
            <span>Kosten</span>
            <strong data-ai-kpi="estimated_cost_usd">$0</strong>
            <em data-ai-price-status>AI_PRICE_* fehlen</em>
          </article>
        </div>
        <div className="rag-game-board" data-ai-source-health aria-label="RAG Quellen-Spielbrett" />
        <section className="panel mt-4">
          <div className="panel-header">
            <div>
              <h3>RAG-Pflegeaktionen</h3>
              <p className="panel-meta" data-ai-reindex-message>
                Quelle -&gt; Textabschnitte -&gt; Vektoren -&gt; Suchbar -&gt; Getestet
              </p>
            </div>
            <div className="toolbar">
              <button className="btn btn-secondary btn-sm" type="button" data-ai-queue-stale>
                Job planen
              </button>
              <button className="btn btn-primary btn-sm" type="button" data-ai-reindex-stale>
                Reindex
              </button>
            </div>
          </div>
        </section>
        <section className="panel mt-4">
          <div className="panel-header">
            <h3>Quellen-Arena</h3>
            <span className="panel-meta">Testfrage direkt gegen aktuelle Quellen prüfen</span>
          </div>
          <AdminAiSourceTestPanel />
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
            Wissen wird geladen
          </span>
        </div>
        <section className="panel">
          <div className="panel-header">
            <div>
              <h3>Quelle Health Matrix</h3>
              <p className="panel-meta">Einträge, Textabschnitte, RAG-Aktivierung und Health je Quelle.</p>
            </div>
          </div>
          <div className="ai-source-grid" data-ai-source-health />
        </section>
        <RagStatusPanel />
        <KnowledgeLifecyclePanel />
        <KnowledgeNetworkPanel />
        <TrainingPanel />
        <KnowledgeDatabasePanel />
      </section>
    </>
  );
}

/**
 * Render RAG readiness and vector sync status hooks.
 */
function RagStatusPanel(): ReactNode {
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h3>RAG-Index Status</h3>
          <p className="panel-meta">Bereitschaft, Vektor-Sync, Problemquellen und Indexabdeckung.</p>
        </div>
        <span className="badge badge-ai" data-rag-readiness>
          RAG
        </span>
      </div>
      <div className="dashboard-grid dashboard-grid-4">
        {["documents", "indexed", "stale", "pending", "searchable_documents", "chunks"].map((key) => (
          <article className="metric-card" key={key}>
            <span>{key}</span>
            <strong data-rag-kpi={key}>0</strong>
          </article>
        ))}
        <article className="metric-card">
          <span>Bereitschaft</span>
          <strong data-rag-readiness-score>0</strong>
        </article>
      </div>
      <div className="content-grid two-columns mt-4">
        <div className="stats-list" data-rag-source-status />
        <div className="stats-list" data-rag-diagnostics />
      </div>
      <div className="content-grid two-columns mt-4">
        <div className="stats-list" data-rag-readiness-reasons />
        <div className="stats-list" data-rag-problem-documents />
      </div>
      <div className="content-grid two-columns mt-4">
        <div className="stats-list" data-rag-vector-sync />
        <div className="stats-list" data-rag-vector-issues />
      </div>
    </section>
  );
}

/**
 * Render knowledge lifecycle review hooks.
 */
function KnowledgeLifecyclePanel(): ReactNode {
  return (
    <section className="panel" data-knowledge-lifecycle-panel>
      <div className="panel-header">
        <div>
          <h3>Wissens-Lebenszyklus</h3>
          <p className="panel-meta">Qualitätsstatus, Prüf-Gates und Freigaben der indexierbaren Wissensbasis.</p>
        </div>
        <span className="badge badge-ai" data-knowledge-lifecycle-state>
          Noch nicht geladen
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
          "non_approved_indexed_documents",
        ].map((key) => (
          <article className="metric-card" key={key}>
            <span>{key}</span>
            <strong data-lifecycle-kpi={key}>0</strong>
          </article>
        ))}
      </div>
      <div className="content-grid two-columns mt-4">
        <div className="stats-list" data-knowledge-lifecycle-review />
        <div className="stats-list" data-knowledge-lifecycle-gate />
      </div>
      <div className="content-grid two-columns mt-4">
        <div className="stats-list" data-knowledge-lifecycle-actions />
        <div className="stats-list" data-knowledge-lifecycle-steps />
      </div>
    </section>
  );
}

/**
 * Render the knowledge network inspector hooks.
 */
function KnowledgeNetworkPanel(): ReactNode {
  return (
    <section className="panel" data-knowledge-network-panel>
      <div className="panel-header">
        <div>
          <h3>Wissensnetz</h3>
          <p className="panel-meta">
            Nur-Lese Sicht auf Maschinen, Fehler, Dokumente, Inventar, Trends und Wissenslücken.
          </p>
        </div>
        <div className="toolbar admin-ai-toolbar">
          <input className="input input-bordered" data-knowledge-network-search placeholder="Netzwerk durchsuchen" />
          <select className="input input-bordered" data-knowledge-network-source aria-label="Netzwerk nach Quelle filtern">
            {SOURCE_OPTIONS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          <select className="input input-bordered" data-knowledge-network-quality aria-label="Netzwerk nach Qualität filtern">
            {QUALITY_OPTIONS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          <select className="input input-bordered" data-knowledge-network-focus-type aria-label="Wissensnetz Ansicht">
            <option value="">Gesamtnetz</option>
            <option value="machine">Maschinenzentriert</option>
            <option value="error">Fehlerzentriert</option>
            <option value="task">Aufgabezentriert</option>
            <option value="knowledge_gap">Gapzentriert</option>
          </select>
          <input className="input input-bordered" data-knowledge-network-focus placeholder="Fokus optional" />
          <button className="btn btn-secondary" type="button" data-knowledge-network-refresh>
            Aktualisieren
          </button>
        </div>
      </div>
      <div className="dashboard-grid dashboard-grid-4" data-knowledge-network-stats />
      <div className="knowledge-network-groups mt-4" data-knowledge-network-groups aria-label="Gruppierte Wissensknoten" />
      <div className="knowledge-network-layout mt-4">
        <div className="stats-list" data-knowledge-network-canvas aria-label="Wissensnetz Visualisierung" />
        <aside className="stats-list" data-knowledge-network-detail aria-label="Wissensnetz Details" />
      </div>
      <div className="knowledge-network-relations mt-4" data-knowledge-network-relations aria-label="Klickbare Wissensverbindungen" />
      <div className="stats-list mt-4" data-knowledge-network-legend aria-label="Wissensnetz Legende" />
    </section>
  );
}

/**
 * Render manual training list and editor hooks.
 */
function TrainingPanel(): ReactNode {
  return (
    <section className="panel admin-training-panel" id="ai-training-data" data-ai-admin-area="training">
      <div className="panel-header">
        <div>
          <span className="section-kicker">4. Trainingsdaten</span>
          <h3>Manuelles Wissen gezielt pflegen</h3>
          <p className="panel-meta">
            Freigegebene Trainingseinträge ergänzen die strukturierten Quellen, umgehen aber keine
            Berechtigungen oder Qualitätsprüfungen.
          </p>
        </div>
        <div className="admin-filterbar">
          <input className="input input-bordered" data-ai-training-search placeholder="Training durchsuchen" />
          <select className="input input-bordered" data-ai-training-active aria-label="Training nach Status filtern">
            <option value="">Alle Trainings</option>
            <option value="true">Nur aktiv</option>
            <option value="false">Nur inaktiv</option>
          </select>
        </div>
      </div>
      <div className="admin-training-workflow">
        <aside className="admin-training-list" data-ai-training aria-label="Trainingseinträge" />
        <form className="admin-training-editor" data-ai-training-form>
          <input type="hidden" name="id" />
          <div className="training-editor-header">
            <div>
              <span className="section-kicker">Editor</span>
              <h4 data-ai-training-editor-title>Neuer Trainingseintrag</h4>
            </div>
            <span className="status-pill is-stale" data-ai-training-editor-status>
              Nach dem Speichern neu indexieren
            </span>
          </div>
          <div className="training-status-strip">
            <label className="inline-form training-active-toggle">
              <span>Aktiv</span>
              <input name="is_active" type="checkbox" defaultChecked />
            </label>
            <label className="inline-form training-priority-field">
              <span>Priorität</span>
              <input className="input input-bordered" name="priority" type="number" min="0" max="100" defaultValue="50" />
            </label>
          </div>
          <div className="content-grid two-columns">
            <input className="input input-bordered" name="title" maxLength={220} placeholder="Titel" />
            <input className="input input-bordered" name="category" maxLength={80} placeholder="Kategorie, z. B. Wartung" />
            <input className="input input-bordered" name="department" maxLength={120} placeholder="Abteilung optional" />
            <input className="input input-bordered" name="keywords" maxLength={1000} placeholder="Keywords, Synonyme, Fehlercodes" />
          </div>
          <textarea className="input input-bordered" name="question" maxLength={1000} rows={3} placeholder="Typische Frage oder Situation" />
          <textarea className="input input-bordered" name="answer" maxLength={6000} rows={6} placeholder="Freigegebene Antwort, Regel oder Wartungshinweis" />
          <p className="panel-meta">
            Aktuelle strukturierte Daten bleiben führend; Training ergänzt nur freigegebenes
            Erfahrungswissen.
          </p>
          <div className="toolbar training-editor-actions">
            <button className="btn btn-primary" type="submit">
              Training speichern
            </button>
            <button className="btn btn-ghost" type="button" data-ai-training-reset>
              Neu
            </button>
          </div>
        </form>
      </div>
    </section>
  );
}

/**
 * Render the knowledge database filters and table hooks.
 */
function KnowledgeDatabasePanel(): ReactNode {
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h3>Wissensdatenbank</h3>
          <p className="panel-meta">Dokumente, Trainingseinträge und automatisch erzeugte Quellen verwalten.</p>
        </div>
        <div className="toolbar admin-ai-toolbar">
          <input className="input input-bordered" data-ai-knowledge-search placeholder="Wissen durchsuchen" />
          <select className="input input-bordered" data-ai-knowledge-source>
            {SOURCE_OPTIONS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          <select className="input input-bordered" data-ai-knowledge-status aria-label="Wissen nach Indexstatus filtern">
            <option value="">Alle Status</option>
            <option value="indexed">Indexiert</option>
            <option value="stale">Veraltet</option>
            <option value="pending">Ausstehend</option>
            <option value="error">Fehler</option>
            <option value="no_text">Ohne Text</option>
          </select>
          <select className="input input-bordered" data-ai-knowledge-quality aria-label="Wissen nach Qualitätsstatus filtern">
            {QUALITY_OPTIONS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          <form className="inline-form" data-ai-knowledge-upload>
            <input className="input input-bordered" name="department" placeholder="Abteilung optional" />
            <input className="input input-bordered" name="file" type="file" accept=".pdf,.txt,.html,.htm" />
            <button className="btn btn-secondary" type="submit">
              Hochladen
            </button>
          </form>
        </div>
      </div>
      <div className="table-wrap">
        <table className="data-table">
          <caption>Wissensdatenbank mit Quelle, Indexstatus, Qualität, Textabschnitte und Abteilung</caption>
          <thead>
            <tr>
              <th scope="col">Titel</th>
              <th scope="col">Quelle</th>
              <th scope="col">Index</th>
              <th scope="col">Qualität</th>
              <th scope="col">Textabschnitte</th>
              <th scope="col">Abteilung</th>
              <th scope="col">Aktionen</th>
            </tr>
          </thead>
          <tbody data-ai-knowledge />
        </table>
      </div>
    </section>
  );
}

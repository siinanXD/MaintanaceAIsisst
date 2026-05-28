import { type ReactNode } from "react";

/**
 * Render the shared source test form and result panel.
 */
export function AdminAiSourceTestPanel(): ReactNode {
  return (
    <>
      <div className="source-test-layout">
        <form className="panel stack source-test-form" data-ai-source-test-form>
          <div className="form-grid">
            <label>
              <span>Workflow</span>
              <select className="input input-bordered" name="workflow" aria-label="Workflow">
                <option value="chat">Wartungs-Chat</option>
                <option value="general_chat">Allgemeiner Chat</option>
                <option value="error_analysis">Fehleranalyse</option>
                <option value="task_suggestion">Aufgaben-Vorschlag</option>
                <option value="document_review">Dokument-Prüfung</option>
              </select>
            </label>
            <label>
              <span>Modus</span>
              <select className="input input-bordered" name="mode" aria-label="Testmodus">
                <option value="dry">Dry-run ohne Modellkosten</option>
                <option value="live">Live-Test mit echtem AI-Call</option>
              </select>
            </label>
          </div>
          <label>
            <span>Testfrage</span>
            <textarea
              className="input input-bordered"
              name="question"
              placeholder="z. B. Warum fällt Presse 3 bei Hydraulikdruck ab?"
              rows={5}
            />
          </label>
          <label>
            <span>Optionaler Kontext</span>
            <textarea
              className="input input-bordered"
              name="context"
              placeholder="Maschine, Abteilung, Fehlercode oder bekannte Quelle"
              rows={4}
            />
          </label>
          <div className="toolbar">
            <button className="btn btn-secondary" type="submit" name="intent" value="dry">
              Dry-run anzeigen
            </button>
            <button className="btn btn-primary" type="submit" name="intent" value="live">
              Live-Test starten
            </button>
            <button className="btn btn-ghost" type="button" data-ai-source-reset>
              Arena zurücksetzen
            </button>
          </div>
        </form>

        <section className="panel source-test-result">
          <div className="panel-header">
            <div>
              <h3>Antwort & Quellen</h3>
              <p className="panel-meta" data-ai-source-test-meta>
                Noch keine Testfrage ausgeführt
              </p>
            </div>
            <span className="status-pill is-muted" data-ai-source-test-state>
              Bereit
            </span>
          </div>
          <div className="source-test-answer" data-ai-source-test-answer>
            Wähle Dry-run für Prompt/Kosten-Nähe oder Live-Test für echte Antwort mit Quellen.
          </div>
          <div className="source-test-score-grid">
            <article>
              <span>Quellen</span>
              <strong data-ai-source-test-kpi="sources">0</strong>
            </article>
            <article>
              <span>Sicherheit</span>
              <strong data-ai-source-test-kpi="confidence">-</strong>
            </article>
            <article>
              <span>Kosten</span>
              <strong data-ai-source-test-kpi="cost">$0</strong>
            </article>
            <article>
              <span>Latenz</span>
              <strong data-ai-source-test-kpi="latency">0 ms</strong>
            </article>
          </div>
          <div className="source-test-sources" data-ai-source-test-sources />
          <div className="toolbar source-test-actions" data-ai-source-test-actions hidden>
            <button className="btn btn-primary" type="button" data-ai-source-feedback="helpful">
              Gut
            </button>
            <button className="btn btn-secondary" type="button" data-ai-source-feedback="partially_helpful">
              Teilweise
            </button>
            <button className="btn btn-ghost" type="button" data-ai-source-feedback="not_helpful">
              Schlecht
            </button>
            <button className="btn btn-secondary" type="button" data-ai-source-create-faq>
              FAQ daraus erstellen
            </button>
            <button className="btn btn-ghost" type="button" data-ai-source-missing>
              Quelle fehlt
            </button>
          </div>
        </section>
      </div>

      <section className="panel mt-4">
        <div className="panel-header">
          <h3>Prompt-Vorschau</h3>
          <span className="panel-meta" data-ai-lab-meta>
            Noch kein Dry-run
          </span>
        </div>
        <pre className="ai-debug-prompt" data-ai-lab-preview>
          Wähle Workflow und Frage.
        </pre>
      </section>
    </>
  );
}

/**
 * Render the source check Admin-AI page.
 */
export function AdminAiSourceCheck(): ReactNode {
  return (
    <section className="ai-admin-area source-check-area" id="ai-source-check" data-ai-admin-area="source-check">
      <div className="ai-admin-area-header">
        <div>
          <span className="section-kicker">2. Quellenprüfung</span>
          <h3>Testfrage stellen, Quellen prüfen und direkt bewerten</h3>
          <p className="panel-meta">
            Dry-run bleibt kostenlos. Live-Test ist explizit und speichert normale Chat-, Audit-
            und Feedback-Daten.
          </p>
        </div>
        <span className="badge badge-ai" data-ai-section-status="lab">
          Bereit
        </span>
      </div>
      <AdminAiSourceTestPanel />
    </section>
  );
}

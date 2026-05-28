import { type ReactNode } from "react";

import { ADMIN_AI_NAVIGATION, type AdminAiView } from "./AdminAiTypes";
import { type AdminAiEffectivenessState } from "./adminAiEffectivenessModel";
import { overviewBadge, type AdminAiOverviewLoadState } from "./adminAiOverviewModel";
import { type AdminAiPromptFaqState } from "./adminAiPromptFaqModel";

type AdminAiShellProps = {
  readonly children: ReactNode;
  readonly effectivenessState: AdminAiEffectivenessState;
  readonly overviewState: AdminAiOverviewLoadState;
  readonly promptFaqState: AdminAiPromptFaqState;
  readonly view: AdminAiView;
};

/**
 * Render the shared Admin-AI page frame and canonical navigation.
 */
export function AdminAiShell({
  children,
  effectivenessState,
  overviewState,
  promptFaqState,
  view
}: AdminAiShellProps): ReactNode {
  const badge = overviewBadge(overviewState);
  const errorMessage =
    view === "overview"
      ? overviewState.errorMessage
      : view === "effectiveness"
        ? effectivenessState.errorMessage
        : view === "prompt_faq"
          ? promptFaqState.errorMessage || promptFaqState.statusMessage
        : "";

  return (
    <section className="page-section ai-admin-page" data-admin-ai-page data-ai-admin-view={view}>
      <header className="ai-admin-hero">
        <div>
          <span className="section-kicker">KI-Steuerzentrale</span>
          <h2>AI-Admin als RAG-Spielbrett</h2>
          <p className="panel-meta">
            Pflege Wissen, Index und Quellen wie ein übersichtliches Spielfeld: testen, bewerten,
            verbessern und Kosten im Blick behalten.
          </p>
        </div>
        <div className="ai-admin-hero-status" aria-label="KI-Administration Schnellstatus">
          <span className={`badge badge-ai ${badge.tone}`} data-ai-overview-state>
            {view === "overview" ? badge.label : "Noch nicht geladen"}
          </span>
          <span className="panel-meta">
            Fachliche Steuerung in RAG-Spielbrett, Quellenprüfung, Prompt & FAQ und Kosten.
          </span>
          <div className="surface-action-row" aria-label="KI-Administration Schnellzugriff">
            <a className="btn btn-primary btn-sm" href="/admin/ai/source-check">
              Testfrage prüfen
            </a>
            <a className="btn btn-secondary btn-sm" href="/admin/ai/rag-board">
              RAG pflegen
            </a>
            <a className="btn btn-ghost btn-sm" href="/admin/ai/effectiveness">
              Kosten ansehen
            </a>
          </div>
        </div>
      </header>

      {view === "overview" ? <AdminAiOverviewIntro view={view} /> : null}

      <nav className="ai-admin-nav" aria-label="KI-Administration Bereiche">
        {ADMIN_AI_NAVIGATION.map((item) => (
          <a
            aria-current={view === item.view ? "page" : undefined}
            className={view === item.view ? "is-active" : undefined}
            href={item.href}
            key={item.view}
          >
            {item.label}
          </a>
        ))}
      </nav>
      <p
        className="panel-meta ai-admin-load-message"
        data-ai-admin-message
        hidden={!errorMessage}
      >
        {errorMessage}
      </p>

      {view === "overview" ? <AdminAiMap view={view} /> : null}
      {children}
    </section>
  );
}

/**
 * Render the overview-only side navigation and test chat intro.
 */
function AdminAiOverviewIntro({ view }: { readonly view: AdminAiView }): ReactNode {
  return (
    <section className="knowledge-center-shell" aria-label="KI-Administrationscenter">
      <aside className="knowledge-side-nav" aria-label="KI-Administration Navigation">
        <div className="knowledge-side-brand">
          <span className="badge badge-ai">RAG aktiv</span>
          <strong>Spielbrett</strong>
          <small>
            RAG-Quellen, Testfragen, Prompts, FAQ, Kosten und technische Diagnose in einem
            Admin-Bereich.
          </small>
        </div>
        {ADMIN_AI_NAVIGATION.map((item) => (
          <a
            aria-current={view === item.view ? "page" : undefined}
            className={view === item.view ? "is-active" : undefined}
            href={item.href}
            key={item.view}
          >
            <span>{item.number}</span>
            <strong>{item.label}</strong>
            <small>{item.description}</small>
          </a>
        ))}
      </aside>
      <div className="knowledge-center-main">
        <div className="knowledge-center-header">
          <div>
            <span className="section-kicker">Admin-Arbeitsbereich</span>
            <h3>Antwortqualität fachlich steuerbar machen</h3>
            <p className="panel-meta">
              Jede Fläche zeigt, ob sie Quellenabdeckung, Indexgesundheit, Antwortqualität,
              Modellkosten oder technische Protokolle beeinflusst.
            </p>
          </div>
          <a className="btn btn-primary btn-sm" href="/documents">
            Dokumente hochladen
          </a>
        </div>
        <div className="document-card-grid" aria-label="KI-Administrationskomponenten">
          <article className="document-card">
            <span>RAG</span>
            <strong>Spielbrett pflegen</strong>
            <small>Zeigt Quellen, Indexfortschritt, Pflegeaktionen und Qualitätsstatus.</small>
          </article>
          <article className="document-card">
            <span>Prüfung</span>
            <strong>Testfragen bewerten</strong>
            <small>Sendet Testfragen, zeigt Quellen und speichert Feedback.</small>
          </article>
          <article className="document-card">
            <span>Prompt & FAQ</span>
            <strong>Antwortverhalten steuern</strong>
            <small>Verbindet Prompt-Versionen, FAQ-Entwürfe und Antwortbausteine.</small>
          </article>
          <article className="document-card">
            <span>Effektivität</span>
            <strong>Kosten gegen Nutzen sehen</strong>
            <small>Vergleicht Tokens, Kosten, Feedback und Quellenlücken.</small>
          </article>
        </div>
      </div>
      <aside className="knowledge-test-chat" aria-label="Antwort-Test Chat">
        <header>
          <span className="badge badge-ai">Test Chat</span>
          <strong>Quellenprüfung</strong>
        </header>
        <div className="test-chat-thread">
          <div className="test-chat-message is-assistant">
            Stelle eine Wartungsfrage. Die Antwort muss Quellen und Sicherheit zeigen.
          </div>
          <div className="test-chat-message is-user">
            Warum fällt Presse 3 bei Hydraulikdruck ab?
          </div>
          <div className="test-chat-message is-assistant">
            Prüfe Fehlerkatalog, Dokument-Textabschnitte und offene Aufgaben. Fehlende Quellen
            werden als Gap markiert.
          </div>
        </div>
        <div className="source-chip-row" aria-label="Quellenanzeige">
          <span className="source-chip">Fehlerkatalog</span>
          <span className="source-chip">FAQ</span>
          <span className="source-chip">Aufgabenverlauf</span>
        </div>
        <label className="chat-test-input" htmlFor="ai-admin-test-query">
          <span>Quellenabruf Abfrage</span>
          <input
            className="input input-bordered input-sm"
            id="ai-admin-test-query"
            placeholder="Frage an Wissensbasis testen"
          />
        </label>
      </aside>
    </section>
  );
}

/**
 * Render the overview-only Admin-AI route map.
 */
function AdminAiMap({ view }: { readonly view: AdminAiView }): ReactNode {
  return (
    <section className="ai-admin-map" aria-label="KI-Administration Struktur">
      {ADMIN_AI_NAVIGATION.map((item) => (
        <a className={view === item.view ? "is-active" : undefined} href={item.href} key={item.view}>
          <span>{item.number}</span>
          <strong>{item.label}</strong>
          <small>{item.description}</small>
        </a>
      ))}
    </section>
  );
}

import { type ReactNode } from "react";

import type { AdminAiOverviewLoadState } from "./adminAiOverviewModel";
import { displayText, numberText, recordReference } from "./AdminAiOverviewShared";

/**
 * Render Admin-AI event and chat activity panels.
 */
export function AdminAiOverviewActivity({
  onChatQueryChange,
  onEventErrorChange,
  overviewChatQuery,
  overviewEventError,
  overviewState
}: {
  readonly onChatQueryChange: (value: string) => void;
  readonly onEventErrorChange: (value: string) => void;
  readonly overviewChatQuery: string;
  readonly overviewEventError: string;
  readonly overviewState: AdminAiOverviewLoadState;
}): ReactNode {
  return (
    <div className="content-grid two-columns">
      <section className="panel">
        <div className="panel-header">
          <div>
            <h3>Letzte AI-Fehler</h3>
            <p className="panel-meta">Metadata-only Audit-Ereignisse zum Eingrenzen von Anbieter-, Modell- und Timeout-Problemen.</p>
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
            <thead><tr><th scope="col">Zeit</th><th scope="col">Workflow</th><th scope="col">Status</th><th scope="col">Fehler</th><th scope="col">Tokens</th></tr></thead>
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
                <tr><td colSpan={5}><span className="empty-state">Keine AI-Fehler für diesen Filter.</span></td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <div><h3>Letzte AI-Anfragen</h3><p className="panel-meta">Schneller Blick auf reale Chat-Nutzung und betroffene Workflows.</p></div>
          <input className="input input-bordered" data-ai-chat-search placeholder="Chats durchsuchen" value={overviewChatQuery} onChange={(event) => onChatQueryChange(event.target.value)} />
        </div>
        <div className="stack" data-ai-chats>
          {overviewState.chats.length ? overviewState.chats.map((chat) => (
            <article className="list-card" key={displayText(chat.id)}>
              <strong>{recordReference("Chat", chat.id)}</strong>
              <p>{displayText(chat.message, "Frage und Antwort sind in dieser Übersicht ausgeblendet.")}</p>
              <small>{[`Typ ${displayText(chat.response_type)}`, `Quellen ${numberText(chat.source_count)}`, `Workflow ${displayText(chat.workflow)}`].join(" / ")}</small>
            </article>
          )) : <p className="empty-state">Keine AI-Anfragen für diese Suche.</p>}
        </div>
      </section>
    </div>
  );
}

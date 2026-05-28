import type { ReactNode } from "react";

/**
 * Render document page header, command bar and help text.
 */
export function DocumentHeader(): ReactNode {
  return (
    <>
      <section className="page-hero">
        <div>
          <p className="page-kicker">Berichte</p>
          <h1 className="page-title">DokumentenÜbersicht</h1>
          <p className="page-description">Berichte und Handbücher als Wissensbasis prüfen, freigeben und herunterladen.</p>
        </div>
      </section>

      <nav className="page-command-bar" aria-label="Dokumente Schnellzugriff">
        <a className="quick-action-row" href="#generated-documents">
          <span>Generierte Dokumente prüfen</span>
          <strong>Berichte</strong>
        </a>
        <a className="quick-action-row" href="#machine-manuals">
          <span>Maschinenhandbücher prüfen</span>
          <strong>Handbücher</strong>
        </a>
        <a className="quick-action-row" data-dashboard-nav="admin_users" hidden href="/admin/ai">
          <span>Quellenstatus prüfen</span>
          <strong>Admin</strong>
        </a>
      </nav>

      <aside className="context-help" aria-label="Dokumente Orientierung">
        <strong>Warum sind Dokumente wichtig?</strong>
        <p>Handbücher und Berichte liefern belastbare Quellen. Gute Dokumente werden geprüft, freigegeben und für die Suche nutzbar gemacht.</p>
        <details className="help-disclosure">
          <summary>Was bedeutet Index-Nutzung?</summary>
          <p>Nur freigegebene und erfolgreich vorbereitete Inhalte können als Quelle in Antworten erscheinen. Der Admin-Bereich zeigt, wenn ein Dokument veraltet oder nicht synchron ist.</p>
        </details>
      </aside>
    </>
  );
}

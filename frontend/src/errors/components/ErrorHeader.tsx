import type { ReactNode } from "react";

type ErrorHeaderProps = {
  readonly onAnalysisFocus: () => void;
  readonly onSearchFocus: () => void;
  readonly writable: boolean;
};

/**
 * Render the incident hub hero and quick actions.
 */
export function ErrorHeader({ onAnalysisFocus, onSearchFocus, writable }: ErrorHeaderProps): ReactNode {
  return (
    <section className="page-hero incident-hub-hero">
      <div>
        <h1 className="page-title">Störungszentrale & Fehlerkatalog</h1>
        <p className="page-description">Störungen strukturiert erfassen, bekannte Fehler finden und Lösungen als belastbare Wissensbasis pflegen.</p>
      </div>
      <div className="incident-hero-actions">
        <a className="btn btn-primary btn-sm" data-permission-write="errors" hidden={!writable} href="#incident-create">Störung erfassen</a>
        <button className="btn btn-outline btn-sm" data-error-search-focus type="button" onClick={onSearchFocus}>Katalog durchsuchen</button>
        <button className="btn btn-ghost btn-sm" data-error-analysis-focus hidden={!writable} type="button" onClick={onAnalysisFocus}>Vorschlag erstellen</button>
      </div>
    </section>
  );
}

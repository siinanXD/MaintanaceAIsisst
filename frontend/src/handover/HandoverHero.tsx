import { type ReactNode } from "react";

type HandoverHeroProps = {
  readonly onFocusList: () => void;
};

/**
 * Render the handover page hero and quick actions.
 */
export function HandoverHero({ onFocusList }: HandoverHeroProps): ReactNode {
  return (
    <section className="page-hero handover-hero">
      <div>
        <h1 className="page-title">Schichtübergabe</h1>
        <p className="page-description">
          Strukturierte Übergabe für Produktion, Instandhaltung, Sicherheit, Material und offene
          Folgearbeiten.
        </p>
      </div>
      <div className="handover-hero-actions">
        <a className="btn btn-primary btn-sm" href="#handover-workflow" data-permission-write="shiftplans">
          Neue Übergabe
        </a>
        <button className="btn btn-outline btn-sm" type="button" data-handover-focus-list="" onClick={onFocusList}>
          Verlauf prüfen
        </button>
      </div>
    </section>
  );
}

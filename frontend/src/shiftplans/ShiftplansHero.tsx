import { type ReactNode } from "react";

/**
 * Render the shift planning page hero.
 */
export function ShiftplansHero(): ReactNode {
  return (
    <section className="page-hero no-print">
      <div>
        <p className="page-kicker">KI-Planung</p>
        <h1 className="page-title">Schichtplan</h1>
        <p className="page-description">
          Abteilung auswählen, Zeitraum festlegen und KI-gestützten Plan generieren - ArbZG-konform
          und fair verteilt.
        </p>
      </div>
    </section>
  );
}

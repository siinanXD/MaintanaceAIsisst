import type { ReactNode } from "react";

/**
 * Render employee page hero.
 */
export function EmployeeHeader(): ReactNode {
  return (
    <section className="page-hero">
      <div>
        <p className="page-kicker">Personalabteilung</p>
        <h1 className="page-title">Mitarbeiter</h1>
        <p className="page-description">Mitarbeiterdaten erfassen und Dokumente direkt an der Person ablegen.</p>
      </div>
    </section>
  );
}

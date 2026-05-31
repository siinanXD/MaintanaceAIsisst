import { type ReactNode } from "react";

import { PageActionBar } from "../components/ui/PageActionBar";
import { createActionDefinition } from "../components/ui/createActionSchema";

type ShiftplansHeroProps = {
  readonly onGenerateOpen: () => void;
  readonly writable: boolean;
};

/**
 * Render the shift planning page hero.
 */
export function ShiftplansHero({ onGenerateOpen, writable }: ShiftplansHeroProps): ReactNode {
  return (
    <section className="page-hero no-print is-compact">
      <div>
        <h1 className="page-title">Schichtplan</h1>
        <p className="page-description">
          Abteilung auswählen, Zeitraum festlegen und KI-gestützten Plan generieren.
        </p>
      </div>
      <PageActionBar
        label="Schichtplan Aktionen"
        actions={[
          { hidden: !writable, onClick: onGenerateOpen, schema: createActionDefinition("shiftplanGenerate"), variant: "primary" },
          { label: "Drucken", onClick: () => window.print(), variant: "outline" }
        ]}
      />
    </section>
  );
}

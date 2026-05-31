import { type ReactNode } from "react";

import { PageActionBar } from "../components/ui/PageActionBar";
import { createActionDefinition } from "../components/ui/createActionSchema";

type HandoverHeroProps = {
  readonly onCreateOpen: () => void;
  readonly onFocusList: () => void;
  readonly writable: boolean;
};

/**
 * Render the handover page hero and quick actions.
 */
export function HandoverHero({ onCreateOpen, onFocusList, writable }: HandoverHeroProps): ReactNode {
  return (
    <section className="page-hero handover-hero is-compact">
      <div>
        <h1 className="page-title">Schichtuebergabe</h1>
        <p className="page-description">
          Strukturierte Uebergabe für Produktion, Instandhaltung, Sicherheit, Material und offene Folgearbeiten.
        </p>
      </div>
      <PageActionBar
        label="Schichtuebergabe Aktionen"
        actions={[
          { hidden: !writable, onClick: onCreateOpen, schema: createActionDefinition("handoverCreate"), variant: "primary" },
          { label: "Verlauf prüfen", onClick: onFocusList, variant: "outline" }
        ]}
      />
    </section>
  );
}

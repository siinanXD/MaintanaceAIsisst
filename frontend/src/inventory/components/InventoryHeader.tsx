import type { ReactNode } from "react";

import { canViewDashboard } from "../../auth/permissions";
import { PageActionBar } from "../../components/ui/PageActionBar";
import { createActionDefinition } from "../../components/ui/createActionSchema";

type InventoryHeaderProps = {
  readonly onCreateMaterial: () => void;
  readonly writable: boolean;
};

/**
 * Render the inventory hero and command bar.
 */
export function InventoryHeader({ onCreateMaterial, writable }: InventoryHeaderProps): ReactNode {
  const canOpenMachines = canViewDashboard("machines");

  /**
   * Trigger the existing forecast form from the compact header action.
   */
  function submitForecastForm(): void {
    const form = document.getElementById("inventory-forecast-command-form");
    if (form instanceof HTMLFormElement) {
      form.requestSubmit();
    }
  }

  return (
    <section className="page-hero is-compact">
      <div>
        <h1 className="page-title">Lager</h1>
        <p className="page-description">
          Materialien mit Kosten, Anzahl, Hersteller und verbauter Maschine verwalten.
        </p>
      </div>
      <PageActionBar
        label="Lager Aktionen"
        actions={[
          { hidden: !writable, onClick: onCreateMaterial, schema: createActionDefinition("inventoryMaterialCreate"), variant: "primary" },
          { label: "Prognose berechnen", onClick: submitForecastForm, variant: "outline" },
          { hidden: !canOpenMachines, href: "/machines", label: "Maschinenbezug", variant: "ghost" }
        ]}
      />
    </section>
  );
}

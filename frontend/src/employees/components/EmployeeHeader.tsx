import type { ReactNode } from "react";

import { PageActionBar } from "../../components/ui/PageActionBar";
import { createActionDefinition } from "../../components/ui/createActionSchema";

type EmployeeHeaderProps = {
  readonly manageable: boolean;
  readonly onCreateEmployee: () => void;
};

/**
 * Render employee page hero.
 */
export function EmployeeHeader({ manageable, onCreateEmployee }: EmployeeHeaderProps): ReactNode {
  return (
    <section className="page-hero is-compact">
      <div>
        <h1 className="page-title">Mitarbeiter</h1>
        <p className="page-description">
          Mitarbeiterdaten erfassen und Dokumente direkt an der Person ablegen.
        </p>
      </div>
      <PageActionBar
        label="Mitarbeiter Aktionen"
        actions={[
          { hidden: !manageable, onClick: onCreateEmployee, schema: createActionDefinition("employeeCreate"), variant: "primary" }
        ]}
      />
    </section>
  );
}

import type { ReactNode } from "react";

/**
 * Render a collapsible intro for the incident hub workflow.
 */
export function ErrorOverviewIntro(): ReactNode {
  return (
    <details className="help-disclosure context-help incident-workflow-help" aria-label="So nutzen Sie die Störungszentrale">
      <summary>So nutzen Sie die Störungszentrale</summary>
      <div className="help-disclosure-body">
        <p className="panel-meta">
          Störung melden oder Katalog durchsuchen, ähnliche Fehler prüfen und Ursache sowie Lösung als
          Wissensbasis für spätere Analysen hinterlegen.
        </p>
      </div>
    </details>
  );
}

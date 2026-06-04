import type { ReactNode } from "react";

import type { DocumentReview, DocumentSummary } from "../documentTypes";
import { ReviewPanel, SummaryPanel } from "./DocumentPanels";

type DocumentInsightPanelsProps = {
  readonly review: DocumentReview | null;
  readonly summary: DocumentSummary | null;
};

/**
 * Group document review and summary output behind one expandable panel.
 */
export function DocumentInsightPanels({ review, summary }: DocumentInsightPanelsProps): ReactNode {
  if (!review && !summary) {
    return null;
  }

  const labelParts = [
    review ? "Prüfung" : null,
    summary ? "Zusammenfassung" : null
  ].filter(Boolean);

  return (
    <details className="help-disclosure ui-secondary-panel documents-insight-disclosure" open>
      <summary>Analyse-Ergebnisse ({labelParts.join(" + ")})</summary>
      <div className="help-disclosure-body documents-insight-stack">
        <ReviewPanel review={review} />
        <SummaryPanel summary={summary} />
      </div>
    </details>
  );
}

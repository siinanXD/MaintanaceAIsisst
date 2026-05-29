import { type ReactNode } from "react";

import { AdminAiSourceTestPanel } from "./AdminAiSectionsSourceCheck";
import { type AdminAiRagBoardProps } from "./AdminAiRagBoardTypes";
import { KnowledgeDocumentsPanel } from "./KnowledgeDocumentsPanel";
import { KnowledgeNetworkPanel } from "./KnowledgeNetworkPanel";
import { KnowledgeStatusPanel, RagHealthStrip, SourceHealthBoard } from "./KnowledgeStatusPanel";
import { ReindexJobsPanel } from "./ReindexJobsPanel";
import { TrainingEntriesPanel } from "./TrainingEntriesPanel";

/**
 * Render the RAG board, knowledge, training and source maintenance areas.
 */
export function AdminAiRagBoard(props: AdminAiRagBoardProps): ReactNode {
  const { ragBoardState } = props;

  return (
    <>
      <section className="ai-admin-area rag-board-area rag-game-shell" id="ai-rag-board" data-ai-admin-area="rag-board">
        <RagHealthStrip state={ragBoardState} />
        <SourceHealthBoard state={ragBoardState} />
        <ReindexJobsPanel {...props} />
        <section className="panel mt-4">
          <div className="panel-header">
            <h3>Quellen-Arena</h3>
            <span className="panel-meta">Testfrage direkt gegen aktuelle Quellen prüfen</span>
          </div>
          <AdminAiSourceTestPanel {...props} />
        </section>
      </section>

      <section className="ai-admin-area" id="ai-knowledge-sources" data-ai-admin-area="data-sources">
        <div className="ai-admin-area-header">
          <div>
            <span className="section-kicker">3. Wissensquellen</span>
            <h3>Welche Quellen speisen SQL, Keyword-Suche und RAG?</h3>
            <p className="panel-meta">
              Fehlerkatalog, Dokumente, Aufgaben, Maschinen, Material, Wartungspläne und
              Schichtdaten mit Status und Freigaben bewerten.
            </p>
          </div>
          <span className="badge badge-ai" data-ai-section-status="knowledge">
            {ragBoardState.isLoading ? "Wissen wird geladen" : "Wissen geladen"}
          </span>
        </div>
        <KnowledgeStatusPanel state={ragBoardState} />
        <KnowledgeNetworkPanel {...props} />
        <TrainingEntriesPanel {...props} />
        <KnowledgeDocumentsPanel {...props} />
      </section>
    </>
  );
}

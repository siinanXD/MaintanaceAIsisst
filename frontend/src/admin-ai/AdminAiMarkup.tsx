import { type ReactNode } from "react";

import { AdminAiEffectiveness } from "./AdminAiSectionsEffectiveness";
import { AdminAiOverview } from "./AdminAiSectionsOverview";
import { AdminAiPromptFaq } from "./AdminAiSectionsPromptFaq";
import { AdminAiRagBoard } from "./AdminAiSectionsRagBoard";
import { AdminAiSourceCheck } from "./AdminAiSectionsSourceCheck";
import { AdminAiTechnical } from "./AdminAiSectionsTechnical";
import { AdminAiShell } from "./AdminAiShell";
import { type AdminAiView } from "./AdminAiTypes";
import { type AdminAiEffectivenessState } from "./adminAiEffectivenessModel";
import { type AdminAiOverviewLoadState } from "./adminAiOverviewModel";
import { type AdminAiFaqEntry, type AdminAiPromptFaqState } from "./adminAiPromptFaqModel";

type AdminAiMarkupProps = {
  readonly effectivenessState: AdminAiEffectivenessState;
  readonly onApproveFaq: (entry: AdminAiFaqEntry) => void;
  readonly onFaqSubmit: (form: HTMLFormElement) => void;
  readonly onPromptVersionSubmit: (form: HTMLFormElement) => void;
  readonly overviewState: AdminAiOverviewLoadState;
  readonly promptFaqState: AdminAiPromptFaqState;
  readonly view: AdminAiView;
};

/**
 * Render the canonical Admin-AI view markup with legacy runtime hooks intact.
 */
export function AdminAiMarkup({
  effectivenessState,
  onApproveFaq,
  onFaqSubmit,
  onPromptVersionSubmit,
  overviewState,
  promptFaqState,
  view
}: AdminAiMarkupProps): ReactNode {
  return (
    <AdminAiShell
      effectivenessState={effectivenessState}
      overviewState={overviewState}
      promptFaqState={promptFaqState}
      view={view}
    >
      {adminAiViewContent({
        effectivenessState,
        onApproveFaq,
        onFaqSubmit,
        onPromptVersionSubmit,
        overviewState,
        promptFaqState,
        view
      })}
    </AdminAiShell>
  );
}

type AdminAiViewContentProps = AdminAiMarkupProps;

/**
 * Render the active Admin-AI section for the current canonical route.
 */
function adminAiViewContent({
  effectivenessState,
  onApproveFaq,
  onFaqSubmit,
  onPromptVersionSubmit,
  overviewState,
  promptFaqState,
  view
}: AdminAiViewContentProps): ReactNode {
  if (view === "rag_board") {
    return <AdminAiRagBoard />;
  }
  if (view === "source_check") {
    return <AdminAiSourceCheck />;
  }
  if (view === "prompt_faq") {
    return (
      <AdminAiPromptFaq
        onApproveFaq={onApproveFaq}
        onFaqSubmit={onFaqSubmit}
        onPromptVersionSubmit={onPromptVersionSubmit}
        promptFaqState={promptFaqState}
      />
    );
  }
  if (view === "effectiveness") {
    return <AdminAiEffectiveness effectivenessState={effectivenessState} />;
  }
  if (view === "technical") {
    return <AdminAiTechnical />;
  }
  return <AdminAiOverview overviewState={overviewState} />;
}

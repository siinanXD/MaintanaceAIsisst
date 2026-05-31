import { type ReactNode } from "react";

import { ADMIN_AI_NAVIGATION, type AdminAiView } from "./AdminAiTypes";
import { type AdminAiEffectivenessState } from "./adminAiEffectivenessModel";
import { overviewBadge, type AdminAiOverviewLoadState } from "./adminAiOverviewModel";
import { type AdminAiPromptFaqState } from "./adminAiPromptFaqModel";
import { type AdminAiRagBoardState } from "./adminAiRagBoardModel";
import { useAdminAiRoleAccess } from "./adminAiRoleAccess";
import { type AdminAiSourceCheckState } from "./adminAiSourceCheckModel";
import { type AdminAiTechnicalState } from "./adminAiTechnicalModel";

type AdminAiShellProps = {
  readonly children: ReactNode;
  readonly effectivenessState: AdminAiEffectivenessState;
  readonly overviewState: AdminAiOverviewLoadState;
  readonly promptFaqState: AdminAiPromptFaqState;
  readonly ragBoardState: AdminAiRagBoardState;
  readonly sourceCheckState: AdminAiSourceCheckState;
  readonly technicalState: AdminAiTechnicalState;
  readonly view: AdminAiView;
};

type AdminAiHeroStatus = {
  readonly label: string;
  readonly tone: "is-active" | "is-stale" | "is-error" | "is-muted";
};

type AdminAiHeroStatusProps = Omit<AdminAiShellProps, "children">;

/**
 * Render the shared Admin-AI page frame and canonical navigation.
 */
export function AdminAiShell({
  children,
  effectivenessState,
  overviewState,
  promptFaqState,
  ragBoardState,
  sourceCheckState,
  technicalState,
  view
}: AdminAiShellProps): ReactNode {
  const heroStatus = adminAiHeroStatus({
    effectivenessState,
    overviewState,
    promptFaqState,
    ragBoardState,
    sourceCheckState,
    technicalState,
    view
  });
  const roleAccess = useAdminAiRoleAccess();
  const visibleNavigation = useVisibleAdminAiNavigation();
  const errorMessage =
    view === "overview"
      ? overviewState.errorMessage
      : view === "effectiveness"
        ? effectivenessState.errorMessage
        : view === "prompt_faq"
          ? promptFaqState.errorMessage || promptFaqState.statusMessage
          : view === "source_check"
            ? sourceCheckState.errorMessage || sourceCheckState.statusMessage
            : view === "rag_board"
              ? ragBoardState.errorMessage || ragBoardState.statusMessage
              : view === "technical"
                ? technicalState.errorMessage || technicalState.statusMessage
                : "";

  return (
    <section className="page-section ai-admin-page" data-admin-ai-page data-ai-admin-view={view}>
      <header className="ai-admin-hero is-compact">
        <div>
          <span className="section-kicker">Admin Control Center</span>
          <h1>AI Admin Control Center</h1>
          <p className="panel-meta">
            Klare Steuerung für Status, Wissensbasis, Antwortqualitaet, Prompts, Kosten und
            technische Betriebsdiagnose.
          </p>
        </div>
        <div className="ai-admin-hero-status" aria-label="KI-Administration Schnellstatus">
          <span className={`badge badge-ai ${heroStatus.tone}`} data-ai-overview-state>
            {heroStatus.label}
          </span>
          <span className="panel-meta">
            AI-Admin-Daten folgen dem Backend-Vertrag: Master Admin.
          </span>
          <div
            className="surface-action-row"
            aria-label="KI-Administration Schnellzugriff"
            hidden={!roleAccess.canUseAdminAiApi}
          >
            <a className="btn btn-primary btn-sm" href="/admin/ai/source-check">
              Testfrage prüfen
            </a>
            <a className="btn btn-secondary btn-sm" href="/admin/ai/rag-board">
              Wissensbasis pflegen
            </a>
            <a className="btn btn-ghost btn-sm" href="/admin/ai/effectiveness">
              Kosten ansehen
            </a>
          </div>
        </div>
      </header>

      <nav className="ai-admin-nav" aria-label="KI-Administration Bereiche">
        {visibleNavigation.map((item) => (
          <a
            aria-current={view === item.view ? "page" : undefined}
            className={view === item.view ? "is-active" : undefined}
            href={item.href}
            key={item.view}
          >
            {item.label}
          </a>
        ))}
      </nav>
      <p
        className="panel-meta ai-admin-load-message"
        data-ai-admin-message
        hidden={!errorMessage}
      >
        {errorMessage}
      </p>

      {children}
    </section>
  );
}

/**
 * Return a status badge for the active Admin-AI section instead of the overview-only state.
 */
function adminAiHeroStatus({
  effectivenessState,
  overviewState,
  promptFaqState,
  ragBoardState,
  sourceCheckState,
  technicalState,
  view
}: AdminAiHeroStatusProps): AdminAiHeroStatus {
  if (view === "overview") return overviewBadge(overviewState);
  if (view === "effectiveness") {
    return loadingStatus(effectivenessState.isLoading, effectivenessState.errorMessage);
  }
  if (view === "prompt_faq") {
    return loadingStatus(
      promptFaqState.isLoading,
      promptFaqState.errorMessage,
      promptFaqState.isSaving ? "Speichert" : promptFaqState.statusMessage
    );
  }
  if (view === "rag_board") {
    return loadingStatus(
      ragBoardState.isLoading,
      ragBoardState.errorMessage,
      ragBoardState.isSaving ? "Aktualisiert" : ragBoardState.statusMessage
    );
  }
  if (view === "source_check") {
    if (sourceCheckState.isRunning) return { label: "Test laeuft", tone: "is-muted" };
    if (sourceCheckState.isSaving) return { label: "Speichert", tone: "is-stale" };
    if (sourceCheckState.errorMessage) return { label: "Fehler", tone: "is-error" };
    return {
      label: sourceCheckState.statusMessage || sourceCheckState.stateLabel,
      tone: toneFromClassName(sourceCheckState.stateClassName)
    };
  }
  if (view === "technical") {
    return loadingStatus(
      technicalState.isLoading,
      technicalState.errorMessage,
      technicalState.isSaving ? "Aktion laeuft" : technicalState.statusMessage
    );
  }
  return { label: "Bereit", tone: "is-muted" };
}

/**
 * Build a compact load status for Admin-AI sections backed by their own data hook.
 */
function loadingStatus(
  isLoading: boolean,
  errorMessage: string,
  statusMessage = ""
): AdminAiHeroStatus {
  if (isLoading) return { label: "Wird geladen", tone: "is-muted" };
  if (errorMessage) return { label: "Teilweise geladen", tone: "is-stale" };
  if (statusMessage) return { label: statusMessage, tone: "is-active" };
  return { label: "Geladen", tone: "is-active" };
}

/**
 * Reuse existing status-pill tones from Source Check for the shared hero badge.
 */
function toneFromClassName(className: string): AdminAiHeroStatus["tone"] {
  if (className.includes("is-error")) return "is-error";
  if (className.includes("is-stale")) return "is-stale";
  if (className.includes("is-active")) return "is-active";
  return "is-muted";
}

/**
 * Return the navigation entries visible to the current AI admin role.
 */
function useVisibleAdminAiNavigation(): typeof ADMIN_AI_NAVIGATION {
  const roleAccess = useAdminAiRoleAccess();
  if (!roleAccess.canUseAdminAiApi) return [];
  return ADMIN_AI_NAVIGATION.filter(
    (item) => item.view !== "technical" || roleAccess.isTechnicalRole
  );
}

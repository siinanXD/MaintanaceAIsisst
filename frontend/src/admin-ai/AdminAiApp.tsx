import { useEffect, useMemo, useState, type ReactNode } from "react";

import { markIslandMounted } from "../app/islandMount";
import {
  approveFaqEntry,
  createFaqEntry,
  createPromptVersion,
  loadFaqEntries,
  loadFaqSuggestions,
  loadAdminAiSummary,
  loadAdminAiUserCosts,
  loadAiStatus,
  loadOperationsHealth,
  loadPromptTemplates,
  loadRetrievalTelemetry,
  loadResponseSnippets
} from "./adminAiApi";
import { AdminAiMarkup } from "./AdminAiMarkup";
import { resolveAdminAiViewFromPathname } from "./AdminAiTypes";
import {
  EMPTY_ADMIN_AI_EFFECTIVENESS_STATE,
  failedEffectivenessState,
  userCostRows,
  type AdminAiEffectivenessState
} from "./adminAiEffectivenessModel";
import {
  EMPTY_ADMIN_AI_OVERVIEW_STATE,
  failedOverviewState,
  type AdminAiOverviewLoadState
} from "./adminAiOverviewModel";
import {
  EMPTY_ADMIN_AI_PROMPT_FAQ_STATE,
  failedPromptFaqState,
  faqEntries,
  faqSuggestions,
  formPayload,
  numericId,
  promptTemplates,
  responseSnippets,
  settledPayload,
  type AdminAiFaqEntry,
  type AdminAiPromptFaqState
} from "./adminAiPromptFaqModel";

const ADMIN_AI_ISLAND = {
  fallbackSelector: "[data-react-admin-ai-fallback]",
  mountedFlag: "maintenanceAdminAiReactMounted",
  mountEvent: "maintenance-admin-ai-react-mounted"
} as const;

type AdminAiRuntimeWindow = Window & {
  maintenanceAdminAiReactRuntime?: string;
};

/**
 * Render the Admin-AI page with React-owned markup and legacy runtime hooks.
 */
export function AdminAiApp(): ReactNode {
  const adminAiView = useMemo(
    () => resolveAdminAiViewFromPathname(window.location.pathname),
    []
  );
  const [overviewState, setOverviewState] = useState<AdminAiOverviewLoadState>(
    EMPTY_ADMIN_AI_OVERVIEW_STATE
  );
  const [effectivenessState, setEffectivenessState] = useState<AdminAiEffectivenessState>(
    EMPTY_ADMIN_AI_EFFECTIVENESS_STATE
  );
  const [promptFaqState, setPromptFaqState] = useState<AdminAiPromptFaqState>(
    EMPTY_ADMIN_AI_PROMPT_FAQ_STATE
  );

  useEffect(() => {
    markIslandMounted(ADMIN_AI_ISLAND);
  }, []);

  useEffect(() => {
    (window as AdminAiRuntimeWindow).maintenanceAdminAiReactRuntime =
      adminAiView === "overview" || adminAiView === "effectiveness" || adminAiView === "prompt_faq"
        ? adminAiView
        : "legacy-bridge";
  }, [adminAiView]);

  useEffect(() => {
    if (adminAiView !== "overview") return undefined;

    const controller = new AbortController();

    /**
     * Load all React-owned Admin-AI overview widgets without blocking the page on partial errors.
     */
    async function loadOverview(): Promise<void> {
      setOverviewState((currentState) => ({ ...currentState, isLoading: true, errorMessage: "" }));
      const [aiStatusResult, summaryResult, operationsResult] = await Promise.allSettled([
        loadAiStatus(controller.signal),
        loadAdminAiSummary(controller.signal),
        loadOperationsHealth(controller.signal)
      ]);

      if (controller.signal.aborted) return;

      const failedResult = [aiStatusResult, summaryResult, operationsResult].find(
        (result) => result.status === "rejected"
      );

      setOverviewState({
        aiStatus: aiStatusResult.status === "fulfilled" ? aiStatusResult.value : null,
        summary: summaryResult.status === "fulfilled" ? summaryResult.value : null,
        operations: operationsResult.status === "fulfilled" ? operationsResult.value : null,
        errorMessage:
          failedResult?.status === "rejected"
            ? failedOverviewState(failedResult.reason).errorMessage
            : "",
        isLoading: false
      });
    }

    void loadOverview();

    return () => {
      controller.abort();
    };
  }, [adminAiView]);

  useEffect(() => {
    if (adminAiView !== "effectiveness") return undefined;

    const controller = new AbortController();

    /**
     * Load React-owned Admin-AI effectiveness widgets with partial failure handling.
     */
    async function loadEffectiveness(): Promise<void> {
      setEffectivenessState((currentState) => ({
        ...currentState,
        errorMessage: "",
        isLoading: true
      }));
      const [summaryResult, userCostsResult, telemetryResult] = await Promise.allSettled([
        loadAdminAiSummary(controller.signal),
        loadAdminAiUserCosts(controller.signal),
        loadRetrievalTelemetry(controller.signal)
      ]);

      if (controller.signal.aborted) return;

      const failedResult = [summaryResult, userCostsResult, telemetryResult].find(
        (result) => result.status === "rejected"
      );
      const userCostsPayload = userCostsResult.status === "fulfilled" ? userCostsResult.value : null;

      setEffectivenessState({
        summary: summaryResult.status === "fulfilled" ? summaryResult.value : null,
        telemetry: telemetryResult.status === "fulfilled" ? telemetryResult.value : null,
        userCosts: userCostRows(userCostsPayload),
        errorMessage:
          failedResult?.status === "rejected"
            ? failedEffectivenessState(failedResult.reason).errorMessage
            : "",
        isLoading: false
      });
    }

    void loadEffectiveness();

    return () => {
      controller.abort();
    };
  }, [adminAiView]);

  useEffect(() => {
    if (adminAiView !== "prompt_faq") return undefined;

    const controller = new AbortController();
    void refreshPromptFaq(controller.signal);

    return () => {
      controller.abort();
    };
  }, [adminAiView]);

  /**
   * Load React-owned Prompt & FAQ data with partial failure handling.
   */
  async function refreshPromptFaq(signal?: AbortSignal): Promise<void> {
    setPromptFaqState((currentState) => ({
      ...currentState,
      errorMessage: "",
      isLoading: true
    }));
    const [promptsResult, faqResult, suggestionsResult, snippetsResult] = await Promise.allSettled([
      loadPromptTemplates(signal),
      loadFaqEntries(signal),
      loadFaqSuggestions(signal),
      loadResponseSnippets(signal)
    ]);

    if (signal?.aborted) return;

    const promptPayload = settledPayload(promptsResult);
    const faqPayload = settledPayload(faqResult);
    const suggestionsPayload = settledPayload(suggestionsResult);
    const snippetsPayload = settledPayload(snippetsResult);
    const suggestionPayload = faqSuggestions(suggestionsPayload);
    const failedResult = [promptsResult, faqResult, suggestionsResult, snippetsResult].find(
      (result) => result.status === "rejected"
    );

    setPromptFaqState((currentState) => ({
      ...currentState,
      errorMessage:
        failedResult?.status === "rejected"
          ? failedPromptFaqState(failedResult.reason).errorMessage
          : "",
      faqEntries: faqEntries(faqPayload),
      frequentQuestions: suggestionPayload.frequentQuestions,
      isLoading: false,
      knowledgeGaps: suggestionPayload.knowledgeGaps,
      prompts: promptTemplates(promptPayload),
      responseSnippets: responseSnippets(snippetsPayload)
    }));
  }

  /**
   * Create a prompt version from the visible Prompt & FAQ form.
   */
  async function handlePromptVersionSubmit(form: HTMLFormElement): Promise<void> {
    const payload = formPayload(form);
    const templateId = numericId(payload.template_id);
    if (!templateId) {
      setPromptFaqState((currentState) => ({
        ...currentState,
        promptFormStatus: "Bitte Workflow auswählen."
      }));
      return;
    }

    setPromptFaqState((currentState) => ({ ...currentState, isSaving: true, promptFormStatus: "Speichert..." }));
    try {
      await createPromptVersion(templateId, payload);
      form.reset();
      setPromptFaqState((currentState) => ({
        ...currentState,
        promptFormStatus: "Entwurf gespeichert",
        statusMessage: "Prompt-Entwurf gespeichert."
      }));
      await refreshPromptFaq();
    } catch (error) {
      setPromptFaqState((currentState) => ({
        ...currentState,
        errorMessage: failedPromptFaqState(error).errorMessage
      }));
    } finally {
      setPromptFaqState((currentState) => ({ ...currentState, isSaving: false }));
    }
  }

  /**
   * Create a manual FAQ draft from the visible Prompt & FAQ form.
   */
  async function handleFaqSubmit(form: HTMLFormElement): Promise<void> {
    const payload = {
      ...formPayload(form),
      source: "manual",
      status: "draft"
    };
    setPromptFaqState((currentState) => ({ ...currentState, isSaving: true }));
    try {
      await createFaqEntry(payload);
      form.reset();
      setPromptFaqState((currentState) => ({
        ...currentState,
        statusMessage: "FAQ-Entwurf gespeichert."
      }));
      await refreshPromptFaq();
    } catch (error) {
      setPromptFaqState((currentState) => ({
        ...currentState,
        errorMessage: failedPromptFaqState(error).errorMessage
      }));
    } finally {
      setPromptFaqState((currentState) => ({ ...currentState, isSaving: false }));
    }
  }

  /**
   * Approve one FAQ entry and refresh the visible list.
   */
  async function handleApproveFaq(entry: AdminAiFaqEntry): Promise<void> {
    const entryId = numericId(entry.id);
    if (!entryId) return;

    setPromptFaqState((currentState) => ({ ...currentState, isSaving: true }));
    try {
      await approveFaqEntry(entryId);
      setPromptFaqState((currentState) => ({
        ...currentState,
        statusMessage: "FAQ freigegeben und für den Index vorgemerkt."
      }));
      await refreshPromptFaq();
    } catch (error) {
      setPromptFaqState((currentState) => ({
        ...currentState,
        errorMessage: failedPromptFaqState(error).errorMessage
      }));
    } finally {
      setPromptFaqState((currentState) => ({ ...currentState, isSaving: false }));
    }
  }

  return (
    <div data-admin-ai-react-shell>
      <AdminAiMarkup
        effectivenessState={effectivenessState}
        onApproveFaq={(entry) => {
          void handleApproveFaq(entry);
        }}
        onFaqSubmit={(form) => {
          void handleFaqSubmit(form);
        }}
        onPromptVersionSubmit={(form) => {
          void handlePromptVersionSubmit(form);
        }}
        overviewState={overviewState}
        promptFaqState={promptFaqState}
        view={adminAiView}
      />
    </div>
  );
}

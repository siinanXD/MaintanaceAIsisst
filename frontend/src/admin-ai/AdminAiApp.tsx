import { useEffect, useMemo, useState, type ReactNode } from "react";

import { markIslandMounted } from "../app/islandMount";
import {
  approveFaqEntry,
  createFaqEntry,
  createPromptVersion,
  deleteKnowledgeDocument,
  deleteTrainingEntry,
  loadFaqEntries,
  loadFaqSuggestions,
  loadAdminAiSummary,
  loadAdminAiUserCosts,
  loadAdminJobs,
  loadAiObservability,
  loadAiStatus,
  loadKnowledgeDocuments,
  loadKnowledgeNetwork,
  loadKnowledgeStatus,
  loadOperationsHealth,
  loadPromptTemplates,
  loadRetrievalDebug,
  loadRetrievalTelemetry,
  loadResponseSnippets,
  loadTrainingEntries,
  queueKnowledgeReindexJob,
  reindexKnowledgeDocument,
  runAiChat,
  runKnowledgeReindex,
  runRetrievalEvaluation,
  saveTrainingEntry,
  submitAiFeedback,
  testPromptDryRun,
  updateKnowledgeQualityStatus,
  uploadKnowledgeDocument,
  type AdminAiPayload
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
import {
  EMPTY_ADMIN_AI_RAG_BOARD_STATE,
  failedRagBoardState,
  knowledgeQueryString,
  networkQueryString,
  ragItems,
  trainingFormFromEntry,
  trainingPayload,
  trainingQueryString,
  type AdminAiRagBoardFilters,
  type AdminAiRagBoardState,
  type AdminAiTrainingForm
} from "./adminAiRagBoardModel";
import {
  EMPTY_ADMIN_AI_SOURCE_CHECK_STATE,
  failedSourceCheckState,
  sourceCheckChatPayload,
  sourceCheckDryRunPayload,
  sourceCheckDryRunState,
  sourceCheckFaqPayload,
  sourceCheckFeedbackPayload,
  sourceCheckFormPayload,
  sourceCheckLiveState,
  sourceCheckQuestion,
  type AdminAiSourceCheckState
} from "./adminAiSourceCheckModel";
import {
  EMPTY_ADMIN_AI_TECHNICAL_STATE,
  failedTechnicalState,
  observabilityQueryString,
  retrievalDebugQueryString,
  technicalItems,
  type AdminAiTechnicalFilters,
  type AdminAiTechnicalState
} from "./adminAiTechnicalModel";

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
  const [sourceCheckState, setSourceCheckState] = useState<AdminAiSourceCheckState>(
    EMPTY_ADMIN_AI_SOURCE_CHECK_STATE
  );
  const [ragBoardState, setRagBoardState] = useState<AdminAiRagBoardState>(
    EMPTY_ADMIN_AI_RAG_BOARD_STATE
  );
  const [technicalState, setTechnicalState] = useState<AdminAiTechnicalState>(
    EMPTY_ADMIN_AI_TECHNICAL_STATE
  );

  useEffect(() => {
    markIslandMounted(ADMIN_AI_ISLAND);
  }, []);

  useEffect(() => {
    (window as AdminAiRuntimeWindow).maintenanceAdminAiReactRuntime =
      adminAiView === "overview"
      || adminAiView === "effectiveness"
      || adminAiView === "prompt_faq"
      || adminAiView === "source_check"
      || adminAiView === "rag_board"
      || adminAiView === "technical"
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

  useEffect(() => {
    if (adminAiView !== "rag_board") return undefined;

    const controller = new AbortController();
    void refreshRagBoard(controller.signal);

    return () => {
      controller.abort();
    };
  }, [adminAiView, ragBoardState.filters]);

  useEffect(() => {
    if (adminAiView !== "technical") return undefined;

    const controller = new AbortController();
    void refreshTechnical(controller.signal);

    return () => {
      controller.abort();
    };
  }, [adminAiView, technicalState.filters]);

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

  /**
   * Load all React-owned RAG Board datasets with partial failure handling.
   */
  async function refreshRagBoard(signal?: AbortSignal): Promise<void> {
    const filters = ragBoardState.filters;
    setRagBoardState((currentState) => ({ ...currentState, errorMessage: "", isLoading: true }));
    const [statusResult, knowledgeResult, trainingResult, networkResult, jobsResult] =
      await Promise.allSettled([
        loadKnowledgeStatus(signal),
        loadKnowledgeDocuments(knowledgeQueryString(filters), signal),
        loadTrainingEntries(trainingQueryString(filters), signal),
        loadKnowledgeNetwork(networkQueryString(filters), signal),
        loadAdminJobs(signal)
      ]);

    if (signal?.aborted) return;

    const failedResult = [
      statusResult,
      knowledgeResult,
      trainingResult,
      networkResult,
      jobsResult
    ].find((result) => result.status === "rejected");

    setRagBoardState((currentState) => ({
      ...currentState,
      errorMessage:
        failedResult?.status === "rejected"
          ? failedRagBoardState(failedResult.reason).errorMessage
          : "",
      isLoading: false,
      jobs: jobsResult.status === "fulfilled" ? ragItems(jobsResult.value) : currentState.jobs,
      knowledge:
        knowledgeResult.status === "fulfilled" ? ragItems(knowledgeResult.value) : currentState.knowledge,
      knowledgeStatus:
        statusResult.status === "fulfilled" ? statusResult.value : currentState.knowledgeStatus,
      network: networkResult.status === "fulfilled" ? networkResult.value : currentState.network,
      training:
        trainingResult.status === "fulfilled" ? ragItems(trainingResult.value) : currentState.training
    }));
  }

  /**
   * Merge one RAG Board filter value and let the loading effect refresh the view.
   */
  function updateRagBoardFilter(key: keyof AdminAiRagBoardFilters, value: string): void {
    setRagBoardState((currentState) => ({
      ...currentState,
      filters: { ...currentState.filters, [key]: value }
    }));
  }

  /**
   * Run a RAG Board action and refresh the board afterwards.
   */
  async function runRagBoardAction(
    statusMessage: string,
    action: () => Promise<AdminAiPayload>
  ): Promise<void> {
    setRagBoardState((currentState) => ({
      ...currentState,
      errorMessage: "",
      isSaving: true,
      statusMessage
    }));
    try {
      await action();
      setRagBoardState((currentState) => ({
        ...currentState,
        isSaving: false,
        statusMessage: "RAG Board aktualisiert."
      }));
      await refreshRagBoard();
    } catch (error) {
      setRagBoardState((currentState) => ({
        ...currentState,
        errorMessage: failedRagBoardState(error).errorMessage,
        isSaving: false,
        statusMessage: ""
      }));
    }
  }

  /**
   * Save a manual training entry from the React editor.
   */
  async function handleSaveTraining(form: AdminAiTrainingForm): Promise<void> {
    const entryId = numericId(form.id);
    await runRagBoardAction("Training wird gespeichert...", () =>
      saveTrainingEntry(trainingPayload(form), entryId || undefined)
    );
    setRagBoardState((currentState) => ({
      ...currentState,
      trainingForm: EMPTY_ADMIN_AI_RAG_BOARD_STATE.trainingForm
    }));
  }

  /**
   * Upload a knowledge document from the React RAG Board.
   */
  async function handleKnowledgeUpload(form: HTMLFormElement): Promise<void> {
    const formData = new FormData(form);
    await runRagBoardAction("Dokument wird hochgeladen...", () => uploadKnowledgeDocument(formData));
    form.reset();
  }

  /**
   * Load all React-owned Technical datasets with partial failure handling.
   */
  async function refreshTechnical(signal?: AbortSignal): Promise<void> {
    const filters = technicalState.filters;
    setTechnicalState((currentState) => ({ ...currentState, errorMessage: "", isLoading: true }));
    const [telemetryResult, debugResult, observabilityResult, jobsResult, operationsResult] =
      await Promise.allSettled([
        loadRetrievalTelemetry(signal),
        loadRetrievalDebug(retrievalDebugQueryString(filters), signal),
        loadAiObservability(observabilityQueryString(), signal),
        loadAdminJobs(signal),
        loadOperationsHealth(signal)
      ]);

    if (signal?.aborted) return;

    const failedResult = [
      telemetryResult,
      debugResult,
      observabilityResult,
      jobsResult,
      operationsResult
    ].find((result) => result.status === "rejected");

    setTechnicalState((currentState) => ({
      ...currentState,
      errorMessage:
        failedResult?.status === "rejected"
          ? failedTechnicalState(failedResult.reason).errorMessage
          : "",
      isLoading: false,
      jobs: jobsResult.status === "fulfilled" ? technicalItems(jobsResult.value) : currentState.jobs,
      observability:
        observabilityResult.status === "fulfilled"
          ? observabilityResult.value
          : currentState.observability,
      operations:
        operationsResult.status === "fulfilled" ? operationsResult.value : currentState.operations,
      retrievalDebug:
        debugResult.status === "fulfilled" ? technicalItems(debugResult.value) : currentState.retrievalDebug,
      telemetry: telemetryResult.status === "fulfilled" ? telemetryResult.value : currentState.telemetry
    }));
  }

  /**
   * Merge one Technical filter and let the loading effect refresh the view.
   */
  function updateTechnicalFilter(key: keyof AdminAiTechnicalFilters, value: string): void {
    setTechnicalState((currentState) => ({
      ...currentState,
      filters: { ...currentState.filters, [key]: value }
    }));
  }

  /**
   * Run a Technical action and refresh diagnostics afterwards.
   */
  async function runTechnicalAction(
    statusMessage: string,
    action: () => Promise<AdminAiPayload>
  ): Promise<void> {
    setTechnicalState((currentState) => ({
      ...currentState,
      errorMessage: "",
      isSaving: true,
      statusMessage
    }));
    try {
      await action();
      setTechnicalState((currentState) => ({
        ...currentState,
        isSaving: false,
        statusMessage: "Technische Diagnose aktualisiert."
      }));
      await refreshTechnical();
    } catch (error) {
      setTechnicalState((currentState) => ({
        ...currentState,
        errorMessage: failedTechnicalState(error).errorMessage,
        isSaving: false,
        statusMessage: ""
      }));
    }
  }

  /**
   * Run a dry or live source test from the React-owned Source Check view.
   */
  async function handleSourceTestSubmit(form: HTMLFormElement, intent?: string): Promise<void> {
    const payload = sourceCheckFormPayload(form);
    const mode = intent || String(payload.mode || "dry");
    const question = sourceCheckQuestion(payload);

    setSourceCheckState((currentState) => ({
      ...currentState,
      errorMessage: "",
      isRunning: true,
      statusMessage: "Quellenprüfung wird ausgeführt..."
    }));

    try {
      if (mode !== "live") {
        const dryRunResult = await testPromptDryRun(sourceCheckDryRunPayload(payload));
        setSourceCheckState({
          ...sourceCheckDryRunState(dryRunResult, question),
          statusMessage: "Dry-run ausgeführt."
        });
        return;
      }

      const liveResult = await runAiChat(sourceCheckChatPayload(payload));
      setSourceCheckState({
        ...sourceCheckLiveState(liveResult, question),
        statusMessage: "Live-Quellenprüfung ausgeführt."
      });
    } catch (error) {
      setSourceCheckState((currentState) => ({
        ...currentState,
        errorMessage: failedSourceCheckState(error).errorMessage,
        isRunning: false,
        statusMessage: ""
      }));
    }
  }

  /**
   * Store feedback for the latest live Source Check result.
   */
  async function handleSourceFeedback(rating: string, comment?: string): Promise<void> {
    if (!sourceCheckState.latestTest || sourceCheckState.latestTest.mode !== "live") {
      setSourceCheckState((currentState) => ({
        ...currentState,
        errorMessage: "Keine Live-Quellenprüfung vorhanden."
      }));
      return;
    }

    setSourceCheckState((currentState) => ({
      ...currentState,
      errorMessage: "",
      isSaving: true,
      statusMessage: "Bewertung wird gespeichert..."
    }));

    try {
      await submitAiFeedback(
        sourceCheckFeedbackPayload(
          sourceCheckState.latestTest,
          rating,
          comment || "Bewertung aus KI-Admin Quellenprüfung"
        )
      );
      setSourceCheckState((currentState) => ({
        ...currentState,
        isSaving: false,
        statusMessage:
          rating === "not_helpful" && comment
            ? "Fehlende Quelle als negatives Feedback markiert."
            : "Quellenprüfung bewertet."
      }));
    } catch (error) {
      setSourceCheckState((currentState) => ({
        ...currentState,
        errorMessage: failedSourceCheckState(error).errorMessage,
        isSaving: false,
        statusMessage: ""
      }));
    }
  }

  /**
   * Create a FAQ draft from the latest live Source Check result.
   */
  async function handleCreateSourceFaq(): Promise<void> {
    if (!sourceCheckState.latestTest || sourceCheckState.latestTest.mode !== "live") {
      setSourceCheckState((currentState) => ({
        ...currentState,
        errorMessage: "Keine Live-Quellenprüfung vorhanden."
      }));
      return;
    }

    setSourceCheckState((currentState) => ({
      ...currentState,
      errorMessage: "",
      isSaving: true,
      statusMessage: "FAQ-Entwurf wird erstellt..."
    }));

    try {
      await createFaqEntry(sourceCheckFaqPayload(sourceCheckState.latestTest));
      setSourceCheckState((currentState) => ({
        ...currentState,
        isSaving: false,
        statusMessage: "FAQ-Entwurf aus der Testfrage erstellt."
      }));
    } catch (error) {
      setSourceCheckState((currentState) => ({
        ...currentState,
        errorMessage: failedSourceCheckState(error).errorMessage,
        isSaving: false,
        statusMessage: ""
      }));
    }
  }

  return (
    <div data-admin-ai-react-shell>
      <AdminAiMarkup
        effectivenessState={effectivenessState}
        onApproveFaq={(entry) => {
          void handleApproveFaq(entry);
        }}
        onCreateSourceFaq={() => {
          void handleCreateSourceFaq();
        }}
        onDeleteKnowledge={(documentId) => {
          void runRagBoardAction("Dokument wird gelöscht...", () => deleteKnowledgeDocument(documentId));
        }}
        onDeleteTraining={(entryId) => {
          void runRagBoardAction("Training wird gelöscht...", () => deleteTrainingEntry(entryId));
        }}
        onFaqSubmit={(form) => {
          void handleFaqSubmit(form);
        }}
        onKnowledgeFilterChange={updateRagBoardFilter}
        onKnowledgeUpload={(form) => {
          void handleKnowledgeUpload(form);
        }}
        onNetworkFilterChange={updateRagBoardFilter}
        onPromptVersionSubmit={(form) => {
          void handlePromptVersionSubmit(form);
        }}
        onQueueDocument={(documentId) => {
          void runRagBoardAction("Dokument-Reindex-Job wird eingeplant...", () =>
            queueKnowledgeReindexJob({ document_id: documentId })
          );
        }}
        onQueueStale={() => {
          void runRagBoardAction("Stale-Reindex-Job wird eingeplant...", () =>
            queueKnowledgeReindexJob({ mode: "stale" })
          );
        }}
        onReindexAll={() => {
          void runRagBoardAction("Wissen wird neu indexiert...", () =>
            runKnowledgeReindex()
          );
        }}
        onReindexDocument={(documentId) => {
          void runRagBoardAction("Dokument wird neu indexiert...", () =>
            reindexKnowledgeDocument(documentId)
          );
        }}
        onReindexStale={() => {
          void runRagBoardAction("Veraltete Quellen werden neu indexiert...", () =>
            runKnowledgeReindex("?mode=stale")
          );
        }}
        onSaveTraining={(form) => {
          void handleSaveTraining(form);
        }}
        onSelectTraining={(entry) => {
          setRagBoardState((currentState) => ({
            ...currentState,
            trainingForm: trainingFormFromEntry(entry)
          }));
        }}
        onSourceFeedback={(rating, comment) => {
          void handleSourceFeedback(rating, comment);
        }}
        onSourceReset={() => {
          setSourceCheckState(EMPTY_ADMIN_AI_SOURCE_CHECK_STATE);
        }}
        onSourceTestSubmit={(form, intent) => {
          void handleSourceTestSubmit(form, intent);
        }}
        onTrainingFilterChange={updateRagBoardFilter}
        onTrainingFormChange={(form) => {
          setRagBoardState((currentState) => ({ ...currentState, trainingForm: form }));
        }}
        onTechnicalFilterChange={updateTechnicalFilter}
        onTechnicalRefresh={() => {
          void refreshTechnical();
        }}
        onTechnicalRunEvaluation={() => {
          void runTechnicalAction("Golden Eval wird ausgeführt...", runRetrievalEvaluation);
        }}
        onUpdateKnowledgeQuality={(documentId, qualityStatus) => {
          void runRagBoardAction("Qualitätsstatus wird gesetzt...", () =>
            updateKnowledgeQualityStatus(documentId, qualityStatus)
          );
        }}
        overviewState={overviewState}
        promptFaqState={promptFaqState}
        ragBoardState={ragBoardState}
        sourceCheckState={sourceCheckState}
        technicalState={technicalState}
        view={adminAiView}
      />
    </div>
  );
}

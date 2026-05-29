import {
  useEffect,
  useMemo,
  useState,
  type ReactNode
} from "react";

import { markIslandMounted } from "../app/islandMount";
import { canWriteDashboard } from "../auth/permissions";
import { loadDepartments, loadErrors } from "./errorApi";
import { ErrorAnalysisPanel } from "./components/ErrorAnalysisPanel";
import { ErrorCatalog } from "./components/ErrorCatalog";
import { ErrorCreatePanel } from "./components/ErrorCreatePanel";
import { ErrorEditDialog } from "./components/ErrorEditDialog";
import { ErrorHeader } from "./components/ErrorHeader";
import { ErrorStats } from "./components/ErrorStats";
import { SimilarErrorsPanel } from "./components/SimilarErrorsPanel";
import type {
  Department,
  ErrorDraft,
  ErrorEntry,
  ErrorFilters,
  MessageState,
  SimilarErrorResult
} from "./errorTypes";
import {
  createEmptyErrorDraft,
  errorMessage,
  initialErrorSearchQuery
} from "./errorUtils";

const ERRORS_ISLAND = {
  mountedFlag: "maintenanceErrorsReactMounted",
  mountEvent: "maintenance-errors-react-mounted"
};

/**
 * Return the user's first visible department as form default.
 */
function defaultDepartment(departments: readonly Department[]): string {
  return departments[0]?.name || "";
}

/**
 * Render the React errors workflow island.
 */
export function ErrorsApp(): ReactNode {
  const writable = canWriteDashboard("errors");
  const [createDraft, setCreateDraft] = useState<ErrorDraft>(createEmptyErrorDraft());
  const [departments, setDepartments] = useState<Department[]>([]);
  const [editingError, setEditingError] = useState<ErrorEntry | null>(null);
  const [errors, setErrors] = useState<ErrorEntry[]>([]);
  const [filters, setFilters] = useState<ErrorFilters>({
    search: initialErrorSearchQuery(),
    status: "",
    severity: "",
    category: "",
    quick: "all"
  });
  const [message, setMessage] = useState<MessageState>({ text: "", error: false });
  const [similarResult, setSimilarResult] = useState<SimilarErrorResult | null>(null);

  const currentDepartment = useMemo(() => createDraft.department || defaultDepartment(departments), [createDraft.department, departments]);

  /**
   * Refresh departments and visible errors in parallel.
   */
  async function refreshErrorsData(): Promise<void> {
    const [loadedDepartments, loadedErrors] = await Promise.all([
      loadDepartments(),
      loadErrors()
    ]);
    setDepartments(loadedDepartments);
    setErrors(loadedErrors);
    setCreateDraft((draft) => ({
      ...draft,
      department: draft.department || defaultDepartment(loadedDepartments)
    }));
  }

  /**
   * Focus the catalog search input.
   */
  function focusSearch(): void {
    document.querySelector<HTMLInputElement>("[data-error-search]")?.focus();
  }

  /**
   * Focus the analysis textarea.
   */
  function focusAnalysis(): void {
    document.querySelector("[data-error-analyze-form]")?.scrollIntoView({ behavior: "smooth", block: "center" });
    window.requestAnimationFrame(() => {
      document.querySelector<HTMLTextAreaElement>("#error-analysis-description")?.focus();
    });
  }

  /**
   * Apply a draft produced by AI analysis.
   */
  function applyDraft(draft: ErrorDraft): void {
    setCreateDraft(draft);
    document.querySelector("[data-error-form]")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  useEffect(() => {
    markIslandMounted(ERRORS_ISLAND);
  }, []);

  useEffect(() => {
    refreshErrorsData().catch((error: unknown) => {
      setMessage({ text: errorMessage(error), error: true });
    });
  }, []);

  return (
    <>
      <ErrorHeader onAnalysisFocus={focusAnalysis} onSearchFocus={focusSearch} writable={writable} />
      <ErrorStats errors={errors} />
      {message.text ? (
        <section className="card app-card" role="alert">
          <div className="card-body">
            <p className={`panel-meta${message.error ? " is-error" : ""}`}>{message.text}</p>
          </div>
        </section>
      ) : null}
      <section className="incident-workflow-grid" aria-label="Störungsworkflows">
        <ErrorCreatePanel
          departments={departments}
          draft={createDraft}
          hidden={!writable}
          message={message}
          onDraftChange={setCreateDraft}
          onMessageChange={setMessage}
          onSaved={refreshErrorsData}
          onSimilarResult={setSimilarResult}
        />
        <ErrorAnalysisPanel
          currentDepartment={currentDepartment}
          hidden={!writable}
          onApplyDraft={applyDraft}
          onSimilarResult={setSimilarResult}
        />
        <SimilarErrorsPanel result={similarResult} />
      </section>
      <ErrorCatalog
        errors={errors}
        filters={filters}
        onEdit={setEditingError}
        onFiltersChange={setFilters}
        onMessageChange={setMessage}
        onMutated={refreshErrorsData}
        onSimilarResult={setSimilarResult}
        writable={writable}
      />
      <ErrorEditDialog
        departments={departments}
        entry={editingError}
        onClose={() => setEditingError(null)}
        onMessageChange={setMessage}
        onSaved={refreshErrorsData}
      />
    </>
  );
}

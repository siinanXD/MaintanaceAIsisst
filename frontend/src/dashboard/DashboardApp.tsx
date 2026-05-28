import { useCallback, useEffect, useState, type ReactNode } from "react";

import { markIslandMounted } from "../app/islandMount";
import { safeErrorMessage } from "../utils/errors";
import {
  completeDashboardTask,
  loadDashboardRuntimeData,
  loadDashboardShiftCalendar,
  loadDashboardTask,
  startDashboardTask,
  updateDashboardTask,
  type DashboardPayload,
  type DashboardShiftCalendar,
  type DashboardTaskMutation,
  type DashboardTaskReportPayload
} from "./dashboardApi";
import { DashboardMarkup } from "./DashboardMarkup";
import { EMPTY_DASHBOARD_VIEW_STATE, type DashboardViewState } from "./dashboardModel";
import { employeesToShiftCalendar } from "./dashboardShiftModel";

const DASHBOARD_ISLAND = {
  fallbackSelector: "[data-react-dashboard-fallback]",
  mountedFlag: "maintenanceDashboardReactMounted",
  mountEvent: "maintenance-dashboard-react-mounted"
} as const;

declare global {
  interface Window {
    maintenanceDashboardReactAssetsOwned?: boolean;
    maintenanceDashboardReactOperationsOwned?: boolean;
    maintenanceDashboardReactPeopleOwned?: boolean;
    maintenanceDashboardReactShiftOwned?: boolean;
    maintenanceDashboardReactSideOwned?: boolean;
    maintenanceDashboardReactTasksOwned?: boolean;
  }
}

/**
 * Render the dashboard with React-owned markup and initial React data loading.
 */
export function DashboardApp(): ReactNode {
  const [dashboardState, setDashboardState] = useState<DashboardViewState>(EMPTY_DASHBOARD_VIEW_STATE);
  const [activeTask, setActiveTask] = useState<DashboardPayload | null>(null);
  const [isTaskBusy, setIsTaskBusy] = useState(false);
  const [isShiftCalendarLoading, setIsShiftCalendarLoading] = useState(true);
  const [selectedShiftEmployeeId, setSelectedShiftEmployeeId] = useState("");
  const [shiftCalendar, setShiftCalendar] = useState<DashboardShiftCalendar | null>(null);
  const [taskMessage, setTaskMessage] = useState("");

  const refreshDashboardData = useCallback(async (signal?: AbortSignal): Promise<void> => {
    setDashboardState((currentState) => ({ ...currentState, errorMessage: "", isLoading: true }));
    const data = await loadDashboardRuntimeData(signal);
    setDashboardState({
      data,
      errorMessage: data.loadErrors.join(" | "),
      isLoading: false
    });
  }, []);

  useEffect(() => {
    window.maintenanceDashboardReactAssetsOwned = true;
    window.maintenanceDashboardReactOperationsOwned = true;
    window.maintenanceDashboardReactPeopleOwned = true;
    window.maintenanceDashboardReactShiftOwned = true;
    window.maintenanceDashboardReactSideOwned = true;
    window.maintenanceDashboardReactTasksOwned = true;
    markIslandMounted(DASHBOARD_ISLAND);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    refreshDashboardData(controller.signal).catch((error: unknown) => {
      if (controller.signal.aborted) {
        return;
      }

      setDashboardState((currentState) => ({
        ...currentState,
        errorMessage: safeErrorMessage(error, "Dashboard-Daten konnten nicht geladen werden."),
        isLoading: false
      }));
    });

    return () => {
      controller.abort();
    };
  }, [refreshDashboardData]);

  useEffect(() => {
    const controller = new AbortController();

    async function refreshShiftCalendar(): Promise<void> {
      setIsShiftCalendarLoading(true);
      try {
        if (selectedShiftEmployeeId) {
          setShiftCalendar(await loadDashboardShiftCalendar(selectedShiftEmployeeId, controller.signal));
        } else {
          setShiftCalendar(employeesToShiftCalendar(dashboardState.data.employees));
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          setShiftCalendar({ entries: [], message: safeErrorMessage(error, "Schichtkalender konnte nicht geladen werden.") });
        }
      } finally {
        if (!controller.signal.aborted) {
          setIsShiftCalendarLoading(false);
        }
      }
    }

    void refreshShiftCalendar();
    const intervalId = window.setInterval(() => {
      void refreshShiftCalendar();
    }, 60 * 1000);

    return () => {
      controller.abort();
      window.clearInterval(intervalId);
    };
  }, [dashboardState.data.employees, selectedShiftEmployeeId]);

  /**
   * Open one task in the React dashboard detail modal.
   */
  async function handleOpenTask(taskId: number): Promise<void> {
    if (!taskId) return;
    setIsTaskBusy(true);
    setTaskMessage("");
    try {
      setActiveTask(await loadDashboardTask(taskId));
    } catch (error) {
      setTaskMessage(safeErrorMessage(error, "Aufgabe konnte nicht geladen werden."));
    } finally {
      setIsTaskBusy(false);
    }
  }

  /**
   * Close the React dashboard task detail modal.
   */
  function handleCloseTask(): void {
    setActiveTask(null);
    setTaskMessage("");
  }

  /**
   * Run a task mutation and refresh the dashboard state afterwards.
   */
  async function runTaskMutation(
    successMessage: string,
    mutation: () => Promise<DashboardPayload>
  ): Promise<void> {
    if (!activeTask?.id) return;
    setIsTaskBusy(true);
    setTaskMessage("");
    try {
      const result = await mutation();
      const suffix = result.generated_document ? " Wartungsbericht wurde erzeugt." : "";
      setActiveTask(await loadDashboardTask(Number(activeTask.id)));
      setTaskMessage(successMessage + suffix);
      await refreshDashboardData();
    } catch (error) {
      setTaskMessage(safeErrorMessage(error, "Aufgabe konnte nicht aktualisiert werden."));
    } finally {
      setIsTaskBusy(false);
    }
  }

  /**
   * Start the active dashboard task.
   */
  function handleStartTask(): void {
    void runTaskMutation("Aufgabe gestartet.", () => startDashboardTask(Number(activeTask?.id || 0)));
  }

  /**
   * Complete the active dashboard task.
   */
  function handleCompleteTask(payload: DashboardTaskReportPayload): void {
    void runTaskMutation("Aufgabe abgeschlossen.", () =>
      completeDashboardTask(Number(activeTask?.id || 0), payload)
    );
  }

  /**
   * Save task edits from the dashboard detail modal.
   */
  function handleUpdateTask(payload: DashboardTaskMutation): void {
    void runTaskMutation("Aufgabe aktualisiert.", () =>
      updateDashboardTask(Number(activeTask?.id || 0), payload)
    );
  }

  return (
    <div data-dashboard-react-shell data-dashboard-react-runtime={dashboardState.isLoading ? "loading" : "ready"}>
      <DashboardMarkup
        activeTask={activeTask}
        dashboardState={dashboardState}
        isTaskBusy={isTaskBusy}
        isShiftCalendarLoading={isShiftCalendarLoading}
        onCloseTask={handleCloseTask}
        onCompleteTask={handleCompleteTask}
        onOpenTask={handleOpenTask}
        onStartTask={handleStartTask}
        onShiftEmployeeChange={setSelectedShiftEmployeeId}
        onUpdateTask={handleUpdateTask}
        selectedShiftEmployeeId={selectedShiftEmployeeId}
        shiftCalendar={shiftCalendar}
        taskMessage={taskMessage}
      />
    </div>
  );
}

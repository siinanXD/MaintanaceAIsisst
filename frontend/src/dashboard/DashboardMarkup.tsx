import { type ReactNode } from "react";

import { DashboardAssetStatus } from "./DashboardAssetStatus";
import { DashboardHiddenForms } from "./DashboardHiddenForms";
import { DashboardHero } from "./DashboardHero";
import { DashboardKpis } from "./DashboardKpis";
import { DashboardOperations } from "./DashboardOperations";
import { DashboardShiftPeople } from "./DashboardShiftPeople";
import { DashboardSideColumn } from "./DashboardSideColumn";
import { DashboardTaskDetailModal } from "./DashboardTaskDetailModal";
import { DashboardTaskOverview } from "./DashboardTaskOverview";
import { DashboardTechnicalDetails } from "./DashboardTechnicalDetails";
import {
  type DashboardPayload,
  type DashboardShiftCalendar,
  type DashboardTaskMutation,
  type DashboardTaskReportPayload
} from "./dashboardApi";
import { dashboardKpiCards, dashboardLoadMessage, type DashboardViewState } from "./dashboardModel";

type DashboardMarkupProps = {
  readonly activeTask: DashboardPayload | null;
  readonly cockpitMessage: string;
  readonly dashboardState: DashboardViewState;
  readonly draftTask: DashboardTaskMutation | null;
  readonly isDraftBusy: boolean;
  readonly isShiftCalendarLoading: boolean;
  readonly isTaskBusy: boolean;
  readonly onCloseTask: () => void;
  readonly onCompleteTask: (payload: DashboardTaskReportPayload) => void;
  readonly onDraftCancel: () => void;
  readonly onDraftChange: (payload: DashboardTaskMutation | null) => void;
  readonly onDraftSubmit: (payload: DashboardTaskMutation) => void;
  readonly onOpenTask: (taskId: number) => void;
  readonly onShiftEmployeeChange: (employeeId: string) => void;
  readonly onStartTask: () => void;
  readonly onSuggestSubmit: (text: string) => void;
  readonly onSuggestTextChange: (text: string) => void;
  readonly onUpdateTask: (payload: DashboardTaskMutation) => void;
  readonly selectedShiftEmployeeId: string;
  readonly shiftCalendar: DashboardShiftCalendar | null;
  readonly suggestText: string;
  readonly taskMessage: string;
};

/**
 * Render the dashboard shell with React-owned KPI data and legacy-compatible hooks.
 */
export function DashboardMarkup({
  activeTask,
  cockpitMessage,
  dashboardState,
  draftTask,
  isDraftBusy,
  isShiftCalendarLoading,
  isTaskBusy,
  onCloseTask,
  onCompleteTask,
  onDraftCancel,
  onDraftChange,
  onDraftSubmit,
  onOpenTask,
  onShiftEmployeeChange,
  onStartTask,
  onSuggestSubmit,
  onSuggestTextChange,
  onUpdateTask,
  selectedShiftEmployeeId,
  shiftCalendar,
  suggestText,
  taskMessage
}: DashboardMarkupProps): ReactNode {
  return (
    <div data-dashboard-static-shell>
      <span data-dashboard-react-status="" hidden>
        {dashboardLoadMessage(dashboardState)}
      </span>
      <DashboardHero dashboardState={dashboardState} />
      <DashboardKpis kpis={dashboardKpiCards(dashboardState)} />
      <section className="control-center-grid" aria-label="Maintenance Control Center">
        <DashboardTaskOverview dashboardState={dashboardState} onOpenTask={onOpenTask} />
        <DashboardAssetStatus dashboardState={dashboardState} />
        <DashboardShiftPeople
          dashboardState={dashboardState}
          isShiftCalendarLoading={isShiftCalendarLoading}
          onShiftEmployeeChange={onShiftEmployeeChange}
          selectedShiftEmployeeId={selectedShiftEmployeeId}
          shiftCalendar={shiftCalendar}
        />
        <DashboardOperations dashboardState={dashboardState} />
        <DashboardSideColumn dashboardState={dashboardState} />
        <DashboardTechnicalDetails dashboardState={dashboardState} />
        <DashboardHiddenForms
          cockpitMessage={cockpitMessage}
          draftTask={draftTask}
          isDraftBusy={isDraftBusy}
          onDraftCancel={onDraftCancel}
          onDraftChange={onDraftChange}
          onDraftSubmit={onDraftSubmit}
          onSuggestSubmit={onSuggestSubmit}
          onSuggestTextChange={onSuggestTextChange}
          suggestText={suggestText}
        />
        <DashboardTaskDetailModal
          activeTask={activeTask}
          isBusy={isTaskBusy}
          message={taskMessage}
          onClose={onCloseTask}
          onComplete={onCompleteTask}
          onStart={onStartTask}
          onUpdate={onUpdateTask}
        />
      </section>
    </div>
  );
}

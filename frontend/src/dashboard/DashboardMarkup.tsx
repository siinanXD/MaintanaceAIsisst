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
  readonly dashboardState: DashboardViewState;
  readonly isShiftCalendarLoading: boolean;
  readonly isTaskBusy: boolean;
  readonly onCloseTask: () => void;
  readonly onCompleteTask: (payload: DashboardTaskReportPayload) => void;
  readonly onOpenTask: (taskId: number) => void;
  readonly onShiftEmployeeChange: (employeeId: string) => void;
  readonly onStartTask: () => void;
  readonly onUpdateTask: (payload: DashboardTaskMutation) => void;
  readonly selectedShiftEmployeeId: string;
  readonly shiftCalendar: DashboardShiftCalendar | null;
  readonly taskMessage: string;
};

/**
 * Render the dashboard shell with React-owned KPI data and legacy-compatible hooks.
 */
export function DashboardMarkup({
  activeTask,
  dashboardState,
  isShiftCalendarLoading,
  isTaskBusy,
  onCloseTask,
  onCompleteTask,
  onOpenTask,
  onShiftEmployeeChange,
  onStartTask,
  onUpdateTask,
  selectedShiftEmployeeId,
  shiftCalendar,
  taskMessage
}: DashboardMarkupProps): ReactNode {
  return (
    <div data-dashboard-static-shell>
      <span data-dashboard-react-status="" hidden>
        {dashboardLoadMessage(dashboardState)}
      </span>
      <DashboardHero />
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
        <DashboardTechnicalDetails />
        <DashboardHiddenForms />
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

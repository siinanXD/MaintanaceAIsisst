import { type DashboardShiftCalendar } from "./dashboardApi";
import { type DashboardViewState } from "./dashboardModel";

export type DashboardShiftPeopleProps = {
  readonly dashboardState: DashboardViewState;
  readonly isShiftCalendarLoading: boolean;
  readonly onShiftEmployeeChange: (employeeId: string) => void;
  readonly selectedShiftEmployeeId: string;
  readonly shiftCalendar: DashboardShiftCalendar | null;
};

export type DashboardPeopleOnlyProps = {
  readonly dashboardState: DashboardViewState;
};

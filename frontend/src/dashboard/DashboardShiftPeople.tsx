import { type ReactNode } from "react";

import { PeopleHintsPanel } from "./DashboardPeoplePanel";
import { ShiftHandoverPanel } from "./DashboardShiftPanel";
import { type DashboardShiftPeopleProps } from "./DashboardShiftPeopleTypes";

/**
 * Render dashboard shift and people panels as React-owned markup.
 */
export function DashboardShiftPeople(props: DashboardShiftPeopleProps): ReactNode {
  return (
    <>
      <ShiftHandoverPanel {...props} />
      <PeopleHintsPanel {...props} />
    </>
  );
}

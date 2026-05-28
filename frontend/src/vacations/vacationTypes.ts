export type MaintenanceUser = {
  readonly id: number;
  readonly username?: string;
  readonly role?: string;
  readonly department?: string | { readonly name?: string };
  readonly employee_id?: number | null;
  readonly employee?: Employee | null;
  readonly permissions?: Record<string, { readonly can_view?: boolean; readonly can_write?: boolean }>;
};

export type Employee = {
  readonly id: number;
  readonly personnel_number?: string;
  readonly name?: string;
  readonly department?: string;
  readonly team?: number | null;
};

export type VacationSummary = {
  readonly employee_id: number;
  readonly name?: string;
  readonly department?: string;
  readonly team?: number | null;
  readonly shift_model?: string;
  readonly current_shift?: string;
  readonly qualifications?: string;
  readonly total?: number;
  readonly used?: number;
  readonly remaining?: number;
  readonly pending?: number;
  readonly available?: number;
};

export type VacationRequest = {
  readonly id: number;
  readonly employee_id: number;
  readonly employee?: Employee | null;
  readonly start_date?: string;
  readonly end_date?: string;
  readonly days_used?: number;
  readonly status?: string;
  readonly requested_by?: string | null;
  readonly approved_by?: string | null;
  readonly cancelled_by?: string | null;
  readonly department?: string;
  readonly shift_type?: string;
  readonly reason?: string;
  readonly representative_employee_id?: number | null;
  readonly representative?: Employee | null;
  readonly impact_level?: string;
  readonly impact_summary?: string;
  readonly notes?: string;
};

export type VacationDraft = {
  employeeId: string;
  startDate: string;
  endDate: string;
  shiftType: string;
  representativeEmployeeId: string;
  reason: string;
  notes: string;
};

export type VacationImpact = {
  readonly level?: string;
  readonly summary?: string;
  readonly workdays?: number;
  readonly overlap?: boolean;
  readonly balance_exceeded?: boolean;
};

export type VacationImpactResponse = {
  readonly impact?: VacationImpact;
};

export type MessageState = {
  readonly text: string;
  readonly type: "" | "error" | "success";
};

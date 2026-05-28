import { apiRequest } from "../api/client";
import { listData } from "../api/payload";
import type {
  Employee,
  MaintenanceUser,
  VacationDraft,
  VacationImpactResponse,
  VacationRequest,
  VacationSummary
} from "./vacationTypes";

/**
 * Load the current authenticated user from the existing auth endpoint.
 */
export async function loadCurrentUser(): Promise<MaintenanceUser> {
  return apiRequest<MaintenanceUser>("/api/v1/auth/me");
}

/**
 * Load employees visible to the current user.
 */
export async function loadVacationEmployees(): Promise<Employee[]> {
  return listData<Employee>(await apiRequest<unknown>("/api/v1/employees?limit=200"));
}

/**
 * Load vacation balances for a year.
 */
export async function loadVacationSummary(year: string): Promise<VacationSummary[]> {
  return listData<VacationSummary>(await apiRequest<unknown>(`/api/v1/vacations/summary?year=${encodeURIComponent(year)}`));
}

/**
 * Load vacation requests for a year.
 */
export async function loadVacationRequests(year: string): Promise<VacationRequest[]> {
  return listData<VacationRequest>(await apiRequest<unknown>(`/api/v1/vacations?year=${encodeURIComponent(year)}`));
}

/**
 * Preview the operational impact for a draft request.
 */
export async function previewVacationImpact(draft: VacationDraft): Promise<VacationImpactResponse> {
  const params = new URLSearchParams({
    employee_id: draft.employeeId,
    start_date: draft.startDate,
    end_date: draft.endDate,
    shift_type: draft.shiftType,
    representative_employee_id: draft.representativeEmployeeId
  });
  return apiRequest<VacationImpactResponse>(`/api/v1/vacations/impact?${params.toString()}`);
}

/**
 * Create a pending vacation request.
 */
export async function createVacationRequest(draft: VacationDraft): Promise<VacationRequest> {
  return apiRequest<VacationRequest>("/api/v1/vacations", {
    method: "POST",
    body: {
      employee_id: Number(draft.employeeId),
      start_date: draft.startDate,
      end_date: draft.endDate,
      shift_type: draft.shiftType,
      representative_employee_id: draft.representativeEmployeeId || null,
      reason: draft.reason,
      notes: draft.notes
    }
  });
}

/**
 * Approve or reject a vacation request.
 */
export async function decideVacationRequest(requestId: number, action: "approve" | "reject"): Promise<VacationRequest> {
  return apiRequest<VacationRequest>(`/api/v1/vacations/${requestId}/${action}`, { method: "POST" });
}

/**
 * Cancel a pending or approved vacation request.
 */
export async function cancelVacationRequest(requestId: number): Promise<VacationRequest> {
  return apiRequest<VacationRequest>(`/api/v1/vacations/${requestId}/cancel`, { method: "POST" });
}

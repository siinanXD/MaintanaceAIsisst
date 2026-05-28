import { apiRequest } from "../api/client";
import { listData } from "../api/payload";
import type { Employee, EmployeeDraft } from "./employeeTypes";

/**
 * Load employees visible to the current user.
 */
export async function loadEmployees(): Promise<Employee[]> {
  return listData<Employee>(await apiRequest<unknown>("/api/v1/employees?limit=200"));
}

/**
 * Create a confidential employee record.
 */
export async function createEmployee(draft: EmployeeDraft): Promise<Employee> {
  return apiRequest<Employee>("/api/v1/employees", {
    method: "POST",
    body: employeePayload(draft)
  });
}

/**
 * Update a confidential employee record.
 */
export async function updateEmployee(employeeId: number, draft: EmployeeDraft): Promise<Employee> {
  return apiRequest<Employee>(`/api/v1/employees/${employeeId}`, {
    method: "PUT",
    body: employeePayload(draft)
  });
}

/**
 * Delete an employee record.
 */
export async function deleteEmployee(employeeId: number): Promise<void> {
  await apiRequest<null>(`/api/v1/employees/${employeeId}`, { method: "DELETE" });
}

/**
 * Upload one confidential document for an employee.
 */
export async function uploadEmployeeDocument(employeeId: number, file: File): Promise<unknown> {
  const formData = new FormData();
  formData.append("document", file);
  return apiRequest<unknown>(`/api/v1/employees/${employeeId}/documents`, {
    method: "POST",
    body: formData
  });
}

/**
 * Build the API payload from a controlled employee draft.
 */
function employeePayload(draft: EmployeeDraft): Record<string, unknown> {
  return {
    personnel_number: draft.personnel_number,
    name: draft.name,
    birth_date: draft.birth_date || null,
    city: draft.city,
    street: draft.street,
    postal_code: draft.postal_code,
    department: draft.department,
    shift_model: draft.shift_model,
    current_shift: draft.current_shift,
    team: draft.team ? Number(draft.team) : null,
    salary_group: draft.salary_group,
    favorite_machine: draft.favorite_machine,
    qualifications: draft.qualifications
  };
}

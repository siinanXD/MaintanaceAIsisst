import { apiRequest } from "../api/client";
import { listData, unwrapData } from "../api/payload";
import type {
  AdminEmployee,
  AdminPermission,
  AdminUser,
  AiSummary,
  AuditEntry,
  BackupEntry,
  PermissionSchema
} from "./adminUserTypes";

/**
 * Load filtered admin users.
 */
export async function loadAdminUsers(filters: { readonly q: string; readonly role: string; readonly status: string }): Promise<AdminUser[]> {
  const params = new URLSearchParams();
  if (filters.q) params.set("q", filters.q);
  if (filters.role) params.set("role", filters.role);
  if (filters.status) params.set("status", filters.status);
  const query = params.toString();
  return listData<AdminUser>(await apiRequest<unknown>(`/api/v1/admin/users${query ? `?${query}` : ""}`));
}

/**
 * Load employee choices for user linkage.
 */
export async function loadEmployeeChoices(): Promise<AdminEmployee[]> {
  return listData<AdminEmployee>(await apiRequest<unknown>("/api/v1/employees?limit=200"));
}

/**
 * Load the permission editor schema.
 */
export async function loadPermissionSchema(): Promise<PermissionSchema> {
  return apiRequest<PermissionSchema>("/api/v1/admin/permissions/schema");
}

/**
 * Update one user's linked employee.
 */
export async function updateUserEmployee(userId: number, employeeId: string): Promise<AdminUser> {
  return apiRequest<AdminUser>(`/api/v1/admin/users/${userId}`, {
    method: "PUT",
    body: { employee_id: employeeId }
  });
}

/**
 * Save one user's dashboard permissions.
 */
export async function saveUserPermissions(userId: number, permissions: Record<string, AdminPermission>): Promise<AdminUser> {
  return apiRequest<AdminUser>(`/api/v1/admin/users/${userId}/permissions`, {
    method: "PUT",
    body: { permissions }
  });
}

/**
 * Reset a user's password.
 */
export async function resetUserPassword(userId: number, password: string): Promise<void> {
  await apiRequest<unknown>(`/api/v1/admin/users/${userId}/reset-password`, {
    method: "POST",
    body: { password }
  });
}

/**
 * Lock or unlock one user account.
 */
export async function setUserLockState(userId: number, locked: boolean): Promise<AdminUser> {
  return apiRequest<AdminUser>(`/api/v1/admin/users/${userId}/${locked ? "lock" : "unlock"}`, {
    method: "POST"
  });
}

/**
 * Delete one user account.
 */
export async function deleteAdminUser(userId: number): Promise<void> {
  await apiRequest<unknown>(`/api/v1/admin/users/${userId}`, { method: "DELETE" });
}

/**
 * Load AI usage summary for the admin area.
 */
export async function loadAiSummary(): Promise<AiSummary> {
  return apiRequest<AiSummary>("/api/v1/admin/ai/summary");
}

/**
 * Load security audit entries.
 */
export async function loadAuditEntries(query: string): Promise<AuditEntry[]> {
  const params = new URLSearchParams();
  params.set("limit", "25");
  if (query.trim()) params.set("q", query.trim());
  return listData<AuditEntry>(await apiRequest<unknown>(`/api/v1/admin/audit-log?${params.toString()}`));
}

/**
 * Load available backup archives.
 */
export async function loadBackups(): Promise<BackupEntry[]> {
  return listData<BackupEntry>(await apiRequest<unknown>("/api/v1/admin/backups"));
}

/**
 * Create a backup archive.
 */
export async function createBackup(): Promise<BackupEntry> {
  return unwrapData<BackupEntry>(await apiRequest<unknown>("/api/v1/admin/backups", { method: "POST" }));
}

/**
 * Restore a backup archive after explicit confirmation.
 */
export async function restoreBackup(backupId: string): Promise<void> {
  await apiRequest<unknown>(`/api/v1/admin/backups/${encodeURIComponent(backupId)}/restore`, {
    method: "POST",
    body: { confirm: true }
  });
}

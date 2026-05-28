import { readStoredSession, type MaintenanceUser } from "./session";

export type MaintenanceAuthRuntime = {
  readonly canManageEmployees?: () => boolean;
  readonly canView?: (dashboard: string) => boolean;
  readonly canWrite?: (dashboard: string) => boolean;
  readonly destinationForUserOrNext?: (user: MaintenanceUser, nextPath: string | null) => string;
  readonly employeeAccessLevel?: () => string;
  readonly token?: () => string | null;
};

declare global {
  interface Window {
    readonly maintenanceAuth?: MaintenanceAuthRuntime;
  }
}

/**
 * Return a stored dashboard permission for early React module execution.
 */
function storedPermissionFor(dashboard: string): { readonly can_view?: boolean; readonly can_write?: boolean } {
  const session = readStoredSession();
  const user = session.user;

  if (user?.role === "master_admin") {
    return { can_view: true, can_write: true };
  }

  const permission = user?.permissions?.[dashboard];
  return typeof permission === "object" && permission !== null && !Array.isArray(permission)
    ? permission
    : {};
}

/**
 * Return whether the current user may view a dashboard area.
 */
export function canViewDashboard(dashboard: string): boolean {
  const maintenanceAuth = window.maintenanceAuth;
  if (maintenanceAuth && typeof maintenanceAuth.canView === "function") {
    return maintenanceAuth.canView(dashboard);
  }

  return Boolean(storedPermissionFor(dashboard).can_view);
}

/**
 * Return whether the current user may write to a dashboard area.
 */
export function canWriteDashboard(dashboard: string): boolean {
  const maintenanceAuth = window.maintenanceAuth;
  if (maintenanceAuth && typeof maintenanceAuth.canWrite === "function") {
    return maintenanceAuth.canWrite(dashboard);
  }

  return Boolean(storedPermissionFor(dashboard).can_write);
}

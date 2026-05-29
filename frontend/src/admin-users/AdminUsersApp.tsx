import { useEffect, type ReactNode } from "react";

import { markIslandMounted } from "../app/islandMount";
import { AdminUserEditDialog } from "./AdminUserEditDialog";
import { AdminUsersPageHeader } from "./AdminUsersPageHeader";
import { AiAnalyticsPanel, AuditLogPanel, BackupPanel } from "./AdminUsersSidePanels";
import { AdminUsersTable } from "./AdminUsersTable";
import { downloadBackup } from "./adminUserUtils";
import { useAdminUsersData } from "./useAdminUsersData";

const ADMIN_USERS_ISLAND = {
  mountedFlag: "maintenanceAdminUsersReactMounted",
  mountEvent: "maintenance-admin-users-react-mounted"
};

/**
 * Render the admin users React island.
 */
export function AdminUsersApp(): ReactNode {
  const adminUsers = useAdminUsersData();

  useEffect(() => {
    markIslandMounted(ADMIN_USERS_ISLAND);
  }, []);

  return (
    <>
      <AdminUsersPageHeader />
      <section className="dashboard-grid">
        {adminUsers.aiSummary ? (
          <AiAnalyticsPanel
            latestEvents={adminUsers.latestEvents}
            summary={adminUsers.aiSummary}
            userMetrics={adminUsers.userMetrics}
          />
        ) : null}
        <AdminUserEditDialog
          draft={adminUsers.permissionDraft}
          message={adminUsers.permissionMessage}
          onPermissionChange={adminUsers.updatePermission}
          onSubmit={adminUsers.submitPermissions}
          schema={adminUsers.schema}
          selectedUser={adminUsers.selectedUser}
        />
        <AuditLogPanel
          auditEntries={adminUsers.auditEntries}
          auditSearch={adminUsers.auditSearch}
          onAuditRefresh={() => adminUsers.refreshAuditEntries()}
          onAuditSearch={adminUsers.setAuditSearch}
        />
        <BackupPanel
          backups={adminUsers.backups}
          message={adminUsers.backupMessage}
          onCreate={adminUsers.createBackupArchive}
          onDownload={(backup) => downloadBackup(backup.download_url, backup.filename)}
          onRestore={adminUsers.restoreBackupArchive}
        />
        <AdminUsersTable
          emptyText={adminUsers.emptyText}
          employees={adminUsers.employees}
          filters={adminUsers.filters}
          message={adminUsers.message}
          onDelete={adminUsers.removeUser}
          onEmployeeChange={adminUsers.changeEmployee}
          onFilterChange={adminUsers.updateFilter}
          onPermissions={adminUsers.openPermissionEditor}
          onResetPassword={adminUsers.resetPassword}
          onToggleLock={adminUsers.toggleLock}
          users={adminUsers.users}
        />
      </section>
    </>
  );
}

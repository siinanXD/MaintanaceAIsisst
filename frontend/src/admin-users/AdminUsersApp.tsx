import { useEffect, useMemo, useState, type ReactNode } from "react";

import { markIslandMounted } from "../app/islandMount";
import { readStoredSession } from "../auth/session";
import {
  createBackup,
  deleteAdminUser,
  loadAdminUsers,
  loadAiSummary,
  loadAuditEntries,
  loadBackups,
  loadEmployeeChoices,
  loadPermissionSchema,
  resetUserPassword,
  restoreBackup,
  saveUserPermissions,
  setUserLockState,
  updateUserEmployee
} from "./adminUserApi";
import type {
  AdminEmployee,
  AdminPermission,
  AdminUser,
  AiSummary,
  AuditEntry,
  BackupEntry,
  MessageState,
  PermissionSchema
} from "./adminUserTypes";
import { AdminUserEditDialog } from "./AdminUserEditDialog";
import { AdminUsersPageHeader } from "./AdminUsersPageHeader";
import { AiAnalyticsPanel, AuditLogPanel, BackupPanel } from "./AdminUsersSidePanels";
import { AdminUsersTable } from "./AdminUsersTable";
import {
  adminUserErrorMessage,
  confirmAdminAction,
  downloadBackup,
  permissionChangeSummary,
  requestPassword,
  schemaDashboardKeys,
  refreshCurrentUserIfNeeded
} from "./adminUserUtils";

const ADMIN_USERS_ISLAND = {
  mountedFlag: "maintenanceAdminUsersReactMounted",
  mountEvent: "maintenance-admin-users-react-mounted"
};

/**
 * Return a local editable permission map for one user.
 */
function permissionDraftFor(schema: PermissionSchema | null, user: AdminUser): Record<string, AdminPermission> {
  return Object.fromEntries(
    schemaDashboardKeys(schema).map((dashboard) => [
      dashboard,
      {
        can_view: Boolean(user.permissions?.[dashboard]?.can_view),
        can_write: Boolean(user.permissions?.[dashboard]?.can_write),
        employee_access_level: user.permissions?.[dashboard]?.employee_access_level || "none"
      }
    ])
  );
}

/**
 * Return the current stored user id.
 */
function currentSessionUserId(): number | undefined {
  return readStoredSession().user?.id;
}

/**
 * Render the admin users React island.
 */
export function AdminUsersApp(): ReactNode {
  const [aiSummary, setAiSummary] = useState<AiSummary | null>(null);
  const [auditEntries, setAuditEntries] = useState<AuditEntry[]>([]);
  const [auditSearch, setAuditSearch] = useState("");
  const [backups, setBackups] = useState<BackupEntry[]>([]);
  const [backupMessage, setBackupMessage] = useState<MessageState>({ text: "", error: false });
  const [employees, setEmployees] = useState<AdminEmployee[]>([]);
  const [filters, setFilters] = useState({ q: "", role: "", status: "" });
  const [message, setMessage] = useState<MessageState>({ text: "Nutzer werden geladen...", error: false });
  const [permissionDraft, setPermissionDraft] = useState<Record<string, AdminPermission>>({});
  const [permissionMessage, setPermissionMessage] = useState<MessageState>({ text: "", error: false });
  const [schema, setSchema] = useState<PermissionSchema | null>(null);
  const [selectedUser, setSelectedUser] = useState<AdminUser | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);

  const hasActiveFilters = Boolean(filters.q || filters.role || filters.status);
  const latestEvents = aiSummary?.latest_events || [];
  const userMetrics = aiSummary?.user_metrics || [];

  /**
   * Refresh user rows and employee choices in parallel.
   */
  async function refreshUsers(nextFilters = filters): Promise<AdminUser[]> {
    setMessage({ text: "Nutzer werden geladen...", error: false });
    try {
      const [loadedUsers, loadedEmployees] = await Promise.all([
        loadAdminUsers(nextFilters),
        loadEmployeeChoices()
      ]);
      setUsers(loadedUsers);
      setEmployees(loadedEmployees);
      setMessage({ text: "", error: false });
      if (selectedUser) {
        const freshUser = loadedUsers.find((item) => item.id === selectedUser.id) || null;
        setSelectedUser(freshUser);
        if (freshUser) setPermissionDraft(permissionDraftFor(schema, freshUser));
      }
      return loadedUsers;
    } catch (error) {
      setUsers([]);
      setMessage({ text: adminUserErrorMessage(error), error: true });
      return [];
    }
  }

  /**
   * Refresh AI, audit and backup side panels independently.
   */
  async function refreshSidePanels(): Promise<void> {
    await Promise.all([
      loadAiSummary().then(setAiSummary).catch(() => setAiSummary(null)),
      refreshAuditEntries(),
      refreshBackups()
    ]);
  }

  /**
   * Refresh the audit log panel.
   */
  async function refreshAuditEntries(query = auditSearch): Promise<void> {
    try {
      setAuditEntries(await loadAuditEntries(query));
    } catch {
      setAuditEntries([]);
    }
  }

  /**
   * Refresh the backup list.
   */
  async function refreshBackups(): Promise<void> {
    try {
      setBackups(await loadBackups());
    } catch (error) {
      setBackupMessage({ text: adminUserErrorMessage(error), error: true });
    }
  }

  /**
   * Update one filter field and refresh the list.
   */
  function updateFilter(field: keyof typeof filters, value: string): void {
    const nextFilters = { ...filters, [field]: value };
    setFilters(nextFilters);
    void refreshUsers(nextFilters);
  }

  /**
   * Select one user for permission editing.
   */
  function openPermissionEditor(user: AdminUser): void {
    setSelectedUser(user);
    setPermissionDraft(permissionDraftFor(schema, user));
    setPermissionMessage({ text: "", error: false });
  }

  /**
   * Update one permission field in local editor state.
   */
  function updatePermission(dashboard: string, action: keyof AdminPermission, value: boolean | string): void {
    setPermissionDraft((current) => ({
      ...current,
      [dashboard]: {
        ...current[dashboard],
        [action]: value
      }
    }));
  }

  /**
   * Save the selected user's permissions after confirmation.
   */
  async function submitPermissions(): Promise<void> {
    if (!selectedUser) return;
    const changes = permissionChangeSummary(schema, selectedUser, permissionDraft);
    if (changes.length) {
      const confirmed = await confirmAdminAction("Diese Rechte speichern?", changes.join("\n"));
      if (!confirmed) return;
    }
    try {
      const updated = await saveUserPermissions(selectedUser.id, permissionDraft);
      await refreshCurrentUserIfNeeded(updated.id, currentSessionUserId());
      setSelectedUser(updated);
      setPermissionDraft(permissionDraftFor(schema, updated));
      setPermissionMessage({ text: "Rechte gespeichert.", error: false });
      await refreshUsers();
      await refreshAuditEntries();
    } catch (error) {
      setPermissionMessage({ text: adminUserErrorMessage(error), error: true });
    }
  }

  /**
   * Link one user to an employee record.
   */
  async function changeEmployee(user: AdminUser, employeeId: string): Promise<void> {
    try {
      const updated = await updateUserEmployee(user.id, employeeId);
      await refreshCurrentUserIfNeeded(updated.id, currentSessionUserId());
      await refreshUsers();
    } catch (error) {
      setPermissionMessage({ text: adminUserErrorMessage(error), error: true });
    }
  }

  /**
   * Reset one user's password through the shared app dialog.
   */
  async function resetPassword(user: AdminUser): Promise<void> {
    try {
      const password = await requestPassword("Passwort zurücksetzen", `Neues Passwort für ${user.username} vergeben.`);
      if (password === null) return;
      await resetUserPassword(user.id, password);
      setPermissionMessage({ text: "Passwort aktualisiert.", error: false });
      await refreshAuditEntries();
    } catch (error) {
      setPermissionMessage({ text: adminUserErrorMessage(error), error: true });
    }
  }

  /**
   * Lock or unlock one user account.
   */
  async function toggleLock(user: AdminUser): Promise<void> {
    try {
      await setUserLockState(user.id, user.is_active);
      setPermissionMessage({ text: user.is_active ? "User gesperrt." : "User entsperrt.", error: false });
      await refreshUsers();
      await refreshAuditEntries();
    } catch (error) {
      setPermissionMessage({ text: adminUserErrorMessage(error), error: true });
    }
  }

  /**
   * Delete one user after confirmation.
   */
  async function removeUser(user: AdminUser): Promise<void> {
    const confirmed = await confirmAdminAction(
      "User löschen",
      `${user.username} wirklich löschen? Diese Aktion kann nicht direkt rückgängig gemacht werden.`,
      "Löschen"
    );
    if (!confirmed) return;
    try {
      await deleteAdminUser(user.id);
      setPermissionMessage({ text: "User gelöscht.", error: false });
      await refreshUsers();
      await refreshAuditEntries();
    } catch (error) {
      setPermissionMessage({ text: adminUserErrorMessage(error), error: true });
    }
  }

  /**
   * Create a backup and refresh the panel.
   */
  async function createBackupArchive(): Promise<void> {
    setBackupMessage({ text: "Backup wird erstellt...", error: false });
    try {
      await createBackup();
      setBackupMessage({ text: "Backup erstellt.", error: false });
      await refreshBackups();
      await refreshAuditEntries();
    } catch (error) {
      setBackupMessage({ text: adminUserErrorMessage(error), error: true });
    }
  }

  /**
   * Restore one backup after confirmation.
   */
  async function restoreBackupArchive(backup: BackupEntry): Promise<void> {
    const confirmed = await confirmAdminAction(
      "Backup wiederherstellen?",
      "Vor dem Restore wird automatisch ein Sicherheitsbackup erstellt.",
      "Restore"
    );
    if (!confirmed) return;
    setBackupMessage({ text: "Restore läuft...", error: false });
    try {
      await restoreBackup(backup.id);
      setBackupMessage({ text: "Backup wiederhergestellt.", error: false });
      await refreshBackups();
      await refreshAuditEntries();
    } catch (error) {
      setBackupMessage({ text: adminUserErrorMessage(error), error: true });
    }
  }

  useEffect(() => {
    markIslandMounted(ADMIN_USERS_ISLAND);
  }, []);

  useEffect(() => {
    loadPermissionSchema()
      .then((loadedSchema) => {
        setSchema(loadedSchema);
        return refreshUsers();
      })
      .catch((error: unknown) => {
        setMessage({ text: adminUserErrorMessage(error), error: true });
      });
    void refreshSidePanels();
  }, []);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void refreshAuditEntries(auditSearch);
    }, 300);
    return () => window.clearTimeout(timeoutId);
  }, [auditSearch]);

  const emptyText = useMemo(() => {
    if (message.text) return message.text;
    if (!users.length && hasActiveFilters) return "Keine Nutzer für diese Filter gefunden.";
    if (!users.length) return "Noch keine Nutzer vorhanden.";
    return "";
  }, [hasActiveFilters, message.text, users.length]);

  return (
    <>
      <AdminUsersPageHeader />
      <section className="dashboard-grid">
        {aiSummary ? <AiAnalyticsPanel latestEvents={latestEvents} summary={aiSummary} userMetrics={userMetrics} /> : null}
        <AdminUserEditDialog
          draft={permissionDraft}
          message={permissionMessage}
          onPermissionChange={updatePermission}
          onSubmit={submitPermissions}
          schema={schema}
          selectedUser={selectedUser}
        />
        <AuditLogPanel auditEntries={auditEntries} auditSearch={auditSearch} onAuditRefresh={() => refreshAuditEntries()} onAuditSearch={setAuditSearch} />
        <BackupPanel
          backups={backups}
          message={backupMessage}
          onCreate={createBackupArchive}
          onDownload={(backup) => downloadBackup(backup.download_url, backup.filename)}
          onRestore={restoreBackupArchive}
        />
        <AdminUsersTable
          emptyText={emptyText}
          employees={employees}
          filters={filters}
          message={message}
          onDelete={removeUser}
          onEmployeeChange={changeEmployee}
          onFilterChange={updateFilter}
          onPermissions={openPermissionEditor}
          onResetPassword={resetPassword}
          onToggleLock={toggleLock}
          users={users}
        />
      </section>
    </>
  );
}

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
import {
  adminDateLabel,
  adminUserErrorMessage,
  compactNumber,
  confirmAdminAction,
  dashboardLabel,
  downloadBackup,
  employeeAccessLabel,
  formatBytes,
  formatUsd,
  percentLabel,
  permissionChangeSummary,
  permissionSummary,
  requestPassword,
  roleDefaultPermission,
  ROLE_OPTIONS,
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
      <AdminUsersHeader />
      <section className="dashboard-grid">
        {aiSummary ? <AiAnalyticsPanel latestEvents={latestEvents} summary={aiSummary} userMetrics={userMetrics} /> : null}
        <PermissionEditor
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
        <UserListPanel
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

/**
 * Render the page hero.
 */
function AdminUsersHeader(): ReactNode {
  return (
    <section className="page-hero">
      <div>
        <p className="page-kicker">Admin</p>
        <h1 className="page-title">Nutzerverwaltung</h1>
        <p className="page-description">Nutzer anzeigen, sperren, entsperren, Passwort zurücksetzen und löschen.</p>
      </div>
    </section>
  );
}

type PermissionEditorProps = {
  readonly draft: Record<string, AdminPermission>;
  readonly message: MessageState;
  readonly onPermissionChange: (dashboard: string, action: keyof AdminPermission, value: boolean | string) => void;
  readonly onSubmit: () => Promise<void>;
  readonly schema: PermissionSchema | null;
  readonly selectedUser: AdminUser | null;
};

/**
 * Render the selected user's permission editor.
 */
function PermissionEditor(props: PermissionEditorProps): ReactNode {
  if (!props.selectedUser || !props.schema) {
    return <article className="card app-card mobile-secondary-card lg:col-span-12" data-permission-editor hidden />;
  }
  const selectedUser = props.selectedUser;
  const schema = props.schema;
  return (
    <article className="card app-card mobile-secondary-card lg:col-span-12" data-permission-editor>
      <div className="card-body">
        <div className="panel-header">
          <div>
            <h2 className="panel-title">Cockpit-Rechte</h2>
            <p className="panel-meta" data-permission-editor-title>{selectedUser.username} - Rechte je Cockpit</p>
            <p className="panel-meta" data-permission-defaults>Rollen-Default: {selectedUser.role} | Abweichungen werden vor dem Speichern angezeigt.</p>
          </div>
        </div>
        <form data-permission-form onSubmit={(event) => { event.preventDefault(); void props.onSubmit(); }}>
          <div className="table-wrap">
            <table className="table data-table">
              <caption>Cockpit-Rechte für den ausgewählten Nutzer</caption>
              <thead>
                <tr>
                  <th scope="col">Cockpit</th>
                  <th scope="col">Anzeigen</th>
                  <th scope="col">Bearbeiten</th>
                  <th scope="col">Mitarbeiterdaten</th>
                </tr>
              </thead>
              <tbody data-permission-list>
                {schema.groups.map((group) => (
                  <PermissionGroupRows
                    draft={props.draft}
                    group={group}
                    key={group.key}
                    onPermissionChange={props.onPermissionChange}
                    schema={schema}
                    selectedUser={selectedUser}
                  />
                ))}
              </tbody>
            </table>
          </div>
          <div className="toolbar form-actions">
            <button className="btn btn-primary" type="submit">Rechte speichern</button>
            <span className={`panel-meta${props.message.error ? " is-error" : ""}`} data-permission-message>{props.message.text}</span>
          </div>
        </form>
      </div>
    </article>
  );
}

type PermissionGroupRowsProps = {
  readonly draft: Record<string, AdminPermission>;
  readonly group: { readonly label: string; readonly dashboards: readonly string[] };
  readonly onPermissionChange: (dashboard: string, action: keyof AdminPermission, value: boolean | string) => void;
  readonly schema: PermissionSchema;
  readonly selectedUser: AdminUser;
};

/**
 * Render one permission group and its dashboard rows.
 */
function PermissionGroupRows(props: PermissionGroupRowsProps): ReactNode {
  return (
    <>
      <tr>
        <td className="panel-meta" colSpan={4}>{props.group.label}</td>
      </tr>
      {props.group.dashboards.map((dashboard) => {
        const permission = props.draft[dashboard] || {};
        const defaultPermission = roleDefaultPermission(props.schema, props.selectedUser.role, dashboard);
        const isAdminUsersDashboard = dashboard === "admin_users";
        const isMasterAdmin = props.selectedUser.role === "master_admin";
        const disabled = isAdminUsersDashboard;
        return (
          <tr key={dashboard}>
            <td>
              <div>
                <strong>{dashboardLabel(props.schema, dashboard)}</strong>
                <p className="panel-meta">Default: {permissionSummary(props.schema, defaultPermission)}</p>
              </div>
            </td>
            <td>
              <input
                checked={isAdminUsersDashboard ? isMasterAdmin : Boolean(permission.can_view)}
                data-dashboard={dashboard}
                data-permission-action="can_view"
                disabled={disabled}
                onChange={(event) => props.onPermissionChange(dashboard, "can_view", event.currentTarget.checked)}
                type="checkbox"
              />
            </td>
            <td>
              <input
                checked={isAdminUsersDashboard ? isMasterAdmin : Boolean(permission.can_write)}
                data-dashboard={dashboard}
                data-permission-action="can_write"
                disabled={disabled}
                onChange={(event) => props.onPermissionChange(dashboard, "can_write", event.currentTarget.checked)}
                type="checkbox"
              />
            </td>
            <td>
              {dashboard === "employees" ? (
                <select
                  className="select select-bordered"
                  data-dashboard={dashboard}
                  data-permission-action="employee_access_level"
                  onChange={(event) => props.onPermissionChange(dashboard, "employee_access_level", event.currentTarget.value)}
                  value={permission.employee_access_level || "none"}
                >
                  {props.schema.employee_access_levels.map((level) => <option key={level.key} value={level.key}>{employeeAccessLabel(props.schema, level.key)}</option>)}
                </select>
              ) : "-"}
            </td>
          </tr>
        );
      })}
    </>
  );
}

type UserListPanelProps = {
  readonly employees: readonly AdminEmployee[];
  readonly emptyText: string;
  readonly filters: { readonly q: string; readonly role: string; readonly status: string };
  readonly message: MessageState;
  readonly onDelete: (user: AdminUser) => Promise<void>;
  readonly onEmployeeChange: (user: AdminUser, employeeId: string) => Promise<void>;
  readonly onFilterChange: (field: "q" | "role" | "status", value: string) => void;
  readonly onPermissions: (user: AdminUser) => void;
  readonly onResetPassword: (user: AdminUser) => Promise<void>;
  readonly onToggleLock: (user: AdminUser) => Promise<void>;
  readonly users: readonly AdminUser[];
};

/**
 * Render filters and the user table.
 */
function UserListPanel(props: UserListPanelProps): ReactNode {
  return (
    <article className="card app-card mobile-primary-card lg:col-span-12">
      <div className="card-body">
        <div className="panel-header">
          <div>
            <h2 className="panel-title">Nutzer suchen</h2>
            <p className="panel-meta">Nur für Master/Admin sichtbar</p>
          </div>
        </div>
        <div className="toolbar mb-4 flex flex-wrap gap-3">
          <input className="input input-bordered flex-1 min-w-48" type="search" placeholder="Nutzername oder E-Mail..." data-filter-q autoComplete="off" value={props.filters.q} onChange={(event) => props.onFilterChange("q", event.currentTarget.value)} />
          <select className="select select-bordered" data-filter-role value={props.filters.role} onChange={(event) => props.onFilterChange("role", event.currentTarget.value)}>
            <option value="">Alle Rollen</option>
            {ROLE_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
          <select className="select select-bordered" data-filter-status value={props.filters.status} onChange={(event) => props.onFilterChange("status", event.currentTarget.value)}>
            <option value="">Alle Status</option>
            <option value="active">Aktiv</option>
            <option value="inactive">Gesperrt</option>
          </select>
        </div>
        <p className={`panel-meta py-6 text-center${props.message.error ? " is-error" : ""}`} data-user-empty hidden={props.users.length > 0}>{props.emptyText}</p>
        <div className="table-wrap" data-user-table hidden={props.users.length === 0}>
          <table className="table data-table">
            <caption>Nutzerliste mit Rolle, Bereich, Status und Aktionen</caption>
            <thead>
              <tr>
                <th scope="col">Nutzer</th>
                <th scope="col">E-Mail</th>
                <th scope="col">Rolle</th>
                <th scope="col">Bereich</th>
                <th scope="col">Mitarbeiter</th>
                <th scope="col">Status</th>
                <th scope="col">Aktionen</th>
              </tr>
            </thead>
            <tbody data-user-list>
              {props.users.map((user) => (
                <tr key={user.id}>
                  <td>{user.username}</td>
                  <td>{user.email}</td>
                  <td>{user.role}</td>
                  <td>{user.department?.name || ""}</td>
                  <td>
                    <select className="select select-bordered" data-user-employee-select={user.id} value={user.employee_id ? String(user.employee_id) : ""} onChange={(event) => void props.onEmployeeChange(user, event.currentTarget.value)}>
                      <option value="">Nicht verknüpft</option>
                      {props.employees.map((employee) => <option key={employee.id} value={employee.id}>{employee.name} ({employee.personnel_number})</option>)}
                    </select>
                  </td>
                  <td>{user.is_active ? "aktiv" : "gesperrt"}</td>
                  <td>
                    <div className="table-actions">
                      <button className="btn btn-primary btn-sm" type="button" onClick={() => props.onPermissions(user)}>Rechte</button>
                      <button className="btn btn-outline btn-sm" type="button" onClick={() => void props.onResetPassword(user)}>Passwort</button>
                      <button className="btn btn-outline btn-sm" type="button" onClick={() => void props.onToggleLock(user)}>{user.is_active ? "Sperren" : "Entsperren"}</button>
                      <button className="btn btn-error btn-sm text-white" type="button" onClick={() => void props.onDelete(user)}>Löschen</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </article>
  );
}

type AuditLogPanelProps = {
  readonly auditEntries: readonly AuditEntry[];
  readonly auditSearch: string;
  readonly onAuditRefresh: () => Promise<void>;
  readonly onAuditSearch: (value: string) => void;
};

/**
 * Render the audit log panel.
 */
function AuditLogPanel(props: AuditLogPanelProps): ReactNode {
  return (
    <article className="card app-card mobile-secondary-card lg:col-span-6" data-audit-log-card>
      <div className="card-body">
        <div className="panel-header">
          <div>
            <h2 className="panel-title">Audit-Log</h2>
            <p className="panel-meta">Sicherheitskritische Admin-Änderungen</p>
          </div>
          <button className="btn btn-outline btn-sm" type="button" data-audit-refresh onClick={() => void props.onAuditRefresh()}>Aktualisieren</button>
        </div>
        <div className="toolbar mb-4">
          <input className="input input-bordered w-full" type="search" placeholder="Aktion, Ressource oder Nutzer suchen..." data-audit-search autoComplete="off" value={props.auditSearch} onChange={(event) => props.onAuditSearch(event.currentTarget.value)} />
        </div>
        <div className="table-wrap">
          <table className="table data-table">
            <caption>Audit-Log sicherheitskritischer Admin-Aktionen</caption>
            <thead>
              <tr>
                <th scope="col">Zeit</th>
                <th scope="col">Aktion</th>
                <th scope="col">Ressource</th>
                <th scope="col">Akteur</th>
              </tr>
            </thead>
            <tbody data-audit-log-list>
              {props.auditEntries.length ? props.auditEntries.map((entry, index) => (
                <tr key={`${entry.action}-${entry.created_at}-${index}`}>
                  <td>{adminDateLabel(entry.created_at)}</td>
                  <td>{entry.action || "-"}</td>
                  <td>{entry.resource_type}{entry.resource_id ? ` #${entry.resource_id}` : ""}</td>
                  <td>{entry.actor?.username || "-"}</td>
                </tr>
              )) : <tr><td colSpan={4}>Keine Audit-Einträge vorhanden.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </article>
  );
}

type BackupPanelProps = {
  readonly backups: readonly BackupEntry[];
  readonly message: MessageState;
  readonly onCreate: () => Promise<void>;
  readonly onDownload: (backup: BackupEntry) => boolean;
  readonly onRestore: (backup: BackupEntry) => Promise<void>;
};

/**
 * Render the backup management panel.
 */
function BackupPanel(props: BackupPanelProps): ReactNode {
  return (
    <article className="card app-card mobile-secondary-card lg:col-span-6" data-backup-card>
      <div className="card-body">
        <div className="panel-header">
          <div>
            <h2 className="panel-title">Backups</h2>
            <p className="panel-meta">Datenbank, Uploads, Dokumente und Logs</p>
          </div>
          <button className="btn btn-primary btn-sm" type="button" data-backup-create onClick={() => void props.onCreate()}>Backup erstellen</button>
        </div>
        <p className={`panel-meta mb-3${props.message.error ? " is-error" : ""}`} data-backup-message>{props.message.text}</p>
        <div className="table-wrap">
          <table className="table data-table">
            <caption>Erstellte Backups mit Größe, Zeitpunkt und Aktionen</caption>
            <thead>
              <tr>
                <th scope="col">Datei</th>
                <th scope="col">Größe</th>
                <th scope="col">Zeit</th>
                <th scope="col">Aktionen</th>
              </tr>
            </thead>
            <tbody data-backup-list>
              {props.backups.length ? props.backups.map((backup) => (
                <tr key={backup.id}>
                  <td>{backup.filename}</td>
                  <td>{formatBytes(backup.size_bytes)}</td>
                  <td>{adminDateLabel(backup.created_at)}</td>
                  <td>
                    <div className="table-actions">
                      <button className="btn btn-outline btn-sm" type="button" onClick={() => props.onDownload(backup)}>Download</button>
                      <button className="btn btn-outline btn-sm" type="button" onClick={() => void props.onRestore(backup)}>Restore</button>
                    </div>
                  </td>
                </tr>
              )) : <tr><td colSpan={4}>Noch keine Backups vorhanden.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </article>
  );
}

type AiAnalyticsPanelProps = {
  readonly latestEvents: readonly NonNullable<AiSummary["latest_events"]>[number][];
  readonly summary: AiSummary;
  readonly userMetrics: readonly NonNullable<AiSummary["user_metrics"]>[number][];
};

/**
 * Render AI analytics for the admin users page.
 */
function AiAnalyticsPanel(props: AiAnalyticsPanelProps): ReactNode {
  const helpfulRate = props.summary.feedback?.helpful_rate;
  return (
    <article className="card app-card mobile-secondary-card lg:col-span-12" data-ai-analytics-card>
      <div className="card-body">
        <div className="panel-header">
          <div>
            <h2 className="panel-title">AI-Auswertung</h2>
            <p className="panel-meta">Nutzung, Fallbacks und Feedback der letzten 7 Tage</p>
          </div>
          <span className="badge badge-ai">AI</span>
        </div>
        <div className="dashboard-kpi-grid">
          <Kpi label="Events" meta="AI-Workflows" value={String(props.summary.events_total || 0)} hook="data-ai-events-total" />
          <Kpi label="Fallbacks" meta="lokal beantwortet" value={String(props.summary.fallback_count || 0)} hook="data-ai-fallback-count" />
          <Kpi label="Feedback" meta="hilfreich Quote" value={helpfulRate === null || helpfulRate === undefined ? "-" : `${Math.round(helpfulRate * 100)}%`} hook="data-ai-feedback-rate" />
          <Kpi label="Nicht hilfreich" meta="Feedback" value={String(props.summary.feedback?.not_helpful || 0)} hook="data-ai-not-helpful" />
          <Kpi label="Ø Latenz" meta="Millisekunden" value={String(props.summary.average_latency_ms || 0)} hook="data-ai-latency" />
          <Kpi label="Tokens" meta="gesamt" value={compactNumber(props.summary.total_tokens || 0)} hook="data-ai-tokens" />
          <Kpi label="Kosten" meta={props.summary.price_configuration?.configured ? "geschätzt" : props.summary.price_configuration?.message || "Kosten nicht konfiguriert"} value={formatUsd(props.summary.estimated_cost_usd || 0)} hook="data-ai-cost" metaHook="data-ai-cost-status" />
        </div>
        <div className="table-wrap mt-4">
          <table className="table data-table">
            <caption>AI-Kosten nach Nutzer mit Langfuse User-ID</caption>
            <thead>
              <tr>
                <th scope="col">Nutzer</th>
                <th scope="col">Langfuse User</th>
                <th scope="col">Events</th>
                <th scope="col">Tokens</th>
                <th scope="col">Kosten</th>
                <th scope="col">Fallback</th>
                <th scope="col">Letzte Nutzung</th>
              </tr>
            </thead>
            <tbody data-ai-user-costs>
              {props.userMetrics.length ? props.userMetrics.map((item, index) => (
                <tr key={`${item.username}-${index}`}>
                  <td>{item.username || "Unbekannt"}</td>
                  <td>{item.langfuse_user_id || "-"}</td>
                  <td>{String(item.events || 0)}</td>
                  <td>{compactNumber(item.total_tokens || 0)}</td>
                  <td>{formatUsd(item.estimated_cost_usd || 0)}</td>
                  <td>{percentLabel(item.fallback_rate || 0)}</td>
                  <td>{item.latest_used_at ? adminDateLabel(item.latest_used_at) : "-"}</td>
                </tr>
              )) : <tr><td colSpan={7}>Noch keine nutzerbezogenen AI-Kosten vorhanden.</td></tr>}
            </tbody>
          </table>
        </div>
        <div className="grid gap-4 md:grid-cols-2 mt-4">
          <MetricList emptyText="Keine Workflows" title="Häufige Workflows" values={props.summary.workflow_counts} hook="data-ai-workflows" />
          <MetricList emptyText="Keine Fehler" title="Letzte Fehlerkategorien" values={props.summary.error_counts} hook="data-ai-error-categories" />
        </div>
        <div className="table-wrap mt-4">
          <table className="table data-table">
            <caption>Letzte AI-Events in der Nutzerverwaltung</caption>
            <thead>
              <tr>
                <th scope="col">Workflow</th>
                <th scope="col">Status</th>
                <th scope="col">Modell</th>
                <th scope="col">Quellen</th>
                <th scope="col">Latenz</th>
                <th scope="col">Fallback</th>
                <th scope="col">Zeit</th>
              </tr>
            </thead>
            <tbody data-ai-latest-events>
              {props.latestEvents.length ? props.latestEvents.map((event, index) => (
                <tr key={`${event.workflow}-${event.created_at}-${index}`}>
                  <td>{event.workflow}</td>
                  <td>{event.status}</td>
                  <td>{event.model || "-"}</td>
                  <td>{String(event.source_count || 0)}</td>
                  <td>{String(event.latency_ms || 0)} ms</td>
                  <td>{event.fallback_used ? "ja" : "nein"}</td>
                  <td>{adminDateLabel(event.created_at)}</td>
                </tr>
              )) : <tr><td colSpan={7}>Noch keine AI-Events vorhanden.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </article>
  );
}

/**
 * Render one KPI card.
 */
function Kpi(props: { readonly hook: string; readonly label: string; readonly meta: string; readonly metaHook?: string; readonly value: string }): ReactNode {
  const valueProps = { [props.hook]: true };
  const metaProps = props.metaHook ? { [props.metaHook]: true } : {};
  return (
    <article className="kpi-card">
      <span className="kpi-label">{props.label}</span>
      <strong className="kpi-value" {...valueProps}>{props.value}</strong>
      <span className="kpi-meta" {...metaProps}>{props.meta}</span>
    </article>
  );
}

/**
 * Render a compact metric list.
 */
function MetricList(props: { readonly emptyText: string; readonly hook: string; readonly title: string; readonly values?: Record<string, number> }): ReactNode {
  const entries = Object.entries(props.values || {}).sort((left, right) => right[1] - left[1]).slice(0, 5);
  const hookProps = { [props.hook]: true };
  return (
    <div className="surface-panel">
      <h3 className="panel-title text-base">{props.title}</h3>
      <div className="stacked-list" {...hookProps}>
        {entries.length ? entries.map(([label, count]) => (
          <div className="stacked-list-row" key={label}>
            <span>{label || "-"}</span>
            <strong>{String(count)}</strong>
          </div>
        )) : <div className="panel-meta">{props.emptyText}</div>}
      </div>
    </div>
  );
}

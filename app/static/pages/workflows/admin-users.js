import {
  DASHBOARD_KEYS,
  DASHBOARD_LABELS,
  EMPLOYEE_ACCESS_LEVELS,
  SHARED_MODULE_URLS,
  TASK_PRIORITIES,
  TASK_STATUSES,
  actionButton,
  api,
  applyAiActionPreview,
  badge,
  canView,
  canWrite,
  confirmAction,
  consumeAiActionPreview,
  downloadFile,
  employeeAccessLevel,
  emptyState,
  fillDepartments,
  fillMachineSelects,
  formDataToObject,
  formatDate,
  formatMoney,
  genericStatusBadgeClass,
  keywordText,
  labeledBadge,
  listData,
  loadWorkflowShared,
  paginationTotal,
  priorityBadgeClass,
  priorityLabel,
  registerWorkflowInitializers,
  renderInlineActionPreview,
  renderQuellePanel,
  renderShiftCalendar,
  requestText,
  resolveWorkflowInitializer,
  revealSurface,
  row,
  runAction,
  setButtonBusy,
  setFormBusy,
  setSelectOptions,
  setStatusMessage,
  setText,
  sharedModulePromise,
  sharedNamespace,
  shiftLabel,
  showInfoDialog,
  showInterfaceToast,
  sourceTypeLabel,
  statusBadgeClass,
  statusLabel,
  taskFormPayload,
  token,
  user
} from "./shared.js";

async function initUsers() {
  const list = document.querySelector("[data-user-list]");
  if (!list || !token()) return;
  const editor = document.querySelector("[data-permission-editor]");
  const editorTitle = document.querySelector("[data-permission-editor-title]");
  const permissionDefaults = document.querySelector("[data-permission-defaults]");
  const permissionList = document.querySelector("[data-permission-list]");
  const permissionForm = document.querySelector("[data-permission-form]");
  const permissionMessage = document.querySelector("[data-permission-message]");
  const filterQ = document.querySelector("[data-filter-q]");
  const filterRole = document.querySelector("[data-filter-role]");
  const filterStatus = document.querySelector("[data-filter-status]");
  const emptyHint = document.querySelector("[data-user-empty]");
  const tableWrap = document.querySelector("[data-user-table]");
  const aiAnalyticsCard = document.querySelector("[data-ai-analytics-card]");
  const aiEventsTotal = document.querySelector("[data-ai-events-total]");
  const aiFallbackCount = document.querySelector("[data-ai-fallback-count]");
  const aiFeedbackRate = document.querySelector("[data-ai-feedback-rate]");
  const aiNotHelpful = document.querySelector("[data-ai-not-helpful]");
  const aiLatency = document.querySelector("[data-ai-latency]");
  const aiTokens = document.querySelector("[data-ai-tokens]");
  const aiCost = document.querySelector("[data-ai-cost]");
  const aiLatestEvents = document.querySelector("[data-ai-latest-events]");
  const aiWorkflows = document.querySelector("[data-ai-workflows]");
  const aiErrorCategories = document.querySelector("[data-ai-error-categories]");
  const auditLogList = document.querySelector("[data-audit-log-list]");
  const auditSearch = document.querySelector("[data-audit-search]");
  const auditRefresh = document.querySelector("[data-audit-refresh]");
  const backupList = document.querySelector("[data-backup-list]");
  const backupCreate = document.querySelector("[data-backup-create]");
  const backupMessage = document.querySelector("[data-backup-message]");
  let selectedUser = null;
  let employees = [];
  let permissionSchema = null;

  function employeeSelect(item) {
    const select = document.createElement("select");
    select.className = "select select-bordered";
    select.dataset.userEmployeeSelect = String(item.id);
    const empty = document.createElement("option");
    empty.value = "";
    empty.textContent = "Nicht verknüpft";
    select.appendChild(empty);
    employees.forEach((employee) => {
      const option = document.createElement("option");
      option.value = String(employee.id);
      option.textContent = employee.name + " (" + employee.personnel_number + ")";
      select.appendChild(option);
    });
    select.value = item.employee_id ? String(item.employee_id) : "";
    select.addEventListener("change", async () => {
      await api("/api/v1/admin/users/" + item.id, {
        method: "PUT",
        body: JSON.stringify({ employee_id: select.value })
      });
      const currentSessionUser = user();
      if (currentSessionUser && currentSessionUser.id === item.id && window.maintenanceAuth) {
        await window.maintenanceAuth.refreshUser();
      }
      await load();
    });
    return select;
  }

  async function loadAiAnalytics() {
    if (!aiAnalyticsCard) return;
    try {
      const summary = await api("/api/v1/admin/ai/summary");
      aiAnalyticsCard.hidden = false;
      if (aiEventsTotal) aiEventsTotal.textContent = String(summary.events_total || 0);
      if (aiFallbackCount) aiFallbackCount.textContent = String(summary.fallback_count || 0);
      if (aiFeedbackRate) {
        const rate = summary.feedback && summary.feedback.helpful_rate;
        aiFeedbackRate.textContent = rate === null || rate === undefined
          ? "-"
          : Math.round(rate * 100) + "%";
      }
      if (aiNotHelpful) {
        aiNotHelpful.textContent = String((summary.feedback && summary.feedback.not_helpful) || 0);
      }
      if (aiLatency) aiLatency.textContent = String(summary.average_latency_ms || 0);
      if (aiTokens) aiTokens.textContent = compactNumber(summary.total_tokens || 0);
      if (aiCost) aiCost.textContent = "$" + Number(summary.estimated_cost_usd || 0).toFixed(4);
      renderMetricList(aiWorkflows, summary.workflow_counts, "Keine Workflows");
      renderMetricList(aiErrorCategories, summary.error_counts, "Keine Fehler");
      if (aiLatestEvents) {
        aiLatestEvents.innerHTML = "";
        const latest = summary.latest_events || [];
        if (!latest.length) {
          aiLatestEvents.innerHTML = '<tr><td colspan="7">Noch keine AI-Events vorhanden.</td></tr>';
          return;
        }
        latest.forEach((event) => {
          aiLatestEvents.appendChild(row([
            event.workflow,
            event.status,
            event.model || "-",
            String(event.source_count || 0),
            String(event.latency_ms || 0) + " ms",
            event.fallback_used ? "ja" : "nein",
            formatDate(event.created_at)
          ]));
        });
      }
    } catch (error) {
      if (aiAnalyticsCard) aiAnalyticsCard.hidden = true;
    }
  }

  function compactNumber(value) {
    const number = Number(value || 0);
    if (number >= 1000000) return (number / 1000000).toFixed(1) + "M";
    if (number >= 1000) return (number / 1000).toFixed(1) + "k";
    return String(number);
  }

  function renderMetricList(container, values, emptyText) {
    if (!container) return;
    container.innerHTML = "";
    const entries = Object.entries(values || {}).sort((left, right) => right[1] - left[1]).slice(0, 5);
    if (!entries.length) {
      const empty = document.createElement("div");
      empty.className = "panel-meta";
      empty.textContent = emptyText;
      container.appendChild(empty);
      return;
    }
    entries.forEach(([label, count]) => {
      const item = document.createElement("div");
      item.className = "stacked-list-row";
      const name = document.createElement("span");
      name.textContent = label || "-";
      const value = document.createElement("strong");
      value.textContent = String(count);
      item.append(name, value);
      container.appendChild(item);
    });
  }

  async function loadPermissionSchema() {
    try {
      permissionSchema = await api("/api/v1/admin/permissions/schema");
    } catch (error) {
      permissionSchema = null;
    }
  }

  function schemaDashboards() {
    if (permissionSchema && Array.isArray(permissionSchema.dashboards)) {
      return permissionSchema.dashboards.map((dashboard) => dashboard.key);
    }
    return DASHBOARD_KEYS;
  }

  function dashboardLabel(dashboard) {
    const match = permissionSchema && Array.isArray(permissionSchema.dashboards)
      ? permissionSchema.dashboards.find((item) => item.key === dashboard)
      : null;
    return match ? match.label : (DASHBOARD_LABELS[dashboard] || dashboard);
  }

  function employeeAccessLabel(level) {
    const match = permissionSchema && Array.isArray(permissionSchema.employee_access_levels)
      ? permissionSchema.employee_access_levels.find((item) => item.key === level)
      : null;
    return match ? match.label : level;
  }

  function roleDefaultPermission(role, dashboard) {
    const defaults = permissionSchema && permissionSchema.role_defaults
      ? permissionSchema.role_defaults[role] || {}
      : {};
    return defaults[dashboard] || {
      can_view: false,
      can_write: false,
      employee_access_level: "none"
    };
  }

  function permissionZusammenfassung(permission) {
    const parts = [];
    if (permission.can_view) parts.push("Anzeigen");
    if (permission.can_write) parts.push("Bearbeiten");
    if (permission.employee_access_level && permission.employee_access_level !== "none") {
      parts.push(employeeAccessLabel(permission.employee_access_level));
    }
    return parts.length ? parts.join(", ") : "Keine Rechte";
  }

  function permissionChanged(left, right) {
    return Boolean(left.can_view) !== Boolean(right.can_view)
      || Boolean(left.can_write) !== Boolean(right.can_write)
      || (left.employee_access_level || "none") !== (right.employee_access_level || "none");
  }

  function collectPermissionPayload() {
    const payload = { permissions: {} };
    schemaDashboards().forEach((dashboard) => {
      payload.permissions[dashboard] = {
        can_view: false,
        can_write: false,
        employee_access_level: "none"
      };
    });
    permissionForm.querySelectorAll("[data-dashboard]").forEach((input) => {
      const dashboard = input.dataset.dashboard;
      const action = input.dataset.permissionAction;
      if (!payload.permissions[dashboard]) return;
      if (action === "employee_access_level") {
        payload.permissions[dashboard].employee_access_level = input.value;
      } else {
        payload.permissions[dashboard][action] = input.checked;
      }
    });
    if (payload.permissions.admin_users) {
      payload.permissions.admin_users.can_view = selectedUser.role === "master_admin";
      payload.permissions.admin_users.can_write = selectedUser.role === "master_admin";
    }
    return payload;
  }

  function permissionChangeZusammenfassung(payload) {
    const changes = [];
    schemaDashboards().forEach((dashboard) => {
      const before = (selectedUser.permissions && selectedUser.permissions[dashboard]) || {
        can_view: false,
        can_write: false,
        employee_access_level: "none"
      };
      const after = payload.permissions[dashboard] || {
        can_view: false,
        can_write: false,
        employee_access_level: "none"
      };
      if (!permissionChanged(before, after)) return;
      changes.push(
        dashboardLabel(dashboard) + ": " + permissionZusammenfassung(before)
          + " -> " + permissionZusammenfassung(after)
      );
    });
    return changes;
  }

  function checkboxCell(dashboard, action, checked, disabled) {
    const input = document.createElement("input");
    input.type = "checkbox";
    input.checked = Boolean(checked);
    input.disabled = Boolean(disabled);
    input.dataset.dashboard = dashboard;
    input.dataset.permissionAction = action;
    return input;
  }

  function accessLevelSelect(dashboard, selected, disabled) {
    const select = document.createElement("select");
    select.className = "select select-bordered";
    select.disabled = Boolean(disabled);
    select.dataset.dashboard = dashboard;
    select.dataset.permissionAction = "employee_access_level";
    const accessLevels = permissionSchema && Array.isArray(permissionSchema.employee_access_levels)
      ? permissionSchema.employee_access_levels.map((level) => level.key)
      : EMPLOYEE_ACCESS_LEVELS;
    accessLevels.forEach((level) => {
      const option = document.createElement("option");
      option.value = level;
      option.textContent = employeeAccessLabel(level);
      select.appendChild(option);
    });
    select.value = selected || "none";
    return select;
  }

  function renderPermissionEditor(item) {
    if (!editor || !permissionList || !permissionForm) return;
    selectedUser = item;
    editor.hidden = false;
    if (editorTitle) {
      editorTitle.textContent = item.username + " - Rechte je Cockpit";
    }
    if (permissionDefaults) {
      permissionDefaults.textContent = "Rollen-Default: " + item.role
        + " | Abweichungen werden vor dem Speichern angezeigt.";
    }
    if (permissionMessage) permissionMessage.textContent = "";
    permissionList.innerHTML = "";

    const groups = permissionSchema && Array.isArray(permissionSchema.groups)
      ? permissionSchema.groups
      : [{ label: "Rechte", dashboards: schemaDashboards() }];
    groups.forEach((group) => {
      const groupRow = document.createElement("tr");
      const groupCell = document.createElement("td");
      groupCell.colSpan = 4;
      groupCell.className = "panel-meta";
      groupCell.textContent = group.label;
      groupRow.appendChild(groupCell);
      permissionList.appendChild(groupRow);
      group.dashboards.forEach((dashboard) => {
        const permission = (item.permissions && item.permissions[dashboard]) || {};
        const defaultPermission = roleDefaultPermission(item.role, dashboard);
        const isAdminUsersDashboard = dashboard === "admin_users";
        const isMasterAdmin = item.role === "master_admin";
        const label = document.createElement("div");
        const name = document.createElement("strong");
        name.textContent = dashboardLabel(dashboard);
        const defaultHint = document.createElement("p");
        defaultHint.className = "panel-meta";
        defaultHint.textContent = "Default: " + permissionZusammenfassung(defaultPermission);
        label.append(name, defaultHint);
        permissionList.appendChild(row([
          label,
          checkboxCell(
            dashboard,
            "can_view",
            isAdminUsersDashboard ? isMasterAdmin : permission.can_view,
            isAdminUsersDashboard
          ),
          checkboxCell(
            dashboard,
            "can_write",
            isAdminUsersDashboard ? isMasterAdmin : permission.can_write,
            isAdminUsersDashboard
          ),
          dashboard === "employees"
            ? accessLevelSelect(dashboard, permission.employee_access_level)
            : "-"
        ]));
      });
    });
  }

  if (permissionForm) {
    permissionForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!selectedUser) return;
      const payload = collectPermissionPayload();
      const changes = permissionChangeZusammenfassung(payload);
      if (changes.length) {
        const confirmed = window.confirm("Diese Rechte speichern?\n\n" + changes.join("\n"));
        if (!confirmed) return;
      }
      setFormBusy(permissionForm, true, "Speichert...");
      try {
        const updated = await api("/api/v1/admin/users/" + selectedUser.id + "/permissions", {
          method: "PUT",
          body: JSON.stringify(payload)
        });
        const currentSessionUser = user();
        if (currentSessionUser && currentSessionUser.id === updated.id && window.maintenanceAuth) {
          await window.maintenanceAuth.refreshUser();
        }
        selectedUser = updated;
        await load();
        await loadAuditLog();
        if (permissionMessage) permissionMessage.textContent = "Rechte gespeichert.";
      } catch (error) {
        if (permissionMessage) permissionMessage.textContent = error.message;
      } finally {
        setFormBusy(permissionForm, false);
      }
    });
  }

  async function loadAuditLog() {
    if (!auditLogList) return;
    const params = new URLSearchParams();
    params.set("limit", "25");
    if (auditSearch && auditSearch.value.trim()) {
      params.set("q", auditSearch.value.trim());
    }
    try {
      const result = await api("/api/v1/admin/audit-log?" + params.toString());
      const entries = listData(result);
      auditLogList.innerHTML = "";
      if (!entries.length) {
        auditLogList.innerHTML = '<tr><td colspan="4">Keine Audit-Einträge vorhanden.</td></tr>';
        return;
      }
      entries.forEach((entry) => {
        auditLogList.appendChild(row([
          formatDate(entry.created_at),
          entry.action,
          entry.resource_type + (entry.resource_id ? " #" + entry.resource_id : ""),
          (entry.actor && entry.actor.username) || "-"
        ]));
      });
    } catch (error) {
      auditLogList.innerHTML = '<tr><td colspan="4">Audit-Log konnte nicht geladen werden.</td></tr>';
    }
  }

  function formatBytes(value) {
    const bytes = Number(value || 0);
    if (bytes >= 1048576) return (bytes / 1048576).toFixed(1) + " MB";
    if (bytes >= 1024) return (bytes / 1024).toFixed(1) + " KB";
    return bytes + " B";
  }

  async function loadBackups() {
    if (!backupList) return;
    try {
      const result = await api("/api/v1/admin/backups");
      const backups = listData(result);
      backupList.innerHTML = "";
      if (!backups.length) {
        backupList.innerHTML = '<tr><td colspan="4">Noch keine Backups vorhanden.</td></tr>';
        return;
      }
      backups.forEach((item) => {
        const actions = document.createElement("div");
        actions.className = "table-actions";
        actions.appendChild(actionButton("Download", async () => {
          await downloadFile(item.download_url, item.filename);
        }));
        actions.appendChild(actionButton("Restore", async () => {
          const confirmed = window.confirm(
            "Backup wiederherstellen?\nVor dem Restore wird automatisch ein Sicherheitsbackup erstellt."
          );
          if (!confirmed) return;
          if (backupMessage) backupMessage.textContent = "Restore läuft...";
          await api("/api/v1/admin/backups/" + item.id + "/restore", {
            method: "POST",
            body: JSON.stringify({ confirm: true })
          });
          if (backupMessage) backupMessage.textContent = "Backup wiederhergestellt.";
          await loadBackups();
          await loadAuditLog();
        }));
        backupList.appendChild(row([
          item.filename,
          formatBytes(item.size_bytes),
          formatDate(item.created_at),
          actions
        ]));
      });
    } catch (error) {
      backupList.innerHTML = '<tr><td colspan="4">Backups konnten nicht geladen werden.</td></tr>';
    }
  }

  async function load() {
    const q = filterQ ? filterQ.value.trim() : "";
    const role = filterRole ? filterRole.value : "";
    const status = filterStatus ? filterStatus.value : "";

    if (emptyHint) {
      emptyHint.hidden = false;
      emptyHint.textContent = "Nutzer werden geladen...";
      emptyHint.classList.remove("is-error");
    }
    if (tableWrap) tableWrap.hidden = true;
    list.innerHTML = "";

    const params = new URLSearchParams();
    if (q) params.set("q", q);
    if (role) params.set("role", role);
    if (status) params.set("status", status);
    const queryString = params.toString();
    let users = [];
    try {
      users = listData(await api("/api/v1/admin/users" + (queryString ? "?" + queryString : "")));
    } catch (error) {
      if (emptyHint) {
        emptyHint.hidden = false;
        emptyHint.textContent = error.message || "Nutzer konnten nicht geladen werden.";
        emptyHint.classList.add("is-error");
      }
      if (tableWrap) tableWrap.hidden = true;
      return [];
    }
    try {
      employees = listData(await api("/api/v1/employees?limit=200"));
    } catch (error) {
      employees = [];
    }
    list.innerHTML = "";
    if (!users.length) {
      if (emptyHint) {
        emptyHint.hidden = false;
        emptyHint.textContent = q || role || status
          ? "Keine Nutzer für diese Filter gefunden."
          : "Noch keine Nutzer vorhanden.";
        emptyHint.classList.remove("is-error");
      }
      if (tableWrap) tableWrap.hidden = true;
      return users;
    }
    if (emptyHint) {
      emptyHint.hidden = true;
      emptyHint.classList.remove("is-error");
    }
    if (tableWrap) tableWrap.hidden = false;
    users.forEach((item) => {
      const actions = document.createElement("div");
      actions.className = "table-actions";

      const reset = document.createElement("button");
      reset.className = "btn btn-outline btn-sm";
      reset.type = "button";
      reset.textContent = "Passwort";
      reset.addEventListener("click", async () => {
        const password = await requestText({
          title: "Passwort zurücksetzen",
          message: "Neues Passwort für " + item.username + " vergeben.",
          label: "Neues Passwort",
          inputType: "password",
          required: true,
          confirmText: "Speichern"
        });
        if (password === null) return;
        setButtonBusy(reset, true, "Speichert...");
        try {
          await api("/api/v1/admin/users/" + item.id + "/reset-password", {
            method: "POST",
            body: JSON.stringify({ password })
          });
          if (permissionMessage) permissionMessage.textContent = "Passwort aktualisiert.";
          await loadAuditLog();
        } catch (error) {
          if (permissionMessage) permissionMessage.textContent = error.message;
        } finally {
          setButtonBusy(reset, false);
        }
      });

      const lock = document.createElement("button");
      lock.className = "btn btn-outline btn-sm";
      lock.type = "button";
      lock.textContent = item.is_active ? "Sperren" : "Entsperren";
      lock.addEventListener("click", async () => {
        setButtonBusy(lock, true, "Läuft...");
        try {
          await api("/api/v1/admin/users/" + item.id + "/" + (item.is_active ? "lock" : "unlock"), { method: "POST" });
          if (permissionMessage) permissionMessage.textContent = item.is_active ? "User gesperrt." : "User entsperrt.";
          await load();
          await loadAuditLog();
        } catch (error) {
          if (permissionMessage) permissionMessage.textContent = error.message;
        } finally {
          setButtonBusy(lock, false);
        }
      });

      const remove = document.createElement("button");
      remove.className = "btn btn-error btn-sm text-white";
      remove.type = "button";
      remove.textContent = "Löschen";
      remove.addEventListener("click", async () => {
        const confirmed = await confirmAction({
          title: "User löschen",
          message: item.username + " wirklich löschen? Diese Aktion kann nicht direkt rückgängig gemacht werden.",
          confirmText: "Löschen"
        });
        if (!confirmed) return;
        setButtonBusy(remove, true, "Löscht...");
        try {
          await api("/api/v1/admin/users/" + item.id, { method: "DELETE" });
          if (permissionMessage) permissionMessage.textContent = "User gelöscht.";
          await load();
          await loadAuditLog();
        } catch (error) {
          if (permissionMessage) permissionMessage.textContent = error.message;
        } finally {
          setButtonBusy(remove, false);
        }
      });

      const permissions = document.createElement("button");
      permissions.className = "btn btn-primary btn-sm";
      permissions.type = "button";
      permissions.textContent = "Rechte";
      permissions.addEventListener("click", () => renderPermissionEditor(item));

      actions.append(permissions, reset, lock, remove);
      list.appendChild(row([
        item.username,
        item.email,
        item.role,
        item.department && item.department.name,
        employeeSelect(item),
        item.is_active ? "aktiv" : "gesperrt",
        actions
      ]));
    });
    if (selectedUser) {
      const freshSelectedUser = users.find((item) => item.id === selectedUser.id);
      if (freshSelectedUser) {
        renderPermissionEditor(freshSelectedUser);
      }
    }
    return users;
  }

  let debounceTimer = null;
  function scheduleLoad() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(load, 300);
  }
  let auditDebounceTimer = null;
  function scheduleAuditLoad() {
    clearTimeout(auditDebounceTimer);
    auditDebounceTimer = setTimeout(loadAuditLog, 300);
  }
  if (filterQ) filterQ.addEventListener("input", scheduleLoad);
  if (filterRole) filterRole.addEventListener("change", load);
  if (filterStatus) filterStatus.addEventListener("change", load);
  if (auditSearch) auditSearch.addEventListener("input", scheduleAuditLoad);
  if (auditRefresh) auditRefresh.addEventListener("click", loadAuditLog);
  if (backupCreate) {
    backupCreate.addEventListener("click", async () => {
      setButtonBusy(backupCreate, true, "Erstellt...");
      if (backupMessage) backupMessage.textContent = "Backup wird erstellt...";
      try {
        await api("/api/v1/admin/backups", { method: "POST" });
        if (backupMessage) backupMessage.textContent = "Backup erstellt.";
        await loadBackups();
        await loadAuditLog();
      } catch (error) {
        if (backupMessage) backupMessage.textContent = error.message;
      } finally {
        setButtonBusy(backupCreate, false);
      }
    });
  }
  await loadPermissionSchema();
  await load();
  await loadAiAnalytics();
  await loadAuditLog();
  await loadBackups();
}

export { initUsers };

registerWorkflowInitializers({
  initUsers: initUsers,
  initBenutzer: initUsers
});

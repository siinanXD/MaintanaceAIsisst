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

async function initEmployees() {
  const list = document.querySelector("[data-employee-list]");
  const form = document.querySelector("[data-employee-form]");
  const message = document.querySelector("[data-employee-message]");
  if (!list || !form || !token()) return;

  const empEditDialog  = document.getElementById("emp-edit-dialog");
  const empdId         = document.getElementById("empd-id");
  const empdName       = document.getElementById("empd-name");
  const empdPnr        = document.getElementById("empd-pnr");
  const empdBirth      = document.getElementById("empd-birth");
  const empdCity       = document.getElementById("empd-city");
  const empdStreet     = document.getElementById("empd-street");
  const empdPostal     = document.getElementById("empd-postal");
  const empdDept       = document.getElementById("empd-dept");
  const empdShiftModel = document.getElementById("empd-shift-model");
  const empdCurrentShift = document.getElementById("empd-current-shift");
  const empdTeam       = document.getElementById("empd-team");
  const empdSalary     = document.getElementById("empd-salary");
  const empdMachine    = document.getElementById("empd-machine");
  const empdQuals      = document.getElementById("empd-qualifications");
  const empdSave       = document.getElementById("empd-save");
  const empdCancel     = document.getElementById("empd-cancel");
  const empdMsg        = document.getElementById("empd-msg");

  function openEmployeeEdit(employee) {
    if (!empEditDialog) return;
    empdId.value          = employee.id;
    empdName.value        = employee.name || "";
    empdPnr.value         = employee.personnel_number || "";
    empdBirth.value       = employee.birth_date || "";
    empdCity.value        = employee.city || "";
    empdStreet.value      = employee.street || "";
    empdPostal.value      = employee.postal_code || "";
    empdDept.value        = employee.department || "";
    empdShiftModel.value  = employee.shift_model || "gleitzeit";
    empdCurrentShift.value = employee.current_shift || "";
    empdTeam.value        = employee.team ? String(employee.team) : "";
    empdSalary.value      = employee.salary_group || "";
    empdMachine.value     = employee.favorite_machine || "";
    empdQuals.value       = employee.qualifications || "";
    if (empdMsg) empdMsg.textContent = "";
    empEditDialog.showModal();
  }

  if (empdCancel) empdCancel.addEventListener("click", () => empEditDialog.close());
  if (empEditDialog) {
    empEditDialog.addEventListener("keydown", (e) => { if (e.key === "Escape") empEditDialog.close(); });
  }
  if (empdSave) empdSave.addEventListener("click", async () => {
    setButtonBusy(empdSave, true, "Speichert...");
    try {
      setStatusMessage(empdMsg, "Wird gespeichert...");
      await api("/api/v1/employees/" + empdId.value, {
        method: "PUT",
        body: JSON.stringify({
          name: empdName.value,
          personnel_number: empdPnr.value,
          birth_date: empdBirth.value || null,
          city: empdCity.value,
          street: empdStreet.value,
          postal_code: empdPostal.value,
          department: empdDept.value,
          shift_model: empdShiftModel.value,
          current_shift: empdCurrentShift.value,
          team: empdTeam.value ? parseInt(empdTeam.value, 10) : null,
          salary_group: empdSalary.value,
          favorite_machine: empdMachine.value,
          qualifications: empdQuals.value
        })
      });
      empEditDialog.close();
      await load();
      if (message) message.textContent = "Mitarbeiter aktualisiert.";
    } catch (err) {
      setStatusMessage(empdMsg, err.message, true);
    } finally {
      setButtonBusy(empdSave, false);
    }
  });

  async function uploadDocument(employeeId, file) {
    const formData = new FormData();
    formData.append("document", file);
    const response = await fetch("/api/v1/employees/" + employeeId + "/documents", {
      method: "POST",
      headers: { "Authorization": "Bearer " + token() },
      body: formData
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => null);
      throw new Error((errorData && (errorData.message || errorData.error)) || "Hochladen fehlgeschlagen");
    }
    return response.json();
  }

  async function downloadEmployeeDocument(documentItem) {
    await downloadFile(documentItem.download_url, documentItem.original_filename);
  }

  function employeeCard(employee, opts) {
    const card = document.createElement("article");
    card.className = "resource-card";

    const header = document.createElement("div");
    header.className = "resource-card-header";

    const titleBlock = document.createElement("div");
    const nameEl = document.createElement("h3");
    nameEl.className = "resource-card-title";
    nameEl.textContent = employee.name;
    const pnr = document.createElement("p");
    pnr.className = "resource-card-subtitle";
    pnr.textContent = employee.personnel_number || "-";
    titleBlock.append(nameEl, pnr);

    const cardBadges = document.createElement("div");
    cardBadges.className = "resource-card-badges";
    if (employee.department) cardBadges.appendChild(badge(employee.department, "badge badge-neutral"));
    if (employee.team) cardBadges.appendChild(badge("Team " + employee.team, "badge badge-info"));
    header.append(titleBlock, cardBadges);

    const metaGrid = document.createElement("div");
    metaGrid.className = "resource-meta-grid";
    [
      ["Schichtmodell", employee.shift_model],
      ["Schicht", employee.current_shift],
      ["Gehaltsklasse", employee.salary_group],
      ["Lieblingsmaschine", employee.favorite_machine]
    ].forEach(function (pair) {
      if (!pair[1]) return;
      const cell = document.createElement("div");
      cell.className = "resource-metric";
      const lbl = document.createElement("span");
      lbl.className = "resource-label";
      lbl.textContent = pair[0];
      const val = document.createElement("span");
      val.className = "resource-value";
      val.textContent = pair[1];
      cell.append(lbl, val);
      metaGrid.appendChild(cell);
    });

    const qualBadges = document.createElement("div");
    qualBadges.className = "badge-list";
    (employee.qualifications || "").split(",").forEach(function (q) {
      const t = q.trim();
      if (t) qualBadges.appendChild(badge(t, "badge badge-sm badge-outline"));
    });

    const actions = document.createElement("div");
    actions.className = "resource-actions";
    (employee.documents || []).forEach(function (doc) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "btn btn-link btn-xs px-0 justify-start";
      btn.textContent = doc.original_filename;
      btn.addEventListener("click", async function () {
        try { await opts.downloadEmployeeDocument(doc); }
        catch (err) { if (opts.message) opts.message.textContent = err.message; }
      });
      actions.appendChild(btn);
    });
    if (!(employee.documents || []).length) {
      const noDoc = document.createElement("span");
      noDoc.className = "panel-meta text-xs";
      noDoc.textContent = "Keine Dokumente";
      actions.appendChild(noDoc);
    }

    card.append(header, metaGrid, qualBadges, actions);

    if (opts.canWrite && opts.employeeAccessLevel === "confidential") {
      const uploadWrap = document.createElement("div");
      uploadWrap.className = "resource-upload";
      const input = document.createElement("input");
      input.type = "file";
      input.multiple = true;
      input.addEventListener("change", async function () {
        if (!input.files.length) return;
        input.disabled = true;
        if (opts.message) opts.message.textContent = "Dokumente werden hochgeladen...";
        try {
          const files = Array.from(input.files);
          for (const file of files) await opts.uploadDocument(employee.id, file);
          input.value = "";
          await opts.reload();
          if (opts.message) opts.message.textContent = files.length === 1
            ? "Dokument hochgeladen." : files.length + " Dokumente hochgeladen.";
        } catch (err) {
          if (opts.message) opts.message.textContent = err.message;
        } finally { input.disabled = false; }
      });
      uploadWrap.appendChild(input);
      card.appendChild(uploadWrap);

      const editDeleteRow = document.createElement("div");
      editDeleteRow.className = "table-actions";
      editDeleteRow.appendChild(actionButton("Bearbeiten", () => opts.openEdit(employee)));
      editDeleteRow.appendChild(actionButton("Löschen", async () => {
        if (!window.confirm(employee.name + " wirklich löschen?")) return;
        try {
          await api("/api/v1/employees/" + employee.id, { method: "DELETE" });
          await opts.reload();
          if (opts.message) opts.message.textContent = "Mitarbeiter gelöscht.";
        } catch (err) {
          if (opts.message) opts.message.textContent = err.message;
        }
      }, true));
      card.appendChild(editDeleteRow);
    }

    return card;
  }

  async function load() {
    const countBadge = document.querySelector("[data-employee-count]");
    const employees = listData(await api("/api/v1/employees?limit=200"));
    list.innerHTML = "";
    if (countBadge) countBadge.textContent = employees.length + " Mitarbeitende";
    if (!employees.length) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = "Keine Mitarbeiter vorhanden.";
      list.appendChild(empty);
      return;
    }
    const opts = {
      canWrite: canWrite("employees"),
      employeeAccessLevel: employeeAccessLevel(),
      downloadEmployeeDocument,
      uploadDocument,
      openEdit: openEmployeeEdit,
      message,
      reload: load
    };
    employees.forEach(function (employee) { list.appendChild(employeeCard(employee, opts)); });
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(form).entries());
    setFormBusy(form, true, "Speichert...");
    try {
      setStatusMessage(message, "Mitarbeiter wird gespeichert...");
      await api("/api/v1/employees", { method: "POST", body: JSON.stringify(data) });
      form.reset();
      await load();
      setStatusMessage(message, "Mitarbeiter gespeichert.");
    } catch (error) {
      setStatusMessage(message, error.message, true);
    } finally {
      setFormBusy(form, false);
    }
  });

  await load();
}

export { initEmployees };

registerWorkflowInitializers({
  initEmployees: initEmployees
});

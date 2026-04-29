(function () {
  function token() {
    return window.maintenanceAuth ? window.maintenanceAuth.token() : null;
  }

  function user() {
    return window.maintenanceAuth ? window.maintenanceAuth.user() : null;
  }

  async function api(path, options) {
    const headers = Object.assign({ "Content-Type": "application/json" }, options && options.headers);
    const authToken = token();
    if (authToken) headers.Authorization = "Bearer " + authToken;

    const response = await fetch(path, Object.assign({}, options, { headers }));
    if (response.status === 204) return null;
    const data = await response.json().catch(() => null);
    if (!response.ok) throw new Error((data && data.error) || "API error");
    return data;
  }

  function fillDepartments(selects, departments) {
    const currentUser = user();
    selects.forEach((select) => {
      select.innerHTML = "";
      const placeholder = document.createElement("option");
      placeholder.value = "";
      placeholder.textContent = "Bereich auswaehlen";
      placeholder.disabled = true;
      placeholder.selected = true;
      select.appendChild(placeholder);

      departments.forEach((department) => {
        if (currentUser && currentUser.role !== "master_admin" && currentUser.department && currentUser.department.name !== department.name) {
          return;
        }
        const option = document.createElement("option");
        option.value = department.name;
        option.textContent = department.name;
        select.appendChild(option);
      });

      if (select.options.length === 1) {
        const option = document.createElement("option");
        option.value = "";
        option.textContent = "Keine Bereiche verfuegbar";
        option.disabled = true;
        select.appendChild(option);
        select.classList.add("has-error");
      } else {
        select.classList.remove("has-error");
        if (select.options.length === 2) {
          select.selectedIndex = 1;
        }
      }
    });
  }

  function row(cells) {
    const tr = document.createElement("tr");
    cells.forEach((cell) => {
      const td = document.createElement("td");
      if (cell instanceof Node) td.appendChild(cell);
      else td.textContent = cell || "-";
      tr.appendChild(td);
    });
    return tr;
  }

  async function initDepartments() {
    const selects = document.querySelectorAll("select[name='department']");
    if (!selects.length || !token()) return;
    try {
      const departments = await api("/api/departments");
      fillDepartments(selects, departments);
    } catch (error) {
      selects.forEach((select) => {
        select.innerHTML = "";
        const option = document.createElement("option");
        option.value = "";
        option.textContent = "Bereiche konnten nicht geladen werden";
        option.disabled = true;
        option.selected = true;
        select.appendChild(option);
        select.classList.add("has-error");
      });
    }
  }

  async function initTasks() {
    const list = document.querySelector("[data-task-list]");
    const form = document.querySelector("[data-task-form]");
    if (!list || !form || !token()) return;

    async function load() {
      const tasks = await api("/api/tasks");
      list.innerHTML = "";
      tasks.forEach((task) => {
        list.appendChild(row([
          task.title,
          task.department && task.department.name,
          task.priority,
          task.status,
          task.due_date
        ]));
      });
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const data = Object.fromEntries(new FormData(form).entries());
      await api("/api/tasks", { method: "POST", body: JSON.stringify(data) });
      form.reset();
      await initDepartments();
      await load();
      const message = document.querySelector("[data-task-message]");
      if (message) message.textContent = "Task gespeichert.";
    });

    await load();
  }

  async function initErrors() {
    const list = document.querySelector("[data-error-list]");
    const form = document.querySelector("[data-error-form]");
    if (!list || !form || !token()) return;

    async function load() {
      const errors = await api("/api/errors");
      list.innerHTML = "";
      errors.forEach((entry) => {
        list.appendChild(row([
          entry.error_code,
          entry.machine,
          entry.title,
          entry.department && entry.department.name,
          entry.solution
        ]));
      });
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const data = Object.fromEntries(new FormData(form).entries());
      data.description = data.title;
      data.possible_causes = "";
      await api("/api/errors", { method: "POST", body: JSON.stringify(data) });
      form.reset();
      await initDepartments();
      await load();
      const message = document.querySelector("[data-error-message]");
      if (message) message.textContent = "Fehler gespeichert.";
    });

    await load();
  }

  async function initUsers() {
    const list = document.querySelector("[data-user-list]");
    if (!list || !token()) return;

    async function load() {
      const users = await api("/api/admin/users");
      list.innerHTML = "";
      users.forEach((item) => {
        const actions = document.createElement("div");
        actions.className = "table-actions";

        const reset = document.createElement("button");
        reset.className = "button";
        reset.type = "button";
        reset.textContent = "Passwort";
        reset.addEventListener("click", async () => {
          const password = window.prompt("Neues Passwort fuer " + item.username);
          if (!password) return;
          await api("/api/admin/users/" + item.id + "/reset-password", {
            method: "POST",
            body: JSON.stringify({ password })
          });
        });

        const lock = document.createElement("button");
        lock.className = "button";
        lock.type = "button";
        lock.textContent = item.is_active ? "Sperren" : "Entsperren";
        lock.addEventListener("click", async () => {
          await api("/api/admin/users/" + item.id + "/" + (item.is_active ? "lock" : "unlock"), { method: "POST" });
          await load();
        });

        const remove = document.createElement("button");
        remove.className = "button";
        remove.type = "button";
        remove.textContent = "Loeschen";
        remove.addEventListener("click", async () => {
          if (!window.confirm(item.username + " wirklich loeschen?")) return;
          await api("/api/admin/users/" + item.id, { method: "DELETE" });
          await load();
        });

        actions.append(reset, lock, remove);
        list.appendChild(row([
          item.username,
          item.email,
          item.role,
          item.department && item.department.name,
          item.is_active ? "aktiv" : "gesperrt",
          actions
        ]));
      });
    }

    await load();
  }

  async function initEmployees() {
    const list = document.querySelector("[data-employee-list]");
    const form = document.querySelector("[data-employee-form]");
    if (!list || !form || !token()) return;

    async function uploadDocument(employeeId, file) {
      const formData = new FormData();
      formData.append("document", file);
      const response = await fetch("/api/employees/" + employeeId + "/documents", {
        method: "POST",
        headers: { "Authorization": "Bearer " + token() },
        body: formData
      });
      if (!response.ok) throw new Error("Upload failed");
    }

    async function load() {
      const employees = await api("/api/employees");
      list.innerHTML = "";
      employees.forEach((employee) => {
        const docs = document.createElement("div");
        docs.className = "document-cell";

        const links = document.createElement("div");
        links.className = "document-links";
        employee.documents.forEach((document) => {
          const link = document.createElement("a");
          link.href = document.download_url;
          link.textContent = document.original_filename;
          link.target = "_blank";
          links.appendChild(link);
        });

        const input = document.createElement("input");
        input.type = "file";
        input.addEventListener("change", async () => {
          if (!input.files.length) return;
          await uploadDocument(employee.id, input.files[0]);
          await load();
        });

        docs.append(links, input);
        list.appendChild(row([
          employee.personnel_number,
          employee.name,
          employee.department,
          employee.current_shift || employee.shift_model,
          employee.team ? "Team " + employee.team : "-",
          employee.salary_group,
          docs
        ]));
      });
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const data = Object.fromEntries(new FormData(form).entries());
      await api("/api/employees", { method: "POST", body: JSON.stringify(data) });
      form.reset();
      await load();
      const message = document.querySelector("[data-employee-message]");
      if (message) message.textContent = "Mitarbeiter gespeichert.";
    });

    await load();
  }

  async function initDashboard() {
    const taskRail = document.querySelector("[data-dashboard-task-rail]");
    const taskCount = document.querySelector("[data-dashboard-task-count]");
    const taskDetailModal = document.querySelector("[data-task-detail-modal]");
    const taskDetailTitle = document.querySelector("[data-task-detail-title]");
    const taskDetailSubtitle = document.querySelector("[data-task-detail-subtitle]");
    const taskDetailBody = document.querySelector("[data-task-detail-body]");
    const taskDetailMessage = document.querySelector("[data-task-detail-message]");
    const taskStartButton = document.querySelector("[data-task-start-button]");
    const taskCompleteButton = document.querySelector("[data-task-complete-button]");
    const taskDetailClose = document.querySelector("[data-task-detail-close]");
    const errorStats = document.querySelector("[data-dashboard-error-stats]");
    if ((!taskRail && !errorStats) || !token()) return;

    let activeTaskId = null;

    function formatDateTime(value) {
      if (!value) return "-";
      return new Date(value).toLocaleString("de-DE");
    }

    function formatUser(value) {
      if (!value) return "-";
      return value.username || value.email || "User #" + value.id;
    }

    function detailRow(label, value) {
      const item = document.createElement("div");
      item.className = "task-detail-row";

      const labelElement = document.createElement("span");
      labelElement.textContent = label;

      const valueElement = document.createElement("strong");
      valueElement.textContent = value || "-";

      item.append(labelElement, valueElement);
      return item;
    }

    function renderTaskDetail(task) {
      if (!taskDetailModal || !taskDetailBody) return;

      activeTaskId = task.id;
      taskDetailTitle.textContent = task.title;
      taskDetailSubtitle.textContent = (task.department && task.department.name) || "-";
      taskDetailBody.innerHTML = "";
      taskDetailBody.append(
        detailRow("Titel", task.title),
        detailRow("Beschreibung", task.description || "Keine Beschreibung"),
        detailRow("Prioritaet", task.priority),
        detailRow("Status", task.status),
        detailRow("Department", task.department && task.department.name),
        detailRow("Ersteller", formatUser(task.creator)),
        detailRow("Erstellt am", formatDateTime(task.created_at)),
        detailRow("Aktuell bearbeitet von", formatUser(task.current_worker)),
        detailRow("Gestartet am", formatDateTime(task.started_at)),
        detailRow("Erledigt von", formatUser(task.completed_by_user)),
        detailRow("Erledigt am", formatDateTime(task.completed_at))
      );

      if (taskStartButton) taskStartButton.disabled = task.status !== "open";
      if (taskCompleteButton) taskCompleteButton.disabled = task.status === "done" || task.status === "cancelled";
      if (taskDetailMessage) taskDetailMessage.textContent = "";
    }

    async function openTaskDetail(taskId) {
      const task = await api("/api/tasks/" + taskId);
      renderTaskDetail(task);
      if (taskDetailModal) taskDetailModal.hidden = false;
    }

    async function refreshActiveTask(message) {
      if (!activeTaskId) return;
      const task = await api("/api/tasks/" + activeTaskId);
      renderTaskDetail(task);
      if (taskDetailMessage) taskDetailMessage.textContent = message;
      await loadDashboardTasks();
    }

    async function loadDashboardTasks() {
      const tasks = await api("/api/tasks");
      taskRail.innerHTML = "";
      if (taskCount) taskCount.textContent = String(tasks.length);
      if (!tasks.length) {
        taskRail.innerHTML = '<div class="empty-state">Noch keine Tasks vorhanden.</div>';
      } else {
        tasks.forEach((task) => {
          const card = document.createElement("button");
          card.type = "button";
          card.className = "task-card";
          card.addEventListener("click", () => openTaskDetail(task.id));
          const priorityClass = task.priority === "urgent" ? "is-urgent" : task.priority === "soon" ? "is-soon" : "is-normal";
          card.innerHTML = `
            <div class="task-card-top">
              <strong>${task.title}</strong>
              <span class="badge ${priorityClass}">${task.priority}</span>
            </div>
            <p>${task.description || "Keine Beschreibung"}</p>
            <small>${task.department ? task.department.name : "-"} · ${task.status} · ${task.due_date}</small>
          `;
          taskRail.appendChild(card);
        });
      }
    }

    if (taskDetailClose && taskDetailModal) {
      taskDetailClose.addEventListener("click", () => {
        taskDetailModal.hidden = true;
      });
    }

    if (taskStartButton) {
      taskStartButton.addEventListener("click", async () => {
        if (!activeTaskId) return;
        await api("/api/tasks/" + activeTaskId + "/start", { method: "POST" });
        await refreshActiveTask("Task gestartet.");
      });
    }

    if (taskCompleteButton) {
      taskCompleteButton.addEventListener("click", async () => {
        if (!activeTaskId) return;
        await api("/api/tasks/" + activeTaskId + "/complete", { method: "POST" });
        await refreshActiveTask("Task abgeschlossen.");
      });
    }

    if (taskRail) {
      await loadDashboardTasks();
    }

    if (errorStats) {
      const errors = await api("/api/errors");
      const counts = new Map();
      errors.forEach((entry) => {
        const name = entry.department ? entry.department.name : "Ohne Bereich";
        counts.set(name, (counts.get(name) || 0) + 1);
      });
      errorStats.innerHTML = "";
      if (!counts.size) {
        errorStats.innerHTML = '<div class="empty-state">Noch keine Fehler erfasst.</div>';
      } else {
        counts.forEach((count, name) => {
          const item = document.createElement("div");
          item.className = "stat-row";
          item.innerHTML = `<span>${name}</span><strong>${count}</strong>`;
          errorStats.appendChild(item);
        });
      }
    }
  }

  document.addEventListener("DOMContentLoaded", async () => {
    if (!token()) return;
    try {
      if (window.maintenanceAuth && window.maintenanceAuth.refreshUser) {
        await window.maintenanceAuth.ensureReady();
      }
      await initDepartments();
      await initDashboard();
      await initTasks();
      await initErrors();
      await initUsers();
      await initEmployees();
    } catch (error) {
      console.warn(error);
    }
  });
})();

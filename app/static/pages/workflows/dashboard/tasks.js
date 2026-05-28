/**
 * Dashboard tasks module.
 * Registers helpers on the current MaintenanceDashboardRuntime object.
 */
(function registerDashboardModule() {
  window.MaintenanceDashboardModules = window.MaintenanceDashboardModules || {};
  window.MaintenanceDashboardModules["tasks"] = function attachDashboardTasks(Dashboard) {
    if (window.maintenanceDashboardReactTasksOwned === true) {
      Object.assign(Dashboard, {
        cockpitAufgabeCard: function cockpitAufgabeCard() {},
        emptyCockpitCard: function emptyCockpitCard() {},
        loadDashboardAufgaben: async function loadDashboardAufgaben() {},
        openAufgabeDetail: async function openAufgabeDetail() {},
        renderAufgabeDetail: function renderAufgabeDetail() {},
        runTaskAction: async function runTaskAction() {},
        updateDashboardAufgabeMetrics: function updateDashboardAufgabeMetrics(tasks) {
          Dashboard.dashboardState.tasks = Array.isArray(tasks) ? tasks : [];
        }
      });
      return;
    }

    with (Dashboard) {
      function updateDashboardAufgabeMetrics(tasks) {
        dashboardState.tasks = tasks;
        const activeTasks = tasks.filter((task) => task.status !== "done" && task.status !== "cancelled");
        const openAufgaben = activeTasks.filter((task) => task.status === "open");
        const progressAufgaben = activeTasks.filter((task) => task.status === "in_progress");
        const doneTasks = tasks.filter((task) => task.status === "done");
        const criticalTasks = activeTasks.filter((task) => task.priority === "urgent" || isOverdue(task));
        taskCountElements.forEach((taskCount) => {
          taskCount.textContent = String(tasks.length);
        });
        setText("[data-dashboard-open-count]", openAufgaben.length);
        setText("[data-dashboard-progress-count]", progressAufgaben.length);
        setText("[data-dashboard-done-count]", doneTasks.length);
        setText("[data-dashboard-critical-count]", criticalTasks.length);
        renderExecutiveDashboard();
        setDashboardText("[data-dashboard-open-meta]", progressAufgaben.length + " in Arbeit");
        setDashboardText("[data-dashboard-critical-meta]", criticalTasks.length ? "sofort prüfen" : "keine kritische Arbeit");
      }

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

      function taskEditField(label, field) {
        const wrapper = document.createElement("label");
        wrapper.className = "field";
        const labelElement = document.createElement("span");
        labelElement.textContent = label;
        wrapper.append(labelElement, field);
        return wrapper;
      }

      function taskEditForm(task) {
        const editForm = document.createElement("form");
        editForm.className = "task-detail-row md:col-span-2";
        editForm.dataset.taskEditForm = "true";

        const title = document.createElement("input");
        title.className = "input input-bordered";
        title.name = "title";
        title.required = true;
        title.value = task.title || "";

        const department = document.createElement("input");
        department.className = "input input-bordered";
        department.name = "department";
        department.required = true;
        department.value = (task.department && task.department.name) || "";

        const priority = document.createElement("select");
        priority.className = "select select-bordered";
        priority.name = "priority";
        setSelectOptions(priority, TASK_PRIORITIES, task.priority || "normal");

        const status = document.createElement("select");
        status.className = "select select-bordered";
        status.name = "status";
        setSelectOptions(status, TASK_STATUSES, task.status || "open");

        const dueDate = document.createElement("input");
        dueDate.className = "input input-bordered";
        dueDate.name = "due_date";
        dueDate.type = "date";
        dueDate.value = task.due_date || "";

        const description = document.createElement("textarea");
        description.className = "textarea textarea-bordered";
        description.name = "description";
        description.value = task.description || "";

        const fields = document.createElement("div");
        fields.className = "form-grid";
        fields.append(
          taskEditField("Titel", title),
          taskEditField("Bereich", department),
          taskEditField("Prioritaet", priority),
          taskEditField("Status", status),
          taskEditField("Fällig am", dueDate),
          taskEditField("Beschreibung", description)
        );

        const actions = document.createElement("div");
        actions.className = "toolbar form-actions";
        const submit = document.createElement("button");
        submit.className = "btn btn-primary";
        submit.type = "submit";
        submit.textContent = "Aenderungen speichern";
        actions.appendChild(submit);

        editForm.append(fields, actions);
        editForm.addEventListener("submit", async (event) => {
          event.preventDefault();
          try {
            submit.disabled = true;
            await api("/api/v1/tasks/" + task.id, {
              method: "PUT",
              body: JSON.stringify(taskFormPayload(editForm))
            });
            const updatedAufgabe = await api("/api/v1/tasks/" + task.id);
            renderAufgabeDetail(updatedAufgabe);
            await loadDashboardAufgaben();
            showAufgabeMessage("Aufgabe aktualisiert.");
          } catch (error) {
            showAufgabeMessage(error.message, true);
          } finally {
            submit.disabled = false;
          }
        });
        return editForm;
      }

      function showAufgabeMessage(message, isError) {
        if (!taskDetailMessage) return;
        taskDetailMessage.textContent = message;
        taskDetailMessage.classList.toggle("is-error", Boolean(isError));
        taskDetailMessage.classList.toggle("is-success", Boolean(message && !isError));
        if (globalLive && message) globalLive.textContent = message;
      }

      function reportPayload() {
        const payload = {};
        if (reportGenerate && reportGenerate.checked) {
          payload.generate_report = true;
          document.querySelectorAll("[data-report-field]").forEach((field) => {
            payload[field.dataset.reportField] = field.value;
          });
          payload.notes = payload.action || "";
        }
        return payload;
      }

      function updateAufgabeActionButtons(task, isBusy) {
        if (taskStartButton) {
          taskStartButton.hidden = !canWrite("tasks");
          taskStartButton.disabled = Boolean(isBusy) || task.status !== "open";
        }
        if (taskCompleteButton) {
          taskCompleteButton.hidden = !canWrite("tasks");
          taskCompleteButton.disabled = Boolean(isBusy) || task.status === "done" || task.status === "cancelled";
        }
      }

      function renderAufgabeDetail(task) {
        if (!taskDetailModal || !taskDetailBody) return;
        activeTask = task;
        activeTaskId = task.id;
        taskDetailTitle.textContent = task.title;
        taskDetailSubtitle.textContent = (task.department && task.department.name) || "-";
        taskDetailBody.innerHTML = "";
        taskDetailBody.append(
          detailRow("Titel", task.title),
          detailRow("Beschreibung", task.description || "Keine Beschreibung"),
          detailRow("Prioritaet", task.priority),
          detailRow("Status", task.status),
          detailRow("Bereich", task.department && task.department.name),
          detailRow("Ersteller", formatUser(task.creator)),
          detailRow("Erstellt am", formatDateTime(task.created_at)),
          detailRow("Aktuell bearbeitet von", formatUser(task.current_worker)),
          detailRow("Gestartet am", formatDateTime(task.started_at)),
          detailRow("Erledigt von", formatUser(task.completed_by_user)),
          detailRow("Erledigt am", formatDateTime(task.completed_at))
        );
        if (canWrite("tasks")) {
          taskDetailBody.appendChild(taskEditForm(task));
        }
        updateAufgabeActionButtons(task);
        showAufgabeMessage("");
      }

      async function openAufgabeDetail(taskId) {
        const task = await api("/api/v1/tasks/" + taskId);
        renderAufgabeDetail(task);
        if (taskDetailModal) {
          taskDetailModal.hidden = false;
          const closeButton = taskDetailModal.querySelector("[data-task-detail-close]");
          if (closeButton) closeButton.focus();
        }
      }

      async function runTaskAction(taskId, action, body) {
        const path = "/api/v1/tasks/" + taskId + "/" + action;
        const success = action === "start" ? "Aufgabe gestartet." : "Aufgabe abgeschlossen.";
        const options = { method: "POST" };
        if (body && Object.keys(body).length) {
          options.body = JSON.stringify(body);
        }
        try {
          const result = await api(path, options);
          const suffix = result && result.generated_document
            ? " Wartungsbericht wurde erzeugt."
            : "";
          announce(success + suffix);
          if (activeTaskId === taskId) {
            renderAufgabeDetail(await api("/api/v1/tasks/" + taskId));
            showAufgabeMessage(success + suffix);
          }
          await loadDashboardAufgaben();
        } catch (error) {
          announce(error.message, true);
          showAufgabeMessage(error.message, true);
        }
      }

      function emptyCockpitCard(groupName) {
        const card = document.createElement("article");
        card.className = "cockpit-task-card is-empty";
        const text = document.createElement("p");
        text.textContent = groupName === "urgent"
          ? "Keine kritischen Aufgaben. Beobachte neue Störungen und überfällige Arbeit."
          : groupName === "today"
            ? "Keine Aufgaben für heute. Neue Arbeit kannst du direkt aus dem Cockpit anlegen."
            : "Keine Aufgaben in Arbeit. Starte offene Aufgaben, sobald Verantwortung und Material klar sind.";
        card.appendChild(text);
        if (cockpitSuggestForm && canWrite("tasks")) {
          const captureButton = actionButton("Aufgaben öffnen", () => {
            if (cockpitSuggestForm.hidden) {
              window.location.href = "/tasks";
              return;
            }
            revealSurface(cockpitSuggestForm);
            const input = cockpitSuggestForm.querySelector("textarea");
            if (input) input.focus();
          });
          captureButton.className = "btn btn-primary btn-sm";
          card.appendChild(captureButton);
        }
        return card;
      }

      function cockpitAufgabeCard(task) {
        const card = document.createElement("article");
        card.className = "cockpit-task-card";
        const title = document.createElement("h4");
        title.className = "cockpit-task-title";
        title.textContent = task.title;
        const priority = labeledBadge(task.priority, priorityBadgeClass(task.priority), priorityLabel);
        const status = labeledBadge(task.status, statusBadgeClass(task.status), statusLabel);
        const badges = document.createElement("div");
        badges.className = "flex flex-wrap gap-2";
        badges.append(priority, status);
        const meta = document.createElement("div");
        meta.className = "cockpit-task-meta";
        [
          task.department && task.department.name,
          relativeDateLabel(task.due_date),
          task.current_worker ? formatUser(task.current_worker) : null
        ].filter(Boolean).forEach((value) => {
          const item = document.createElement("span");
          item.textContent = value;
          meta.appendChild(item);
        });
        const actions = document.createElement("div");
        actions.className = "cockpit-task-actions";
        actions.appendChild(actionButton("Details", () => openAufgabeDetail(task.id)));
        if (canWrite("tasks") && task.status === "open") {
          const start = actionButton("Starten", () => runTaskAction(task.id, "start"));
          start.className = "btn btn-primary btn-sm";
          actions.appendChild(start);
        }
        if (canWrite("tasks") && task.status !== "done" && task.status !== "cancelled") {
          const complete = actionButton("Erledigt", () => runTaskAction(task.id, "complete"));
          complete.className = "btn btn-success btn-sm text-white";
          actions.appendChild(complete);
        }
        card.append(title, badges, meta, actions);
        return card;
      }

      async function loadDashboardAufgaben() {
        const tasks = listData(await api("/api/v1/tasks?limit=100"));
        const lists = {
          urgent: document.querySelector("[data-cockpit-list='urgent']"),
          today: document.querySelector("[data-cockpit-list='today']"),
          progress: document.querySelector("[data-cockpit-list='progress']")
        };
        Object.values(lists).forEach((list) => {
          if (list) list.innerHTML = "";
        });
        updateDashboardAufgabeMetrics(tasks);
        const groups = { urgent: [], today: [], progress: [] };
        const activeTasks = tasks.filter((task) => task.status !== "done" && task.status !== "cancelled");
        activeTasks.forEach((task) => {
          if (task.status === "in_progress") groups.progress.push(task);
          else if (task.priority === "urgent" || isOverdue(task)) groups.urgent.push(task);
          else if (task.due_date === todayIso()) groups.today.push(task);
        });
        Object.entries(groups).forEach(([name, group]) => {
          setText("[data-cockpit-count='" + name + "']", group.length);
          const list = lists[name];
          if (!list) return;
          if (!group.length) {
            list.appendChild(emptyCockpitCard(name));
            return;
          }
          group.forEach((task) => list.appendChild(cockpitAufgabeCard(task)));
        });
      }

      if (taskDetailClose && taskDetailModal) {
        taskDetailClose.addEventListener("click", () => {
          taskDetailModal.hidden = true;
        });
      }

      if (taskStartButton) {
        taskStartButton.addEventListener("click", () => {
          if (activeTaskId) runTaskAction(activeTaskId, "start");
        });
      }

      if (taskCompleteButton) {
        taskCompleteButton.addEventListener("click", () => {
          if (activeTaskId) runTaskAction(activeTaskId, "complete", reportPayload());
        });
      }

      if (cockpitSuggestForm && cockpitDraft) {
        cockpitSuggestForm.addEventListener("submit", async (event) => {
          event.preventDefault();
          const data = Object.fromEntries(new FormData(cockpitSuggestForm).entries());
          setFormBusy(cockpitSuggestForm, true, "Erstellt...");
          announce("KI erstellt Vorschlag...");
          try {
            const suggestion = await api("/api/v1/tasks/suggest", {
              method: "POST",
              body: JSON.stringify(data)
            });
            cockpitDraft.hidden = false;
            cockpitDraft.elements.title.value = suggestion.title || "";
            cockpitDraft.elements.department.value = suggestion.department || "";
            cockpitDraft.elements.priority.value = suggestion.priority || "normal";
            cockpitDraft.elements.status.value = suggestion.status || "open";
            cockpitDraft.elements.description.value = [
              suggestion.description,
              suggestion.possible_cause ? "Mögliche Ursache: " + suggestion.possible_cause : "",
              suggestion.recommended_action ? "Nächste Aktion: " + suggestion.recommended_action : ""
            ].filter(Boolean).join("\n\n");
            announce("Vorschlag erstellt. Bitte prüfen und speichern.");
          } catch (error) {
            announce(error.message, true);
          } finally {
            setFormBusy(cockpitSuggestForm, false);
          }
        });

        cockpitDraft.addEventListener("submit", async (event) => {
          event.preventDefault();
          const data = Object.fromEntries(new FormData(cockpitDraft).entries());
          setFormBusy(cockpitDraft, true, "Speichert...");
          try {
            await api("/api/v1/tasks", { method: "POST", body: JSON.stringify(data) });
            cockpitSuggestForm.reset();
            cockpitDraft.reset();
            cockpitDraft.hidden = true;
            announce("Aufgabe gespeichert.");
            await loadDashboardAufgaben();
          } catch (error) {
            announce(error.message, true);
          } finally {
            setFormBusy(cockpitDraft, false);
          }
        });
      }

      if (cockpitDraftCancel && cockpitDraft) {
        cockpitDraftCancel.addEventListener("click", () => {
          cockpitDraft.reset();
          cockpitDraft.hidden = true;
          announce("Vorschlag verworfen.");
        });
      }

      quickAiButtons.forEach((button) => {
        if (button.dataset.bound === "true") return;
        button.addEventListener("click", () => {
          const chatToggle = document.querySelector(".chat-toggle");
          const chatInput = document.querySelector("#chat-message-input, [data-chat-input], textarea[name='message']");
          if (chatToggle) chatToggle.click();
          window.setTimeout(() => {
            if (chatInput && typeof chatInput.focus === "function") chatInput.focus();
          }, 120);
        });
        button.dataset.bound = "true";
      });
      Object.assign(Dashboard, { updateDashboardAufgabeMetrics, formatDateTime, formatUser, detailRow, taskEditField, taskEditForm, showAufgabeMessage, reportPayload, updateAufgabeActionButtons, renderAufgabeDetail, openAufgabeDetail, runTaskAction, emptyCockpitCard, cockpitAufgabeCard, loadDashboardAufgaben });
    }
  };
})();

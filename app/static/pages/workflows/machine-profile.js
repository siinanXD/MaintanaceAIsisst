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

async function initMachineProfile() {
  const root = document.querySelector("[data-machine-profile-page]");
  if (!root || !token()) return;
  const machineId = root.dataset.machineId;
  const message = root.querySelector("[data-machine-profile-message]");
  if (!machineId) {
    setStatusMessage(message, "Maschinen-ID fehlt.", true);
    return;
  }

  function profileData(payload) {
    return payload && payload.machine ? payload : ((payload && payload.data) || {});
  }

  function profileList(selector) {
    return root.querySelector(selector + " .machine-profile-list");
  }

  function valueText(value) {
    if (value === 0) return "0";
    return value || "-";
  }

  function dateLabel(value, options) {
    if (!value) return "-";
    const raw = String(value);
    const parsed = new Date(raw.includes("T") ? raw : raw + "T00:00:00");
    if (Number.isNaN(parsed.getTime())) return raw;
    return parsed.toLocaleDateString("de-DE", options || {
      day: "2-digit",
      month: "2-digit",
      year: "numeric"
    });
  }

  function minutesLabel(value) {
    const minutes = Number(value || 0);
    if (!minutes) return "0 min";
    if (minutes < 60) return minutes + " min";
    const hours = Math.floor(minutes / 60);
    const rest = minutes % 60;
    return rest ? hours + " h " + rest + " min" : hours + " h";
  }

  function machineStatusLabel(status) {
    const labels = {
      running: "Läuft",
      stopped: "Stillstand",
      maintenance: "Wartung",
      warning: "Warnung",
      offline: "Offline"
    };
    return labels[status] || status || "-";
  }

  function criticalityLabel(criticality) {
    const labels = {
      critical: "Kritisch",
      high: "Hoch",
      normal: "Normal",
      low: "Niedrig"
    };
    return labels[criticality] || criticality || "Normal";
  }

  function criticalityBadgeClass(criticality) {
    if (criticality === "critical" || criticality === "high") {
      return "badge badge-priority is-urgent";
    }
    if (criticality === "low") return "badge badge-priority is-normal";
    return "badge badge-status is-done";
  }

  function severityLabel(severity) {
    const labels = {
      critical: "Kritisch",
      high: "Hoch",
      medium: "Mittel",
      low: "Niedrig"
    };
    return labels[severity] || severity || "-";
  }

  function errorStatusLabel(status) {
    const labels = {
      open: "Offen",
      in_progress: "In Arbeit",
      closed: "Geschlossen"
    };
    return labels[status] || status || "-";
  }

  function profileEmpty(text, action) {
    const empty = document.createElement("div");
    empty.className = "machine-profile-empty";
    const strong = document.createElement("strong");
    strong.textContent = text;
    empty.appendChild(strong);
    if (action && action.href) {
      const link = document.createElement("a");
      link.className = "btn btn-outline btn-sm";
      link.href = action.href;
      link.textContent = action.label || "Öffnen";
      empty.appendChild(link);
    }
    return empty;
  }

  function metric(label, value) {
    const item = document.createElement("span");
    const labelElement = document.createElement("small");
    const valueElement = document.createElement("strong");
    labelElement.textContent = label;
    valueElement.textContent = valueText(value);
    item.append(labelElement, valueElement);
    return item;
  }

  function profileRecordCard(data) {
    const card = document.createElement("article");
    card.className = "machine-profile-record";

    const header = document.createElement("div");
    header.className = "machine-profile-record-header";
    const titleBlock = document.createElement("div");
    const title = document.createElement("h3");
    title.textContent = data.title || "-";
    const subtitle = document.createElement("p");
    subtitle.textContent = data.subtitle || "";
    titleBlock.append(title, subtitle);
    const badges = document.createElement("div");
    badges.className = "machine-profile-record-badges";
    (data.badges || []).forEach((item) => {
      badges.appendChild(badge(item[0], item[1]));
    });
    header.append(titleBlock, badges);
    card.appendChild(header);

    if (data.summary) {
      const summary = document.createElement("p");
      summary.className = "machine-profile-record-summary";
      summary.textContent = data.summary;
      card.appendChild(summary);
    }

    if (data.metrics && data.metrics.length) {
      const metrics = document.createElement("div");
      metrics.className = "machine-profile-record-metrics";
      data.metrics.forEach((item) => metrics.appendChild(metric(item[0], item[1])));
      card.appendChild(metrics);
    }

    if (data.url) {
      const actions = document.createElement("div");
      actions.className = "machine-profile-record-actions";
      const link = document.createElement("a");
      link.className = "btn btn-outline btn-sm";
      link.href = data.url;
      link.textContent = data.actionLabel || "Öffnen";
      actions.appendChild(link);
      card.appendChild(actions);
    }
    return card;
  }

  function renderRecords(container, items, emptyText, mapper, action) {
    if (!container) return;
    container.innerHTML = "";
    const rows = Array.isArray(items) ? items : [];
    if (!rows.length) {
      container.appendChild(profileEmpty(emptyText, action));
      return;
    }
    rows.forEach((item) => container.appendChild(profileRecordCard(mapper(item))));
  }

  function renderDenied(container, text) {
    if (!container) return;
    container.innerHTML = "";
    container.appendChild(profileEmpty(text || "Keine Berechtigung für diesen Bereich."));
  }

  function renderHero(profile) {
    const machine = profile.machine || {};
    const name = root.querySelector("[data-machine-profile-name]");
    const summary = root.querySelector("[data-machine-profile-summary]");
    const badges = root.querySelector("[data-machine-profile-badges]");
    const taskLink = root.querySelector("[data-machine-profile-task-link]");
    const errorLink = root.querySelector("[data-machine-profile-error-link]");
    const documentLink = root.querySelector("[data-machine-profile-document-link]");
    if (name) name.textContent = machine.name || "Maschine";
    if (summary) {
      summary.textContent = [
        machine.produced_item || "Kein Produkt hinterlegt",
        (machine.required_employees || 1) + " Mitarbeiter pro Schicht",
        machine.site && machine.site.name ? machine.site.name : "Werk nicht zugeordnet"
      ].join(" · ");
    }
    if (badges) {
      badges.innerHTML = "";
      badges.appendChild(
        badge(machineStatusLabel(machine.status), genericStatusBadgeClass(machine.status))
      );
      badges.appendChild(
        badge(criticalityLabel(machine.criticality), criticalityBadgeClass(machine.criticality))
      );
    }
    const query = encodeURIComponent(machine.name || "");
    if (taskLink) taskLink.href = "/tasks?search=" + query;
    if (errorLink) errorLink.href = "/errors?search=" + query;
    if (documentLink) documentLink.href = "/documents?search=" + query;
  }

  function renderKpis(profile) {
    const container = root.querySelector("[data-machine-profile-kpis]");
    const kpis = profile.kpis || {};
    if (!container) return;
    container.innerHTML = "";
    [
      ["Offene Aufgaben", kpis.open_tasks || 0, "Aktive Arbeit zur Maschine", "is-work"],
      ["Aktive Störungen", kpis.active_errors || 0, "Offen oder in Bearbeitung", "is-risk"],
      ["Kritisch", kpis.critical_errors || 0, "Hohe Dringlichkeit", "is-critical"],
      ["Wartung fällig", kpis.maintenance_due || 0, "Aktive Wartungspläne", "is-maintenance"],
      ["Dokumente", kpis.documents || 0, "Berichte und Handbücher", "is-knowledge"],
      ["Stillstand", minutesLabel(kpis.downtime_minutes), "Erfasste Ausfallzeit", "is-downtime"]
    ].forEach(([label, value, meta, tone]) => {
      const card = document.createElement("article");
      card.className = "machine-profile-kpi-card " + tone;
      const labelElement = document.createElement("span");
      const valueElement = document.createElement("strong");
      const metaElement = document.createElement("small");
      labelElement.textContent = label;
      valueElement.textContent = String(value);
      metaElement.textContent = meta;
      card.append(labelElement, valueElement, metaElement);
      container.appendChild(card);
    });
  }

  function renderMaster(profile) {
    const container = root.querySelector("[data-machine-profile-master] .machine-profile-facts");
    const machine = profile.machine || {};
    if (!container) return;
    container.innerHTML = "";
    [
      ["Status", machineStatusLabel(machine.status)],
      ["Kritikalität", criticalityLabel(machine.criticality)],
      ["Produkt", machine.produced_item || "-"],
      ["Personalbedarf", (machine.required_employees || 1) + " MA"],
      ["Werk", machine.site && machine.site.name ? machine.site.name : "-"],
      ["Angelegt", dateLabel(machine.created_at)]
    ].forEach((item) => container.appendChild(metric(item[0], item[1])));
  }

  function taskRecord(task) {
    return {
      title: task.title,
      subtitle: task.department && task.department.name ? task.department.name : "Bereich offen",
      summary: task.description || "Keine Beschreibung hinterlegt.",
      badges: [
        [priorityLabel(task.priority), priorityBadgeClass(task.priority)],
        [statusLabel(task.status), statusBadgeClass(task.status)]
      ],
      metrics: [
        ["Fällig", dateLabel(task.due_date)],
        ["Zuordnung", task.current_worker ? task.current_worker.username : "Nicht gestartet"],
        ["Bezug", task.machine_match || "-"]
      ],
      url: task.ui_url || "/tasks?search=" + encodeURIComponent(task.title || ""),
      actionLabel: "Aufgabe öffnen"
    };
  }

  function errorRecord(error) {
    return {
      title: [error.error_code, error.title].filter(Boolean).join(" · "),
      subtitle: error.cause_category || error.machine || "Störung",
      summary: error.symptoms || error.description || error.solution || "Keine Details hinterlegt.",
      badges: [
        [errorStatusLabel(error.status), genericStatusBadgeClass(error.status)],
        [severityLabel(error.severity), criticalityBadgeClass(error.severity)]
      ],
      metrics: [
        ["Auswirkung", error.impact || "-"],
        ["Stillstand", minutesLabel(error.downtime_minutes)],
        ["Erfasst", dateLabel(error.created_at)]
      ],
      url: error.ui_url || "/errors?search=" + encodeURIComponent(error.error_code || ""),
      actionLabel: "Störung öffnen"
    };
  }

  function maintenanceRecord(plan) {
    return {
      title: plan.title,
      subtitle: plan.department && plan.department.name ? plan.department.name : "Wartungsplan",
      summary: plan.description || "Kein Ablauf hinterlegt.",
      badges: [
        [priorityLabel(plan.priority), priorityBadgeClass(plan.priority)],
        [plan.is_due ? "Fällig" : "Geplant", plan.is_due ? "badge badge-priority is-soon" : "badge badge-status is-progress"]
      ],
      metrics: [
        ["Intervall", (plan.interval_days || 0) + " Tage"],
        ["Nächster Termin", dateLabel(plan.next_due_date)],
        ["Letzte Erzeugung", dateLabel(plan.last_generated_at)]
      ],
      url: plan.ui_url || "/machines",
      actionLabel: "Wartungspläne"
    };
  }

  function documentRecord(document, typeLabel) {
    return {
      title: document.title || document.original_filename || typeLabel,
      subtitle: typeLabel,
      summary: document.summary || document.analysis || "Noch keine Zusammenfassung hinterlegt.",
      badges: [
        [document.status || document.analysis_status || "not_started", genericStatusBadgeClass(document.status || document.analysis_status)]
      ],
      metrics: [
        ["Bereich", document.department || "-"],
        ["Version", document.version || "-"],
        ["Erstellt", dateLabel(document.created_at)]
      ],
      url: document.ui_url || "/documents",
      actionLabel: "Dokumente öffnen"
    };
  }

  function handoverRecord(handover) {
    return {
      title: dateLabel(handover.shift_date) + " · " + valueText(handover.shift_type),
      subtitle: handover.area || handover.department || "Schichtübergabe",
      summary: handover.machine_status || handover.action_taken || handover.content || "Keine Maschinennotiz hinterlegt.",
      badges: [
        [handover.status === "completed" ? "Bestätigt" : "Offen", genericStatusBadgeClass(handover.status)]
      ],
      metrics: [
        ["Vorher", handover.previous_shift || "-"],
        ["Nächste", handover.next_shift || "-"],
        ["Verantwortlich", handover.responsible_employee || handover.handed_over_by || "-"]
      ],
      url: handover.ui_url || "/handover",
      actionLabel: "Übergabe öffnen"
    };
  }

  function materialRecord(material) {
    return {
      title: material.name,
      subtitle: material.manufacturer || "Ersatzteil",
      summary: material.is_below_minimum
        ? "Mindestbestand unterschritten."
        : "Bestand im Profil hinterlegt.",
      badges: [
        [material.is_below_minimum ? "Prüfen" : "OK", material.is_below_minimum ? "badge badge-priority is-soon" : "badge badge-status is-done"]
      ],
      metrics: [
        ["Bestand", material.quantity || 0],
        ["Minimum", material.min_quantity || 0],
        ["Wert", (material.total_value || 0) + " EUR"]
      ],
      url: "/inventory",
      actionLabel: "Lager öffnen"
    };
  }

  function timelineRecord(item) {
    return {
      title: item.title,
      subtitle: dateLabel(item.date),
      summary: item.summary || "Kein Kurztext hinterlegt.",
      badges: [[item.label || item.type, genericStatusBadgeClass(item.status)]],
      metrics: [
        ["Typ", item.label || item.type],
        ["Status", item.status || "-"]
      ],
      url: item.ui_url,
      actionLabel: "Quelle öffnen"
    };
  }

  function renderProfile(profile) {
    const permissions = profile.permissions || {};
    renderHero(profile);
    renderKpis(profile);
    renderMaster(profile);

    if (permissions.tasks === false) {
      renderDenied(profileList("[data-machine-profile-tasks]"));
    } else {
      renderRecords(
        profileList("[data-machine-profile-tasks]"),
        profile.open_tasks,
        "Keine offenen Aufgaben zur Maschine.",
        taskRecord,
        { href: "/tasks", label: "Aufgabe anlegen" }
      );
    }

    if (permissions.errors === false) {
      renderDenied(profileList("[data-machine-profile-errors]"));
      renderDenied(profileList("[data-machine-profile-error-history]"));
    } else {
      renderRecords(
        profileList("[data-machine-profile-errors]"),
        profile.active_errors,
        "Keine aktive Störung zur Maschine.",
        errorRecord,
        { href: "/errors", label: "Störung melden" }
      );
      renderRecords(
        profileList("[data-machine-profile-error-history]"),
        profile.error_history,
        "Noch keine Fehlerhistorie vorhanden.",
        errorRecord
      );
    }

    if (permissions.documents === false) {
      renderDenied(profileList("[data-machine-profile-documents]"));
    } else {
      const documents = profile.documents || {};
      const reportRecords = (documents.reports || []).map((item) => ({ item, type: "Bericht" }));
      const manualRecords = (documents.manuals || []).map((item) => ({ item, type: "Handbuch" }));
      renderRecords(
        profileList("[data-machine-profile-documents]"),
        reportRecords.concat(manualRecords),
        "Keine Dokumente oder Handbücher zugeordnet.",
        (entry) => documentRecord(entry.item, entry.type),
        { href: "/documents", label: "Dokument hochladen" }
      );
    }

    renderRecords(
      profileList("[data-machine-profile-maintenance]"),
      profile.maintenance_plans,
      "Keine Wartungspläne für diese Maschine.",
      maintenanceRecord,
      { href: "/machines", label: "Wartungsplan prüfen" }
    );

    if (permissions.shiftplans === false) {
      renderDenied(profileList("[data-machine-profile-handovers]"));
    } else {
      renderRecords(
        profileList("[data-machine-profile-handovers]"),
        profile.shift_handovers,
        "Keine Übergaben zur Maschine.",
        handoverRecord,
        { href: "/handover", label: "Übergabe erfassen" }
      );
    }

    if (permissions.inventory === false) {
      renderDenied(profileList("[data-machine-profile-materials]"));
    } else {
      renderRecords(
        profileList("[data-machine-profile-materials]"),
        profile.materials,
        "Keine Ersatzteile zugeordnet.",
        materialRecord,
        { href: "/inventory", label: "Lager öffnen" }
      );
    }

    renderRecords(
      profileList("[data-machine-profile-timeline]"),
      profile.timeline,
      "Noch keine Signale im Maschinenverlauf.",
      timelineRecord
    );
  }

  try {
    setStatusMessage(message, "Maschinenprofil wird geladen...");
    const payload = await api("/api/v1/machines/" + machineId + "/profile");
    const profile = profileData(payload);
    renderProfile(profile);
    setStatusMessage(message, "Maschinenprofil bereit.");
  } catch (error) {
    setStatusMessage(message, error.message || "Maschinenprofil konnte nicht geladen werden.", true);
  }
}

export { initMachineProfile };

registerWorkflowInitializers({
  initMachineProfile: initMachineProfile
});

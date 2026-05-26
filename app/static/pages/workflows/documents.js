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

async function initDocuments() {
  const list = document.querySelector("[data-document-list]");
  const form = document.querySelector("[data-document-filter-form]");
  const reset = document.querySelector("[data-document-filter-reset]");
  const reviewPanel = document.querySelector("[data-document-review-panel]");
  const reviewZusammenfassung = document.querySelector("[data-document-review-summary]");
  const reviewScore = document.querySelector("[data-document-review-score]");
  const reviewStatus = document.querySelector("[data-document-review-status]");
  const reviewStatusBadge = document.querySelector("[data-document-review-status-badge]");
  const reviewQuelle = document.querySelector("[data-document-review-source]");
  const reviewFindings = document.querySelector("[data-document-review-findings]");
  const reviewRecommendations = document.querySelector("[data-document-review-recommendations]");
  const summaryPanel = document.querySelector("[data-document-summary-panel]");
  const summaryTitle = document.querySelector("[data-document-summary-title]");
  const summaryStatus = document.querySelector("[data-document-summary-status]");
  const summaryText = document.querySelector("[data-document-summary-text]");
  const uploadCheckForm = document.querySelector("[data-document-upload-check-form]");
  const uploadCheckMessage = document.querySelector("[data-document-upload-check-message]");
  const uploadCheckFile = uploadCheckForm ? uploadCheckForm.querySelector("input[type='file']") : null;
  const documentMessage = document.querySelector("[data-document-message]");
  const manualForm = document.querySelector("[data-manual-upload-form]");
  const manualList = document.querySelector("[data-manual-list]");
  const manualMessage = document.querySelector("[data-manual-message]");
  const manualMachineSelect = document.querySelector("[data-manual-machine-select]");
  if (!list || !form) return;
  if (!token()) {
    setStatusMessage(documentMessage, "Sitzung wird geladen. Dokumentaktionen werden gleich aktiviert.");
    return;
  }
  if (uploadCheckFile && uploadCheckMessage) {
    if (!uploadCheckMessage.id) uploadCheckMessage.id = "document-upload-check-message";
    uploadCheckFile.setAttribute("aria-describedby", uploadCheckMessage.id);
  }

  function reviewStatusLabel(status) {
    if (status === "good") return "Gut";
    if (status === "needs_review") return "Prüfen";
    return "Unvollständig";
  }

  function reviewStatusClass(status) {
    if (status === "good") return "badge badge-status is-done";
    if (status === "needs_review") return "badge badge-status is-progress";
    return "badge badge-status is-open";
  }

  function renderTableMessage(tableBody, colspan, message, isError) {
    if (!tableBody) return;
    if (tableBody.tagName !== "TBODY") {
      tableBody.innerHTML = "";
      const empty = document.createElement("article");
      empty.className = isError ? "guided-empty-state empty-state is-error" : "guided-empty-state empty-state";
      const title = document.createElement("strong");
      title.textContent = message;
      const hint = document.createElement("p");
      if (isError || message.includes("werden geladen")) {
        hint.textContent = isError ? "Bitte erneut versuchen oder die Berechtigung prüfen." : "Die Wissensbasis wird aktualisiert.";
      } else {
        hint.textContent = message.includes("Handb")
          ? "Lade ein Maschinenhandbuch hoch und ordne es Maschine und Bereich zu, damit es als Quelle nutzbar wird."
          : "Nutze Filter, lade ein Dokument hoch oder prüfe abgeschlossene Aufgaben, wenn du einen Bericht erwartest.";
      }
      empty.append(title, hint);
      tableBody.appendChild(empty);
      return;
    }
    const cell = document.createElement("td");
    cell.colSpan = colspan;
    cell.className = isError ? "table-message is-error" : "table-message";
    if (isError || message.includes("werden geladen")) {
      cell.textContent = message;
    } else {
      const empty = document.createElement("div");
      empty.className = "guided-empty-state";
      const title = document.createElement("strong");
      title.textContent = message;
      const hint = document.createElement("p");
      hint.textContent = message.includes("Handbücher")
        ? "Lade ein Maschinenhandbuch hoch und ordne es Maschine und Bereich zu, damit die AI eine belastbare Quelle findet."
        : "Nutze Filter, lade ein Dokument hoch oder prüfe abgeschlossene Aufgaben, wenn du einen Bericht erwartest.";
      empty.append(title, hint);
      cell.appendChild(empty);
    }
    const tableRow = document.createElement("tr");
    tableRow.appendChild(cell);
    tableBody.innerHTML = "";
    tableBody.appendChild(tableRow);
  }

  function severityClass(severity) {
    const value = String(severity || "").toLowerCase();
    if (["critical", "error", "high"].includes(value)) return "is-critical";
    if (["warning", "warn", "medium", "needs_review"].includes(value)) return "is-warning";
    return "is-good";
  }

  function severityMarker(severity) {
    const value = severityClass(severity);
    if (value === "is-critical") return "!";
    if (value === "is-warning") return "?";
    return "OK";
  }

  function reviewFindingItem(finding) {
    const item = document.createElement("article");
    item.className = "review-check-item " + severityClass(finding && finding.severity);
    const marker = document.createElement("span");
    marker.className = "review-check-marker";
    marker.textContent = severityMarker(finding && finding.severity);
    const content = document.createElement("div");
    content.className = "review-check-content";
    const title = document.createElement("strong");
    title.textContent = (finding && finding.field) || "Prüfpunkt";
    const message = document.createElement("span");
    message.textContent = (finding && finding.message) || "Keine Details vorhanden.";
    const meta = document.createElement("small");
    meta.textContent = (finding && finding.severity) ? "Schweregrad: " + finding.severity : "Hinweis";
    content.appendChild(title);
    content.appendChild(message);
    content.appendChild(meta);
    item.appendChild(marker);
    item.appendChild(content);
    return item;
  }

  function allowedCheckFile(file) {
    if (!file) return false;
    const name = String(file.name || "").toLowerCase();
    const type = String(file.type || "").toLowerCase();
    return name.endsWith(".html")
      || name.endsWith(".htm")
      || name.endsWith(".txt")
      || type === "text/html"
      || type === "text/plain";
  }

  function validateUploadCheckFile(fileInput) {
    if (!fileInput || !fileInput.files || !fileInput.files.length) {
      if (fileInput) fileInput.setAttribute("aria-invalid", "true");
      setStatusMessage(uploadCheckMessage, "Bitte eine HTML- oder TXT-Datei auswählen.", true);
      return false;
    }
    const file = fileInput.files[0];
    if (!allowedCheckFile(file)) {
      fileInput.setAttribute("aria-invalid", "true");
      setStatusMessage(uploadCheckMessage, "Nur HTML-, HTM- oder TXT-Dateien können geprüft werden.", true);
      return false;
    }
    fileInput.removeAttribute("aria-invalid");
    return true;
  }

  function renderDocumentReview(review) {
    if (!reviewPanel || !reviewFindings) return;
    const documentMeta = (review && review.document) || {};
    const findings = Array.isArray(review && review.findings) ? review.findings : [];
    const recommendations = Array.isArray(review && review.recommendations) ? review.recommendations : [];
    reviewPanel.hidden = false;
    if (reviewZusammenfassung) {
      reviewZusammenfassung.textContent = "Prüfung für " + (documentMeta.title || documentMeta.filename || "Dokument");
    }
    if (reviewScore) reviewScore.textContent = String((review && review.quality_score) || 0);
    if (reviewStatus) reviewStatus.textContent = reviewStatusLabel(review && review.status);
    if (reviewStatusBadge) {
      reviewStatusBadge.className = reviewStatusClass(review && review.status);
      reviewStatusBadge.textContent = reviewStatusLabel(review && review.status);
    }
    if (reviewQuelle) {
      reviewQuelle.textContent = documentMeta.source || documentMeta.document_type || "Dokument";
    }
    reviewFindings.innerHTML = "";
    if (!findings.length) {
      reviewFindings.appendChild(reviewFindingItem({
        field: "Keine Findings",
        message: "Die Prüfung hat keine offenen Punkte gefunden.",
        severity: "good"
      }));
    } else {
      findings.forEach((finding) => {
        reviewFindings.appendChild(reviewFindingItem(finding));
      });
    }
    if (reviewRecommendations) {
      reviewRecommendations.textContent = recommendations.length
        ? "Empfehlungen: " + recommendations.join(" | ")
        : "Keine Empfehlungen erforderlich.";
    }
    reviewPanel.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function reviewDocument(documentItem) {
    const review = await api("/api/v1/documents/" + documentItem.id + "/review", {
      method: "POST"
    });
    renderDocumentReview(review);
  }

  async function downloadDocument(documentItem) {
    await downloadFile(documentItem.download_url, "maintenance_report_task_" + documentItem.task_id + ".html");
  }

  async function downloadDocumentPdf(documentItem) {
    await downloadFile(
      "/api/v1/documents/" + documentItem.id + "/download.pdf",
      "maintenance_report_task_" + documentItem.task_id + ".pdf"
    );
  }

  function renderZusammenfassung(title, status, text) {
    if (!summaryPanel || !summaryText) return;
    summaryPanel.hidden = false;
    if (summaryTitle) summaryTitle.textContent = title;
    if (summaryStatus) summaryStatus.textContent = status || "-";
    summaryText.textContent = text || "Keine Zusammenfassung vorhanden.";
    summaryPanel.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function summarizeDocument(documentItem) {
    const result = await api("/api/v1/documents/" + documentItem.id + "/summarize", {
      method: "POST"
    });
    renderZusammenfassung(result.title, result.summary_status, result.summary);
  }

  async function showVersions(documentItem) {
    const result = await api("/api/v1/documents/" + documentItem.id + "/versions");
    const versions = listData(result).map((version) => (
      "v" + version.version_number + " - " + new Date(version.created_at).toLocaleString("de-DE")
    ));
    await showInfoDialog({
      title: "Dokumentversionen",
      message: versions.length ? versions.join("\n") : "Keine Versionen vorhanden."
    });
  }

  async function changeDocumentStatus(documentItem, action) {
    const comment = await requestText({
      title: action === "approve" ? "Dokument freigeben" : "Dokument ablehnen",
      message: "Kommentar für " + (action === "approve" ? "Freigabe" : "Ablehnung") + ". Leerlassen ist erlaubt.",
      label: "Kommentar",
      multiline: true,
      defaultValue: "",
      confirmText: action === "approve" ? "Freigeben" : "Ablehnen"
    });
    if (comment === null) return;
    await api("/api/v1/documents/" + documentItem.id + "/" + action, {
      method: "POST",
      body: JSON.stringify({ comment })
    });
    await load();
  }

  function statusText(value) {
    if (value === "in_review") return "In Prüfung";
    if (value === "approved") return "Freigegeben";
    if (value === "rejected") return "Abgelehnt";
    return "Entwurf";
  }

  function documentStatusBadge(value) {
    if (value === "approved" || value === "ready") return badge(statusText(value), "badge badge-status is-done");
    if (value === "in_review" || value === "needs_review") return badge(statusText(value), "badge badge-status is-progress");
    if (value === "rejected" || value === "error") return badge(statusText(value), "badge badge-status is-open");
    return badge(statusText(value), "badge badge-status is-open");
  }

  function recordMetaItem(label, value) {
    const item = document.createElement("span");
    const itemLabel = document.createElement("small");
    const itemValue = document.createElement("strong");
    itemLabel.textContent = label;
    itemValue.textContent = value || "-";
    item.append(itemLabel, itemValue);
    return item;
  }

  function manualRecordCard(manual, actions) {
    const card = document.createElement("article");
    card.className = "record-card document-record-card";
    card.dataset.searchText = [
      manual.title,
      manual.original_filename,
      manual.department,
      manual.machine && manual.machine.name,
      manual.analysis_status,
      manual.summary_status
    ].filter(Boolean).join(" ");

    const header = document.createElement("div");
    header.className = "record-card-header";
    const titleBlock = document.createElement("div");
    const title = document.createElement("h3");
    title.className = "record-card-title";
    title.textContent = manual.title || manual.original_filename || "Handbuch";
    const subtitle = document.createElement("p");
    subtitle.className = "record-card-subtitle";
    subtitle.textContent = manual.machine && manual.machine.name ? manual.machine.name : "Keine Maschine zugeordnet";
    titleBlock.append(title, subtitle);
    header.append(titleBlock, badge(manual.analysis_status || "nicht geprüft", "badge badge-status is-progress"));

    const meta = document.createElement("div");
    meta.className = "record-card-meta";
    meta.append(
      recordMetaItem("Bereich", manual.department || "-"),
      recordMetaItem("Analyse", manual.analysis_status || "-"),
      recordMetaItem("Zusammenfassung", manual.summary_status || "-")
    );
    actions.classList.remove("table-actions");
    actions.classList.add("record-card-actions");
    card.append(header, meta, actions);
    return card;
  }

  function documentRecordCard(documentItem, actions) {
    const card = document.createElement("article");
    card.className = "record-card document-record-card";
    card.dataset.searchText = [
      documentItem.title,
      documentItem.task_id,
      documentItem.department,
      documentItem.machine,
      statusText(documentItem.status)
    ].filter(Boolean).join(" ");

    const header = document.createElement("div");
    header.className = "record-card-header";
    const titleBlock = document.createElement("div");
    const title = document.createElement("h3");
    title.className = "record-card-title";
    title.textContent = documentItem.title || "Wartungsbericht";
    const subtitle = document.createElement("p");
    subtitle.className = "record-card-subtitle";
    subtitle.textContent = "Aufgabe #" + documentItem.task_id + " · " + (documentItem.machine || "Keine Maschine");
    titleBlock.append(title, subtitle);
    header.append(titleBlock, documentStatusBadge(documentItem.status));

    const meta = document.createElement("div");
    meta.className = "record-card-meta";
    meta.append(
      recordMetaItem("Bereich", documentItem.department || "-"),
      recordMetaItem("Version", documentItem.version ? "v" + documentItem.version : "-"),
      recordMetaItem("Erstellt", documentItem.created_at ? new Date(documentItem.created_at).toLocaleString("de-DE") : "-")
    );
    actions.classList.remove("table-actions");
    actions.classList.add("record-card-actions");
    card.append(header, meta, actions);
    return card;
  }

  async function loadManualMachines() {
    if (!manualMachineSelect) return;
    try {
      const machines = listData(await api("/api/v1/machines?limit=200"));
      machines.forEach((machine) => {
        const option = document.createElement("option");
        option.value = String(machine.id);
        option.textContent = machine.name;
        manualMachineSelect.appendChild(option);
      });
    } catch (error) {
      if (manualMessage) manualMessage.textContent = "Maschinen konnten nicht geladen werden.";
    }
  }

  async function loadManuals() {
    if (!manualList) return [];
    renderTableMessage(manualList, 6, "Handbücher werden geladen...");
    let manualPayload;
    try {
      manualPayload = await api("/api/v1/documents/manuals?limit=100");
    } catch (error) {
      renderTableMessage(manualList, 6, "Handbücher konnten nicht geladen werden.", true);
      throw error;
    }
    const manuals = listData(manualPayload);
    manualList.innerHTML = "";
    document.querySelectorAll("[data-manual-count]").forEach((element) => {
      element.textContent = paginationTotal(manualPayload, manuals) + " Handbücher";
    });
    if (!manuals.length) {
      renderTableMessage(manualList, 6, "Keine Handbücher vorhanden.");
      return manuals;
    }
    manuals.forEach((manual) => {
      const actions = document.createElement("div");
      actions.className = "table-actions";
      actions.appendChild(actionButton("Download", async () => {
        await downloadFile(manual.download_url, manual.original_filename);
      }, { successMessage: "Herunterladen wurde gestartet." }));
      actions.appendChild(actionButton("Analysieren", async () => {
        const result = await api("/api/v1/documents/manuals/" + manual.id + "/analyze", { method: "POST" });
        renderZusammenfassung(result.title, result.analysis_status, result.analysis);
        await loadManuals();
      }, { busyText: "Analysiert...", successMessage: "Handbuchanalyse aktualisiert." }));
      actions.appendChild(actionButton("Zusammenfassen", async () => {
        const result = await api("/api/v1/documents/manuals/" + manual.id + "/summarize", { method: "POST" });
        renderZusammenfassung(result.title, result.summary_status, result.summary);
        await loadManuals();
      }, { busyText: "Fasst zusammen...", successMessage: "Handbuch-Zusammenfassung aktualisiert." }));
      if (canWrite("documents")) {
        actions.appendChild(actionButton("Löschen", async () => {
          if (!window.confirm(manual.title + " wirklich löschen?")) return;
          await api("/api/v1/documents/manuals/" + manual.id, { method: "DELETE" });
          await loadManuals();
        }, { danger: true, busyText: "Löscht...", successMessage: "Handbuch gelöscht." }));
      }
      manualList.appendChild(manualRecordCard(manual, actions));
    });
    return manuals;
  }

  function documentSearchParams() {
    const params = new URLSearchParams();
    new FormData(form).forEach((value, key) => {
      if (value) params.set(key, value);
    });
    params.set("limit", "100");
    return params;
  }

  async function load(params) {
    const queryParams = params || documentSearchParams();
    renderTableMessage(list, 8, "Dokumente werden geladen...");
    const suffix = "?" + queryParams.toString();
    let documentPayload;
    try {
      documentPayload = await api("/api/v1/documents" + suffix);
    } catch (error) {
      renderTableMessage(list, 8, "Dokumente konnten nicht geladen werden.", true);
      throw error;
    }
    const documents = listData(documentPayload);
    list.innerHTML = "";
    document.querySelectorAll("[data-document-count]").forEach((element) => {
      element.textContent = paginationTotal(documentPayload, documents) + " Dokumente";
    });
    if (!documents.length) {
      renderTableMessage(list, 8, "Keine Dokumente gefunden.");
      return documents;
    }
    documents.forEach((documentItem) => {
      const actions = document.createElement("div");
      actions.className = "table-actions";
      actions.appendChild(actionButton("Prüfen", async () => {
        await reviewDocument(documentItem);
      }, { busyText: "Prüft...", successMessage: "Dokumentprüfung aktualisiert." }));
      actions.appendChild(actionButton("HTML", async () => {
        await downloadDocument(documentItem);
      }, { successMessage: "HTML-Herunterladen wurde gestartet." }));
      actions.appendChild(actionButton("PDF", async () => {
        await downloadDocumentPdf(documentItem);
      }, { successMessage: "PDF-Herunterladen wurde gestartet." }));
      actions.appendChild(actionButton("Zusammenfassung", async () => {
        await summarizeDocument(documentItem);
      }, { busyText: "Fasst zusammen...", successMessage: "Zusammenfassung aktualisiert." }));
      actions.appendChild(actionButton("Versionen", async () => {
        await showVersions(documentItem);
      }, { successMessage: "Versionen geladen." }));
      if (canWrite("documents")) {
        actions.appendChild(actionButton("Prüfung", async () => {
          await changeDocumentStatus(documentItem, "submit-review");
        }, { busyText: "Sendet...", successMessage: "Dokument wurde zur Prüfung eingereicht." }));
        actions.appendChild(actionButton("Freigeben", async () => {
          await changeDocumentStatus(documentItem, "approve");
        }, { busyText: "Gibt frei...", successMessage: "Dokument freigegeben." }));
        actions.appendChild(actionButton("Ablehnen", async () => {
          await changeDocumentStatus(documentItem, "reject");
        }, { danger: true, busyText: "Lehnt ab...", successMessage: "Dokument abgelehnt." }));
      }
      list.appendChild(documentRecordCard(documentItem, actions));
    });
    return documents;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const params = documentSearchParams();
    await runAction({
      action: async () => load(params),
      form,
      busyText: "Filtert...",
      errorMessage: "Dokumente konnten nicht geladen werden.",
      pendingMessage: "Dokumente werden geladen...",
      statusElement: documentMessage,
      successMessage: "Dokumentliste aktualisiert.",
      toast: false
    });
  });

  if (reset) {
    reset.addEventListener("click", async () => {
      form.reset();
      await runAction({
        action: async () => load(documentSearchParams()),
        button: reset,
        busyText: "Setzt zurück...",
        errorMessage: "Filter konnten nicht zurückgesetzt werden.",
        pendingMessage: "Filter werden zurückgesetzt...",
        statusElement: documentMessage,
        successMessage: "Filter zurückgesetzt."
      });
    });
  }

  if (uploadCheckFile) {
    uploadCheckFile.addEventListener("change", () => {
      if (!uploadCheckFile.files || !uploadCheckFile.files.length) {
        uploadCheckFile.removeAttribute("aria-invalid");
        setStatusMessage(uploadCheckMessage, "");
        return;
      }
      if (validateUploadCheckFile(uploadCheckFile)) {
        setStatusMessage(uploadCheckMessage, "Datei bereit: " + uploadCheckFile.files[0].name, false);
      }
    });
  }

  if (uploadCheckForm) {
    uploadCheckForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!validateUploadCheckFile(uploadCheckFile)) {
        if (uploadCheckFile) uploadCheckFile.focus();
        return;
      }
      const payload = new FormData(uploadCheckForm);
      await runAction({
        action: async () => {
          const review = await api("/api/v1/documents/check", {
            method: "POST",
            body: payload
          });
          renderDocumentReview(review);
          return review;
        },
        busyText: "Prüft...",
        errorMessage: "Dokument konnte nicht geprüft werden.",
        form: uploadCheckForm,
        pendingMessage: "Dokument wird geprüft...",
        statusElement: uploadCheckMessage,
        successMessage: "Dokument geprüft."
      });
    });
  }

  if (manualForm) {
    manualForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const payload = new FormData(manualForm);
      await runAction({
        action: async () => {
          await api("/api/v1/documents/manuals", {
            method: "POST",
            body: payload
          });
          manualForm.reset();
          await loadManuals();
        },
        busyText: "Lädt...",
        errorMessage: "Hochladen fehlgeschlagen.",
        form: manualForm,
        pendingMessage: "Handbuch wird hochgeladen...",
        statusElement: manualMessage,
        successMessage: "Handbuch hochgeladen."
      });
    });
  }

  try {
    await loadManualMachines();
    await loadManuals();
    const documents = await load();
    setStatusMessage(documentMessage, "Dokumentaktionen bereit.", false);
    const documentPreview = consumeAiActionPreview("documents");
    if (documentPreview && documentPreview.payload) {
      const documentItem = documents.find((item) => item.id === documentPreview.payload.document_id);
      if (documentItem) await reviewDocument(documentItem);
    }
  } catch (error) {
    renderTableMessage(list, 8, "Dokumente konnten nicht geladen werden.", true);
    setStatusMessage(documentMessage, error.message || "Dokumente konnten nicht geladen werden.", true);
    showInterfaceToast("Dokumente konnten nicht geladen werden.", "error");
  }
}

export { initDocuments };

registerWorkflowInitializers({
  initDocuments: initDocuments
});

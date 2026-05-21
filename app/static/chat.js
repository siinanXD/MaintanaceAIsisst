(function () {
  const widget = document.querySelector(".chat-widget");
  const toggle = document.querySelector(".chat-toggle");
  const panel = document.querySelector(".chat-panel");
  const close = document.querySelector(".chat-close");
  const form = document.querySelector("[data-chat-form]");
  const messages = document.querySelector("[data-chat-messages]");
  const suggestions = document.querySelector("[data-chat-suggestions]");
  const historyPanel = document.querySelector("[data-chat-history-panel]");
  const historySearch = document.querySelector("[data-chat-history-search]");
  const historyList = document.querySelector("[data-chat-history-list]");
  const historyCount = document.querySelector("[data-chat-history-count]");
  const chatInput = form ? form.querySelector("input") : null;
  let chatTemplateItems = [];
  let isTemplateLoading = false;
  let hasHydratedPanel = false;
  let isSending = false;
  let hasSubmittedMessage = false;
  let hasTypedInCurrentChat = false;
  let lastFocusedElement = null;
  const CHAT_OPEN_KEY = "maintenance_chat_open";
  const CHAT_SESSION_KEY = "maintenance_ai_chat_session_id";
  let fallbackChatSessionId = "";
  let warnedChatSessionStorage = false;

  if (!widget || !toggle || !panel || !form || !messages) {
    return;
  }

  function isOpen() {
    return widget.classList.contains("is-open");
  }

  /**
   * Return a compact random identifier for one browser chat session.
   */
  function buildChatSessionId() {
    if (window.crypto && typeof window.crypto.randomUUID === "function") {
      return window.crypto.randomUUID();
    }
    return "chat-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 10);
  }

  /**
   * Warn once when sessionStorage is unavailable and fall back in memory.
   */
  function warnChatSessionStorage(error) {
    if (warnedChatSessionStorage) return;
    warnedChatSessionStorage = true;
    if (window.console && typeof window.console.warn === "function") {
      window.console.warn("Chat session storage is unavailable; using an in-memory session id.", error);
    }
  }

  /**
   * Return the current short-term chat session id without replaying history.
   */
  function chatSessionId() {
    try {
      const existing = window.sessionStorage.getItem(CHAT_SESSION_KEY);
      if (existing) {
        fallbackChatSessionId = existing;
        return existing;
      }
      const next = buildChatSessionId();
      window.sessionStorage.setItem(CHAT_SESSION_KEY, next);
      fallbackChatSessionId = next;
      return next;
    } catch (error) {
      warnChatSessionStorage(error);
      if (!fallbackChatSessionId) {
        fallbackChatSessionId = buildChatSessionId();
      }
      return fallbackChatSessionId;
    }
  }

  /**
   * Start a new short-term chat session for the next request.
   */
  function resetChatSession() {
    const next = buildChatSessionId();
    fallbackChatSessionId = next;
    try {
      window.sessionStorage.setItem(CHAT_SESSION_KEY, next);
    } catch (error) {
      warnChatSessionStorage(error);
    }
  }

  function hydrateChatPanel() {
    if (!hasHydratedPanel) {
      hasHydratedPanel = true;
      renderSuggestions();
    }
    loadChatHistory();
  }

  function focusChatInput() {
    if (chatInput) chatInput.focus();
  }

  function focusableChatElements() {
    return Array.from(panel.querySelectorAll(
      "a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])"
    )).filter((element) => element.offsetParent !== null || element === document.activeElement);
  }

  function restorePreviousFocus() {
    if (lastFocusedElement && typeof lastFocusedElement.focus === "function" && document.contains(lastFocusedElement)) {
      lastFocusedElement.focus();
      return;
    }
    toggle.focus();
  }

  function setOpen(open) {
    const wasOpen = isOpen();
    if (open && !wasOpen) {
      lastFocusedElement = document.activeElement;
    }
    widget.classList.toggle("is-open", open);
    toggle.setAttribute("aria-expanded", String(open));
    panel.setAttribute("aria-hidden", String(!open));
    panel.setAttribute("aria-modal", String(open));
    window.localStorage.setItem(CHAT_OPEN_KEY, String(open));
    if (open) {
      panel.focus({ preventScroll: true });
      focusChatInput();
      hydrateChatPanel();
      return;
    }
    if (wasOpen) {
      restorePreviousFocus();
    }
  }

  function openAIErrorLabel(diagnostics) {
    const error = diagnostics && diagnostics.error;
    if (error === "model_not_allowed" || error === "model_not_found") {
      return "Ausweichantwort - OpenAI-Modell nicht freigeschaltet";
    }
    if (error === "rate_limit") {
      return "Ausweichantwort - OpenAI-Rate-Limit erreicht";
    }
    if (error === "authentication_error") {
      return "Ausweichantwort - OpenAI-Key abgelehnt";
    }
    if (error === "timeout") {
      return "Ausweichantwort - OpenAI-Timeout";
    }
    if (error === "connection_error") {
      return "Ausweichantwort - OpenAI-Verbindung fehlgeschlagen";
    }
    if (error === "permission_denied") {
      return "Ausweichantwort - OpenAI-Zugriff verweigert";
    }
    return "Ausweichantwort - OpenAI nicht erreichbar";
  }

  function statusText(diagnostics) {
    const status = diagnostics && diagnostics.status;
    const provider = (diagnostics && diagnostics.provider) || "OpenAI";
    const model = diagnostics && diagnostics.model;
    const sourceCount = diagnostics && diagnostics.source_count;
    const sourceLabel = sourceCount ? " - " + sourceCount + " Quellen" : "";
    if (status === "openai_used" && sourceCount) {
      return provider + (model ? " - " + model : "") + sourceLabel;
    }
    if (status === "api_key_missing" && sourceCount) {
      return "Ausweichantwort - AI API-Key fehlt" + sourceLabel;
    }
    if (status === "openai_error" && sourceCount) {
      return openAIErrorLabel(diagnostics) + sourceLabel;
    }

    if (status === "openai_used") {
      return provider + (model ? " - " + model : "");
    }
    if (status === "local_answer") {
      return "Lokale Antwort" + sourceLabel;
    }
    if (status === "api_key_missing") {
      return "Ausweichantwort - AI API-Key fehlt";
    }
    if (status === "openai_error") {
      return openAIErrorLabel(diagnostics);
    }
    if (status === "permission_denied") {
      return "Berechtigung fehlt" + sourceLabel;
    }
    if (diagnostics && diagnostics.fallback_used) {
      return "Ausweichantwort" + sourceLabel;
    }
    if (sourceCount) {
      return sourceCount + " Quellen";
    }
    return "";
  }

  /**
   * Return a number when the value can be parsed.
   */
  function numericValue(value, fallback) {
    const number = Number(value);
    return Number.isFinite(number) ? number : fallback;
  }

  /**
   * Return a short, bounded display string.
   */
  function boundedText(value, fallback, maxLength) {
    const text = String(value || fallback || "").trim();
    if (!maxLength || text.length <= maxLength) return text;
    return text.slice(0, maxLength - 1).trim() + "...";
  }

  /**
   * Remove all children from an element.
   */
  function clearElement(element) {
    while (element.firstChild) {
      element.removeChild(element.firstChild);
    }
  }

  /**
   * Return a compact score label for source and confidence values.
   */
  function scoreLabel(value) {
    if (value === undefined || value === null || value === "") return "";
    const score = numericValue(value, null);
    if (score === null) return "";
    return Math.round(score > 0 && score <= 1 ? score * 100 : score) + "%";
  }

  /**
   * Return the most useful confidence payload available in diagnostics.
   */
  function confidencePayload(diagnostics) {
    const source = diagnostics || {};
    const rawSicherheit = source.confidence;
    const confidence = rawSicherheit && typeof rawSicherheit === "object" ? rawSicherheit : {};
    const score = rawSicherheit !== undefined && typeof rawSicherheit !== "object"
      ? rawSicherheit
      : confidence.score !== undefined ? confidence.score : source.confidence_score;
    const level = confidence.level || source.confidence_level || "";
    if ((score === undefined || score === null || score === "") && !level) return null;
    const payload = {
      score: score === undefined || score === null || score === "" ? null : numericValue(score, null),
      level: String(level || "").toLowerCase(),
      warning: confidence.warning || "",
      reasons: Array.isArray(confidence.reasons) ? confidence.reasons : [],
      factors: confidence.factors || {},
      method: confidence.method || ""
    };
    payload.level = normalizedSicherheitLevel(payload);
    return payload;
  }

  /**
   * Return a normalized high, medium, or low confidence level.
   */
  function normalizedSicherheitLevel(confidence) {
    const level = String((confidence && confidence.level) || "").toLowerCase();
    if (level === "high" || level === "medium" || level === "low") return level;
    const score = confidence && confidence.score !== undefined && confidence.score !== null
      ? numericValue(confidence.score, null)
      : null;
    if (score === null) return "";
    const percent = score > 0 && score <= 1 ? score * 100 : score;
    if (percent >= 75) return "high";
    if (percent >= 45) return "medium";
    return "low";
  }

  /**
   * Return a user-facing confidence label.
   */
  function confidenceLevelLabel(level) {
    const normalized = normalizedSicherheitLevel({ level });
    const labels = {
      high: "Hohe Sicherheit",
      medium: "Mittlere Sicherheit",
      low: "Niedrige Sicherheit"
    };
    return labels[normalized] || "Sicherheit";
  }

  /**
   * Return a short trust-oriented confidence explanation.
   */
  function confidenceTrustCopy(level) {
    const normalized = normalizedSicherheitLevel({ level });
    const labels = {
      high: "Gut belegt",
      medium: "Plausibel, prüfen",
      low: "Vorsichtig nutzen"
    };
    return labels[normalized] || "Einordnung prüfen";
  }

  /**
   * Return a compact confidence score percentage.
   */
  function confidenceScorePercent(confidence) {
    if (!confidence || confidence.score === undefined || confidence.score === null || confidence.score === "") {
      return null;
    }
    const score = numericValue(confidence.score, null);
    if (score === null) return null;
    return Math.round(score > 0 && score <= 1 ? score * 100 : score);
  }

  /**
   * Return CSS tone class for confidence and risk indicators.
   */
  function confidenceTone(level) {
    const normalized = normalizedSicherheitLevel({ level });
    if (normalized === "high") return "is-positive";
    if (normalized === "low") return "is-risk";
    return "is-warning";
  }

  /**
   * Return a compact visual high, medium, low confidence meter.
   */
  function confidenceMeter(confidence) {
    const level = normalizedSicherheitLevel(confidence);
    const percent = confidenceScorePercent(confidence);
    const meter = document.createElement("div");
    const scale = document.createElement("div");
    const labels = {
      low: "Niedrig",
      medium: "Mittel",
      high: "Hoch"
    };
    meter.className = "chat-confidence-meter " + confidenceTone(level);
    meter.setAttribute(
      "aria-label",
      [
        confidenceLevelLabel(level),
        percent === null ? "" : percent + " Prozent",
        confidenceTrustCopy(level)
      ].filter(Boolean).join(", ")
    );
    scale.className = "chat-confidence-scale";
    ["low", "medium", "high"].forEach((segmentLevel) => {
      const segment = document.createElement("span");
      segment.className = "chat-confidence-segment is-" + segmentLevel
        + (segmentLevel === level ? " is-active" : "");
      segment.textContent = labels[segmentLevel];
      scale.appendChild(segment);
    });
    meter.appendChild(scale);
    return meter;
  }

  /**
   * Append a compact badge to a target.
   */
  function appendAnswerBadge(target, label, tone) {
    if (!label) return null;
    const badge = document.createElement("span");
    badge.className = "chat-answer-badge " + (tone || "is-neutral");
    badge.textContent = label;
    target.appendChild(badge);
    return badge;
  }

  /**
   * Return a readable source type label.
   */
  function sourceTypeLabel(source) {
    const type = String(
      (source && (source.module || source.source_type || source.type || source.document_type)) || ""
    );
    const labels = {
      error: "Fehlerkatalog",
      error_entry: "Fehlerkatalog",
      generated_document: "Dokument",
      inventory: "Inventar",
      knowledge: "Wissen",
      machine: "Maschine",
      machine_manual: "Maschinenhandbuch",
      manual_training: "Training",
      task: "Aufgabe",
      upload: "Hochladen"
    };
    return labels[type] || boundedText(type, "Quelle", 40);
  }

  /**
   * Return a stable source category for visual badges.
   */
  function sourceKind(source) {
    const kind = String((source && source.source_kind) || "").toLowerCase();
    const type = String((source && source.type) || "").toLowerCase();
    const knowledgeType = String(
      (source && (source.knowledge_source_type || source.source_type || source.document_type)) || ""
    ).toLowerCase();
    if (kind.includes("sql") || kind === "structured") return "sql";
    if (type === "manual_training" || knowledgeType === "manual_training") return "manual_training";
    if (type === "document" || knowledgeType === "generated_document") return "generated_document";
    if (kind === "rag" || type === "knowledge") return "rag";
    return "sql";
  }

  /**
   * Return a short label for the source retrieval category.
   */
  function sourceKindLabel(source) {
    const labels = {
      generated_document: "Generated Document",
      manual_training: "Manual Training",
      rag: "RAG",
      sql: "SQL"
    };
    return labels[sourceKind(source)] || "Quelle";
  }

  /**
   * Return the CSS class for a source retrieval category.
   */
  function sourceKindClass(source) {
    return "is-" + sourceKind(source).replaceAll("_", "-");
  }

  /**
   * Return display-safe machine metadata for one source.
   */
  function sourceMachineLabel(source) {
    const explainability = sourceExplainability(source);
    const machine = source && (source.machine || explainability.machine);
    return boundedText(machine, "", 72);
  }

  /**
   * Return display-safe department metadata for one source.
   */
  function sourceDepartmentLabel(source) {
    const explainability = sourceExplainability(source);
    const department = source && (source.department || explainability.department);
    return boundedText(department, "", 72);
  }

  /**
   * Return a compact relevance label for one source.
   */
  function sourceRelevanceLabel(source) {
    if (!source) return "";
    return scoreLabel(
      source.relevance !== undefined
        ? source.relevance
        : source.normalized_score !== undefined ? source.normalized_score : source.score
    );
  }

  /**
   * Return a compact quality label.
   */
  function qualityStatusLabel(status) {
    const labels = {
      admin_approved: "freigegeben",
      ai_suggested: "AI-Vorschlag",
      draft: "Entwurf",
      low_quality: "niedrige Qualität",
      duplicate: "Duplikat",
      outdated: "veraltet",
      rejected: "abgelehnt",
      technician_confirmed: "technisch bestätigt"
    };
    return labels[status] || boundedText(status, "", 40);
  }

  /**
   * Return explainability metadata for a source.
   */
  function sourceExplainability(source) {
    if (!source || typeof source !== "object") return {};
    return source.explainability && typeof source.explainability === "object"
      ? source.explainability
      : {};
  }

  /**
   * Return machine-match reason labels for a source.
   */
  function machineReasonLabels(reasons) {
    const labels = {
      same_machine: "gleiche Maschine",
      same_machine_series: "gleiche Maschinenserie",
      same_error_code: "gleicher Fehlercode",
      similar_error_code: "ähnlicher Fehlercode"
    };
    return (Array.isArray(reasons) ? reasons : [])
      .map((reason) => labels[reason] || boundedText(reason, "", 60))
      .filter(Boolean);
  }

  /**
   * Return machine-context labels derived from one source.
   */
  function sourceMachineReasons(source) {
    const explainability = sourceExplainability(source);
    const directReasons = source && source.machine_match_reasons;
    const reasons = directReasons || explainability.machine_match_reasons || [];
    return machineReasonLabels(reasons);
  }

  /**
   * Return a user-facing quality reason for one source.
   */
  function sourceQualityReason(source) {
    const status = (source && source.quality_status) || sourceExplainability(source).quality_status;
    if (status === "admin_approved") return "freigegebene Quelle";
    if (status === "technician_confirmed") return "technisch bestätigte Quelle";
    const label = qualityStatusLabel(status);
    return label ? "Qualität: " + label : "";
  }

  /**
   * Return short source reason labels for answer trust UI.
   */
  function sourceReasonLabels(source) {
    if (!source) return [];
    const explainability = sourceExplainability(source);
    const labels = [];
    const machineReasons = sourceMachineReasons(source);
    const directReason = boundedText(source.reason, "", 64);
    const section = source.section_title || source.source_section;
    if (machineReasons.length || numericValue(explainability.machine_match, 0) > 0) {
      labels.push("Maschinenbezug");
    }
    if (numericValue(explainability.semantic_similarity, 0) > 0) {
      labels.push("semantisch passend");
    }
    if (explainability.error_code_alignment === "exact_error_code") {
      labels.push("Fehlercode exakt");
    } else if (explainability.error_code_alignment === "similar_error_code") {
      labels.push("aehnlicher Fehlercode");
    } else if (explainability.error_code_alignment === "conflicting_error_code") {
      labels.push("abweichender Fehlercode");
    }
    if (
      numericValue(explainability.lexical_score, 0) > 0
      || numericValue(explainability.lexical_similarity, 0) > 0
    ) {
      labels.push("Begriffstreffer");
    }
    const qualityReason = sourceQualityReason(source);
    if (qualityReason) labels.push(qualityReason);
    if (directReason) labels.push(directReason);
    if (section) labels.push("Abschnitt: " + boundedText(section, "", 42));
    return Array.from(new Set(labels.filter(Boolean))).slice(0, 4);
  }

  /**
   * Return a compact source title for trust explanations.
   */
  function sourceTrustTitle(source) {
    return boundedText(source && source.title, "sichtbare Quelle", 74);
  }

  /**
   * Return concise answer-basis cards from diagnostics and sources.
   */
  function answerBasisItems(diagnostics, sources) {
    const safeQuelles = Array.isArray(sources) ? sources : [];
    const topQuelle = safeQuelles[0];
    const machineQuelle = safeQuelles.find((source) => (
      sourceMachineReasons(source).length || isMachineOrErrorQuelle(source)
    ));
    const confidence = confidencePayload(diagnostics);
    const items = [];
    if (topQuelle) {
      items.push({
        tone: "is-source",
        title: "Warum diese Quelle?",
        value: sourceTrustTitle(topQuelle),
        detail: sourceReasonLabels(topQuelle).join(" - ") || "höchster sichtbarer Quellenabruf-Treffer"
      });
    }
    if (machineQuelle) {
      const reasons = sourceMachineReasons(machineQuelle);
      items.push({
        tone: "is-machine",
        title: "Warum diese Maschine?",
        value: sourceTrustTitle(machineQuelle),
        detail: reasons.join(" - ") || "Quelle enthält passenden Maschinen- oder Fehlerkontext"
      });
    }
    if (topQuelle || confidence) {
      const confidenceReason = confidence && confidence.reasons.length
        ? boundedText(confidence.reasons[0], "", 120)
        : "";
      items.push({
        tone: "is-solution",
        title: "Warum diese Lösung?",
        value: topQuelle ? "Aus sichtbarem Wartungskontext" : confidenceLevelLabel(confidence.level),
        detail: confidenceReason || "Antwort basiert auf den bestbewerteten erlaubten Quellen."
      });
    }
    return items.filter((item, index, allItems) => (
      index === allItems.findIndex((candidate) => candidate.title === item.title)
    )).slice(0, 3);
  }

  /**
   * Return whether a source is a likely machine or fault hint.
   */
  function isMachineOrErrorQuelle(source) {
    const type = String(
      (source && (source.module || source.source_type || source.type || source.document_type)) || ""
    );
    return (
      type === "machine"
      || type === "error"
      || type === "error_entry"
      || sourceMachineReasons(source).length > 0
    );
  }

  /**
   * Return the retrieval explainability payload from diagnostics.
   */
  function retrievalExplainability(diagnostics) {
    const explainability = diagnostics && diagnostics.retrieval_explainability;
    return explainability && typeof explainability === "object" ? explainability : {};
  }

  /**
   * Return sanitized safety payloads from diagnostics.
   */
  function safetyPayloads(diagnostics) {
    const explainability = retrievalExplainability(diagnostics);
    return [
      diagnostics && diagnostics.safety,
      diagnostics && diagnostics.post_generation_safety,
      explainability.safety,
      explainability.post_generation_safety
    ].filter((item) => item && typeof item === "object");
  }

  /**
   * Return user-facing safety warnings.
   */
  function safetyWarnings(diagnostics) {
    const warnings = [];
    safetyPayloads(diagnostics).forEach((payload) => {
      if (!payload.safety_relevant && !payload.modified) return;
      const risk = boundedText(payload.risk_level, "sicherheitsrelevant", 60);
      warnings.push("Sicherheitsrelevant: " + risk);
      (payload.warnings || []).slice(0, 3).forEach((warning) => {
        warnings.push(boundedText(warning, "", 160));
      });
      if (payload.modified) {
        warnings.push("Antwort wurde durch die finale Sicherheit-Prüfung entschärft.");
      }
    });
    return Array.from(new Set(warnings.filter(Boolean))).slice(0, 5);
  }

  /**
   * Return source conflict metadata from diagnostics.
   */
  function conflictPayload(diagnostics) {
    const explainability = retrievalExplainability(diagnostics);
    const conflicts = (diagnostics && diagnostics.source_conflicts) || explainability.conflicts || {};
    return conflicts && typeof conflicts === "object" ? conflicts : {};
  }

  /**
   * Return user-facing conflict warnings.
   */
  function conflictWarnings(diagnostics) {
    const conflicts = conflictPayload(diagnostics);
    if (!conflicts.has_conflicts && !conflicts.count) return [];
    const warnings = [boundedText(conflicts.summary, "Quellenkonflikte erkannt.", 180)];
    (conflicts.conflicts || []).slice(0, 3).forEach((conflict) => {
      warnings.push(boundedText(conflict.reason, "Widersprüchliche Quellenlage.", 180));
    });
    return Array.from(new Set(warnings.filter(Boolean))).slice(0, 4);
  }

  /**
   * Return a compact query type label.
   */
  function queryTypeLabel(diagnostics) {
    const explainability = retrievalExplainability(diagnostics);
    const understanding = (diagnostics && diagnostics.query_understanding)
      || explainability.query_understanding
      || {};
    return boundedText(understanding.query_type, "", 60);
  }

  /**
   * Return a user-facing answer mode label.
   */
  function answerModeLabel(diagnostics) {
    const mode = String((diagnostics && diagnostics.answer_mode) || "");
    const labels = {
      document_search: "Dokumentensuche",
      error_analysis: "Fehleranalyse",
      machine_knowledge: "Maschinenwissen",
      maintenance_assistant: "Maintenance Antwort",
      similar_errors: "Aehnliche Fehler",
      summary: "Zusammenfassung",
      task_help: "Aufgabenhilfe",
      task_prioritization: "Priorisierung"
    };
    return labels[mode] || "AI Antwort";
  }

  /**
   * Return visible quality warnings from diagnostics.
   */
  function qualityWarnings(diagnostics) {
    const direct = diagnostics && diagnostics.quality_warnings;
    const warnings = Array.isArray(direct) ? direct : [];
    return warnings.map((warning) => {
      if (typeof warning === "string") {
        return { severity: "warning", message: warning };
      }
      return {
        severity: warning.severity || "warning",
        type: warning.type || "",
        message: warning.message || ""
      };
    }).filter((warning) => warning.message).slice(0, 4);
  }

  /**
   * Return retrieval duration from diagnostics.
   */
  function retrievalDuration(diagnostics) {
    const explainability = retrievalExplainability(diagnostics);
    const duration = diagnostics && diagnostics.retrieval_duration_ms !== undefined
      ? diagnostics.retrieval_duration_ms
      : explainability.retrieval_duration_ms;
    const number = numericValue(duration, null);
    return number === null ? "" : Math.round(number) + " ms";
  }

  /**
   * Render the answer-card header with status and trust badges.
   */
  function renderAnswerHeader(bubble, diagnostics, sources) {
    let header = bubble.querySelector(".chat-answer-header");
    if (!header) {
      header = document.createElement("div");
      header.className = "chat-answer-header";
      bubble.insertBefore(header, bubble.firstChild);
    }
    clearElement(header);
    const title = document.createElement("div");
    title.className = "chat-answer-title";
    const label = document.createElement("span");
    label.textContent = answerModeLabel(diagnostics);
    const status = document.createElement("small");
    status.textContent = statusText(diagnostics) || "lokale Auswertung";
    title.append(label, status);

    const badges = document.createElement("div");
    badges.className = "chat-answer-badges";
    const confidence = confidencePayload(diagnostics);
    if (confidence) {
      const confidenceLabel = [
        confidenceLevelLabel(confidence.level),
        scoreLabel(confidence.score)
      ].filter(Boolean).join(" - ");
      appendAnswerBadge(
        badges,
        confidenceLabel || confidenceLevelLabel(confidence.level),
        confidenceTone(confidence.level)
      );
    }
    if (sources && sources.length) {
      appendAnswerBadge(badges, sources.length + " Quellen", "is-info");
    }
    if (safetyWarnings(diagnostics).length) {
      appendAnswerBadge(badges, "Sicherheit", "is-risk");
    }
    if (conflictWarnings(diagnostics).length) {
      appendAnswerBadge(badges, "Konflikt", "is-warning");
    }
    if (qualityWarnings(diagnostics).some((warning) => warning.type === "empty_retrieval")) {
      appendAnswerBadge(badges, "Keine Quelle", "is-warning");
    }
    if (qualityWarnings(diagnostics).some((warning) => warning.type === "hallucination_risk")) {
      appendAnswerBadge(badges, "Halluzination blockiert", "is-risk");
    }
    header.append(title, badges);
  }

  /**
   * Remove previously rendered answer-card evidence sections.
   */
  function clearAnswerEvidence(bubble) {
    bubble.querySelectorAll(
      ".chat-answer-alerts, .chat-answer-insights, .chat-answer-basis, .chat-sources, .chat-context-hints, .chat-explainability"
    ).forEach((element) => element.remove());
  }

  /**
   * Render compact trust metrics below the answer.
   */
  function renderAnswerInsights(bubble, diagnostics, sources) {
    const confidence = confidencePayload(diagnostics);
    const explainability = retrievalExplainability(diagnostics);
    const items = [];
    if (confidence) {
      items.push({
        label: "Antwortsicherheit",
        value: confidenceLevelLabel(confidence.level),
        meta: [
          scoreLabel(confidence.score),
          confidenceTrustCopy(confidence.level)
        ].filter(Boolean).join(" - "),
        tone: confidenceTone(confidence.level),
        confidence
      });
    }
    items.push({
      label: "Quellen",
      value: String((sources || []).length),
      meta: (explainability.explained_source_count || 0) + " erklärt",
      tone: (sources || []).length ? "is-info" : "is-warning"
    });
    if (explainability.machine_match_count || (sources || []).some(isMachineOrErrorQuelle)) {
      items.push({
        label: "Maschinenkontext",
        value: String(explainability.machine_match_count || 1),
        meta: "passende Signale",
        tone: "is-positive"
      });
    }
    if (retrievalDuration(diagnostics)) {
      items.push({
        label: "Quellensuche",
        value: retrievalDuration(diagnostics),
        meta: queryTypeLabel(diagnostics) || "Query",
        tone: "is-neutral"
      });
    }
    if (qualityWarnings(diagnostics).length) {
      items.push({
        label: "Qualitätskontrolle",
        value: String(qualityWarnings(diagnostics).length),
        meta: "Warnhinweise",
        tone: qualityWarnings(diagnostics).some((warning) => warning.severity === "risk")
          ? "is-risk"
          : "is-warning"
      });
    }
    if (!items.length) return;

    const grid = document.createElement("div");
    grid.className = "chat-answer-insights";
    items.slice(0, 4).forEach((item) => {
      const card = document.createElement("div");
      card.className = "chat-answer-insight " + item.tone;
      const label = document.createElement("span");
      const value = document.createElement("strong");
      const meta = document.createElement("small");
      if (item.confidence) {
        card.classList.add("chat-confidence-card");
      }
      label.textContent = item.label;
      value.textContent = item.value;
      meta.textContent = item.meta;
      card.append(label, value, meta);
      if (item.confidence) {
        card.appendChild(confidenceMeter(item.confidence));
      }
      grid.appendChild(card);
    });
    bubble.appendChild(grid);
  }

  /**
   * Render safety and conflict warnings.
   */
  function renderAnswerAlerts(bubble, diagnostics) {
    const safetyMessages = safetyWarnings(diagnostics);
    const conflictMessages = conflictWarnings(diagnostics);
    const qualityMessages = qualityWarnings(diagnostics);
    const alerts = [];
    if (safetyMessages.length) {
      alerts.push({
        title: "Sicherheit-Hinweis",
        message: boundedText(safetyMessages.join(" "), "", 280),
        tone: "is-risk"
      });
    }
    if (conflictMessages.length) {
      alerts.push({
        title: "Widerspruch in Quellen",
        message: boundedText(conflictMessages.join(" "), "", 280),
        tone: "is-warning"
      });
    }
    qualityMessages.forEach((warning) => {
      alerts.push({
        title: warning.type === "empty_retrieval" ? "Keine Quellen" : "Qualitätskontrolle",
        message: boundedText(warning.message, "", 240),
        tone: warning.severity === "risk" ? "is-risk" : "is-warning"
      });
    });
    if (!alerts.length) return;
    const wrapper = document.createElement("div");
    wrapper.className = "chat-answer-alerts";
    alerts.slice(0, 4).forEach((alert) => {
      const item = document.createElement("div");
      const title = document.createElement("span");
      const message = document.createElement("strong");
      item.className = "chat-answer-alert " + alert.tone;
      item.setAttribute("role", alert.tone === "is-risk" ? "alert" : "status");
      title.className = "chat-answer-alert-title";
      message.className = "chat-answer-alert-message";
      title.textContent = alert.title;
      message.textContent = alert.message;
      item.append(title, message);
      wrapper.appendChild(item);
    });
    bubble.appendChild(wrapper);
  }

  /**
   * Render short explanations for source, machine, and solution choice.
   */
  function renderAnswerBasis(bubble, diagnostics, sources) {
    const items = answerBasisItems(diagnostics, sources);
    if (!items.length) return;
    const section = document.createElement("section");
    const header = document.createElement("div");
    const title = document.createElement("strong");
    const meta = document.createElement("span");
    const list = document.createElement("div");
    section.className = "chat-answer-basis chat-answer-section";
    section.setAttribute("aria-label", "Begründung der AI Antwort");
    header.className = "chat-answer-section-title";
    title.textContent = "Worauf basiert die Antwort?";
    meta.textContent = items.length + " Hinweise";
    header.append(title, meta);
    list.className = "chat-answer-basis-list";
    items.forEach((item) => {
      const card = document.createElement("article");
      const cardTitle = document.createElement("span");
      const value = document.createElement("strong");
      const detail = document.createElement("small");
      card.className = "chat-answer-basis-card " + item.tone;
      cardTitle.textContent = item.title;
      value.textContent = item.value;
      detail.textContent = item.detail;
      card.append(cardTitle, value, detail);
      list.appendChild(card);
    });
    section.append(header, list);
    bubble.appendChild(section);
  }

  function appendInlineText(parent, text) {
    const pattern = /\*\*(.+?)\*\*/g;
    let lastIndex = 0;
    let match = pattern.exec(text);
    while (match) {
      if (match.index > lastIndex) {
        parent.appendChild(document.createTextNode(text.slice(lastIndex, match.index)));
      }
      const strong = document.createElement("strong");
      strong.textContent = match[1];
      parent.appendChild(strong);
      lastIndex = pattern.lastIndex;
      match = pattern.exec(text);
    }
    if (lastIndex < text.length) {
      parent.appendChild(document.createTextNode(text.slice(lastIndex)));
    }
  }

  function renderFormattedText(container, text) {
    container.innerHTML = "";
    const lines = String(text || "").split(/\r?\n/);
    let list = null;
    let inCodeBlock = false;
    let pre = null;

    lines.forEach((rawLine) => {
      const line = rawLine.trim();

      if (inCodeBlock) {
        if (line === "```") {
          container.appendChild(pre);
          pre = null;
          inCodeBlock = false;
        } else {
          pre.querySelector("code").textContent += rawLine + "\n";
        }
        return;
      }

      if (!line) {
        list = null;
        return;
      }

      if (line.startsWith("```")) {
        list = null;
        pre = document.createElement("pre");
        pre.className = "chat-code-block";
        const code = document.createElement("code");
        pre.appendChild(code);
        inCodeBlock = true;
        return;
      }

      if (line.startsWith("## ")) {
        list = null;
        const title = document.createElement("div");
        title.className = "chat-message-title";
        title.textContent = line.slice(3).trim();
        container.appendChild(title);
        return;
      }

      if (line.startsWith("- ")) {
        if (!list) {
          list = document.createElement("ul");
          list.className = "chat-message-list";
          container.appendChild(list);
        }
        const item = document.createElement("li");
        appendInlineText(item, line.slice(2).trim());
        list.appendChild(item);
        return;
      }

      list = null;
      const paragraph = document.createElement("p");
      paragraph.className = "chat-message-paragraph";
      appendInlineText(paragraph, line);
      container.appendChild(paragraph);
    });

    if (inCodeBlock && pre) {
      container.appendChild(pre);
    }
  }

  function appendMessage(text, type, diagnostics) {
    const bubble = document.createElement("div");
    bubble.className = "chat-message " + (type === "user" ? "is-user" : "is-assistant");
    bubble.setAttribute("role", "article");
    if (type !== "user") {
      bubble.classList.add("chat-answer-card");
      renderAnswerHeader(bubble, diagnostics || {}, []);
    }

    const body = document.createElement("div");
    body.className = "chat-message-text";
    if (type === "user") {
      body.textContent = text;
    } else {
      renderFormattedText(body, text);
    }
    bubble.appendChild(body);

    messages.appendChild(bubble);
    messages.scrollTop = messages.scrollHeight;
    return bubble;
  }

  /**
   * Render a deterministic loading state that mirrors the retrieval pipeline.
   */
  function renderLoadingState(bubble) {
    const body = bubble.querySelector(".chat-message-text");
    if (!body) return;
    clearElement(body);
    const wrapper = document.createElement("div");
    const title = document.createElement("strong");
    const steps = document.createElement("div");
    wrapper.className = "chat-loading-state";
    title.textContent = "AI prüft die freigegebenen Daten";
    steps.className = "chat-loading-steps";
    ["Query verstehen", "Quellen abrufen", "Antwort absichern"].forEach((step) => {
      const item = document.createElement("span");
      item.textContent = step;
      steps.appendChild(item);
    });
    wrapper.append(title, steps);
    body.appendChild(wrapper);
  }

  /**
   * Return a source preview label.
   */
  function sourcePreviewMeta(source) {
    const parts = [];
    const relevance = sourceRelevanceLabel(source);
    const machine = sourceMachineLabel(source);
    const department = sourceDepartmentLabel(source);
    const quality = qualityStatusLabel(
      (source && source.quality_status) || sourceExplainability(source).quality_status
    );
    const section = source && (source.section_title || source.source_section);
    const chunk = source && source.chunk_id;
    const semantic = sourceExplainability(source).semantic_similarity;
    if (relevance) parts.push("Relevanz " + relevance);
    if (machine) parts.push("Maschine " + machine);
    if (department) parts.push("Department " + department);
    if (semantic) parts.push("Similarity " + scoreLabel(semantic));
    if (chunk !== undefined && chunk !== null && chunk !== "") parts.push("Textabschnitt " + chunk);
    if (quality) parts.push(quality);
    if (section) parts.push(boundedText(section, "", 48));
    return parts.join(" - ");
  }

  /**
   * Create a compact source preview chip.
   */
  function sourcePreviewChip(source) {
    const item = document.createElement(source && source.url ? "a" : "span");
    const header = document.createElement("div");
    const badges = document.createElement("div");
    const badge = document.createElement("span");
    const title = document.createElement("strong");
    const type = document.createElement("small");
    const facts = document.createElement("dl");
    const meta = document.createElement("small");
    const reason = document.createElement("small");
    item.className = "chat-source-chip " + sourceKindClass(source);
    if (source && source.url) item.href = source.url;
    header.className = "chat-source-chip-header";
    badges.className = "chat-source-badges";
    badge.className = "chat-source-kind " + sourceKindClass(source);
    badge.textContent = sourceKindLabel(source);
    title.textContent = boundedText(source && source.title, "Wissensquelle", 72);
    type.textContent = sourceTypeLabel(source) + ((source && source.id) ? " #" + source.id : "");
    facts.className = "chat-source-facts";
    [
      ["Quelle-Type", sourceTypeLabel(source)],
      ["Maschine", sourceMachineLabel(source) || "-"],
      ["Relevanz", sourceRelevanceLabel(source) || "-"],
      ["Department", sourceDepartmentLabel(source) || "-"]
    ].forEach(([labelText, valueText]) => {
      const term = document.createElement("dt");
      const description = document.createElement("dd");
      term.textContent = labelText;
      description.textContent = valueText;
      facts.append(term, description);
    });
    meta.textContent = sourcePreviewMeta(source);
    reason.className = "chat-source-reason";
    reason.textContent = sourceReasonLabels(source).slice(0, 3).join(" - ");
    item.title = boundedText((source && source.reason) || meta.textContent, "", 180);
    badges.appendChild(badge);
    header.append(title, badges);
    item.append(header, type, facts);
    if (meta.textContent) item.appendChild(meta);
    if (reason.textContent) item.appendChild(reason);
    return item;
  }

  /**
   * Render source chips below an assistant answer.
   */
  function renderQuelles(bubble, sources) {
    const existing = bubble.querySelector(".chat-sources");
    if (existing) existing.remove();
    if (!sources || !sources.length) return;
    const sourceList = document.createElement("section");
    sourceList.className = "chat-sources chat-answer-section";
    sourceList.setAttribute("aria-label", "Verwendete Quellen und Dokumente");
    const header = document.createElement("div");
    header.className = "chat-answer-section-title";
    const title = document.createElement("strong");
    const count = document.createElement("span");
    title.textContent = "Quellen";
    count.textContent = sources.length + " verwendet";
    header.append(title, count);
    const chips = document.createElement("div");
    chips.className = "chat-source-list";
    sources.slice(0, 4).forEach((source) => {
      chips.appendChild(sourcePreviewChip(source));
    });
    sourceList.append(header, chips);
    bubble.appendChild(sourceList);
  }

  /**
   * Render machine and similar-error hints from retrieved sources.
   */
  function renderContextHints(bubble, diagnostics, sources) {
    const hints = [];
    (sources || []).forEach((source) => {
      const reasons = sourceMachineReasons(source);
      if (reasons.length) {
        hints.push(sourceTypeLabel(source) + ": " + reasons.join(", "));
      } else if (isMachineOrErrorQuelle(source)) {
        hints.push(sourceTypeLabel(source) + ": " + boundedText(source.title, "Kontextquelle", 80));
      }
    });
    const explainability = retrievalExplainability(diagnostics);
    const links = ((diagnostics && diagnostics.knowledge_links) || explainability.knowledge_links || {}).links || [];
    links.slice(0, 3).forEach((link) => {
      const reasons = Array.isArray(link.reasons) ? link.reasons.join(", ") : "";
      hints.push("Dokumentbezug: " + sourceTypeLabel(link) + (reasons ? " - " + reasons : ""));
    });
    const uniqueHints = Array.from(new Set(hints.filter(Boolean))).slice(0, 4);
    if (!uniqueHints.length) return;

    const wrapper = document.createElement("section");
    wrapper.className = "chat-context-hints chat-answer-section";
    const header = document.createElement("div");
    header.className = "chat-answer-section-title";
    const title = document.createElement("strong");
    const meta = document.createElement("span");
    title.textContent = "Maschinen- und Fehlerkontext";
    meta.textContent = uniqueHints.length + " Hinweise";
    header.append(title, meta);
    const list = document.createElement("div");
    list.className = "chat-context-list";
    uniqueHints.forEach((hint) => {
      const item = document.createElement("span");
      item.textContent = hint;
      list.appendChild(item);
    });
    wrapper.append(header, list);
    bubble.appendChild(wrapper);
  }

  /**
   * Append one explainability row.
   */
  function appendExplainabilityRow(target, label, value) {
    if (value === undefined || value === null || value === "") return;
    const row = document.createElement("div");
    const labelNode = document.createElement("span");
    const valueNode = document.createElement("strong");
    labelNode.textContent = label;
    valueNode.textContent = String(value);
    row.append(labelNode, valueNode);
    target.appendChild(row);
  }

  /**
   * Render a compact explainability disclosure.
   */
  function renderExplainability(bubble, diagnostics, sources) {
    const explainability = retrievalExplainability(diagnostics);
    const confidence = confidencePayload(diagnostics);
    const details = document.createElement("details");
    details.className = "chat-explainability chat-answer-section";
    const summary = document.createElement("summary");
    summary.textContent = "Warum diese Antwort?";
    const rows = document.createElement("div");
    rows.className = "chat-explainability-grid";
    appendExplainabilityRow(rows, "Query-Typ", queryTypeLabel(diagnostics));
    appendExplainabilityRow(rows, "Suchzeit", retrievalDuration(diagnostics));
    appendExplainabilityRow(rows, "Quellen erklärt", explainability.explained_source_count || 0);
    appendExplainabilityRow(rows, "Maschinenabgleich", explainability.machine_match_count || 0);
    appendExplainabilityRow(rows, "Feedback-Signale", explainability.feedback_influenced_count || 0);
    appendExplainabilityRow(rows, "Recency-Signale", explainability.recency_influenced_count || 0);
    if (confidence) {
      appendExplainabilityRow(rows, "Sicherheit-Methode", confidence.method);
      confidence.reasons.slice(0, 3).forEach((reason, index) => {
        appendExplainabilityRow(rows, "Sicherheit " + (index + 1), reason);
      });
    }
    (sources || []).slice(0, 3).forEach((source, index) => {
      const sourceExplain = sourceExplainability(source);
      const sourceScore = source && source.normalized_score !== undefined
        ? source.normalized_score
        : source && source.score;
      const sourceSummary = [
        sourceTrustTitle(source),
        "Score " + scoreLabel(sourceScore || 0),
        qualityStatusLabel((source && source.quality_status) || sourceExplain.quality_status),
        sourceReasonLabels(source).join(", ")
      ].filter(Boolean).join(" - ");
      appendExplainabilityRow(rows, "Warum Quelle " + (index + 1), sourceSummary);
    });
    details.append(summary, rows);
    bubble.appendChild(details);
  }

  /**
   * Render all structured evidence below one assistant answer.
   */
  function renderAssistantEvidence(bubble, diagnostics, sources) {
    const safeDiagnostics = diagnostics || {};
    const safeQuelles = Array.isArray(sources) ? sources : [];
    renderAnswerHeader(bubble, safeDiagnostics, safeQuelles);
    clearAnswerEvidence(bubble);
    renderAnswerAlerts(bubble, safeDiagnostics);
    renderAnswerInsights(bubble, safeDiagnostics, safeQuelles);
    renderAnswerBasis(bubble, safeDiagnostics, safeQuelles);
    renderQuelles(bubble, safeQuelles);
    renderContextHints(bubble, safeDiagnostics, safeQuelles);
    renderExplainability(bubble, safeDiagnostics, safeQuelles);
  }

  function renderChatHistory(items) {
    if (!historyList) return;
    historyList.innerHTML = "";
    const historyItems = items || [];
    if (historyCount) {
      historyCount.textContent = String(historyItems.length);
    }
    if (historyPanel) {
      historyPanel.hidden = historyItems.length === 0;
    }
    historyItems.forEach((item) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "chat-history-item";
      const question = document.createElement("strong");
      question.textContent = item.message || "";
      const meta = document.createElement("small");
      meta.textContent = historyMetaText(item);
      button.append(question, meta);
      button.addEventListener("click", () => {
        appendMessage(item.message, "user");
        const bubble = appendMessage(item.response, "assistant", item.diagnostics || {});
        renderAssistantEvidence(bubble, item.diagnostics || {}, item.sources || []);
      });
      historyList.appendChild(button);
    });
  }

  function historyMetaText(item) {
    const responseType = item.response_type || "assistant";
    if (!item.created_at) return responseType;
    const createdAt = new Date(item.created_at);
    if (Number.isNaN(createdAt.getTime())) {
      return responseType;
    }
    return responseType + " - " + createdAt.toLocaleString("de-DE", {
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit"
    });
  }

  async function loadChatHistory() {
    if (!historyPanel || !historyList) return;
    const token = window.localStorage.getItem("maintenance_access_token");
    if (!token) {
      renderChatHistory([]);
      return;
    }
    const query = historySearch ? historySearch.value.trim() : "";
    const response = await fetch("/api/v1/ai/chat/history?limit=12&q=" + encodeURIComponent(query), {
      headers: { "Authorization": "Bearer " + token }
    });
    if (!response.ok) return;
    const payload = await response.json();
    const data = payload && payload.data ? payload.data : payload;
    renderChatHistory(data.items || []);
  }

  function applyActionPreview(preview) {
    if (!preview || !preview.target) return;
    window.sessionStorage.setItem("maintenance_ai_action_preview", JSON.stringify(preview));
    window.location.href = preview.url || "/";
  }

  function renderActionPreview(bubble, preview) {
    const existing = bubble.querySelector(".chat-action-preview");
    if (existing) existing.remove();
    if (!preview || !preview.label) return;
    const wrapper = document.createElement("div");
    wrapper.className = "chat-action-preview";
    const button = document.createElement("button");
    button.type = "button";
    button.className = "btn btn-primary btn-sm";
    button.textContent = preview.label;
    button.addEventListener("click", () => applyActionPreview(preview));
    wrapper.appendChild(button);
    bubble.appendChild(wrapper);
  }

  function updateAssistantMessage(bubble, text, diagnostics, sources, actionPreview, result) {
    const body = bubble.querySelector(".chat-message-text");
    const meta = bubble.querySelector(".chat-message-meta");
    if (body) renderFormattedText(body, text);
    if (meta) {
      meta.remove();
    }
    const diagnosticsWithSicherheit = Object.assign({}, diagnostics || {});
    if (result && result.confidence && !diagnosticsWithSicherheit.confidence) {
      diagnosticsWithSicherheit.confidence = result.confidence;
    }
    renderAssistantEvidence(bubble, diagnosticsWithSicherheit, sources);
    renderActionPreview(bubble, actionPreview);
  }

  async function askAssistant(message) {
    const token = window.localStorage.getItem("maintenance_access_token");
    if (!token) {
      return {
        answer: "Bitte zuerst einloggen. Danach kann ich die KI-Funktionen nutzen.",
        diagnostics: { status: "permission_denied" }
      };
    }

    const response = await fetch("/api/v1/ai/chat", {
      method: "POST",
      headers: {
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ message, session_id: chatSessionId() })
    });

    if (!response.ok) {
      if (response.status === 401 || response.status === 422) {
        if (window.maintenanceAuth && window.maintenanceAuth.clearSession) {
          window.maintenanceAuth.clearSession({ redirect: false });
        } else {
          window.localStorage.removeItem("maintenance_access_token");
          window.localStorage.removeItem("maintenance_user");
          window.dispatchEvent(new Event("maintenance-auth-changed"));
        }
        return {
          answer: "Deine Sitzung ist abgelaufen. Bitte neu einloggen.",
          diagnostics: { status: "permission_denied" }
        };
      }
      const errorData = await response.json().catch(() => null);
      return {
        answer: (
          errorData && (errorData.message || errorData.error)
        ) || "Die KI-Anfrage konnte gerade nicht verarbeitet werden.",
        diagnostics: { status: "openai_error", fallback_used: true }
      };
    }

    const responseData = await response.json();
    const data = responseData && responseData.answer
      ? responseData
      : responseData && responseData.success === true && Object.prototype.hasOwnProperty.call(responseData, "data")
        ? responseData.data
        : responseData;
    const diagnostics = data.diagnostics || {};
    const isGeneralChat = data.type === "general_chat";
    let answer = data.answer || "Ich habe keine Antwort erhalten.";

    if (!isGeneralChat && diagnostics.status === "api_key_missing") {
      answer += "\n- **Hinweis:** Lokale Ausweichantwort, AI API-Key fehlt";
    }
    if (!isGeneralChat && diagnostics.status === "openai_error") {
      answer += "\n- **Hinweis:** Lokale Ausweichantwort, OpenAI nicht erreichbar";
    }
    if (!isGeneralChat && diagnostics.fallback_used) {
      answer += "\n- **Quelle:** Lokale Ausweichantwort";
    }
    return {
      answer,
      diagnostics,
      confidence: data.confidence || diagnostics.confidence || null,
      type: data.type || null,
      prompt: message,
      sources: data.sources || [],
      action_preview: data.action_preview || null,
      chat_message_id: data.chat_message_id || null,
      audit_event_id: diagnostics.audit_event_id || null
    };
  }

  async function sendFeedback(feedback) {
    const token = window.localStorage.getItem("maintenance_access_token");
    if (!token) return;
    const response = await fetch("/api/v1/ai/feedback", {
      method: "POST",
      headers: {
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json"
      },
      body: JSON.stringify(feedback)
    });
    if (!response.ok) {
      throw new Error("feedback_failed");
    }
  }

  function addFeedbackButtons(bubble, result) {
    const actions = document.createElement("div");
    actions.className = "chat-feedback";
    actions.setAttribute("aria-label", "Antwort bewerten");
    const helpful = document.createElement("button");
    helpful.type = "button";
    helpful.textContent = "Hilfreich";
    helpful.setAttribute("aria-pressed", "false");
    const partial = document.createElement("button");
    partial.type = "button";
    partial.textContent = "Teilweise";
    partial.setAttribute("aria-pressed", "false");
    const notHelpful = document.createElement("button");
    notHelpful.type = "button";
    notHelpful.textContent = "Nicht hilfreich";
    notHelpful.setAttribute("aria-pressed", "false");
    const comment = document.createElement("input");
    comment.className = "input input-bordered";
    comment.placeholder = "Optionaler Kommentar";
    [helpful, partial, notHelpful].forEach((button) => {
      button.className = "chat-feedback-button";
    });
    async function storeFeedback(rating) {
      const selectedButton = rating === "helpful"
        ? helpful
        : rating === "partially_helpful"
          ? partial
          : notHelpful;
      selectedButton.setAttribute("aria-pressed", "true");
      helpful.disabled = true;
      partial.disabled = true;
      notHelpful.disabled = true;
      comment.disabled = true;
      try {
        await sendFeedback({
          chat_message_id: result.chat_message_id,
          audit_event_id: result.audit_event_id,
          prompt: result.prompt || "",
          response: result.answer || "",
          response_type: result.type || "assistant",
          rating,
          comment: comment.value,
          sources: result.sources || []
        });
        actions.textContent = "Feedback gespeichert.";
      } catch (error) {
        actions.textContent = "Feedback konnte nicht gespeichert werden.";
      }
    }
    helpful.addEventListener("click", async () => {
      await storeFeedback("helpful");
    });
    notHelpful.addEventListener("click", async () => {
      await storeFeedback("not_helpful");
    });
    partial.addEventListener("click", async () => {
      await storeFeedback("partially_helpful");
    });
    actions.append(comment, helpful, partial, notHelpful);
    bubble.appendChild(actions);
  }

  const clearBtn = document.querySelector(".chat-clear");

  function clearChat() {
    messages.innerHTML = "";
    hasSubmittedMessage = false;
    hasTypedInCurrentChat = false;
    resetChatSession();
    const initial = document.createElement("div");
    initial.className = "chat-message is-assistant";
    initial.textContent = "Frag mich nach Aufgaben, Fehlern, Maschinen, Lager, Dokumenten oder Schichtplanung.";
    messages.appendChild(initial);
    renderSuggestions();
  }

  function fallbackChatSuggestionsForUser() {
    const auth = window.maintenanceAuth;
    if (!auth || !auth.user || !auth.user()) return [];
    const items = [];
    if (auth.canView("tasks")) items.push({ category: "tasks", message: "Welche Aufgaben sind heute wichtig?" });
    if (auth.canWrite("tasks")) items.push({ category: "tasks", message: "Aufgabe erstellen: Maschine 3 macht Geräusche" });
    if (auth.canView("errors")) items.push({ category: "errors", message: "Was bedeutet Fehler E104?" });
    if (auth.canWrite("errors")) items.push({ category: "errors", message: "Fehleranalyse: Sensor meldet kein Signal" });
    if (auth.canView("machines")) items.push({ category: "machines", message: "Welche Maschinen brauchen Aufmerksamkeit?" });
    if (auth.canView("inventory")) items.push({ category: "inventory", message: "Welche Lagerteile sind kritisch?" });
    if (auth.canView("documents")) items.push({ category: "documents", message: "Welche Dokumente sollte ich prüfen?" });
    return items.slice(0, 6);
  }

  function templateCategoryLabel(category) {
    const labels = {
      tasks: "Aufgaben",
      errors: "Störungen",
      machines: "Maschinen",
      inventory: "Inventar",
      documents: "Dokumente",
      shiftplans: "Schicht"
    };
    return labels[category] || "Vorschlag";
  }

  function normalizeTemplateItem(item) {
    if (typeof item === "string") {
      return { category: "general", label: item, message: item };
    }
    const message = item && (item.message || item.label);
    return {
      category: (item && (item.category || item.scope)) || "general",
      label: (item && item.label) || message,
      message
    };
  }

  function chatSuggestionsForUser() {
    if (chatTemplateItems.length) {
      return chatTemplateItems.map(normalizeTemplateItem).filter((item) => item.message);
    }
    return fallbackChatSuggestionsForUser();
  }

  function updateSuggestionVisibility(items) {
    if (!suggestions) return;
    const hasSuggestions = Array.isArray(items) && items.length > 0;
    const hasInputText = chatInput && chatInput.value.trim().length > 0;
    suggestions.hidden = !hasSuggestions || hasInputText || hasSubmittedMessage || hasTypedInCurrentChat;
  }

  async function loadChatTemplates() {
    const token = window.localStorage.getItem("maintenance_access_token");
    if (!token || isTemplateLoading) return;
    isTemplateLoading = true;
    try {
      const response = await fetch("/api/v1/ai/chat/templates", {
        headers: { "Authorization": "Bearer " + token }
      });
      if (!response.ok) return;
      const payload = await response.json();
      const data = payload && payload.data ? payload.data : payload;
      chatTemplateItems = Array.isArray(data.items) ? data.items : [];
      renderSuggestions(false);
    } finally {
      isTemplateLoading = false;
    }
  }

  function renderSuggestions(loadRemote) {
    if (!suggestions) return;
    const shouldLoadRemote = loadRemote !== false;
    suggestions.innerHTML = "";
    const items = chatSuggestionsForUser();
    if (!chatTemplateItems.length && shouldLoadRemote) {
      loadChatTemplates();
    }
    updateSuggestionVisibility(items);
    items.forEach((item) => {
      const template = normalizeTemplateItem(item);
      const chip = document.createElement("button");
      const scope = document.createElement("span");
      const label = document.createElement("strong");
      chip.type = "button";
      chip.className = "chat-suggestion";
      scope.textContent = templateCategoryLabel(template.category);
      label.textContent = template.label || template.message;
      chip.append(scope, label);
      chip.title = template.message;
      chip.addEventListener("click", () => {
        suggestions.hidden = true;
        if (chatInput) {
          chatInput.value = template.message;
          chatInput.focus();
          updateSuggestionVisibility(items);
        }
      });
      suggestions.appendChild(chip);
    });
  }

  toggle.addEventListener("click", () => setOpen(!widget.classList.contains("is-open")));
  close.addEventListener("click", () => setOpen(false));
  if (clearBtn) clearBtn.addEventListener("click", clearChat);

  function setChatFormBusy(busy) {
    const input = form.querySelector("input");
    const button = form.querySelector("button[type='submit']");
    isSending = busy;
    form.setAttribute("aria-busy", String(busy));
    if (input) input.disabled = busy;
    if (button) {
      button.disabled = busy;
      button.setAttribute("aria-busy", String(busy));
      button.textContent = busy ? "Analysiere..." : "Senden";
    }
  }

  document.addEventListener("keydown", (event) => {
    if (!isOpen()) return;
    if (event.key === "Escape") {
      event.preventDefault();
      setOpen(false);
      return;
    }
    if (event.key !== "Tab") return;
    const focusable = focusableChatElements();
    if (!focusable.length) {
      event.preventDefault();
      panel.focus();
      return;
    }
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
      return;
    }
    if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (isSending) return;
    const input = chatInput || form.querySelector("input");
    const message = input.value.trim();
    if (!message) return;

    input.value = "";
    hasSubmittedMessage = true;
    setChatFormBusy(true);
    if (suggestions) suggestions.hidden = true;
    appendMessage(message, "user");
    const loading = appendMessage(
      "Ich prüfe die freigegebenen Daten und formuliere eine sichere Antwort...",
      "assistant"
    );
    loading.classList.add("is-loading");
    renderLoadingState(loading);

    try {
      const result = await askAssistant(message);
      updateAssistantMessage(
        loading,
        result.answer,
        result.diagnostics,
        result.sources,
        result.action_preview,
        result
      );
      addFeedbackButtons(loading, result);
      loading.classList.remove("is-loading");
    } catch (error) {
      updateAssistantMessage(
        loading,
        "Keine Verbindung zur API. Bitte prüfe, ob der Server läuft.",
        { status: "openai_error", fallback_used: true },
        [],
        null,
        null
      );
      loading.classList.remove("is-loading");
    } finally {
      setChatFormBusy(false);
      const currentInput = form.querySelector("input");
      if (currentInput) currentInput.focus();
    }
  });

  window.addEventListener("maintenance-auth-ready", () => {
    chatTemplateItems = [];
    if (isOpen()) {
      hasHydratedPanel = false;
      hydrateChatPanel();
    }
  });
  window.addEventListener("maintenance-auth-changed", () => {
    chatTemplateItems = [];
    if (isOpen()) {
      hasHydratedPanel = false;
      hydrateChatPanel();
    }
  });
  if (historySearch) {
    historySearch.addEventListener("input", () => {
      window.clearTimeout(historySearch._timer);
      historySearch._timer = window.setTimeout(loadChatHistory, 250);
    });
  }
  if (chatInput) {
    chatInput.addEventListener("input", () => {
      if (chatInput.value.trim()) {
        hasTypedInCurrentChat = true;
      }
      updateSuggestionVisibility(chatSuggestionsForUser());
    });
  }
  window.maintenanceChat = {
    open: () => setOpen(true),
    close: () => setOpen(false),
    toggle: () => setOpen(!isOpen()),
    hydrate: hydrateChatPanel
  };

  if (window.localStorage.getItem(CHAT_OPEN_KEY) === "true") {
    setOpen(true);
  }
})();

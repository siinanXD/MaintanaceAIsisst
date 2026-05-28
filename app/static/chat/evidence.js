/**
 * Chat widget evidence module.
 * Registers helpers on the shared MaintenanceChatRuntime object.
 */
(function registerChatModule(Chat) {
  const { state } = Chat;
  const {
    widget,
    toggle,
    panel,
    close,
    form,
    messages,
    suggestions,
    historyPanel,
    historySearch,
    historyList,
    historyCount,
    chatInput,
    CHAT_OPEN_KEY,
    CHAT_SESSION_KEY
  } = Chat;

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

  /**
   * Return the authenticated user object known by the shell.
   */
  function currentChatUser() {
    if (window.maintenanceAuth && typeof window.maintenanceAuth.user === "function") {
      return window.maintenanceAuth.user();
    }
    try {
      return JSON.parse(window.localStorage.getItem("maintenance_user") || "null");
    } catch (error) {
      return null;
    }
  }

  /**
   * Return whether the current user may see source and diagnostic cards.
   */
  function canViewChatEvidence() {
    const user = currentChatUser();
    const role = String((user && user.role) || "").toLowerCase();
    return role === "master_admin" || role === "it";
  }

  /**
   * Return whether an assistant answer should show evidence sections.
   */
  function canRenderAssistantEvidence(diagnostics) {
    if (!canViewChatEvidence()) return false;
    if (diagnostics && diagnostics.evidence_visible === false) return false;
    return !(diagnostics && diagnostics.status === "permission_denied");
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
  Object.assign(Chat, { openAIErrorLabel, currentChatUser, canViewChatEvidence, canRenderAssistantEvidence, statusText, numericValue, boundedText, clearElement, scoreLabel, confidencePayload, normalizedSicherheitLevel, confidenceLevelLabel, confidenceTrustCopy, confidenceScorePercent, confidenceTone, confidenceMeter, appendAnswerBadge, sourceTypeLabel, sourceKind, sourceKindLabel, sourceKindClass, sourceMachineLabel, sourceDepartmentLabel, sourceRelevanceLabel, qualityStatusLabel, sourceExplainability, machineReasonLabels, sourceMachineReasons, sourceQualityReason, sourceReasonLabels, sourceTrustTitle, answerBasisItems, isMachineOrErrorQuelle, retrievalExplainability, safetyPayloads, safetyWarnings, conflictPayload, conflictWarnings, queryTypeLabel, answerModeLabel, qualityWarnings, retrievalDuration });
})(window.MaintenanceChatRuntime);

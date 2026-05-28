/**
 * Chat widget rendering module.
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

  const answerBasisItems = (...args) => Chat.answerBasisItems(...args);
  const answerModeLabel = (...args) => Chat.answerModeLabel(...args);
  const appendAnswerBadge = (...args) => Chat.appendAnswerBadge(...args);
  const boundedText = (...args) => Chat.boundedText(...args);
  const canRenderAssistantEvidence = (...args) => Chat.canRenderAssistantEvidence(...args);
  const clearElement = (...args) => Chat.clearElement(...args);
  const confidenceLevelLabel = (...args) => Chat.confidenceLevelLabel(...args);
  const confidenceMeter = (...args) => Chat.confidenceMeter(...args);
  const confidencePayload = (...args) => Chat.confidencePayload(...args);
  const confidenceTone = (...args) => Chat.confidenceTone(...args);
  const confidenceTrustCopy = (...args) => Chat.confidenceTrustCopy(...args);
  const conflictWarnings = (...args) => Chat.conflictWarnings(...args);
  const isMachineOrErrorQuelle = (...args) => Chat.isMachineOrErrorQuelle(...args);
  const qualityStatusLabel = (...args) => Chat.qualityStatusLabel(...args);
  const qualityWarnings = (...args) => Chat.qualityWarnings(...args);
  const queryTypeLabel = (...args) => Chat.queryTypeLabel(...args);
  const retrievalDuration = (...args) => Chat.retrievalDuration(...args);
  const retrievalExplainability = (...args) => Chat.retrievalExplainability(...args);
  const safetyWarnings = (...args) => Chat.safetyWarnings(...args);
  const scoreLabel = (...args) => Chat.scoreLabel(...args);
  const sourceDepartmentLabel = (...args) => Chat.sourceDepartmentLabel(...args);
  const sourceExplainability = (...args) => Chat.sourceExplainability(...args);
  const sourceKindClass = (...args) => Chat.sourceKindClass(...args);
  const sourceKindLabel = (...args) => Chat.sourceKindLabel(...args);
  const sourceMachineLabel = (...args) => Chat.sourceMachineLabel(...args);
  const sourceMachineReasons = (...args) => Chat.sourceMachineReasons(...args);
  const sourceReasonLabels = (...args) => Chat.sourceReasonLabels(...args);
  const sourceRelevanceLabel = (...args) => Chat.sourceRelevanceLabel(...args);
  const sourceTrustTitle = (...args) => Chat.sourceTrustTitle(...args);
  const sourceTypeLabel = (...args) => Chat.sourceTypeLabel(...args);
  const statusText = (...args) => Chat.statusText(...args);
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
    if (!canRenderAssistantEvidence(safeDiagnostics)) {
      return;
    }
    renderAnswerAlerts(bubble, safeDiagnostics);
    renderAnswerInsights(bubble, safeDiagnostics, safeQuelles);
    renderAnswerBasis(bubble, safeDiagnostics, safeQuelles);
    renderQuelles(bubble, safeQuelles);
    renderContextHints(bubble, safeDiagnostics, safeQuelles);
    renderExplainability(bubble, safeDiagnostics, safeQuelles);
  }
  Object.assign(Chat, { renderAnswerHeader, clearAnswerEvidence, renderAnswerInsights, renderAnswerAlerts, renderAnswerBasis, appendInlineText, renderFormattedText, appendMessage, renderLoadingState, sourcePreviewMeta, sourcePreviewChip, renderQuelles, renderContextHints, appendExplainabilityRow, renderExplainability, renderAssistantEvidence });
})(window.MaintenanceChatRuntime);

/**
 * Admin AI retrieval module.
 * Registers view helpers on the shared MaintenanceAdminAI runtime.
 */
(function registerAdminAiModule(AdminAI) {
  const { root, adminView, state, QUALITY_STATUS_OPTIONS } = AdminAI;
  const api = (...args) => AdminAI.api(...args);
  const cell = (...args) => AdminAI.cell(...args);
  const confidenceLabel = (...args) => AdminAI.confidenceLabel(...args);
  const dateTimeText = (...args) => AdminAI.dateTimeText(...args);
  const flowStatusClass = (...args) => AdminAI.flowStatusClass(...args);
  const flowStatusLabel = (...args) => AdminAI.flowStatusLabel(...args);
  const msText = (...args) => AdminAI.msText(...args);
  const numberText = (...args) => AdminAI.numberText(...args);
  const queryTypeLabel = (...args) => AdminAI.queryTypeLabel(...args);
  const recordReference = (...args) => AdminAI.recordReference(...args);
  const redactSensitiveText = (...args) => AdminAI.redactSensitiveText(...args);
  const renderAdminEmptyState = (...args) => AdminAI.renderAdminEmptyState(...args);
  const renderAiClaritySummary = (...args) => AdminAI.renderAiClaritySummary(...args);
  const scoreText = (...args) => AdminAI.scoreText(...args);
  const sourceReferenceLabel = (...args) => AdminAI.sourceReferenceLabel(...args);
  const statusPill = (...args) => AdminAI.statusPill(...args);
  const statusRow = (...args) => AdminAI.statusRow(...args);
  const text = (...args) => AdminAI.text(...args);
  function renderRetrievalDebug(data) {
    const tbody = root.querySelector("[data-retrieval-debug-rows]");
    if (!tbody) return;
    tbody.innerHTML = "";
    state.retrievalDebugItems = data.items || [];
    if (
      state.retrievalDebugItems.length
      && !state.retrievalDebugItems.some((item) => item.chat_message_id === state.selectedRetrievalFlowId)
    ) {
      state.selectedRetrievalFlowId = state.retrievalDebugItems[0].chat_message_id;
    }
    if (!state.retrievalDebugItems.length) {
      state.selectedRetrievalFlowId = null;
    }
    renderRetrievalFlow(selectedRetrievalFlowItem());
    renderAiClaritySummary();
    const items = data.items || [];
    if (!items.length) {
      renderAdminEmptyState(
        tbody,
        "Keine Quellenabruf-Debug-Daten für diesen Filter.",
        "Passe Zeitraum, Suchbegriff oder Query-Typ an."
      );
      return;
    }
    items.forEach((item) => {
      const row = document.createElement("tr");
      const action = document.createElement("td");
      const button = document.createElement("button");
      const conflicts = item.conflicts || {};
      const safety = item.safety || {};
      const sourceText = (item.used_sources || []).length + " Quellen";
      const conflictText = conflicts.has_conflicts
        ? conflicts.count + " Konflikte"
        : (safety.safety_relevant ? "Sicherheit " + safety.risk_level : "-");
      row.className = state.selectedRetrievalFlowId === item.chat_message_id ? "is-selected" : "";
      button.type = "button";
      button.className = "btn btn-ghost btn-sm";
      button.dataset.retrievalFlowSelect = item.chat_message_id;
      button.textContent = "Ansehen";
      action.appendChild(button);
      row.append(
        cell(dateTimeText(item.created_at)),
        cell(recordReference("Chat", item.chat_message_id)),
        cell(queryTypeLabel(item.query_type)),
        cell(sourceText),
        cell(text(item.confidence && item.confidence.score) + " / " + text(item.confidence && item.confidence.level)),
        cell(conflictText),
        cell(text(item.retrieval_duration_ms) + " ms"),
        action
      );
      tbody.appendChild(row);
    });
  }

  function selectedRetrievalFlowItem() {
    if (!state.retrievalDebugItems.length) return null;
    return (
      state.retrievalDebugItems.find((item) => item.chat_message_id === state.selectedRetrievalFlowId)
      || state.retrievalDebugItems[0]
    );
  }

  function renderRetrievalFlow(item) {
    const statusTarget = root.querySelector("[data-retrieval-flow-status]");
    const durationTarget = root.querySelector("[data-retrieval-flow-duration]");
    const summaryTarget = root.querySelector("[data-retrieval-flow-summary]");
    const timelineTarget = root.querySelector("[data-retrieval-flow-timeline]");
    const sourceMapTarget = root.querySelector("[data-retrieval-flow-source-map]");
    const answerTarget = root.querySelector("[data-retrieval-flow-answer]");
    if (!summaryTarget || !timelineTarget || !sourceMapTarget || !answerTarget) return;
    summaryTarget.innerHTML = "";
    timelineTarget.innerHTML = "";
    sourceMapTarget.innerHTML = "";
    answerTarget.innerHTML = "";
    if (!item) {
      if (statusTarget) {
        statusTarget.textContent = "Keine Daten";
        statusTarget.className = "badge badge-ai is-muted";
      }
      if (durationTarget) durationTarget.textContent = "-";
      summaryTarget.appendChild(statusRow("Flow", "Noch keine Quellenabruf-Debug-Daten vorhanden."));
      renderRetrievalAnalysis(null);
      return;
    }
    const worstStatus = retrievalFlowWorstStatus(item.flow_steps || []);
    if (statusTarget) {
      statusTarget.textContent = flowStatusLabel(worstStatus);
      statusTarget.className = "badge badge-ai " + flowStatusClass(worstStatus);
    }
    if (durationTarget) durationTarget.textContent = msText(item.retrieval_duration_ms || 0);
    renderRetrievalFlowSummary(summaryTarget, item);
    renderRetrievalFlowTimeline(timelineTarget, item);
    renderRetrievalFlowQuelles(sourceMapTarget, item);
    renderRetrievalFlowAnswer(answerTarget, item);
    renderRetrievalAnalysis(item);
  }

  function renderRetrievalAnalysis(item) {
    const target = root.querySelector("[data-retrieval-analysis]");
    if (!target) return;
    target.innerHTML = "";
    const empty = !item;
    const reranking = empty ? {} : (item.reranking || {});
    const metrics = [
      {
        label: "Gefundene Textabschnitte",
        value: empty ? "0" : numberText((item.rag_chunks || []).length),
        detail: "RAG-Kontext"
      },
      {
        label: "Hybrid Treffer",
        value: empty ? "0" : numberText((item.used_sources || []).length),
        detail: "Strukturiert + RAG"
      },
      {
        label: "Re-Ranking",
        value: numberText(reranking.reranked_count || 0),
        detail: "sichtbar neu sortiert"
      },
      {
        label: "Top Score",
        value: scoreText(reranking.top_score),
        detail: "bestbewertete Quelle"
      },
      {
        label: "Berechtigungsstatus",
        value: empty ? "-" : "gefiltert",
        detail: "nur erlaubte Quellen im Flow"
      },
      {
        label: "Suchdauer",
        value: empty ? "0 ms" : msText(item.retrieval_duration_ms || 0),
        detail: "bis Context Building"
      },
      {
        label: "Tokens",
        value: "-",
        detail: "prompt-sicher nicht persistiert"
      },
      {
        label: "Textabschnitt IDs",
        value: empty ? "-" : (item.rag_chunks || []).map((chunk) => chunk.chunk_id).filter(Boolean).slice(0, 3).join(", ") || "-",
        detail: "Top sichtbare Textabschnitte"
      }
    ];
    metrics.forEach((metric) => {
      const card = document.createElement("article");
      const label = document.createElement("span");
      const value = document.createElement("strong");
      const detail = document.createElement("small");
      card.className = "ai-retrieval-metric";
      label.textContent = metric.label;
      value.textContent = metric.value;
      detail.textContent = metric.detail;
      card.append(label, value, detail);
      target.appendChild(card);
    });
  }

  function retrievalFlowWorstStatus(steps) {
    const order = { ok: 0, empty: 1, warning: 2, critical: 3 };
    return (steps || []).reduce((worst, step) => (
      order[step.status] > order[worst] ? step.status : worst
    ), "ok");
  }

  function renderRetrievalFlowSummary(target, item) {
    const question = document.createElement("article");
    const meta = document.createElement("div");
    question.className = "retrieval-flow-question";
    meta.className = "retrieval-flow-meta";
    const title = document.createElement("span");
    const textNode = document.createElement("strong");
    title.textContent = "Chat-Referenz";
    textNode.textContent = recordReference("Chat", item.chat_message_id);
    question.append(title, textNode);
    [
      ["Query-Typ", queryTypeLabel(item.query_type)],
      ["Strukturierte Quellen", numberText((item.structured_sources || []).length)],
      ["RAG-Textabschnitte", numberText((item.rag_chunks || []).length)],
      ["Konfidenz", confidenceLabel(item.confidence)]
    ].forEach(([label, value]) => {
      meta.appendChild(statusRow(label, value));
    });
    target.append(question, meta);
  }

  function renderRetrievalFlowTimeline(target, item) {
    const steps = item.flow_steps || [];
    if (!steps.length) {
      target.appendChild(statusRow("Timeline", "Keine Flow-Schritte gespeichert."));
      return;
    }
    steps.forEach((step, index) => {
      const details = document.createElement("details");
      const summary = document.createElement("summary");
      const marker = document.createElement("span");
      const body = document.createElement("div");
      const title = document.createElement("strong");
      const badge = statusPill(flowStatusLabel(step.status), flowStatusClass(step.status));
      const subtitle = document.createElement("small");
      details.className = "retrieval-flow-step " + flowStatusClass(step.status);
      details.open = index < 3 || step.status === "warning" || step.status === "critical";
      marker.className = "retrieval-flow-step-marker";
      marker.textContent = String(index + 1);
      body.className = "retrieval-flow-step-body";
      title.textContent = step.label;
      subtitle.textContent = step.summary || "-";
      body.append(title, subtitle);
      summary.append(marker, body, badge);
      details.appendChild(summary);
      details.appendChild(retrievalFlowMetrics(step.metrics));
      target.appendChild(details);
    });
  }

  function retrievalFlowMetrics(metrics) {
    const grid = document.createElement("div");
    grid.className = "retrieval-flow-metrics";
    const safeMetrics = metrics && typeof metrics === "object" ? metrics : {};
    const entries = Object.entries(safeMetrics)
      .filter(([, value]) => value != null && value !== "" && typeof value !== "object")
      .slice(0, 8);
    if (!entries.length) {
      grid.appendChild(statusRow("Details", "Keine zusätzlichen Metriken."));
      return grid;
    }
    entries.forEach(([key, value]) => {
      grid.appendChild(statusRow(flowMetricLabel(key), flowMetricValue(key, value)));
    });
    return grid;
  }

  function flowMetricLabel(key) {
    const labels = {
      query_type: "Query-Typ",
      query_confidence: "Abfragekonfidenz",
      source_count: "Quellen",
      chunk_count: "Textabschnitte",
      candidate_count: "Kandidaten",
      shown_count: "Sichtbar",
      reranked_count: "Re-Ranked",
      top_score: "Top Score",
      section_count: "Sections",
      used_chars: "Kontext",
      max_chars: "Budget",
      answer_preview_chars: "Antwortvorschau"
    };
    return labels[key] || key.replaceAll("_", " ");
  }

  function flowMetricValue(key, value) {
    if (key.includes("score") || key.includes("confidence")) return scoreText(value);
    if (key.includes("chars")) return numberText(value);
    return text(value);
  }

  function renderRetrievalFlowQuelles(target, item) {
    const heading = document.createElement("div");
    const title = document.createElement("strong");
    const meta = document.createElement("span");
    const list = document.createElement("div");
    heading.className = "retrieval-flow-card-header";
    title.textContent = "Quelle → Antwort";
    meta.textContent = (item.source_answer_links || []).length + " Links";
    list.className = "retrieval-flow-source-list";
    heading.append(title, meta);
    target.appendChild(heading);
    if (!(item.source_answer_links || []).length) {
      target.appendChild(statusRow("Quellen", "Keine Quellen im Flow."));
      return;
    }
    (item.source_answer_links || []).slice(0, 8).forEach((link) => {
      const source = link.source || {};
      const card = document.createElement("article");
      const cardTitle = document.createElement("strong");
      const cardMeta = document.createElement("small");
      const reasons = document.createElement("div");
      card.className = "retrieval-flow-source";
      cardTitle.textContent = sourceReferenceLabel(source);
      cardMeta.textContent = [
        "Rank " + text(source.rank),
        "Score " + scoreText(source.final_score != null ? source.final_score : source.score),
        source.quality_status ? "Quality " + source.quality_status : ""
      ].filter(Boolean).join(" · ");
      reasons.className = "retrieval-flow-badges";
      (link.reasons || []).forEach((reason) => {
        reasons.appendChild(statusPill(flowReasonLabel(reason), "is-muted"));
      });
      card.append(cardTitle, cardMeta, reasons);
      list.appendChild(card);
    });
    target.appendChild(list);
  }

  function flowReasonLabel(reason) {
    const labels = {
      score_signal: "Score",
      quality_gate: "Quality Gate",
      machine_context: "Maschinenkontext",
      section_context: "Abschnitt",
      retrieved_context: "Quellenabruf",
      used_as_answer_context: "Antwortkontext"
    };
    return labels[reason] || text(reason);
  }

  function renderRetrievalFlowAnswer(target, item) {
    const heading = document.createElement("div");
    const title = document.createElement("strong");
    const meta = document.createElement("span");
    const answer = document.createElement("p");
    const checks = document.createElement("div");
    heading.className = "retrieval-flow-card-header";
    title.textContent = "Finale Antwort und Sicherheit";
    meta.textContent = confidenceLabel(item.confidence);
    answer.className = "retrieval-flow-answer-preview";
    answer.textContent = redactSensitiveText(
      item.answer_preview,
      "Antwortvorschau aus Datenschutz ausgeblendet."
    );
    checks.className = "retrieval-flow-checks";
    (item.safety_checks || []).forEach((check) => {
      checks.appendChild(statusRow(
        check.label,
        check.safety_relevant
          ? "relevant · " + text(check.risk_level || check.action || "-")
          : "nicht relevant"
      ));
    });
    heading.append(title, meta);
    target.append(heading, answer, checks);
  }

  async function loadRetrievalDebug() {
    const query = root.querySelector("[data-retrieval-debug-search]").value;
    const queryType = root.querySelector("[data-retrieval-debug-type]").value;
    const params = new URLSearchParams({
      limit: "20",
      q: query,
      query_type: queryType
    });
    const data = await api("/api/v1/admin/ai/retrieval-debug?" + params.toString());
    renderRetrievalDebug(data);
  }
  Object.assign(AdminAI, { renderRetrievalDebug, selectedRetrievalFlowItem, renderRetrievalFlow, renderRetrievalAnalysis, retrievalFlowWorstStatus, renderRetrievalFlowSummary, renderRetrievalFlowTimeline, retrievalFlowMetrics, flowMetricLabel, flowMetricValue, renderRetrievalFlowQuelles, flowReasonLabel, renderRetrievalFlowAnswer, loadRetrievalDebug });
})(window.MaintenanceAdminAI);

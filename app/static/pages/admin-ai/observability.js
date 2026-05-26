/**
 * Admin AI observability module.
 * Registers view helpers on the shared MaintenanceAdminAI runtime.
 */
(function registerAdminAiModule(AdminAI) {
  const { root, adminView, state, QUALITY_STATUS_OPTIONS } = AdminAI;
  const api = (...args) => AdminAI.api(...args);
  const cell = (...args) => AdminAI.cell(...args);
  const confidenceLabel = (...args) => AdminAI.confidenceLabel(...args);
  const dateTimeText = (...args) => AdminAI.dateTimeText(...args);
  const healthClass = (...args) => AdminAI.healthClass(...args);
  const msText = (...args) => AdminAI.msText(...args);
  const numberText = (...args) => AdminAI.numberText(...args);
  const percentText = (...args) => AdminAI.percentText(...args);
  const pillCell = (...args) => AdminAI.pillCell(...args);
  const queryTypeLabel = (...args) => AdminAI.queryTypeLabel(...args);
  const readinessLabel = (...args) => AdminAI.readinessLabel(...args);
  const recordReference = (...args) => AdminAI.recordReference(...args);
  const redactSensitiveText = (...args) => AdminAI.redactSensitiveText(...args);
  const renderAdminEmptyState = (...args) => AdminAI.renderAdminEmptyState(...args);
  const renderAiClaritySummary = (...args) => AdminAI.renderAiClaritySummary(...args);
  const renderProviderConfiguration = (...args) => AdminAI.renderProviderConfiguration(...args);
  const renderSafetyFallbackSummary = (...args) => AdminAI.renderSafetyFallbackSummary(...args);
  const renderSectionStatusSummaries = (...args) => AdminAI.renderSectionStatusSummaries(...args);
  const renderTopErrors = (...args) => AdminAI.renderTopErrors(...args);
  const renderWorkflowMetrics = (...args) => AdminAI.renderWorkflowMetrics(...args);
  const safeErrorMessage = (...args) => AdminAI.safeErrorMessage(...args);
  const scoreText = (...args) => AdminAI.scoreText(...args);
  const setAdminMessage = (...args) => AdminAI.setAdminMessage(...args);
  const setButtonBusy = (...args) => AdminAI.setButtonBusy(...args);
  const setHealthCard = (...args) => AdminAI.setHealthCard(...args);
  const sourceReferenceLabel = (...args) => AdminAI.sourceReferenceLabel(...args);
  const sourceTypeLabel = (...args) => AdminAI.sourceTypeLabel(...args);
  const statusPill = (...args) => AdminAI.statusPill(...args);
  const statusRow = (...args) => AdminAI.statusRow(...args);
  const text = (...args) => AdminAI.text(...args);
  const truncateLabel = (...args) => AdminAI.truncateLabel(...args);
  async function loadSummary() {
    const summary = await api("/api/v1/admin/ai/summary?days=7");
    state.latestAiSummary = summary || {};
    const formatters = {
      events_total: numberText,
      fallback_rate: percentText,
      error_rate: percentText,
      average_latency_ms: (value) => numberText(value) + " ms",
      total_tokens: numberText,
      estimated_cost_usd: moneyText,
      cache_rate: percentText,
      cost_per_1k_tokens: moneyText
    };
    Object.keys(formatters).forEach((key) => {
      const target = root.querySelector('[data-ai-kpi="' + key + '"]');
      if (target) target.textContent = formatters[key](summary[key]);
    });
    renderWorkflowMetrics(summary.top_workflows || []);
    renderTopErrors(summary.top_errors || []);
    const readiness = summary.readiness || {};
    setHealthCard("ai", readiness.status || "warning", (readiness.reasons || []).join(" "));
    renderSafetyFallbackSummary();
    renderSectionStatusSummaries();
    renderAiClaritySummary();
  }

  function retrievalSloLabel(metric) {
    const labels = {
      retrieval_p95_ms: "P95 Suchzeit",
      no_source_rate: "Ohne Quellen",
      low_confidence_rate: "Niedrige Sicherheit",
      permission_filtered_candidate_count: "Berechtigungsfilter",
      negative_feedback_rate: "Negatives Feedback",
      safety_risk_count: "Sicherheitsrisiken",
      fallback_rate: "Ausweichantworten",
      vector_sync_failure_count: "Index-Sync-Fehler",
      stale_index_count: "Veralteter Index"
    };
    return labels[metric] || text(metric);
  }

  function retrievalSloValue(metric, value) {
    if (metric === "retrieval_p95_ms") return msText(value);
    if (
      metric === "no_source_rate"
      || metric === "low_confidence_rate"
      || metric === "negative_feedback_rate"
      || metric === "fallback_rate"
    ) {
      return percentText(value);
    }
    return numberText(value);
  }

  function renderRetrievalSlo(payload) {
    const slo = (payload && payload.retrieval_slo) || {};
    const values = slo.last_values || {};
    const status = slo.status || "ok";
    const statusTarget = root.querySelector("[data-retrieval-slo-status]");
    if (statusTarget) {
      statusTarget.textContent = readinessLabel(status);
      statusTarget.className = "badge badge-ai " + healthClass(status);
    }
    root.querySelectorAll("[data-retrieval-slo-kpi]").forEach((target) => {
      const key = target.dataset.retrievalSloKpi;
      if (key === "index_sync_risks") {
        target.textContent = numberText(
          Number(values.vector_sync_failure_count || 0) + Number(values.stale_index_count || 0)
        );
        return;
      }
      target.textContent = retrievalSloValue(key, values[key]);
    });

    const trendList = root.querySelector("[data-retrieval-slo-trends]");
    if (trendList) {
      trendList.innerHTML = "";
      const trends = slo.trends || {};
      Object.keys(trends).slice(0, 9).forEach((metric) => {
        const item = trends[metric] || {};
        const delta = item.delta || 0;
        const sign = delta > 0 ? "+" : "";
        trendList.appendChild(statusRow(
          retrievalSloLabel(metric),
          retrievalSloValue(metric, item.current) + " (" + sign + retrievalSloValue(metric, delta) + ")"
        ));
      });
      if (!Object.keys(trends).length) {
        trendList.appendChild(statusRow("Trend", "noch keine Messwerte"));
      }
    }

    const warningList = root.querySelector("[data-retrieval-slo-warnings]");
    if (warningList) {
      warningList.innerHTML = "";
      const warnings = slo.warnings || [];
      if (!warnings.length) {
        warningList.appendChild(statusRow("SLO-Status", "keine Warnungen"));
      } else {
        warnings.forEach((warning) => {
          warningList.appendChild(statusRow(
            retrievalSloLabel(warning.metric),
            readinessLabel(warning.status) + " ab " + retrievalSloValue(warning.metric, warning.threshold)
          ));
        });
      }
    }
    renderOverviewState();
    renderSafetyFallbackSummary();
    renderSectionStatusSummaries();
    renderAiClaritySummary();
  }

  function monitoringStatus(metrics, qualityMetrics) {
    const errorRate = Number((metrics && metrics.error_rate) || 0);
    const emptyRate = Number((metrics && metrics.empty_retrieval_rate) || 0);
    const warnings = Number((metrics && metrics.hallucination_warning_count) || 0);
    const hitRate = Number((qualityMetrics && qualityMetrics.retrieval_hit_rate) || 0);
    if (errorRate >= 0.25 || emptyRate >= 0.35 || warnings >= 5 || hitRate < 0.5) {
      return "critical";
    }
    if (errorRate > 0 || emptyRate >= 0.15 || warnings > 0 || hitRate < 0.75) {
      return "warning";
    }
    return "ok";
  }

  function monitoringKpiValue(key, metrics, qualityMetrics) {
    const source = key in qualityMetrics ? qualityMetrics : metrics;
    const value = source[key];
    if (key.includes("rate") || key.includes("similarity")) return percentText(value);
    if (key.includes("_ms")) return msText(Math.round(Number(value || 0)));
    return numberText(value);
  }

  function renderMiniBar(target, label, value, maxValue) {
    const row = document.createElement("div");
    const header = document.createElement("div");
    const bar = document.createElement("span");
    const fill = document.createElement("i");
    const safeMax = Math.max(Number(maxValue || 0), Number(value || 0), 1);
    row.className = "ai-mini-bar";
    header.append(statusPill(label, "is-muted"), document.createElement("strong"));
    header.querySelector("strong").textContent = numberText(value);
    fill.style.width = Math.max(4, Math.round((Number(value || 0) / safeMax) * 100)) + "%";
    bar.appendChild(fill);
    row.append(header, bar);
    target.appendChild(row);
  }

  function renderMonitoringList(target, title, rows, emptyText, rowRenderer) {
    if (!target) return;
    target.innerHTML = "";
    const heading = document.createElement("div");
    const headingTitle = document.createElement("strong");
    heading.className = "ai-monitor-list-header";
    headingTitle.textContent = title;
    heading.appendChild(headingTitle);
    target.appendChild(heading);
    if (!rows || !rows.length) {
      target.appendChild(statusRow(title, emptyText));
      return;
    }
    rows.forEach((row, index) => target.appendChild(rowRenderer(row, index)));
  }

  function monitoringRow(label, value, meta, className) {
    const row = document.createElement("article");
    const title = document.createElement("strong");
    const detail = document.createElement("span");
    const foot = document.createElement("small");
    row.className = "ai-monitor-row " + (className || "");
    title.textContent = label;
    detail.textContent = value;
    foot.textContent = meta || "";
    row.append(title, detail, foot);
    return row;
  }

  function renderAiObservability(payload) {
    state.latestAiObservability = payload || {};
    const metrics = state.latestAiObservability.metrics || {};
    const quality = state.latestAiObservability.quality_metrics || {};
    const retrieval = state.latestAiObservability.retrieval_monitoring || {};
    const status = monitoringStatus(metrics, quality);
    const statusTarget = root.querySelector("[data-ai-observability-status]");
    if (statusTarget) {
      statusTarget.textContent = readinessLabel(status);
      statusTarget.className = "badge badge-ai " + healthClass(status);
    }
    root.querySelectorAll("[data-ai-monitoring-kpi]").forEach((target) => {
      const key = target.dataset.aiMonitoringKpi;
      target.textContent = monitoringKpiValue(key, metrics, quality);
    });
    renderTopQuestions(metrics.top_questions || []);
    renderQuelleDistribution(metrics.source_distribution_rows || []);
    renderRetrievalHits(retrieval);
    renderQualityMetrics(quality, retrieval.score_summary || {});
    renderAiObservabilityLogs(state.latestAiObservability.ai_logs || []);
    renderDebugTools(state.latestAiObservability.debug_tools || {});
    renderSafetyFallbackSummary();
    renderSectionStatusSummaries();
    renderAiClaritySummary();
  }

  function renderTopQuestions(rows) {
    renderMonitoringList(
      root.querySelector("[data-ai-top-questions]"),
      "Häufigste Fragen",
      rows,
      "noch keine Fragen",
      (row, index) => monitoringRow(
        "Fragegruppe " + (index + 1),
        numberText(row.count) + "x",
        "Ø Konfidenz " + text(row.average_confidence) + " - Inhalt ausgeblendet"
      )
    );
  }

  function renderQuelleDistribution(rows) {
    const target = root.querySelector("[data-ai-source-distribution]");
    if (!target) return;
    target.innerHTML = "";
    const heading = document.createElement("div");
    heading.className = "ai-monitor-list-header";
    heading.appendChild(document.createElement("strong"));
    heading.querySelector("strong").textContent = "Quellenverteilung";
    target.appendChild(heading);
    if (!rows.length) {
      target.appendChild(statusRow("Quellen", "noch keine Quellen genutzt"));
      return;
    }
    const maxValue = Math.max(...rows.map((row) => Number(row.count || 0)), 1);
    rows.forEach((row) => renderMiniBar(target, sourceTypeLabel(row.key), row.count, maxValue));
  }

  function renderRetrievalHits(retrieval) {
    renderMonitoringList(
      root.querySelector("[data-ai-top-hits]"),
      "Top Treffer",
      retrieval.top_hits || [],
      "noch keine Treffer",
      (row) => monitoringRow(
        truncateLabel(row.label, 120),
        "Score " + scoreText(row.score),
        "Rank " + text(row.rank) + " · Similarity " + scoreText(row.similarity)
      )
    );
    renderMonitoringList(
      root.querySelector("[data-ai-poor-hits]"),
      "Schlechte Treffer",
      retrieval.poor_hits || [],
      "keine auffälligen Treffer",
      (row) => monitoringRow(
        truncateLabel(row.label, 120),
        "Score " + scoreText(row.score),
        "Similarity " + scoreText(row.similarity),
        "is-warning"
      )
    );
    renderMonitoringList(
      root.querySelector("[data-ai-chunk-usage]"),
      "Textabschnitt-Nutzung",
      retrieval.chunk_usage || [],
      "noch keine Textabschnitt-Nutzung",
      (row) => monitoringRow(
        truncateLabel(row.label || row.source_type + " #" + row.source_id, 120),
        numberText(row.uses) + " Nutzungen",
        row.chunk_id ? "Textabschnitt #" + row.chunk_id : "ohne Textabschnitt"
      )
    );
  }

  function renderQualityMetrics(quality, scoreSummary) {
    const rows = [
      ["Recall@K", quality.recall_at_k == null ? "-" : percentText(quality.recall_at_k)],
      ["Trefferquote", percentText(quality.retrieval_hit_rate)],
      ["Leere Suchläufe", percentText(quality.empty_retrieval_rate)],
      ["Similarity Ø", percentText(quality.average_similarity_score)],
      ["Score Ø", scoreText(scoreSummary.average_score)],
      ["Niedrige Ähnlichkeit", numberText(quality.low_similarity_count)]
    ];
    renderMonitoringList(
      root.querySelector("[data-ai-quality-metrics]"),
      "Qualitätsmetriken",
      rows,
      "noch keine Metriken",
      (row) => monitoringRow(row[0], row[1], "")
    );
  }

  function renderAiObservabilityLogs(logs) {
    const tbody = root.querySelector("[data-ai-observability-logs]");
    if (!tbody) return;
    tbody.innerHTML = "";
    if (!logs.length) {
      renderAdminEmptyState(
        tbody,
        "Noch keine AI-Logs im Zeitraum.",
        "Monitoring-Daten erscheinen, sobald AI-Anfragen verarbeitet wurden."
      );
      return;
    }
    logs.forEach((item) => {
      const row = document.createElement("tr");
      const action = document.createElement("td");
      const button = document.createElement("button");
      button.type = "button";
      button.className = "btn btn-ghost btn-sm";
      button.dataset.aiDebugSelect = item.chat_message_id;
      button.textContent = "Analysieren";
      action.appendChild(button);
      row.append(
        cell(dateTimeText(item.created_at)),
        cell(recordReference("Chat", item.chat_message_id)),
        pillCell(answerQualityLabel(item.answer_quality), answerQualityClass(item.answer_quality)),
        cell(confidenceLabel(item.confidence)),
        cell(numberText(item.source_count)),
        cell(msText(item.response_duration_ms || item.retrieval_duration_ms || 0)),
        action
      );
      tbody.appendChild(row);
    });
  }

  function answerQualityLabel(value) {
    const labels = {
      good: "gut",
      ok: "ok",
      warning: "prüfen",
      risk: "Risiko"
    };
    return labels[value] || text(value);
  }

  function answerQualityClass(value) {
    if (value === "good") return "is-active";
    if (value === "risk") return "is-error";
    if (value === "warning") return "is-stale";
    return "is-muted";
  }

  function renderDebugTools(debugTools) {
    const select = root.querySelector("[data-ai-debug-request]");
    const analysisTarget = root.querySelector("[data-ai-debug-analysis]");
    const promptTarget = root.querySelector("[data-ai-debug-prompt]");
    if (!select || !analysisTarget || !promptTarget) return;
    const selectedId = String(debugTools.selected_chat_message_id || "");
    select.innerHTML = "";
    (debugTools.available_requests || []).forEach((item) => {
      const option = document.createElement("option");
      option.value = item.chat_message_id;
      option.textContent = recordReference("Chat", item.chat_message_id);
      option.selected = String(item.chat_message_id) === selectedId;
      select.appendChild(option);
    });
    if (!select.options.length) {
      const option = document.createElement("option");
      option.value = "";
      option.textContent = "Keine Anfrage vorhanden";
      select.appendChild(option);
    }
    renderDebugAnalysis(analysisTarget, debugTools.request_analysis);
    promptTarget.textContent = promptDebugText(debugTools.prompt_blueprint);
  }

  function renderDebugAnalysis(target, analysis) {
    target.innerHTML = "";
    if (!analysis) {
      target.appendChild(statusRow("Analyse", "noch keine Anfrage vorhanden"));
      return;
    }
    const retrieval = analysis.retrieval || {};
    const contextBuilder = analysis.context_builder || {};
    const stats = contextBuilder.stats || {};
    target.appendChild(statusRow("Frage", redactSensitiveText(analysis.question, "Inhalt ausgeblendet")));
    target.appendChild(statusRow("Query-Typ", queryTypeLabel((analysis.query_understanding || {}).query_type)));
    target.appendChild(statusRow("Quellen", numberText(retrieval.source_count)));
    target.appendChild(statusRow("Suchdauer", msText(retrieval.retrieval_duration_ms || 0)));
    target.appendChild(statusRow("Context Sections", numberText((contextBuilder.sections || []).length)));
    target.appendChild(statusRow("Kontextbudget", numberText(stats.used_chars) + " / " + numberText(stats.max_chars)));
    target.appendChild(statusRow("Konfidenz", confidenceLabel(analysis.confidence)));
    target.appendChild(statusRow("Warnungen", numberText((analysis.quality_warnings || []).length)));
  }

  function promptDebugText(prompt) {
    if (!prompt) return "Kein Prompt-Blueprint geladen.";
    return [
      "System Prompt:",
      redactSensitiveText(prompt.system_prompt, "ausgeblendet"),
      "",
      "Kontextsicht:",
      prompt.context_visibility || "-",
      "",
      "Prompt Preview:",
      redactSensitiveText(prompt.prompt_preview, "ausgeblendet"),
      "",
      "Quellen:",
      (prompt.source_references || []).map((source) => "- " + sourceReferenceLabel(source)).join("\n") || "-",
      "",
      "Hinweis:",
      "Rohprompts, Chatfragen und Antworttexte werden in dieser Admin-Ansicht nicht angezeigt."
    ].join("\n");
  }

  async function loadAiObservability(chatMessageId) {
    const params = new URLSearchParams({ days: "30", limit: "10" });
    if (chatMessageId) params.set("chat_message_id", chatMessageId);
    const payload = await api("/api/v1/admin/ai/observability?" + params.toString());
    renderAiObservability(payload);
  }

  function retrievalEvaluationValue(metric, value) {
    if (metric === "recall_at_k" || metric === "mrr" || metric === "ndcg_at_k") {
      return percentText(value);
    }
    return numberText(value);
  }

  function retrievalEvaluationLabel(metric) {
    const labels = {
      recall_at_k: "Recall@K",
      mrr: "MRR",
      ndcg_at_k: "nDCG@K",
      permission_leak_count: "Permission Leaks",
      forbidden_source_hit_count: "Verbotene Quellen",
      no_result_count: "Keine Treffer"
    };
    return labels[metric] || text(metric);
  }

  function renderRetrievalEvaluationHistory(payload) {
    const history = (payload && payload.retrieval_evaluation_history) || {};
    const latest = history.latest || {};
    const regression = history.regression || {};
    const status = history.unavailable ? "warning" : (regression.regressed ? "warning" : "ok");
    const statusTarget = root.querySelector("[data-retrieval-evaluation-status]");
    if (statusTarget) {
      statusTarget.textContent = history.unavailable ? "Nicht verfügbar" : readinessLabel(status);
      statusTarget.className = "badge badge-ai " + healthClass(status);
    }

    root.querySelectorAll("[data-retrieval-evaluation-kpi]").forEach((target) => {
      const key = target.dataset.retrievalEvaluationKpi;
      target.textContent = retrievalEvaluationValue(key, latest[key]);
    });

    const regressionList = root.querySelector("[data-retrieval-evaluation-regression]");
    if (regressionList) {
      regressionList.innerHTML = "";
      const signals = regression.signals || [];
      if (!latest.id) {
        regressionList.appendChild(statusRow("Golden Eval", "noch keine Runs gespeichert"));
      } else if (!signals.length) {
        regressionList.appendChild(statusRow("Regression", "keine Regression erkannt"));
      } else {
        signals.forEach((signal) => {
          const delta = signal.delta > 0 ? "+" + signal.delta : signal.delta;
          regressionList.appendChild(statusRow(
            retrievalEvaluationLabel(signal.metric),
            retrievalEvaluationValue(signal.metric, signal.current) + " (" + delta + ")"
          ));
        });
      }
    }

    const runList = root.querySelector("[data-retrieval-evaluation-runs]");
    if (runList) {
      runList.innerHTML = "";
      const runs = history.runs || [];
      if (!runs.length) {
        runList.appendChild(statusRow("Historie", "keine gespeicherten Runs"));
      } else {
        runs.slice(0, 5).forEach((run) => {
          runList.appendChild(statusRow(
            dateTimeText(run.created_at),
            retrievalEvaluationValue("recall_at_k", run.recall_at_k)
              + " / "
              + retrievalEvaluationValue("mrr", run.mrr)
              + " / "
              + retrievalEvaluationValue("ndcg_at_k", run.ndcg_at_k)
          ));
        });
      }
    }
  }

  async function loadRetrievalTelemetry() {
    const telemetry = await api("/api/v1/admin/ai/retrieval-telemetry?days=30&limit=5");
    state.latestRetrievalTelemetry = telemetry;
    renderRetrievalSlo(telemetry);
    renderRetrievalEvaluationHistory(telemetry);
  }

  async function runRetrievalEvaluation() {
    const button = root.querySelector("[data-retrieval-evaluation-run]");
    setButtonBusy(button, true, "Eval laeuft...");
    setAdminMessage("Golden Quellenabruf Evaluation laeuft...");
    try {
      const result = await api("/api/v1/admin/ai/retrieval-evaluations/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ limit: 20 })
      });
      setAdminMessage(
        "Golden Eval #" + text(result.evaluation_run && result.evaluation_run.id)
        + " abgeschlossen: Recall "
        + percentText(result.recall_at_k)
        + ", MRR "
        + percentText(result.mrr)
        + "."
      );
      await loadRetrievalTelemetry();
    } catch (error) {
      setAdminMessage(safeErrorMessage(error, "Golden Eval ausfuehren"), true);
    } finally {
      setButtonBusy(button, false);
    }
  }

  function renderAiStatus(status) {
    state.latestAiStatus = status || {};
    const card = root.querySelector("[data-ai-model-card]");
    const label = root.querySelector("[data-ai-model-status]");
    const detail = root.querySelector("[data-ai-model-detail]");
    if (!card || !label || !detail) return;
    card.classList.remove("is-active", "is-stale", "is-error");
    card.classList.add(state.latestAiStatus.ready ? "is-active" : "is-stale");
    label.textContent = state.latestAiStatus.model || "lokal";
    detail.textContent = [
      state.latestAiStatus.provider || "provider offen",
      state.latestAiStatus.streaming_enabled ? "Streaming aktiv" : "Streaming aus",
      state.latestAiStatus.last_error ? "Fehler: " + state.latestAiStatus.last_error : "kein letzter Fehler"
    ].join(" - ");
    renderProviderConfiguration(state.latestAiStatus);
    renderCapabilities();
    renderOverviewState();
    renderSafetyFallbackSummary();
    renderSectionStatusSummaries();
    renderAiClaritySummary();
  }

  async function loadAiStatus() {
    const status = await api("/api/v1/ai/status");
    renderAiStatus(status);
  }

  function renderOverviewState() {
    const target = root.querySelector("[data-ai-overview-state]");
    if (!target) return;
    const aiReady = !state.latestAiStatus || state.latestAiStatus.ready !== false;
    const ragScore = Number((state.latestKnowledgeStatus || {}).readiness_score || 0);
    const sloStatus = (
      state.latestRetrievalTelemetry
      && state.latestRetrievalTelemetry.retrieval_slo
      && state.latestRetrievalTelemetry.retrieval_slo.status
    ) || "ok";
    const critical = !aiReady || ragScore < 40 || sloStatus === "critical";
    const warning = !critical && (ragScore < 80 || sloStatus === "warning");
    target.textContent = critical ? "Handlungsbedarf" : (warning ? "Beobachten" : "Betriebsbereit");
    target.className = "badge badge-ai " + (critical ? "is-error" : (warning ? "is-stale" : "is-active"));
  }

  function capabilityGroups() {
    const ragReady = Number((state.latestKnowledgeStatus || {}).readiness_score || 0) >= 60;
    const modelReady = !state.latestAiStatus || state.latestAiStatus.ready !== false;
    return {
      supported: [
        ["Permission-aware Quellenabruf", "Quellen werden rollen- und berechtigungsbewusst gefiltert."],
        ["Fehlerkatalog-Assistenz", "Fehlercodes, Ursachen und L&ouml;sungen bleiben strukturiert nutzbar."],
        ["Konfidenz & Nachvollziehbarkeit", "Antworten zeigen Score, Begr&uuml;ndung und verwendete Quellen."],
        ["Sicherheitsprüfungen", "Riskante Wartungshinweise werden vor und nach der Generierung gepr&uuml;ft."]
      ],
      partial: [
        [
          "RAG & Dokumentwissen",
          ragReady
            ? "Aktiv, aber abh&auml;ngig von Indexfrische und Quellenqualit&auml;t."
            : "Nur eingeschr&auml;nkt, solange Bereitschaft oder Textabschnitte fehlen."
        ],
        ["Golden Quellenabruf Evaluation", "Historie ist vorhanden, ben&ouml;tigt regelm&auml;&szlig;ige Runs f&uuml;r Trends."],
        [
          "OpenAI-Anbindung",
          modelReady ? "Konfiguriert; Fallbacks bleiben m&ouml;glich." : "Nicht voll bereit; lokale/strukturierte Antworten bleiben m&ouml;glich."
        ],
        ["Wissensnetz", "Nur-Lese Analyse verf&uuml;gbar; keine GraphDB erforderlich."]
      ],
      unsupported: [
        ["Autonome Maschinenfreigaben", "Die KI darf keine sicherheitskritischen Freigaben erteilen."],
        ["Arbeiten unter Spannung", "Gef&auml;hrliche Schritt-f&uuml;r-Schritt-Anleitungen werden entsch&auml;rft."],
        ["Ungefilterte Prompt-/Textabschnitt-Einsicht", "Admin-Debug bleibt prompt-sicher und zeigt keine sensiblen Rohtexte."]
      ]
    };
  }

  function renderCapabilityCard(target, title, detail, tone) {
    const card = document.createElement("article");
    const heading = document.createElement("strong");
    const textNode = document.createElement("p");
    card.className = "ai-capability-card " + tone;
    heading.innerHTML = title;
    textNode.innerHTML = detail;
    card.append(heading, textNode);
    target.appendChild(card);
  }

  function renderCapabilities() {
    const groups = capabilityGroups();
    Object.keys(groups).forEach((key) => {
      const target = root.querySelector('[data-ai-capabilities="' + key + '"]');
      if (!target) return;
      target.innerHTML = "";
      const tone = key === "supported" ? "is-active" : (key === "unsupported" ? "is-muted" : "is-stale");
      groups[key].forEach(([title, detail]) => renderCapabilityCard(target, title, detail, tone));
    });
  }

  function renderAnswerQualityGuide() {
    const target = root.querySelector("[data-ai-answer-quality-guide]");
    if (!target) return;
    target.innerHTML = "";
    [
      ["Quellen", "Verwendete Quellen und Dokumente werden als Chips angezeigt.", "is-active"],
      ["Konfidenzwert", "Hoch, mittel oder niedrig mit visueller Skala.", "is-active"],
      ["Antwortqualit&auml;t", "SLOs, Feedback und Golden Eval zeigen Qualit&auml;t &uuml;ber Zeit.", "is-stale"],
        ["Unsicherheit", "Niedrige Sicherheit, Konflikte und fehlende Quellen werden sichtbar markiert.", "is-stale"],
      ["Sicherheit", "Sicherheitsrelevante Inhalte erhalten klare Warnhinweise.", "is-error"],
      ["Dokumentbezug", "Abschnitte, Textabschnitte und Quelle-zu-Antwort-Bezug bleiben nachvollziehbar.", "is-active"]
    ].forEach(([title, detail, tone]) => {
      renderCapabilityCard(target, title, detail, tone);
    });
  }
  Object.assign(AdminAI, { loadSummary, retrievalSloLabel, retrievalSloValue, renderRetrievalSlo, monitoringStatus, monitoringKpiValue, renderMiniBar, renderMonitoringList, monitoringRow, renderAiObservability, renderTopQuestions, renderQuelleDistribution, renderRetrievalHits, renderQualityMetrics, renderAiObservabilityLogs, answerQualityLabel, answerQualityClass, renderDebugTools, renderDebugAnalysis, promptDebugText, loadAiObservability, retrievalEvaluationValue, retrievalEvaluationLabel, renderRetrievalEvaluationHistory, loadRetrievalTelemetry, runRetrievalEvaluation, renderAiStatus, loadAiStatus, renderOverviewState, capabilityGroups, renderCapabilityCard, renderCapabilities, renderAnswerQualityGuide });
})(window.MaintenanceAdminAI);

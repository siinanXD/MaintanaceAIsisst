(function () {
  const root = document.querySelector("[data-admin-ai-page]");
  if (!root) return;

  const QUALITY_STATUS_OPTIONS = [
    "draft",
    "ai_suggested",
    "technician_confirmed",
    "admin_approved",
    "outdated",
    "rejected"
  ];

  function token() {
    return window.localStorage.getItem("maintenance_access_token");
  }

  async function api(path, options) {
    const response = await fetch(path, {
      ...options,
      headers: {
        ...(options && options.headers ? options.headers : {}),
        Authorization: "Bearer " + token()
      }
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.message || payload.error || "API error");
    return payload.data || payload;
  }

  function text(value) {
    return value == null || value === "" ? "-" : String(value);
  }

  function numberText(value) {
    if (value == null || value === "") return "0";
    const number = Number(value);
    if (!Number.isFinite(number)) return text(value);
    return number.toLocaleString("de-DE");
  }

  function percentText(value) {
    const number = Number(value || 0);
    return Math.round(number * 100) + "%";
  }

  function msText(value) {
    return numberText(value) + " ms";
  }

  function moneyText(value) {
    const number = Number(value || 0);
    return "$" + number.toLocaleString("de-DE", {
      minimumFractionDigits: 0,
      maximumFractionDigits: 6
    });
  }

  function secondsText(value) {
    const number = Number(value || 0);
    return Math.round(number) + " s";
  }

  function cell(value) {
    const item = document.createElement("td");
    item.textContent = text(value);
    return item;
  }

  function statusPill(label, className) {
    const item = document.createElement("span");
    item.className = "status-pill " + (className || "");
    item.textContent = label;
    return item;
  }

  function pillCell(label, className) {
    const item = document.createElement("td");
    item.appendChild(statusPill(label, className));
    return item;
  }

  function statusRow(label, value) {
    const item = document.createElement("div");
    item.className = "stat-row";
    const labelElement = document.createElement("span");
    labelElement.textContent = label;
    const valueElement = document.createElement("strong");
    valueElement.textContent = text(value);
    item.append(labelElement, valueElement);
    return item;
  }

  function readinessLabel(status) {
    const labels = {
      ok: "bereit",
      warning: "Warnung",
      critical: "kritisch"
    };
    return labels[status] || text(status);
  }

  function healthClass(status) {
    if (status === "ok") return "is-active";
    if (status === "critical") return "is-error";
    return "is-stale";
  }

  function setHealthCard(key, status, detail) {
    const card = root.querySelector('[data-ai-health="' + key + '"]');
    if (!card) return;
    card.classList.remove("is-active", "is-stale", "is-error");
    card.classList.add(healthClass(status));
    const label = card.querySelector("[data-ai-health-label]");
    const detailElement = card.querySelector("[data-ai-health-detail]");
    if (label) label.textContent = readinessLabel(status);
    if (detailElement) detailElement.textContent = detail || "-";
  }

  function sourceTypeLabel(sourceType) {
    const labels = {
      upload: "Uploads",
      generated_document: "Berichte",
      error_entry: "Fehlerkatalog",
      task: "Tasks",
      machine: "Maschinen",
      inventory_material: "Inventar",
      maintenance_plan: "Wartungspläne",
      machine_manual: "Maschineninfos",
      shift_handover: "Schichtübergaben",
      manual_training: "Manuelles Training"
    };
    return labels[sourceType] || sourceType;
  }

  function knowledgeOriginKind(documentItem) {
    const sourceType = documentItem.source_type || "";
    const title = String(documentItem.title || "");
    if (sourceType === "manual_training" && title.startsWith("Tag-Bibliothek:")) {
      return "prebuilt";
    }
    if (sourceType === "upload" || sourceType === "manual_training") {
      return "manual";
    }
    return "automatic";
  }

  function knowledgeOriginLabel(origin) {
    const labels = {
      automatic: "Automatisch",
      manual: "Manuell",
      prebuilt: "Vorgefertigt"
    };
    return labels[origin] || "Automatisch";
  }

  function knowledgeOriginClass(origin) {
    const classes = {
      automatic: "is-source-automatic",
      manual: "is-source-manual",
      prebuilt: "is-source-prebuilt"
    };
    return classes[origin] || classes.automatic;
  }

  function knowledgeSourceCell(documentItem) {
    const item = document.createElement("td");
    const origin = knowledgeOriginKind(documentItem);
    item.className = "knowledge-source-cell";
    item.append(
      statusPill(sourceTypeLabel(documentItem.source_type), "is-muted"),
      statusPill(knowledgeOriginLabel(origin), knowledgeOriginClass(origin))
    );
    return item;
  }

  function qualityStatusLabel(status) {
    const labels = {
      draft: "Entwurf",
      ai_suggested: "AI-Vorschlag",
      technician_confirmed: "Techniker bestaetigt",
      admin_approved: "Admin freigegeben",
      outdated: "Veraltet",
      rejected: "Abgelehnt"
    };
    return labels[status] || text(status || "draft");
  }

  function qualityStatusClass(status) {
    if (status === "admin_approved" || status === "technician_confirmed") return "is-active";
    if (status === "outdated") return "is-stale";
    if (status === "rejected") return "is-error";
    return "is-muted";
  }

  function networkTypeLabel(type) {
    const labels = {
      machine: "Maschine",
      error: "Fehler",
      solution: "Loesung",
      document: "Dokument",
      inventory_part: "Inventar",
      recurring_issue: "Wiederkehrender Fehler",
      knowledge_gap: "Knowledge-Gap",
      component: "Komponente",
      sensor: "Sensor"
    };
    return labels[type] || text(type);
  }

  function queryTypeLabel(type) {
    const labels = {
      error_analysis: "Fehleranalyse",
      machine_question: "Maschinenfrage",
      inventory_question: "Inventarfrage",
      task_question: "Taskfrage",
      document_question: "Dokumentfrage",
      safety_question: "Sicherheitsfrage",
      general_question: "Allgemein",
      knowledge_gap: "Wissensluecke",
      trend_history_question: "Trend/Historie"
    };
    return labels[type] || text(type);
  }

  function networkTypeColor(type) {
    const colors = {
      machine: "#2563eb",
      error: "#dc2626",
      solution: "#16a34a",
      document: "#7c3aed",
      inventory_part: "#ca8a04",
      recurring_issue: "#ea580c",
      knowledge_gap: "#be123c",
      component: "#0f766e",
      sensor: "#4f46e5"
    };
    return colors[type] || "#475569";
  }

  function truncateLabel(value, maxLength) {
    const label = text(value);
    if (label.length <= maxLength) return label;
    return label.slice(0, maxLength - 3).trim() + "...";
  }

  function networkNodeRadius(node) {
    const weight = Number(node.weight || 0);
    return Math.max(9, Math.min(22, 8 + Math.sqrt(weight) * 3));
  }

  function networkNodeMap(nodes) {
    const map = {};
    (nodes || []).forEach((node) => {
      map[node.id] = node;
    });
    return map;
  }

  function networkPositions(nodes) {
    const width = 920;
    const height = 520;
    const center = { x: width / 2, y: height / 2 };
    const ringByType = {
      document: 0,
      machine: 1,
      error: 1,
      recurring_issue: 1,
      solution: 2,
      inventory_part: 2,
      knowledge_gap: 2,
      component: 3,
      sensor: 3
    };
    const ringRadii = [72, 154, 218, 252];
    const rings = [[], [], [], []];
    const positions = {};
    nodes.forEach((node) => {
      const ring = ringByType[node.type] == null ? 3 : ringByType[node.type];
      rings[ring].push(node);
    });
    rings.forEach((ringNodes, ringIndex) => {
      if (!ringNodes.length) return;
      ringNodes.sort((left, right) => String(left.id).localeCompare(String(right.id)));
      ringNodes.forEach((node, index) => {
        const angle = (-Math.PI / 2) + (2 * Math.PI * index) / ringNodes.length;
        const radius = ringRadii[ringIndex];
        positions[node.id] = {
          x: center.x + Math.cos(angle) * radius,
          y: center.y + Math.sin(angle) * radius
        };
      });
    });
    return { positions, width, height };
  }

  function metadataValue(value) {
    if (value == null || value === "") return "-";
    if (typeof value === "object") return JSON.stringify(value);
    return String(value);
  }

  function renderKnowledgeNetworkStats(stats) {
    const target = root.querySelector("[data-knowledge-network-stats]");
    if (!target) return;
    target.innerHTML = "";
    [
      ["Nodes", stats.node_count || 0],
      ["Edges", stats.edge_count || 0],
      ["Roh-Nodes", stats.raw_node_count || 0],
      ["Zeitraum", (stats.window_days || 30) + " Tage"]
    ].forEach(([label, value]) => {
      const card = document.createElement("article");
      const span = document.createElement("span");
      const strong = document.createElement("strong");
      card.className = "metric-card";
      span.textContent = label;
      strong.textContent = numberText(value).replace(" Tage", "") + (label === "Zeitraum" ? " Tage" : "");
      card.append(span, strong);
      target.appendChild(card);
    });
  }

  function renderKnowledgeNetworkLegend(payload) {
    const target = root.querySelector("[data-knowledge-network-legend]");
    if (!target) return;
    target.innerHTML = "";
    const stats = payload.stats || {};
    const nodesByType = stats.nodes_by_type || {};
    Object.keys(nodesByType).sort().forEach((type) => {
      target.appendChild(statusRow(
        networkTypeLabel(type),
        nodesByType[type] + " Nodes"
      ));
    });
    if (!Object.keys(nodesByType).length) {
      target.appendChild(statusRow("Legende", "Keine Netzwerkdaten vorhanden"));
    }
    const privacy = payload.privacy || {};
    target.appendChild(statusRow("Privacy", privacy.mode || "metadata_only"));
  }

  function renderKnowledgeNetworkDetail(node, payload) {
    const target = root.querySelector("[data-knowledge-network-detail]");
    if (!target) return;
    target.innerHTML = "";
    if (!node) {
      target.appendChild(statusRow("Auswahl", "Node anklicken"));
      return;
    }
    const edges = payload.edges || [];
    const nodes = networkNodeMap(payload.nodes || []);
    const connected = edges.filter((edge) => edge.source === node.id || edge.target === node.id);
    target.append(
      statusRow("Titel", node.title || node.label),
      statusRow("Typ", networkTypeLabel(node.type)),
      statusRow("Gewicht", Number(node.weight || 0).toFixed(1)),
      statusRow("Evidenz", node.evidence_count || 0),
      statusRow("Status", node.status || node.quality_status || "-"),
      statusRow("Quelle", node.source_type ? sourceTypeLabel(node.source_type) : "-")
    );
    Object.keys(node.metadata || {}).slice(0, 8).forEach((key) => {
      target.appendChild(statusRow(key, truncateLabel(metadataValue(node.metadata[key]), 80)));
    });
    if (connected.length) {
      connected.slice(0, 8).forEach((edge) => {
        const otherId = edge.source === node.id ? edge.target : edge.source;
        const other = nodes[otherId];
        target.appendChild(statusRow(
          edge.label || edge.type,
          other ? truncateLabel(other.label, 42) : otherId
        ));
      });
    } else {
      target.appendChild(statusRow("Verbindungen", "keine sichtbaren Kanten"));
    }
  }

  function renderKnowledgeNetworkCanvas(payload) {
    const container = root.querySelector("[data-knowledge-network-canvas]");
    if (!container) return;
    container.innerHTML = "";
    const nodes = payload.nodes || [];
    const edges = payload.edges || [];
    if (!nodes.length) {
      container.appendChild(statusRow("Knowledge Network", "Keine Daten fuer diesen Filter."));
      renderKnowledgeNetworkDetail(null, payload);
      return;
    }

    const svgNamespace = "http://www.w3.org/2000/svg";
    const layout = networkPositions(nodes);
    const svg = document.createElementNS(svgNamespace, "svg");
    svg.setAttribute("viewBox", "0 0 " + layout.width + " " + layout.height);
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", "Knowledge Network");
    svg.style.width = "100%";
    svg.style.minHeight = "440px";
    svg.style.display = "block";
    svg.style.background = "#f8fafc";
    svg.style.border = "1px solid #e2e8f0";
    svg.style.borderRadius = "8px";

    edges.forEach((edge) => {
      const sourcePosition = layout.positions[edge.source];
      const targetPosition = layout.positions[edge.target];
      if (!sourcePosition || !targetPosition) return;
      const line = document.createElementNS(svgNamespace, "line");
      line.setAttribute("x1", sourcePosition.x);
      line.setAttribute("y1", sourcePosition.y);
      line.setAttribute("x2", targetPosition.x);
      line.setAttribute("y2", targetPosition.y);
      line.setAttribute("stroke", edge.type === "source_relation" ? "#64748b" : "#cbd5e1");
      line.setAttribute("stroke-width", Math.max(1, Math.min(5, Number(edge.weight || 1) / 3)));
      line.setAttribute("stroke-opacity", edge.type === "source_relation" ? "0.7" : "0.45");
      const title = document.createElementNS(svgNamespace, "title");
      title.textContent = edge.label + " (" + Number(edge.weight || 0).toFixed(1) + ")";
      line.appendChild(title);
      svg.appendChild(line);
    });

    nodes.forEach((node) => {
      const position = layout.positions[node.id];
      if (!position) return;
      const group = document.createElementNS(svgNamespace, "g");
      const circle = document.createElementNS(svgNamespace, "circle");
      const label = document.createElementNS(svgNamespace, "text");
      const title = document.createElementNS(svgNamespace, "title");
      group.setAttribute("tabindex", "0");
      group.setAttribute("role", "button");
      group.dataset.networkNodeId = node.id;
      circle.setAttribute("cx", position.x);
      circle.setAttribute("cy", position.y);
      circle.setAttribute("r", networkNodeRadius(node));
      circle.setAttribute("fill", networkTypeColor(node.type));
      circle.setAttribute("fill-opacity", "0.88");
      circle.setAttribute("stroke", "#ffffff");
      circle.setAttribute("stroke-width", "2");
      label.setAttribute("x", position.x);
      label.setAttribute("y", position.y + networkNodeRadius(node) + 14);
      label.setAttribute("text-anchor", "middle");
      label.setAttribute("font-size", "11");
      label.setAttribute("fill", "#0f172a");
      label.textContent = truncateLabel(node.label, 22);
      title.textContent = node.title || node.label;
      group.append(circle, label, title);
      group.addEventListener("click", () => {
        svg.querySelectorAll("[data-network-node-id] circle").forEach((item) => {
          item.setAttribute("stroke", "#ffffff");
          item.setAttribute("stroke-width", "2");
        });
        circle.setAttribute("stroke", "#020617");
        circle.setAttribute("stroke-width", "4");
        renderKnowledgeNetworkDetail(node, payload);
      });
      group.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        group.dispatchEvent(new Event("click"));
      });
      svg.appendChild(group);
    });
    container.appendChild(svg);
    renderKnowledgeNetworkDetail(nodes[0], payload);
  }

  function renderKnowledgeNetwork(payload) {
    renderKnowledgeNetworkStats(payload.stats || {});
    renderKnowledgeNetworkLegend(payload);
    renderKnowledgeNetworkCanvas(payload);
  }

  async function loadKnowledgeNetwork() {
    const query = root.querySelector("[data-knowledge-network-search]").value;
    const source = root.querySelector("[data-knowledge-network-source]").value;
    const quality = root.querySelector("[data-knowledge-network-quality]").value;
    const focus = root.querySelector("[data-knowledge-network-focus]").value;
    const params = new URLSearchParams({
      limit: "120",
      q: query,
      source_type: source,
      quality_status: quality,
      focus
    });
    const data = await api("/api/v1/admin/ai/knowledge-network?" + params.toString());
    renderKnowledgeNetwork(data);
  }

  function renderRetrievalDebug(data) {
    const tbody = root.querySelector("[data-retrieval-debug-rows]");
    if (!tbody) return;
    tbody.innerHTML = "";
    const items = data.items || [];
    if (!items.length) {
      const row = document.createElement("tr");
      const empty = document.createElement("td");
      empty.colSpan = 7;
      empty.textContent = "Keine Retrieval-Debug-Daten fuer diesen Filter.";
      row.appendChild(empty);
      tbody.appendChild(row);
      return;
    }
    items.forEach((item) => {
      const row = document.createElement("tr");
      const conflicts = item.conflicts || {};
      const safety = item.safety || {};
      const sourceText = (item.used_sources || []).length + " Quellen";
      const conflictText = conflicts.has_conflicts
        ? conflicts.count + " Konflikte"
        : (safety.safety_relevant ? "Safety " + safety.risk_level : "-");
      row.append(
        cell(dateTimeText(item.created_at)),
        cell(truncateLabel(item.user_question, 80)),
        cell(queryTypeLabel(item.query_type)),
        cell(sourceText),
        cell(text(item.confidence && item.confidence.score) + " / " + text(item.confidence && item.confidence.level)),
        cell(conflictText),
        cell(text(item.retrieval_duration_ms) + " ms")
      );
      tbody.appendChild(row);
    });
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

  function lifecycleStepStatusLabel(status) {
    const labels = {
      available: "vorhanden",
      partial: "teilweise",
      missing: "offen"
    };
    return labels[status] || text(status);
  }

  function dateTimeText(value) {
    if (!value) return "-";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return text(value);
    return date.toLocaleString("de-DE");
  }

  function setAdminMessage(message, isError) {
    const target = root.querySelector("[data-ai-reindex-message]");
    if (!target) return;
    target.textContent = message || "";
    target.classList.toggle("is-error", Boolean(isError));
    if (message && window.maintenanceFrontend && window.maintenanceFrontend.showInterfaceToast) {
      window.maintenanceFrontend.showInterfaceToast(message, isError ? "error" : "info");
    }
  }

  function setButtonBusy(button, busy, busyText) {
    if (window.maintenanceFrontend && window.maintenanceFrontend.setButtonBusy) {
      window.maintenanceFrontend.setButtonBusy(button, busy, busyText);
      return;
    }
    if (!button) return;
    if (busy) {
      if (!button.dataset.originalText) button.dataset.originalText = button.textContent;
      button.disabled = true;
      button.setAttribute("aria-busy", "true");
      if (busyText) {
        button.dataset.busyText = busyText;
        button.textContent = busyText;
      }
      return;
    }
    button.disabled = false;
    button.removeAttribute("aria-busy");
    if (button.dataset.originalText) {
      if (!button.dataset.busyText || button.textContent === button.dataset.busyText) {
        button.textContent = button.dataset.originalText;
      }
      delete button.dataset.originalText;
      delete button.dataset.busyText;
    }
  }

  function setFormBusy(form, busy, busyText) {
    if (window.maintenanceFrontend && window.maintenanceFrontend.setFormBusy) {
      window.maintenanceFrontend.setFormBusy(form, busy, busyText);
      return;
    }
    if (!form) return;
    setButtonBusy(form.querySelector("button[type='submit']"), busy, busyText);
    form.setAttribute("aria-busy", String(Boolean(busy)));
  }

  async function loadSummary() {
    const summary = await api("/api/v1/admin/ai/summary?days=7");
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
  }

  function retrievalSloLabel(metric) {
    const labels = {
      retrieval_p95_ms: "P95 Retrieval",
      no_source_rate: "Ohne Quellen",
      low_confidence_rate: "Low Confidence",
      permission_filtered_candidate_count: "Permission Filter",
      negative_feedback_rate: "Negatives Feedback",
      safety_risk_count: "Safety Risiken",
      fallback_rate: "Fallback Rate",
      vector_sync_failure_count: "Vector Sync Fehler",
      stale_index_count: "Stale Index"
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
        warningList.appendChild(statusRow("SLO Status", "keine Warnungen"));
      } else {
        warnings.forEach((warning) => {
          warningList.appendChild(statusRow(
            retrievalSloLabel(warning.metric),
            readinessLabel(warning.status) + " ab " + retrievalSloValue(warning.metric, warning.threshold)
          ));
        });
      }
    }
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
    renderRetrievalSlo(telemetry);
    renderRetrievalEvaluationHistory(telemetry);
  }

  function renderWorkflowMetrics(workflows) {
    const tbody = root.querySelector("[data-ai-workflows]");
    if (!tbody) return;
    tbody.innerHTML = "";
    if (!workflows.length) {
      const row = document.createElement("tr");
      const empty = document.createElement("td");
      empty.colSpan = 7;
      empty.textContent = "Noch keine AI-Workflow-Metriken vorhanden.";
      row.appendChild(empty);
      tbody.appendChild(row);
      return;
    }
    workflows.slice(0, 8).forEach((workflow) => {
      const row = document.createElement("tr");
      row.append(
        cell(workflow.workflow),
        cell(numberText(workflow.events)),
        cell(percentText(workflow.fallback_rate)),
        cell(numberText(workflow.errors)),
        cell(numberText(workflow.total_tokens)),
        cell(moneyText(workflow.estimated_cost_usd)),
        cell(numberText(workflow.average_latency_ms) + " ms")
      );
      tbody.appendChild(row);
    });
  }

  function renderTopErrors(errors) {
    const list = root.querySelector("[data-ai-top-errors]");
    if (!list) return;
    list.innerHTML = "";
    if (!errors.length) {
      list.appendChild(statusRow("AI Fehler", "keine Fehler im Zeitraum"));
      return;
    }
    errors.slice(0, 6).forEach((item) => {
      list.appendChild(statusRow(item.error_category, numberText(item.count)));
    });
  }

  function lifecycleKpiValue(lifecycle, key) {
    const reviewQueue = lifecycle.review_queue || {};
    const qualityGate = lifecycle.rag_quality_gate || {};
    if (key === "needs_admin_approval") return reviewQueue.needs_admin_approval || 0;
    if (key === "non_approved_indexed_documents") {
      return qualityGate.non_approved_indexed_documents || 0;
    }
    return lifecycle[key] || 0;
  }

  function renderLifecycle(lifecycle) {
    const data = lifecycle || {};
    root.querySelectorAll("[data-lifecycle-kpi]").forEach((target) => {
      target.textContent = numberText(lifecycleKpiValue(data, target.dataset.lifecycleKpi));
    });

    const state = root.querySelector("[data-knowledge-lifecycle-state]");
    if (state) {
      const hasProblems = Number(data.problem_documents || 0) > 0;
      const reviewQueue = data.review_queue || {};
      const hasReview = Number(reviewQueue.needs_technician_review || 0) > 0
        || Number(reviewQueue.needs_admin_approval || 0) > 0
        || Number(reviewQueue.needs_refresh || 0) > 0;
      state.textContent = hasProblems ? "kritisch" : (hasReview ? "Review offen" : "bereit");
      state.className = "badge badge-ai "
        + (hasProblems ? "is-error" : (hasReview ? "is-stale" : "is-active"));
    }

    renderLifecycleReview(data.review_queue || {});
    renderLifecycleGate(data.rag_quality_gate || {});
    renderLifecycleActions(data.next_actions || []);
    renderLifecycleSteps(data.steps || []);
  }

  function renderLifecycleReview(reviewQueue) {
    const list = root.querySelector("[data-knowledge-lifecycle-review]");
    if (!list) return;
    list.innerHTML = "";
    list.append(
      statusRow("Techniker-Review", numberText(reviewQueue.needs_technician_review || 0)),
      statusRow("Admin-Freigabe", numberText(reviewQueue.needs_admin_approval || 0)),
      statusRow("Refresh", numberText(reviewQueue.needs_refresh || 0)),
      statusRow("Abgelehnt", numberText(reviewQueue.rejected || 0))
    );
  }

  function renderLifecycleGate(qualityGate) {
    const list = root.querySelector("[data-knowledge-lifecycle-gate]");
    if (!list) return;
    list.innerHTML = "";
    list.append(
      statusRow("Quality Gate", qualityGate.enabled ? "aktiv" : "diagnostisch"),
      statusRow(
        "Freigegeben indexiert",
        numberText(qualityGate.approved_indexed_documents || 0)
      ),
      statusRow(
        "Nicht freigegeben indexiert",
        numberText(qualityGate.non_approved_indexed_documents || 0)
      ),
      statusRow("Hinweis", qualityGate.reason || "-")
    );
  }

  function renderLifecycleActions(actions) {
    const list = root.querySelector("[data-knowledge-lifecycle-actions]");
    if (!list) return;
    list.innerHTML = "";
    const items = actions.length ? actions : ["Keine offenen Lifecycle-Aktionen."];
    items.slice(0, 6).forEach((action, index) => {
      list.appendChild(statusRow("Aktion " + (index + 1), action));
    });
  }

  function renderLifecycleSteps(steps) {
    const list = root.querySelector("[data-knowledge-lifecycle-steps]");
    if (!list) return;
    list.innerHTML = "";
    if (!steps.length) {
      list.appendChild(statusRow("Lifecycle", "keine Diagnostik vorhanden"));
      return;
    }
    steps.slice(0, 9).forEach((step) => {
      list.appendChild(statusRow(step.label, lifecycleStepStatusLabel(step.status)));
    });
  }

  function vectorSyncEventText(event) {
    if (!event) return "-";
    const timestamp = event.synced_at || event.failed_at;
    return "#" + text(event.document_id) + " " + dateTimeText(timestamp);
  }

  function renderVectorStoreStatus(vectorStatus) {
    const syncList = root.querySelector("[data-rag-vector-sync]");
    const issueList = root.querySelector("[data-rag-vector-issues]");
    const data = vectorStatus || {};
    if (syncList) {
      syncList.innerHTML = "";
      syncList.append(
        statusRow("Vector Backend", data.store || "-"),
        statusRow("Konfiguriert", data.configured_store || "-"),
        statusRow("Fallback", data.fallback_active ? "aktiv" : "nein"),
        statusRow("Soll Vektoren", numberText(data.expected_vector_count || 0)),
        statusRow("Ist Vektoren", data.actual_vector_count == null ? "-" : numberText(data.actual_vector_count)),
        statusRow("Letzter Index", dateTimeText(data.latest_indexed_at)),
        statusRow("Letzter Sync", vectorSyncEventText(data.last_successful_sync)),
        statusRow("Letzter Fehler", vectorSyncEventText(data.last_failed_sync))
      );
    }
    if (issueList) {
      issueList.innerHTML = "";
      issueList.append(
        statusRow("Reindex empfohlen", data.reindex_recommended ? "ja" : "nein"),
        statusRow("Stale Dokumente", numberText(data.stale_document_count || 0)),
        statusRow("Fehlende Chunks", numberText(data.missing_chunk_count || 0)),
        statusRow("Chunk Mismatch", numberText(data.chunk_mismatch_count || 0)),
        statusRow("Sync Fehler", numberText(data.vector_sync_failure_count || 0))
      );
      const reasons = data.reindex_reasons || [];
      if (reasons.length) {
        issueList.appendChild(statusRow("Grund", reasons.join(", ")));
      }
    }
  }

  function renderKnowledgeStatus(status) {
    ["documents", "indexed", "stale", "pending", "searchable_documents", "chunks"].forEach((key) => {
      const target = root.querySelector('[data-rag-kpi="' + key + '"]');
      if (target) target.textContent = text(status[key]);
    });

    const readiness = root.querySelector("[data-rag-readiness]");
    if (readiness) {
      readiness.textContent = status.diagnostics && status.diagnostics.ready
        ? "bereit"
        : "nicht bereit";
    }
    const score = Number(status.readiness_score || 0);
    const scoreTarget = root.querySelector("[data-rag-readiness-score]");
    if (scoreTarget) scoreTarget.textContent = score + "/100";
    const ragHealth = score >= 80 ? "ok" : (score >= 40 ? "warning" : "critical");
    setHealthCard(
      "rag",
      ragHealth,
      score + "/100 - " + (status.readiness_reasons || []).join(" ")
    );

    const sourceList = root.querySelector("[data-rag-source-status]");
    sourceList.innerHTML = "";
    const sourceTypes = status.source_types || [];
    if (!sourceTypes.length) {
      sourceList.appendChild(statusRow("Quellen", "Noch keine Daten indexiert"));
    } else {
      sourceTypes.forEach((item) => {
        sourceList.appendChild(statusRow(
          sourceTypeLabel(item.source_type),
          item.searchable_documents + "/" + item.documents + " durchsuchbar, " + item.chunks + " Chunks"
        ));
      });
    }

    const diagnostics = status.diagnostics || {};
    const diagnosticList = root.querySelector("[data-rag-diagnostics]");
    diagnosticList.innerHTML = "";
    diagnosticList.append(
      statusRow("RAG aktiv", diagnostics.rag_enabled ? "ja" : "nein"),
      statusRow("Vector Store", diagnostics.vector_store),
      statusRow("Embedding", diagnostics.embedding_provider),
      statusRow("Chunking", diagnostics.chunk_size + " / " + diagnostics.chunk_overlap),
      statusRow("Top K", diagnostics.top_k),
      statusRow("Scan Limit", diagnostics.scan_limit)
    );

    const reasonList = root.querySelector("[data-rag-readiness-reasons]");
    if (reasonList) {
      reasonList.innerHTML = "";
      (status.readiness_reasons || ["Keine Readiness-Daten vorhanden."]).forEach((reason) => {
        reasonList.appendChild(statusRow("Readiness", reason));
      });
    }

    const problemList = root.querySelector("[data-rag-problem-documents]");
    if (problemList) {
      problemList.innerHTML = "";
      const problemDocuments = status.problem_documents || [];
      if (!problemDocuments.length) {
        problemList.appendChild(statusRow("Problemdokumente", "keine offenen Quellen"));
      } else {
        problemDocuments.forEach((documentItem) => {
          problemList.appendChild(statusRow(
            "#" + documentItem.id + " " + sourceTypeLabel(documentItem.source_type),
            documentItem.status + " - " + documentItem.title
          ));
        });
      }
    }

    renderLifecycle(status.lifecycle || {});
    renderVectorStoreStatus(status.vector_store || {});
  }

  async function loadKnowledgeStatus() {
    const status = await api("/api/v1/admin/ai/knowledge/status");
    renderKnowledgeStatus(status);
  }

  async function loadJobs() {
    const data = await api("/api/v1/admin/jobs?job_type=rag_reindex&limit=10");
    const tbody = root.querySelector("[data-ai-jobs]");
    const count = root.querySelector("[data-ai-job-count]");
    const statusList = root.querySelector("[data-ai-job-status]");
    tbody.innerHTML = "";
    if (count) count.textContent = data.pagination.total + " Jobs";
    const statusCounts = {};
    let oldestQueued = null;
    data.items.forEach((job) => {
      statusCounts[job.status] = (statusCounts[job.status] || 0) + 1;
      if (job.status === "queued" && !oldestQueued) oldestQueued = job;
      const row = document.createElement("tr");
      row.dataset.jobStatus = job.status;
      row.append(
        cell(job.id),
        cell(job.job_type),
        cell(job.status),
        cell(job.attempts + "/" + job.max_attempts),
        cell(job.error_message || JSON.stringify(job.result || {}))
      );
      tbody.appendChild(row);
    });
    if (!data.items.length) {
      const row = document.createElement("tr");
      const empty = document.createElement("td");
      empty.colSpan = 5;
      empty.textContent = "Keine RAG-Reindex-Jobs vorhanden.";
      row.appendChild(empty);
      tbody.appendChild(row);
    }
    if (statusList) {
      statusList.innerHTML = "";
      statusList.append(
        statusRow("Queued", statusCounts.queued || 0),
        statusRow("Running", statusCounts.running || 0),
        statusRow("Failed", statusCounts.failed || 0),
        statusRow("Done", statusCounts.done || 0),
        statusRow("Aeltester queued Job", oldestQueued ? "#" + oldestQueued.id : "-")
      );
    }
  }

  function renderOperationsMetrics(data) {
    const database = data.database || {};
    const jobs = data.background_jobs || {};
    const ai = data.ai || {};
    const rag = data.rag || {};
    const generated = root.querySelector("[data-ops-generated]");
    const dbLatency = root.querySelector('[data-ops-kpi="database_latency_ms"]');
    const queueLength = root.querySelector('[data-ops-kpi="queue_length"]');
    const runningJobs = root.querySelector('[data-ops-kpi="running_jobs"]');
    const failedJobs = root.querySelector('[data-ops-kpi="failed_jobs"]');
    const aiLatency = root.querySelector('[data-ops-kpi="ai_latency_ms"]');
    const ragStale = root.querySelector('[data-ops-kpi="rag_stale_ratio"]');
    const oldestQueuedAge = root.querySelector('[data-ops-kpi="oldest_queued_age"]');
    const jobAvgDuration = root.querySelector('[data-ops-kpi="job_avg_duration"]');
    if (generated) generated.textContent = data.generated_at ? new Date(data.generated_at).toLocaleTimeString("de-DE") : "-";
    if (dbLatency) dbLatency.textContent = text(database.latency_ms) + " ms";
    if (queueLength) queueLength.textContent = text(jobs.queue_length);
    if (runningJobs) runningJobs.textContent = text(jobs.running);
    if (failedJobs) failedJobs.textContent = text(jobs.failed);
    if (aiLatency) aiLatency.textContent = text(ai.avg_latency_ms) + " ms";
    if (ragStale) ragStale.textContent = Math.round((rag.stale_ratio || 0) * 100) + "%";
    if (oldestQueuedAge) oldestQueuedAge.textContent = secondsText(jobs.oldest_queued_age_seconds);
    if (jobAvgDuration) jobAvgDuration.textContent = secondsText(jobs.recent_avg_duration_seconds);
    const queueStatus = jobs.failed ? "critical" : (jobs.queue_length || jobs.running ? "warning" : "ok");
    setHealthCard(
      "queue",
      queueStatus,
      (jobs.queue_length || 0) + " queued, " + (jobs.running || 0) + " running, "
      + (jobs.failed || 0) + " failed"
    );

    const slowList = root.querySelector("[data-ops-slow-endpoints]");
    if (!slowList) return;
    slowList.innerHTML = "";
    const slowEndpoints = (data.requests && data.requests.slow_endpoints) || [];
    if (!slowEndpoints.length) {
      slowList.appendChild(statusRow("Slow Endpoints", "noch keine Messwerte"));
      return;
    }
    slowEndpoints.slice(0, 5).forEach((item) => {
      slowList.appendChild(
        statusRow(
          item.endpoint,
          item.avg_duration_ms + " ms avg / " + item.slow_count + " slow"
        )
      );
    });
  }

  async function loadOperationsMetrics() {
    const data = await api("/api/v1/health/operations");
    renderOperationsMetrics(data);
  }

  async function loadEvents() {
    const error = root.querySelector("[data-ai-event-error]").value;
    const data = await api("/api/v1/admin/ai/events?limit=20&error=" + encodeURIComponent(error));
    const tbody = root.querySelector("[data-ai-events]");
    tbody.innerHTML = "";
    data.items.forEach((event) => {
      const row = document.createElement("tr");
      row.append(
        cell(event.created_at),
        cell(event.workflow),
        cell(event.status),
        cell(event.error_category),
        cell(event.total_tokens)
      );
      tbody.appendChild(row);
    });
  }

  async function loadChats() {
    const query = root.querySelector("[data-ai-chat-search]").value;
    const data = await api("/api/v1/admin/ai/chats?limit=20&q=" + encodeURIComponent(query));
    const list = root.querySelector("[data-ai-chats]");
    list.innerHTML = "";
    data.items.forEach((chat) => {
      const item = document.createElement("article");
      item.className = "list-card";
      const user = document.createElement("strong");
      const prompt = document.createElement("p");
      const meta = document.createElement("small");
      user.textContent = text(chat.user && chat.user.username);
      prompt.textContent = text(chat.message);
      meta.textContent = text(chat.response_type) + " - " + text(chat.created_at);
      item.append(user, prompt, meta);
      list.appendChild(item);
    });
  }

  async function loadKnowledgeGaps() {
    const data = await api("/api/v1/admin/ai/knowledge-gaps?status=open&limit=10");
    const tbody = root.querySelector("[data-ai-knowledge-gaps]");
    const count = root.querySelector("[data-ai-knowledge-gap-count]");
    if (count) count.textContent = numberText(data.open_count || 0) + " offen";
    if (!tbody) return;
    tbody.innerHTML = "";
    if (!data.items.length) {
      const row = document.createElement("tr");
      const empty = document.createElement("td");
      empty.colSpan = 7;
      empty.textContent = "Keine offenen Knowledge Gaps.";
      row.appendChild(empty);
      tbody.appendChild(row);
      return;
    }
    data.items.forEach((gap) => {
      const row = document.createElement("tr");
      row.append(
        cell(gap.question),
        cell(gap.department),
        cell(gap.machine),
        cell(gap.status),
        cell(gap.occurrence_count),
        cell(dateTimeText(gap.last_seen_at))
      );
      tbody.appendChild(row);
    });
  }

  function trainingPayload(form) {
    return {
      title: form.elements.title.value.trim(),
      category: form.elements.category.value.trim() || "wartung",
      department: form.elements.department.value.trim(),
      keywords: form.elements.keywords.value.trim(),
      question: form.elements.question.value.trim(),
      answer: form.elements.answer.value.trim(),
      is_active: form.elements.is_active.checked,
      priority: Number(form.elements.priority.value || 50)
    };
  }

  function resetTrainingForm() {
    const form = root.querySelector("[data-ai-training-form]");
    if (!form) return;
    form.reset();
    form.elements.id.value = "";
    form.elements.is_active.checked = true;
    form.elements.priority.value = "50";
    const title = root.querySelector("[data-ai-training-editor-title]");
    const status = root.querySelector("[data-ai-training-editor-status]");
    if (title) title.textContent = "Neuer Trainingseintrag";
    if (status) {
      status.textContent = "Nach dem Speichern neu indexieren";
      status.className = "status-pill is-stale";
    }
    root.querySelectorAll(".training-card.is-selected").forEach((item) => {
      item.classList.remove("is-selected");
    });
  }

  function fillTrainingForm(entry) {
    const form = root.querySelector("[data-ai-training-form]");
    if (!form) return;
    form.elements.id.value = entry.id;
    form.elements.title.value = entry.title || "";
    form.elements.category.value = entry.category || "";
    form.elements.department.value = entry.department || "";
    form.elements.keywords.value = entry.keywords || "";
    form.elements.question.value = entry.question || "";
    form.elements.answer.value = entry.answer || "";
    form.elements.is_active.checked = Boolean(entry.is_active);
    form.elements.priority.value = entry.priority || 50;
    const title = root.querySelector("[data-ai-training-editor-title]");
    const status = root.querySelector("[data-ai-training-editor-status]");
    if (title) title.textContent = "Training bearbeiten";
    if (status) {
      status.textContent = entry.is_active ? "Aktiv im RAG-Index" : "Inaktiv, wird nicht genutzt";
      status.className = "status-pill " + (entry.is_active ? "is-active" : "is-muted");
    }
    root.querySelectorAll(".training-card").forEach((item) => {
      item.classList.toggle("is-selected", item.dataset.trainingId === String(entry.id));
    });
    form.elements.title.focus();
  }

  async function loadTraining() {
    const query = root.querySelector("[data-ai-training-search]").value;
    const active = root.querySelector("[data-ai-training-active]").value;
    const data = await api(
      "/api/v1/admin/ai/training?limit=50&q="
      + encodeURIComponent(query)
      + "&active="
      + encodeURIComponent(active)
    );
    const list = root.querySelector("[data-ai-training]");
    const selectedId = root.querySelector("[data-ai-training-form]").elements.id.value;
    list.innerHTML = "";
    if (!data.items.length) {
      const empty = document.createElement("div");
      empty.className = "admin-empty";
      empty.textContent = "Keine passenden Trainingseinträge gefunden.";
      list.appendChild(empty);
      return;
    }
    data.items.forEach((entry) => {
      const item = document.createElement("article");
      item.className = "training-card";
      item.dataset.trainingId = entry.id;
      item.classList.toggle("is-selected", selectedId === String(entry.id));
      const title = document.createElement("strong");
      const question = document.createElement("p");
      const meta = document.createElement("div");
      const actions = document.createElement("div");
      const editButton = document.createElement("button");
      const deleteButton = document.createElement("button");
      title.textContent = text(entry.title);
      question.textContent = text(entry.question);
      meta.className = "training-card-meta";
      meta.append(
        statusPill(entry.is_active ? "aktiv" : "inaktiv", entry.is_active ? "is-active" : "is-muted"),
        statusPill("Priorität " + text(entry.priority), ""),
        statusPill(text(entry.category), ""),
        statusPill(text(entry.department || "alle Abteilungen"), "")
      );
      actions.className = "training-card-actions";
      editButton.type = "button";
      editButton.className = "btn btn-secondary btn-sm";
      editButton.textContent = "Bearbeiten";
      editButton.addEventListener("click", () => fillTrainingForm(entry));
      deleteButton.type = "button";
      deleteButton.className = "btn btn-ghost btn-sm";
      deleteButton.dataset.deleteTraining = entry.id;
      deleteButton.textContent = "Löschen";
      actions.append(editButton, deleteButton);
      item.append(title, question, meta, actions);
      list.appendChild(item);
    });
  }

  async function loadKnowledge() {
    const query = root.querySelector("[data-ai-knowledge-search]").value;
    const source = root.querySelector("[data-ai-knowledge-source]").value;
    const status = root.querySelector("[data-ai-knowledge-status]").value;
    const quality = root.querySelector("[data-ai-knowledge-quality]").value;
    const data = await api(
      "/api/v1/admin/ai/knowledge?limit=50&q="
      + encodeURIComponent(query)
      + "&source_type="
      + encodeURIComponent(source)
      + "&status="
      + encodeURIComponent(status)
      + "&quality_status="
      + encodeURIComponent(quality)
    );
    const tbody = root.querySelector("[data-ai-knowledge]");
    tbody.innerHTML = "";
    if (!data.items.length) {
      const row = document.createElement("tr");
      const empty = document.createElement("td");
      empty.colSpan = 7;
      empty.textContent = "Keine Wissensquellen für diesen Filter.";
      row.appendChild(empty);
      tbody.appendChild(row);
      return;
    }
    data.items.forEach((documentItem) => {
      const row = document.createElement("tr");
      const actions = document.createElement("td");
      const reindexButton = document.createElement("button");
      const queueButton = document.createElement("button");
      const qualitySelect = knowledgeQualitySelect(documentItem);
      const qualityButton = document.createElement("button");
      reindexButton.type = "button";
      reindexButton.className = "btn btn-secondary btn-sm";
      reindexButton.dataset.reindexKnowledge = documentItem.id;
      reindexButton.textContent = "Indexieren";
      queueButton.type = "button";
      queueButton.className = "btn btn-ghost btn-sm";
      queueButton.dataset.queueKnowledge = documentItem.id;
      queueButton.textContent = "Job planen";
      qualityButton.type = "button";
      qualityButton.className = "btn btn-secondary btn-sm";
      qualityButton.dataset.updateKnowledgeQuality = documentItem.id;
      qualityButton.textContent = "Status setzen";
      const button = document.createElement("button");
      button.type = "button";
      button.className = "btn btn-ghost btn-sm";
      button.dataset.deleteKnowledge = documentItem.id;
      button.textContent = "Löschen";
      actions.className = "table-actions";
      actions.append(reindexButton, queueButton, qualitySelect, qualityButton, button);
      row.dataset.knowledgeStatus = documentItem.status;
      row.dataset.knowledgeQualityStatus = documentItem.quality_status || "draft";
      row.setAttribute("data-knowledge-origin", knowledgeOriginKind(documentItem));
      row.append(
        cell(documentItem.title),
        knowledgeSourceCell(documentItem),
        cell(documentItem.status),
        pillCell(
          qualityStatusLabel(documentItem.quality_status),
          qualityStatusClass(documentItem.quality_status)
        ),
        cell(documentItem.chunk_count),
        cell(documentItem.department),
        actions
      );
      tbody.appendChild(row);
    });
  }

  function knowledgeQualitySelect(documentItem) {
    const select = document.createElement("select");
    select.className = "input input-bordered";
    select.dataset.knowledgeQualitySelect = documentItem.id;
    select.setAttribute("aria-label", "Knowledge-Qualitätsstatus setzen");
    QUALITY_STATUS_OPTIONS.forEach((status) => {
      const option = document.createElement("option");
      option.value = status;
      option.textContent = qualityStatusLabel(status);
      option.selected = status === (documentItem.quality_status || "draft");
      select.appendChild(option);
    });
    return select;
  }

  async function refreshAll() {
    await Promise.all([
      loadSummary(),
      loadEvents(),
      loadChats(),
      loadKnowledgeGaps(),
      loadTraining(),
      loadKnowledge(),
      loadKnowledgeNetwork(),
      loadRetrievalDebug(),
      loadRetrievalTelemetry(),
      loadKnowledgeStatus(),
      loadJobs(),
      loadOperationsMetrics()
    ]);
  }

  root.querySelector("[data-ai-event-error]").addEventListener("change", loadEvents);
  root.querySelector("[data-ai-chat-search]").addEventListener("input", () => {
    window.clearTimeout(root._chatTimer);
    root._chatTimer = window.setTimeout(loadChats, 250);
  });
  root.querySelector("[data-ai-training-search]").addEventListener("input", () => {
    window.clearTimeout(root._trainingTimer);
    root._trainingTimer = window.setTimeout(loadTraining, 250);
  });
  root.querySelector("[data-ai-training-active]").addEventListener("change", loadTraining);
  root.querySelector("[data-ai-training-reset]").addEventListener("click", resetTrainingForm);
  root.querySelector("[data-ai-knowledge-search]").addEventListener("input", () => {
    window.clearTimeout(root._knowledgeTimer);
    root._knowledgeTimer = window.setTimeout(loadKnowledge, 250);
  });
  root.querySelector("[data-ai-knowledge-source]").addEventListener("change", loadKnowledge);
  root.querySelector("[data-ai-knowledge-status]").addEventListener("change", loadKnowledge);
  root.querySelector("[data-ai-knowledge-quality]").addEventListener("change", loadKnowledge);
  root.querySelector("[data-knowledge-network-search]").addEventListener("input", () => {
    window.clearTimeout(root._knowledgeNetworkTimer);
    root._knowledgeNetworkTimer = window.setTimeout(loadKnowledgeNetwork, 250);
  });
  root.querySelector("[data-knowledge-network-focus]").addEventListener("input", () => {
    window.clearTimeout(root._knowledgeNetworkFocusTimer);
    root._knowledgeNetworkFocusTimer = window.setTimeout(loadKnowledgeNetwork, 250);
  });
  root.querySelector("[data-knowledge-network-source]").addEventListener("change", loadKnowledgeNetwork);
  root.querySelector("[data-knowledge-network-quality]").addEventListener("change", loadKnowledgeNetwork);
  root.querySelector("[data-knowledge-network-refresh]").addEventListener("click", loadKnowledgeNetwork);
  root.querySelector("[data-retrieval-debug-search]").addEventListener("input", () => {
    window.clearTimeout(root._retrievalDebugTimer);
    root._retrievalDebugTimer = window.setTimeout(loadRetrievalDebug, 250);
  });
  root.querySelector("[data-retrieval-debug-type]").addEventListener("change", loadRetrievalDebug);
  root.querySelector("[data-retrieval-debug-refresh]").addEventListener("click", loadRetrievalDebug);
  root.querySelector("[data-ai-training-form]").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const entryId = form.elements.id.value;
    const path = entryId
      ? "/api/v1/admin/ai/training/" + entryId
      : "/api/v1/admin/ai/training";
    const method = entryId ? "PUT" : "POST";
    setFormBusy(form, true, "Speichert...");
    setAdminMessage(entryId ? "Training wird aktualisiert..." : "Training wird gespeichert...");
    try {
      await api(path, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(trainingPayload(form))
      });
      resetTrainingForm();
      setAdminMessage("Training gespeichert. Bitte veraltete Quellen indexieren.");
      await Promise.all([loadTraining(), loadKnowledge(), loadKnowledgeNetwork(), loadKnowledgeStatus()]);
    } catch (error) {
      setAdminMessage(error.message, true);
    } finally {
      setFormBusy(form, false);
    }
  });
  async function runReindex(button, path) {
    button.disabled = true;
    setAdminMessage("Index wird neu aufgebaut...");
    try {
      const result = await api(path, { method: "POST" });
      setAdminMessage(
        "Indexiert: " + result.indexed + " Dokumente, " + result.chunks + " Chunks."
      );
      await Promise.all([
        loadKnowledge(),
        loadKnowledgeNetwork(),
        loadKnowledgeStatus(),
        loadJobs(),
        loadOperationsMetrics()
      ]);
    } catch (error) {
      setAdminMessage(error.message, true);
    } finally {
      button.disabled = false;
    }
  }

  root.querySelector("[data-ai-reindex]").addEventListener("click", async () => {
    await runReindex(
      root.querySelector("[data-ai-reindex]"),
      "/api/v1/admin/ai/knowledge/reindex"
    );
  });
  root.querySelector("[data-ai-reindex-stale]").addEventListener("click", async () => {
    await runReindex(
      root.querySelector("[data-ai-reindex-stale]"),
      "/api/v1/admin/ai/knowledge/reindex?mode=stale"
    );
  });
  root.querySelector("[data-ai-queue-stale]").addEventListener("click", async () => {
    const button = root.querySelector("[data-ai-queue-stale]");
    setButtonBusy(button, true, "Plant...");
    setAdminMessage("RAG-Reindex-Job wird eingeplant...");
    try {
      const job = await api("/api/v1/admin/ai/knowledge/reindex/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: "stale" })
      });
      setAdminMessage("Job #" + job.id + " wurde eingeplant.");
      await Promise.all([loadJobs(), loadOperationsMetrics()]);
    } catch (error) {
      setAdminMessage(error.message, true);
    } finally {
      setButtonBusy(button, false);
    }
  });
  root.querySelector("[data-ai-knowledge-upload]").addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    setFormBusy(event.currentTarget, true, "Lädt...");
    setAdminMessage("Dokument wird hochgeladen...");
    try {
      await api("/api/v1/admin/ai/knowledge/upload", { method: "POST", body: formData });
      event.currentTarget.reset();
      setAdminMessage("Dokument hochgeladen und indexiert.");
      await Promise.all([
        loadKnowledge(),
        loadKnowledgeNetwork(),
        loadKnowledgeStatus(),
        loadJobs(),
        loadOperationsMetrics()
      ]);
    } catch (error) {
      setAdminMessage(error.message, true);
    } finally {
      setFormBusy(event.currentTarget, false);
    }
  });
  root.addEventListener("click", async (event) => {
    const trainingDeleteButton = event.target.closest("[data-delete-training]");
    if (trainingDeleteButton) {
      setButtonBusy(trainingDeleteButton, true, "Löscht...");
      try {
        await api("/api/v1/admin/ai/training/" + trainingDeleteButton.dataset.deleteTraining, {
          method: "DELETE"
        });
        setAdminMessage("Training gelöscht.");
        await Promise.all([
          loadTraining(),
          loadKnowledge(),
          loadKnowledgeNetwork(),
          loadKnowledgeStatus()
        ]);
      } catch (error) {
        setAdminMessage(error.message, true);
      } finally {
        setButtonBusy(trainingDeleteButton, false);
      }
      return;
    }

    const qualityButton = event.target.closest("[data-update-knowledge-quality]");
    if (qualityButton) {
      const row = qualityButton.closest("tr");
      const select = row && row.querySelector("[data-knowledge-quality-select]");
      if (!select) return;
      setButtonBusy(qualityButton, true, "Speichert...");
      setAdminMessage("Knowledge-Qualitätsstatus wird aktualisiert...");
      try {
        const documentItem = await api(
          "/api/v1/admin/ai/knowledge/"
          + qualityButton.dataset.updateKnowledgeQuality
          + "/quality-status",
          {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ quality_status: select.value })
          }
        );
        setAdminMessage(
          "Knowledge #" + documentItem.id + " ist "
          + qualityStatusLabel(documentItem.quality_status) + "."
        );
        await Promise.all([
          loadKnowledge(),
          loadKnowledgeNetwork(),
          loadKnowledgeStatus(),
          loadOperationsMetrics()
        ]);
      } catch (error) {
        setAdminMessage(error.message, true);
      } finally {
        setButtonBusy(qualityButton, false);
      }
      return;
    }

    const reindexButton = event.target.closest("[data-reindex-knowledge]");
    if (reindexButton) {
      reindexButton.disabled = true;
      setAdminMessage("Dokument wird neu indexiert...");
      try {
        const documentItem = await api(
          "/api/v1/admin/ai/knowledge/" + reindexButton.dataset.reindexKnowledge + "/reindex",
          { method: "POST" }
        );
        setAdminMessage(
          "Dokument " + documentItem.id + " ist " + documentItem.status + "."
        );
        await Promise.all([
          loadKnowledge(),
          loadKnowledgeNetwork(),
          loadKnowledgeStatus(),
          loadJobs(),
          loadOperationsMetrics()
        ]);
      } catch (error) {
        setAdminMessage(error.message, true);
      } finally {
        reindexButton.disabled = false;
      }
      return;
    }

    const queueButton = event.target.closest("[data-queue-knowledge]");
    if (queueButton) {
      setButtonBusy(queueButton, true, "Plant...");
      setAdminMessage("Dokument-Reindex-Job wird eingeplant...");
      try {
        const job = await api("/api/v1/admin/ai/knowledge/reindex/jobs", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ document_id: Number(queueButton.dataset.queueKnowledge) })
        });
        setAdminMessage("Job #" + job.id + " wurde eingeplant.");
        await Promise.all([loadJobs(), loadOperationsMetrics()]);
      } catch (error) {
        setAdminMessage(error.message, true);
      } finally {
        setButtonBusy(queueButton, false);
      }
      return;
    }

    const button = event.target.closest("[data-delete-knowledge]");
    if (!button) return;
    setButtonBusy(button, true, "Löscht...");
    try {
      await api("/api/v1/admin/ai/knowledge/" + button.dataset.deleteKnowledge, { method: "DELETE" });
      setAdminMessage("Dokument gelöscht.");
      await Promise.all([
        loadKnowledge(),
        loadKnowledgeNetwork(),
        loadKnowledgeStatus(),
        loadJobs(),
        loadOperationsMetrics()
      ]);
    } catch (error) {
      setAdminMessage(error.message, true);
    } finally {
      setButtonBusy(button, false);
    }
  });

  refreshAll().catch((error) => {
    setAdminMessage("AI Admin konnte nicht vollständig geladen werden: " + error.message, true);
  });
})();

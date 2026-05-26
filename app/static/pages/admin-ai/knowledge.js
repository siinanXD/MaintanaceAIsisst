/**
 * Admin AI knowledge module.
 * Registers view helpers on the shared MaintenanceAdminAI runtime.
 */
(function registerAdminAiModule(AdminAI) {
  const { root, adminView, state, QUALITY_STATUS_OPTIONS } = AdminAI;
  const api = (...args) => AdminAI.api(...args);
  const dateTimeText = (...args) => AdminAI.dateTimeText(...args);
  const numberText = (...args) => AdminAI.numberText(...args);
  const statusPill = (...args) => AdminAI.statusPill(...args);
  const statusRow = (...args) => AdminAI.statusRow(...args);
  const text = (...args) => AdminAI.text(...args);
  function sourceTypeLabel(sourceType) {
    const labels = {
      upload: "Uploads",
      generated_document: "Berichte",
      error_entry: "Fehlerkatalog",
      task: "Aufgaben",
      machine: "Maschinen",
      inventory_material: "Inventar",
      maintenance_plan: "Wartungspläne",
      machine_manual: "Maschineninfos",
      shift_handover: "Schichtübergaben",
      manual_training: "Manuelles Training"
    };
    return labels[sourceType] || sourceType;
  }

  function dataQuelleDefinitions() {
    return [
      {
        key: "error_catalog",
        label: "Fehlerkatalog",
        description: "Fehlercodes, Ursachen und L&ouml;sungen",
        types: ["error_entry"]
      },
      {
        key: "documents",
        label: "Dokumente",
        description: "Uploads, Berichte und Maschinenhandb&uuml;cher",
        types: ["upload", "generated_document", "machine_manual", "maintenance_plan"]
      },
      {
        key: "tasks",
        label: "Aufgaben",
        description: "Wartungs- und Eskalationsaufgaben",
        types: ["task"]
      },
      {
        key: "machines",
        label: "Maschinen",
        description: "Anlagen, Komponenten und Maschinenkontext",
        types: ["machine"]
      },
      {
        key: "shift_data",
        label: "Schichtdaten",
        description: "Schicht&uuml;bergaben und operative Hinweise",
        types: ["shift_handover"]
      },
      {
        key: "training",
        label: "Trainingsdaten",
        description: "Manuelles Assistant-Training",
        types: ["manual_training"]
      }
    ];
  }

  function sourceMetrics(status, types) {
    const sourceTypes = status.source_types || [];
    const matching = sourceTypes.filter((item) => types.includes(item.source_type));
    return matching.reduce((result, item) => ({
      documents: result.documents + Number(item.documents || 0),
      searchable: result.searchable + Number(item.searchable_documents || 0),
      chunks: result.chunks + Number(item.chunks || 0),
      active: result.active || Boolean(item.searchable),
    }), { documents: 0, searchable: 0, chunks: 0, active: false });
  }

  function sourceHealth(metrics, ragEnabled) {
    if (!ragEnabled) {
      return { label: "RAG aus", className: "is-muted", detail: "Strukturierte Daten bleiben nutzbar" };
    }
    if (!metrics.documents) {
      return { label: "leer", className: "is-muted", detail: "noch keine Quelle registriert" };
    }
    if (metrics.active && metrics.searchable === metrics.documents) {
      return { label: "gesund", className: "is-active", detail: "vollst&auml;ndig im Quellenabruf nutzbar" };
    }
    if (metrics.active) {
      return { label: "teilweise", className: "is-stale", detail: "ein Teil ist suchbar" };
    }
    return { label: "nicht aktiv", className: "is-error", detail: "nicht im RAG-Kontext verf&uuml;gbar" };
  }

  function appendQuelleStat(target, label, value) {
    const item = document.createElement("span");
    const key = document.createElement("small");
    const count = document.createElement("strong");
    key.textContent = label;
    count.textContent = text(value);
    item.append(key, count);
    target.appendChild(item);
  }

  function renderQuelleHealth(status) {
    const target = root.querySelector("[data-ai-source-health]");
    if (!target) return;
    const data = status || {};
    const ragEnabled = Boolean(data.diagnostics && data.diagnostics.rag_enabled);
    const vectorStatus = data.vector_store || {};
    const lastUpdate = vectorStatus.latest_indexed_at
      || (vectorStatus.last_successful_sync && vectorStatus.last_successful_sync.synced_at)
      || "";
    target.innerHTML = "";
    dataQuelleDefinitions().forEach((definition) => {
      const metrics = sourceMetrics(data, definition.types);
      const health = sourceHealth(metrics, ragEnabled);
      const card = document.createElement("article");
      const header = document.createElement("div");
      const title = document.createElement("strong");
      const badge = statusPill(health.label, health.className);
      const description = document.createElement("p");
      const stats = document.createElement("div");
      const meta = document.createElement("small");
      card.className = "ai-source-card " + health.className;
      header.className = "ai-source-card-header";
      title.textContent = definition.label;
      description.innerHTML = definition.description;
      stats.className = "ai-source-stats";
      appendQuelleStat(stats, "Einträge", numberText(metrics.documents));
      appendQuelleStat(stats, "Textabschnitte", numberText(metrics.chunks));
      appendQuelleStat(stats, "Suchbar", numberText(metrics.searchable));
      meta.innerHTML = [
        "Embedding: " + text(data.diagnostics && data.diagnostics.embedding_provider),
        "RAG: " + (metrics.active ? "aktiv genutzt" : "nicht aktiv"),
        "Letzte Aktualisierung: " + (lastUpdate ? dateTimeText(lastUpdate) : "nicht verf&uuml;gbar"),
        "Health: " + health.detail
      ].join(" &middot; ");
      header.append(title, badge);
      card.append(header, description, stats, meta);
      target.appendChild(card);
    });
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
      low_quality: "Niedrige Qualität",
      duplicate: "Duplikat",
      outdated: "Veraltet",
      rejected: "Abgelehnt"
    };
    return labels[status] || text(status || "draft");
  }

  function qualityStatusClass(status) {
    if (status === "admin_approved" || status === "technician_confirmed") return "is-active";
    if (status === "outdated" || status === "low_quality" || status === "duplicate") {
      return "is-stale";
    }
    if (status === "rejected") return "is-error";
    return "is-muted";
  }

  function networkTypeLabel(type) {
    const labels = {
      machine: "Maschine",
      error: "Fehler",
      solution: "Lösung",
      document: "Dokument",
      task: "Aufgabe",
      inventory_part: "Inventar",
      recurring_issue: "Wiederkehrender Fehler",
      knowledge_gap: "Wissenslücke",
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
      task_question: "Aufgabenfrage",
      document_question: "Dokumentfrage",
      safety_question: "Sicherheitsfrage",
      general_question: "Allgemein",
      knowledge_gap: "Wissenslücke",
      trend_history_question: "Trend/Historie"
    };
    return labels[type] || text(type);
  }

  function scoreText(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return "-";
    if (number > 0 && number <= 1) return Math.round(number * 100) + "%";
    return Math.round(number).toLocaleString("de-DE");
  }

  function flowStatusLabel(status) {
    const labels = {
      ok: "OK",
      warning: "Warnung",
      empty: "Keine Daten",
      critical: "Kritisch"
    };
    return labels[status] || text(status);
  }

  function flowStatusClass(status) {
    if (status === "ok") return "is-active";
    if (status === "warning") return "is-stale";
    if (status === "critical") return "is-error";
    return "is-muted";
  }

  function confidenceLabel(confidence) {
    const score = confidence && confidence.score != null ? confidence.score : "-";
    const level = confidence && confidence.level ? confidence.level : "-";
    return score + " / " + level;
  }

  function sourceReferenceLabel(source) {
    if (!source) return "Quelle";
    if (source.source_label) return source.source_label;
    let label = text(source.type || "knowledge");
    if (source.id != null) label += " #" + source.id;
    if (source.chunk_id != null) label += " / Textabschnitt #" + source.chunk_id;
    if (source.section_title) label += " - " + truncateLabel(source.section_title, 52);
    return label;
  }

  function networkTypeColor(type) {
    const colors = {
      machine: "#2563eb",
      error: "#dc2626",
      solution: "#16a34a",
      document: "#7c3aed",
      task: "#0891b2",
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
      task: 2,
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

  function networkEdgeNodeLabels(edge, payload) {
    const nodes = networkNodeMap(payload.nodes || []);
    const source = nodes[edge.source];
    const target = nodes[edge.target];
    return {
      source: source ? source.label : edge.source,
      target: target ? target.label : edge.target
    };
  }

  function networkEdgeDetail(edge) {
    const labels = {
      source_relation: "Direkte Quelle",
      mentions: "Entity-Erwaehnung",
      recurring_pattern: "Wiederkehrendes Muster",
      knowledge_gap: "Wissenslücke",
      task_context: "Aufgabenkontext"
    };
    return labels[edge.type] || text(edge.type);
  }

  function renderKnowledgeNetworkGroups(payload) {
    const target = root.querySelector("[data-knowledge-network-groups]");
    if (!target) return;
    target.innerHTML = "";
    const groups = payload.groups || [];
    if (!groups.length) {
      target.appendChild(statusRow("Gruppen", "Keine gruppierten Nodes vorhanden"));
      return;
    }
    groups.forEach((group) => {
      const card = document.createElement("article");
      const header = document.createElement("div");
      const title = document.createElement("strong");
      const count = document.createElement("span");
      const list = document.createElement("div");
      card.className = "knowledge-network-group-card";
      header.className = "knowledge-network-group-header";
      title.textContent = group.label || networkTypeLabel(group.type);
      count.textContent = numberText(group.count) + " Nodes / " + numberText(group.edge_count) + " Links";
      header.append(title, count);
      list.className = "knowledge-network-group-nodes";
      (group.top_nodes || []).forEach((node) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "knowledge-network-node-chip";
        button.dataset.networkGroupNode = node.id;
        button.textContent = truncateLabel(node.label, 34);
        button.addEventListener("click", () => {
          const nodeDetail = (state.currentKnowledgeNetworkPayload.nodes || []).find((item) => item.id === node.id);
          renderKnowledgeNetworkDetail(nodeDetail, state.currentKnowledgeNetworkPayload);
        });
        list.appendChild(button);
      });
      card.append(header, list);
      target.appendChild(card);
    });
  }

  function renderKnowledgeNetworkRelations(payload) {
    const target = root.querySelector("[data-knowledge-network-relations]");
    if (!target) return;
    target.innerHTML = "";
    const edges = (payload.edges || []).slice(0, 16);
    const heading = document.createElement("div");
    const title = document.createElement("strong");
    const meta = document.createElement("span");
    heading.className = "knowledge-network-relations-header";
    title.textContent = "Klickbare Verbindungen";
    meta.textContent = edges.length ? edges.length + " wichtigste Beziehungen" : "Keine sichtbaren Beziehungen";
    heading.append(title, meta);
    target.appendChild(heading);
    if (!edges.length) return;
    edges.forEach((edge) => {
      const labels = networkEdgeNodeLabels(edge, payload);
      const button = document.createElement("button");
      const relation = document.createElement("span");
      const source = document.createElement("strong");
      const score = document.createElement("small");
      button.type = "button";
      button.className = "knowledge-network-relation-card";
      button.dataset.networkRelation = edge.id;
      relation.textContent = networkEdgeDetail(edge);
      source.textContent = truncateLabel(labels.source, 34) + " -> " + truncateLabel(labels.target, 34);
      score.textContent = "Gewicht " + Number(edge.weight || 0).toFixed(1) + " / Evidenz " + numberText(edge.evidence_count || 0);
      button.append(relation, source, score);
      button.addEventListener("click", () => renderKnowledgeNetworkEdgeDetail(edge, payload));
      target.appendChild(button);
    });
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

  function renderKnowledgeNetworkEdgeDetail(edge, payload) {
    const target = root.querySelector("[data-knowledge-network-detail]");
    if (!target) return;
    target.innerHTML = "";
    if (!edge) {
      target.appendChild(statusRow("Auswahl", "Node oder Verbindung anklicken"));
      return;
    }
    const nodes = networkNodeMap(payload.nodes || []);
    const source = nodes[edge.source];
    const targetNode = nodes[edge.target];
    target.append(
      statusRow("Beziehung", networkEdgeDetail(edge)),
      statusRow("Von", source ? truncateLabel(source.label, 80) : edge.source),
      statusRow("Nach", targetNode ? truncateLabel(targetNode.label, 80) : edge.target),
      statusRow("Gewicht", Number(edge.weight || 0).toFixed(1)),
      statusRow("Evidenz", edge.evidence_count || 0),
      statusRow("Typ", edge.type || "-")
    );
    ((edge.explainability || {}).signals || []).slice(0, 8).forEach((signal) => {
      target.appendChild(statusRow("Signal", signal));
    });
  }

  function renderKnowledgeNetworkCanvas(payload) {
    const container = root.querySelector("[data-knowledge-network-canvas]");
    if (!container) return;
    container.innerHTML = "";
    const nodes = payload.nodes || [];
    const edges = payload.edges || [];
    if (!nodes.length) {
      container.appendChild(statusRow("Wissensnetz", "Keine Daten für diesen Filter."));
      renderKnowledgeNetworkDetail(null, payload);
      return;
    }

    const svgNamespace = "http://www.w3.org/2000/svg";
    const layout = networkPositions(nodes);
    const svg = document.createElementNS(svgNamespace, "svg");
    svg.setAttribute("viewBox", "0 0 " + layout.width + " " + layout.height);
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", "Wissensnetz");
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
      const edgeGroup = document.createElementNS(svgNamespace, "g");
      const hitLine = document.createElementNS(svgNamespace, "line");
      const line = document.createElementNS(svgNamespace, "line");
      edgeGroup.setAttribute("tabindex", "0");
      edgeGroup.setAttribute("role", "button");
      edgeGroup.setAttribute("class", "knowledge-network-edge");
      edgeGroup.dataset.networkEdgeId = edge.id;
      hitLine.setAttribute("x1", sourcePosition.x);
      hitLine.setAttribute("y1", sourcePosition.y);
      hitLine.setAttribute("x2", targetPosition.x);
      hitLine.setAttribute("y2", targetPosition.y);
      hitLine.setAttribute("stroke", "transparent");
      hitLine.setAttribute("stroke-width", "14");
      line.setAttribute("x1", sourcePosition.x);
      line.setAttribute("y1", sourcePosition.y);
      line.setAttribute("x2", targetPosition.x);
      line.setAttribute("y2", targetPosition.y);
      line.setAttribute("stroke", edge.type === "source_relation" ? "#64748b" : "#cbd5e1");
      line.setAttribute("stroke-width", Math.max(1, Math.min(5, Number(edge.weight || 1) / 3)));
      line.setAttribute("stroke-opacity", edge.type === "source_relation" ? "0.7" : "0.45");
      const title = document.createElementNS(svgNamespace, "title");
      title.textContent = edge.label + " (" + Number(edge.weight || 0).toFixed(1) + ")";
      edgeGroup.append(hitLine, line, title);
      edgeGroup.addEventListener("click", () => {
        svg.querySelectorAll("[data-network-edge-id]").forEach((item) => {
          item.classList.remove("is-selected");
        });
        svg.querySelectorAll("[data-network-node-id] circle").forEach((item) => {
          item.setAttribute("stroke", "#ffffff");
          item.setAttribute("stroke-width", "2");
        });
        edgeGroup.classList.add("is-selected");
        renderKnowledgeNetworkEdgeDetail(edge, payload);
      });
      edgeGroup.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        edgeGroup.dispatchEvent(new Event("click"));
      });
      svg.appendChild(edgeGroup);
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
        svg.querySelectorAll("[data-network-edge-id]").forEach((item) => {
          item.classList.remove("is-selected");
        });
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
    payload = payload || { nodes: [], edges: [], groups: [], stats: {} };
    state.currentKnowledgeNetworkPayload = payload;
    renderKnowledgeNetworkStats(payload.stats || {});
    renderKnowledgeNetworkGroups(payload);
    renderKnowledgeNetworkLegend(payload);
    renderKnowledgeNetworkCanvas(payload);
    renderKnowledgeNetworkRelations(payload);
  }

  async function loadKnowledgeNetwork() {
    const query = root.querySelector("[data-knowledge-network-search]").value;
    const source = root.querySelector("[data-knowledge-network-source]").value;
    const quality = root.querySelector("[data-knowledge-network-quality]").value;
    const focusType = root.querySelector("[data-knowledge-network-focus-type]").value;
    const focus = root.querySelector("[data-knowledge-network-focus]").value;
    const params = new URLSearchParams({
      limit: "120",
      q: query,
      source_type: source,
      quality_status: quality,
      focus,
      focus_type: focusType
    });
    const data = await api("/api/v1/admin/ai/knowledge-network?" + params.toString());
    renderKnowledgeNetwork(data);
  }
  Object.assign(AdminAI, { sourceTypeLabel, dataQuelleDefinitions, sourceMetrics, sourceHealth, appendQuelleStat, renderQuelleHealth, knowledgeOriginKind, knowledgeOriginLabel, knowledgeOriginClass, knowledgeSourceCell, qualityStatusLabel, qualityStatusClass, networkTypeLabel, queryTypeLabel, scoreText, flowStatusLabel, flowStatusClass, confidenceLabel, sourceReferenceLabel, networkTypeColor, truncateLabel, networkNodeRadius, networkNodeMap, networkPositions, metadataValue, networkEdgeNodeLabels, networkEdgeDetail, renderKnowledgeNetworkGroups, renderKnowledgeNetworkRelations, renderKnowledgeNetworkStats, renderKnowledgeNetworkLegend, renderKnowledgeNetworkDetail, renderKnowledgeNetworkEdgeDetail, renderKnowledgeNetworkCanvas, renderKnowledgeNetwork, loadKnowledgeNetwork });
})(window.MaintenanceAdminAI);

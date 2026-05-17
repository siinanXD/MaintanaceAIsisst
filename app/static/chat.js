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
  let chatTemplateItems = [];
  let isTemplateLoading = false;
  let hasHydratedPanel = false;
  let isSending = false;
  let lastFocusedElement = null;
  const CHAT_OPEN_KEY = "maintenance_chat_open";

  if (!widget || !toggle || !panel || !form || !messages) {
    return;
  }

  function isOpen() {
    return widget.classList.contains("is-open");
  }

  function hydrateChatPanel() {
    if (!hasHydratedPanel) {
      hasHydratedPanel = true;
      renderSuggestions();
    }
    loadChatHistory();
  }

  function focusChatInput() {
    const input = form.querySelector("input");
    if (input) input.focus();
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
      return "Fallback - OpenAI-Modell nicht erlaubt";
    }
    if (error === "rate_limit") {
      return "Fallback - OpenAI-Rate-Limit erreicht";
    }
    if (error === "authentication_error") {
      return "Fallback - OpenAI-Key abgelehnt";
    }
    if (error === "timeout") {
      return "Fallback - OpenAI-Timeout";
    }
    if (error === "connection_error") {
      return "Fallback - OpenAI-Verbindung fehlgeschlagen";
    }
    if (error === "permission_denied") {
      return "Fallback - OpenAI-Zugriff verweigert";
    }
    return "Fallback - OpenAI nicht erreichbar";
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
      return "Fallback - OPENAI_API_KEY fehlt in .env" + sourceLabel;
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
      return "Fallback - OPENAI_API_KEY fehlt in .env";
    }
    if (status === "openai_error") {
      return openAIErrorLabel(diagnostics);
    }
    if (status === "permission_denied") {
      return "Berechtigung fehlt" + sourceLabel;
    }
    if (diagnostics && diagnostics.fallback_used) {
      return "Fallback" + sourceLabel;
    }
    if (sourceCount) {
      return sourceCount + " Quellen";
    }
    return "";
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

    const body = document.createElement("div");
    body.className = "chat-message-text";
    if (type === "user") {
      body.textContent = text;
    } else {
      renderFormattedText(body, text);
    }
    bubble.appendChild(body);

    if (type !== "user") {
      const label = statusText(diagnostics);
      if (label) {
        const meta = document.createElement("div");
        meta.className = "chat-message-meta";
        meta.textContent = label;
        bubble.appendChild(meta);
      }
    }

    messages.appendChild(bubble);
    messages.scrollTop = messages.scrollHeight;
    return bubble;
  }

  function renderSources(bubble, sources) {
    const existing = bubble.querySelector(".chat-sources");
    if (existing) existing.remove();
    if (!sources || !sources.length) return;
    const sourceList = document.createElement("div");
    sourceList.className = "chat-sources";
    sourceList.setAttribute("aria-label", "Verwendete Quellen");
    sources.slice(0, 4).forEach((source) => {
      const item = document.createElement(source.url ? "a" : "span");
      const moduleName = source.module || source.type || "Quelle";
      const sourceId = source.id ? " #" + source.id : "";
      const title = source.title || "Wissensquelle";
      const label = document.createElement("strong");
      const meta = document.createElement("small");
      if (source.url) item.href = source.url;
      item.title = source.reason || "";
      label.textContent = title;
      meta.textContent = moduleName + sourceId;
      item.append(label, meta);
      sourceList.appendChild(item);
    });
    bubble.appendChild(sourceList);
  }

  function renderChatHistory(items) {
    if (!historyList) return;
    historyList.innerHTML = "";
    const historyItems = items || [];
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
        renderSources(bubble, item.sources || []);
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

  function updateAssistantMessage(bubble, text, diagnostics, sources, actionPreview) {
    const body = bubble.querySelector(".chat-message-text");
    const meta = bubble.querySelector(".chat-message-meta");
    if (body) renderFormattedText(body, text);
    const label = statusText(diagnostics);
    if (label) {
      if (meta) {
        meta.textContent = label;
      } else {
        const newMeta = document.createElement("div");
        newMeta.className = "chat-message-meta";
        newMeta.textContent = label;
        bubble.appendChild(newMeta);
      }
    } else if (meta) {
      meta.remove();
    }
    renderSources(bubble, sources);
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
      body: JSON.stringify({ message })
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
      answer += "\n- **Hinweis:** Lokaler Fallback, API-Key fehlt";
    }
    if (!isGeneralChat && diagnostics.status === "openai_error") {
      answer += "\n- **Hinweis:** Lokaler Fallback, OpenAI nicht erreichbar";
    }
    if (!isGeneralChat && diagnostics.fallback_used) {
      answer += "\n- **Quelle:** Lokaler Fallback";
    }
    return {
      answer,
      diagnostics,
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
    const initial = document.createElement("div");
    initial.className = "chat-message is-assistant";
    initial.textContent = "Frag mich nach Tasks, Fehlern, Maschinen, Lager, Dokumenten oder Schichtplanung.";
    messages.appendChild(initial);
    renderSuggestions();
  }

  function fallbackChatSuggestionsForUser() {
    const auth = window.maintenanceAuth;
    if (!auth || !auth.user || !auth.user()) return [];
    const items = [];
    if (auth.canView("tasks")) items.push({ category: "tasks", message: "Welche Tasks sind heute wichtig?" });
    if (auth.canWrite("tasks")) items.push({ category: "tasks", message: "Task erstellen: Maschine 3 macht Geräusche" });
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
    suggestions.hidden = items.length === 0;
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
        const input = form.querySelector("input");
        if (input) {
          input.value = template.message;
          input.focus();
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
      button.textContent = busy ? "Prüfe..." : "Senden";
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
    const input = form.querySelector("input");
    const message = input.value.trim();
    if (!message) return;

    input.value = "";
    setChatFormBusy(true);
    if (suggestions) suggestions.hidden = true;
    appendMessage(message, "user");
    const loading = appendMessage(
      "Ich prüfe die freigegebenen Daten und formuliere eine sichere Antwort...",
      "assistant"
    );
    loading.classList.add("is-loading");

    try {
      const result = await askAssistant(message);
      updateAssistantMessage(
        loading,
        result.answer,
        result.diagnostics,
        result.sources,
        result.action_preview
      );
      addFeedbackButtons(loading, result);
      loading.classList.remove("is-loading");
    } catch (error) {
      updateAssistantMessage(
        loading,
        "Keine Verbindung zur API. Bitte prüfe, ob der Server läuft.",
        { status: "openai_error", fallback_used: true }
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

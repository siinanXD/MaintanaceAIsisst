/**
 * Chat widget history module.
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

  const appendMessage = (...args) => Chat.appendMessage(...args);
  const canViewChatEvidence = (...args) => Chat.canViewChatEvidence(...args);
  const chatSessionId = (...args) => Chat.chatSessionId(...args);
  const renderAssistantEvidence = (...args) => Chat.renderAssistantEvidence(...args);
  const renderFormattedText = (...args) => Chat.renderFormattedText(...args);
  const resetChatSession = (...args) => Chat.resetChatSession(...args);
  const setOpen = (...args) => Chat.setOpen(...args);
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
      body: JSON.stringify({
        message,
        session_id: chatSessionId(),
        response_mode: canViewChatEvidence() ? "full" : "answer_only"
      })
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
    state.hasSubmittedMessage = false;
    state.hasTypedInCurrentChat = false;
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
    if (state.chatTemplateItems.length) {
      return state.chatTemplateItems.map(normalizeTemplateItem).filter((item) => item.message);
    }
    return fallbackChatSuggestionsForUser();
  }

  function updateSuggestionVisibility(items) {
    if (!suggestions) return;
    const hasSuggestions = Array.isArray(items) && items.length > 0;
    const hasInputText = chatInput && chatInput.value.trim().length > 0;
    suggestions.hidden = !hasSuggestions || hasInputText || state.hasSubmittedMessage || state.hasTypedInCurrentChat;
  }

  async function loadChatTemplates() {
    const token = window.localStorage.getItem("maintenance_access_token");
    if (!token || state.isTemplateLoading) return;
    state.isTemplateLoading = true;
    try {
      const response = await fetch("/api/v1/ai/chat/templates", {
        headers: { "Authorization": "Bearer " + token }
      });
      if (!response.ok) return;
      const payload = await response.json();
      const data = payload && payload.data ? payload.data : payload;
      state.chatTemplateItems = Array.isArray(data.items) ? data.items : [];
      renderSuggestions(false);
    } finally {
      state.isTemplateLoading = false;
    }
  }

  function renderSuggestions(loadRemote) {
    if (!suggestions) return;
    const shouldLoadRemote = loadRemote !== false;
    suggestions.innerHTML = "";
    const items = chatSuggestionsForUser();
    if (!state.chatTemplateItems.length && shouldLoadRemote) {
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
  Object.assign(Chat, { renderChatHistory, historyMetaText, loadChatHistory, applyActionPreview, renderActionPreview, updateAssistantMessage, askAssistant, sendFeedback, addFeedbackButtons, clearChat, fallbackChatSuggestionsForUser, templateCategoryLabel, normalizeTemplateItem, chatSuggestionsForUser, updateSuggestionVisibility, loadChatTemplates, renderSuggestions });
})(window.MaintenanceChatRuntime);

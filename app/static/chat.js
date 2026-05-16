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

  if (!widget || !toggle || !panel || !form || !messages) {
    return;
  }

  function setOpen(open) {
    widget.classList.toggle("is-open", open);
    toggle.setAttribute("aria-expanded", String(open));
    panel.setAttribute("aria-hidden", String(!open));
    if (open) {
      const input = form.querySelector("input");
      if (input) input.focus();
      loadChatHistory();
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
      return provider + (model ? " · " + model : "");
    }
    if (status === "local_answer") {
      return "Lokale Antwort" + sourceLabel;
    }
    if (status === "api_key_missing") {
      return "Fallback · OPENAI_API_KEY fehlt in .env";
    }
    if (status === "openai_error") {
      return openAIErrorLabel(diagnostics);
    }
    if (status === "openai_error") {
      return "Fallback · OpenAI nicht erreichbar";
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
    sources.slice(0, 4).forEach((source) => {
      const item = document.createElement("a");
      item.href = source.url || "#";
      item.textContent = source.module + " #" + source.id + ": " + source.title;
      item.title = source.reason || "";
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
      action_preview: data.action_preview || null
    };
  }

  async function sendFeedback(prompt, response, rating, comment) {
    const token = window.localStorage.getItem("maintenance_access_token");
    if (!token) return;
    await fetch("/api/v1/ai/feedback", {
      method: "POST",
      headers: {
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ prompt, response, rating, comment: comment || "" })
    });
  }

  function addFeedbackButtons(bubble, prompt, response) {
    const actions = document.createElement("div");
    actions.className = "chat-feedback";
    const helpful = document.createElement("button");
    helpful.type = "button";
    helpful.textContent = "Hilfreich";
    const notHelpful = document.createElement("button");
    notHelpful.type = "button";
    notHelpful.textContent = "Nicht hilfreich";
    const comment = document.createElement("input");
    comment.className = "input input-bordered";
    comment.placeholder = "Optionaler Kommentar";
    [helpful, notHelpful].forEach((button) => {
      button.className = "chat-feedback-button";
    });
    helpful.addEventListener("click", async () => {
      await sendFeedback(prompt, response, "helpful", comment.value);
      actions.textContent = "Feedback gespeichert.";
    });
    notHelpful.addEventListener("click", async () => {
      await sendFeedback(prompt, response, "not_helpful", comment.value);
      actions.textContent = "Feedback gespeichert.";
    });
    actions.append(comment, helpful, notHelpful);
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

  function chatSuggestionsForUser() {
    const auth = window.maintenanceAuth;
    if (!auth || !auth.user || !auth.user()) return [];
    const items = [];
    if (auth.canView("tasks")) items.push("Welche Tasks sind heute wichtig?");
    if (auth.canWrite("tasks")) items.push("Task erstellen: Maschine 3 macht Geraeusche");
    if (auth.canView("errors")) items.push("Was bedeutet Fehler E104?");
    if (auth.canWrite("errors")) items.push("Fehleranalyse: Sensor meldet kein Signal");
    if (auth.canView("machines")) items.push("Welche Maschinen brauchen Aufmerksamkeit?");
    if (auth.canView("inventory")) items.push("Welche Lagerteile sind kritisch?");
    if (auth.canView("documents")) items.push("Welche Dokumente sollte ich pruefen?");
    return items.slice(0, 6);
  }

  function renderSuggestions() {
    if (!suggestions) return;
    suggestions.innerHTML = "";
    const items = chatSuggestionsForUser();
    suggestions.hidden = items.length === 0;
    items.forEach((text) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "chat-suggestion";
      chip.textContent = text;
      chip.addEventListener("click", () => {
        suggestions.hidden = true;
        const input = form.querySelector("input");
        if (input) {
          input.value = text;
          input.focus();
        }
      });
      suggestions.appendChild(chip);
    });
  }

  toggle.addEventListener("click", () => setOpen(!widget.classList.contains("is-open")));
  close.addEventListener("click", () => setOpen(false));
  if (clearBtn) clearBtn.addEventListener("click", clearChat);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const input = form.querySelector("input");
    const message = input.value.trim();
    if (!message) return;

    input.value = "";
    if (suggestions) suggestions.hidden = true;
    appendMessage(message, "user");
    const loading = appendMessage(
      "Ich sende deine Frage an den Assistenten und pruefe die freigegebenen Daten...",
      "assistant"
    );

    try {
      const result = await askAssistant(message);
      updateAssistantMessage(
        loading,
        result.answer,
        result.diagnostics,
        result.sources,
        result.action_preview
      );
      addFeedbackButtons(loading, result.prompt || message, result.answer);
    } catch (error) {
      updateAssistantMessage(
        loading,
        "Keine Verbindung zur API. Bitte pruefe, ob der Server laeuft.",
        { status: "openai_error", fallback_used: true }
      );
    }
  });

  window.addEventListener("maintenance-auth-ready", renderSuggestions);
  window.addEventListener("maintenance-auth-changed", renderSuggestions);
  if (historySearch) {
    historySearch.addEventListener("input", () => {
      window.clearTimeout(historySearch._timer);
      historySearch._timer = window.setTimeout(loadChatHistory, 250);
    });
  }
  renderSuggestions();
})();

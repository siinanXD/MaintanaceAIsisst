/**
 * Chat widget actions module.
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

  const addFeedbackButtons = (...args) => Chat.addFeedbackButtons(...args);
  const appendMessage = (...args) => Chat.appendMessage(...args);
  const askAssistant = (...args) => Chat.askAssistant(...args);
  const chatSuggestionsForUser = (...args) => Chat.chatSuggestionsForUser(...args);
  const focusableChatElements = (...args) => Chat.focusableChatElements(...args);
  const hydrateChatPanel = (...args) => Chat.hydrateChatPanel(...args);
  const isOpen = (...args) => Chat.isOpen(...args);
  const renderLoadingState = (...args) => Chat.renderLoadingState(...args);
  const setOpen = (...args) => Chat.setOpen(...args);
  const updateAssistantMessage = (...args) => Chat.updateAssistantMessage(...args);
  const updateSuggestionVisibility = (...args) => Chat.updateSuggestionVisibility(...args);
  function setChatFormBusy(busy) {
  const input = form.querySelector("input");
  const button = form.querySelector("button[type='submit']");
  state.isSending = busy;
  form.setAttribute("aria-busy", String(busy));
  if (input) input.disabled = busy;
  if (button) {
    button.disabled = busy;
    button.setAttribute("aria-busy", String(busy));
    button.textContent = busy ? "Analysiere..." : "Senden";
  }
  }

  function bindChatWidgetEvents() {
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
    if (state.isSending) return;
    const input = chatInput || form.querySelector("input");
    const message = input.value.trim();
    if (!message) return;

    input.value = "";
    state.hasSubmittedMessage = true;
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
    state.chatTemplateItems = [];
    if (isOpen()) {
      state.hasHydratedPanel = false;
      hydrateChatPanel();
    }
  });
  window.addEventListener("maintenance-auth-changed", () => {
    state.chatTemplateItems = [];
    if (isOpen()) {
      state.hasHydratedPanel = false;
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
        state.hasTypedInCurrentChat = true;
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
  }
  Object.assign(Chat, { setChatFormBusy, bindChatWidgetEvents });
})(window.MaintenanceChatRuntime);

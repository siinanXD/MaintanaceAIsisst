/**
 * Chat widget session module.
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

  const loadChatHistory = (...args) => Chat.loadChatHistory(...args);
  const renderSuggestions = (...args) => Chat.renderSuggestions(...args);
  function isOpen() {
    return widget.classList.contains("is-open");
  }

  /**
   * Return a compact random identifier for one browser chat session.
   */
  function buildChatSessionId() {
    if (window.crypto && typeof window.crypto.randomUUID === "function") {
      return window.crypto.randomUUID();
    }
    return "chat-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 10);
  }

  /**
   * Warn once when sessionStorage is unavailable and fall back in memory.
   */
  function warnChatSessionStorage(error) {
    if (state.warnedChatSessionStorage) return;
    state.warnedChatSessionStorage = true;
    if (window.console && typeof window.console.warn === "function") {
      window.console.warn("Chat session storage is unavailable; using an in-memory session id.", error);
    }
  }

  /**
   * Return the current short-term chat session id without replaying history.
   */
  function chatSessionId() {
    try {
      const existing = window.sessionStorage.getItem(CHAT_SESSION_KEY);
      if (existing) {
        state.fallbackChatSessionId = existing;
        return existing;
      }
      const next = buildChatSessionId();
      window.sessionStorage.setItem(CHAT_SESSION_KEY, next);
      state.fallbackChatSessionId = next;
      return next;
    } catch (error) {
      warnChatSessionStorage(error);
      if (!state.fallbackChatSessionId) {
        state.fallbackChatSessionId = buildChatSessionId();
      }
      return state.fallbackChatSessionId;
    }
  }

  /**
   * Start a new short-term chat session for the next request.
   */
  function resetChatSession() {
    const next = buildChatSessionId();
    state.fallbackChatSessionId = next;
    try {
      window.sessionStorage.setItem(CHAT_SESSION_KEY, next);
    } catch (error) {
      warnChatSessionStorage(error);
    }
  }

  function hydrateChatPanel() {
    if (!state.hasHydratedPanel) {
      state.hasHydratedPanel = true;
      renderSuggestions();
    }
    loadChatHistory();
  }

  function focusChatInput() {
    if (chatInput) chatInput.focus();
  }

  function focusableChatElements() {
    return Array.from(panel.querySelectorAll(
      "a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])"
    )).filter((element) => element.offsetParent !== null || element === document.activeElement);
  }

  function restorePreviousFocus() {
    if (state.lastFocusedElement && typeof state.lastFocusedElement.focus === "function" && document.contains(state.lastFocusedElement)) {
      state.lastFocusedElement.focus();
      return;
    }
    toggle.focus();
  }

  function setOpen(open) {
    const wasOpen = isOpen();
    if (open && !wasOpen) {
      state.lastFocusedElement = document.activeElement;
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
  Object.assign(Chat, { isOpen, buildChatSessionId, warnChatSessionStorage, chatSessionId, resetChatSession, hydrateChatPanel, focusChatInput, focusableChatElements, restorePreviousFocus, setOpen });
})(window.MaintenanceChatRuntime);

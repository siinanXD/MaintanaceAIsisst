(function bootstrapChatWidget() {
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
  const historyCount = document.querySelector("[data-chat-history-count]");
  const chatInput = form ? form.querySelector("input") : null;

  if (!widget || !toggle || !panel || !form || !messages) {
    return;
  }

  window.MaintenanceChatRuntime = {
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
    CHAT_OPEN_KEY: "maintenance_chat_open",
    CHAT_SESSION_KEY: "maintenance_ai_chat_session_id",
    state: {
      chatTemplateItems: [],
      isTemplateLoading: false,
      hasHydratedPanel: false,
      isSending: false,
      hasSubmittedMessage: false,
      hasTypedInCurrentChat: false,
      lastFocusedElement: null,
      fallbackChatSessionId: "",
      warnedChatSessionStorage: false
    }
  };

  const modules = ["session", "evidence", "rendering", "history", "actions"];

  function moduleBaseUrl() {
    const currentScript = document.currentScript;
    if (!currentScript || !currentScript.src) return "/static/chat/";
    return currentScript.src.split("/static/chat.js")[0] + "/static/chat/";
  }

  function loadScript(name) {
    return new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = moduleBaseUrl() + name + ".js";
      script.defer = true;
      script.onload = resolve;
      script.onerror = () => reject(new Error("Chat-Modul konnte nicht geladen werden: " + name));
      document.head.appendChild(script);
    });
  }

  async function startChatWidget() {
    for (const name of modules) {
      await loadScript(name);
    }
    window.MaintenanceChatRuntime.bindChatWidgetEvents();
  }

  startChatWidget().catch((error) => {
    if (window.console && typeof window.console.warn === "function") {
      window.console.warn(error);
    }
  });
})();

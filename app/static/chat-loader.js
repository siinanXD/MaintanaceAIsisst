(function () {
  const CHAT_MODULE_URL = "/static/chat.js?v=20260517-dashboard-refresh1";
  const CHAT_OPEN_KEY = "maintenance_chat_open";
  let chatImportPromise = null;

  function loadChatModule() {
    if (!chatImportPromise) {
      chatImportPromise = import(CHAT_MODULE_URL).catch((error) => {
        chatImportPromise = null;
        console.warn(error);
        return null;
      });
    }
    return chatImportPromise;
  }

  async function openChat() {
    await loadChatModule();
    if (window.maintenanceChat && window.maintenanceChat.open) {
      window.maintenanceChat.open();
    }
  }

  function initChatLoader() {
    const widget = document.querySelector(".chat-widget");
    const toggle = document.querySelector(".chat-toggle");
    if (!widget || !toggle) return;

    toggle.addEventListener("click", (event) => {
      if (window.maintenanceChat && window.maintenanceChat.toggle) return;
      event.preventDefault();
      openChat();
    });

    if (window.localStorage.getItem(CHAT_OPEN_KEY) === "true") {
      openChat();
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initChatLoader, { once: true });
  } else {
    initChatLoader();
  }
})();

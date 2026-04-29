(function () {
  const widget = document.querySelector(".chat-widget");
  const toggle = document.querySelector(".chat-toggle");
  const panel = document.querySelector(".chat-panel");
  const close = document.querySelector(".chat-close");
  const form = document.querySelector("[data-chat-form]");
  const messages = document.querySelector("[data-chat-messages]");

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
    }
  }

  function appendMessage(text, type) {
    const bubble = document.createElement("div");
    bubble.className = "chat-message " + (type === "user" ? "is-user" : "is-assistant");
    bubble.textContent = text;
    messages.appendChild(bubble);
    messages.scrollTop = messages.scrollHeight;
    return bubble;
  }

  async function askAssistant(message) {
    const token = window.localStorage.getItem("maintenance_access_token");
    if (!token) {
      return "Bitte zuerst einloggen. Danach kann ich echte Antworten ueber /api/ai/chat geben.";
    }

    const response = await fetch("/api/ai/chat", {
      method: "POST",
      headers: {
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ message })
    });

    if (!response.ok) {
      if (response.status === 401) {
        window.localStorage.removeItem("maintenance_access_token");
        return "Deine Sitzung ist abgelaufen. Bitte neu einloggen.";
      }
      return "Die KI-Anfrage konnte gerade nicht verarbeitet werden.";
    }

    const data = await response.json();
    return data.answer || "Ich habe keine Antwort erhalten.";
  }

  toggle.addEventListener("click", () => setOpen(!widget.classList.contains("is-open")));
  close.addEventListener("click", () => setOpen(false));

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const input = form.querySelector("input");
    const message = input.value.trim();
    if (!message) return;

    input.value = "";
    appendMessage(message, "user");
    const loading = appendMessage("Ich pruefe das gerade...", "assistant");

    try {
      loading.textContent = await askAssistant(message);
    } catch (error) {
      loading.textContent = "Keine Verbindung zur API. Bitte pruefe, ob der Server laeuft.";
    }
  });
})();

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

  function statusText(diagnostics) {
    const status = diagnostics && diagnostics.status;
    const provider = (diagnostics && diagnostics.provider) || "OpenAI";
    const model = diagnostics && diagnostics.model;

    if (status === "openai_used") {
      return provider + (model ? " · " + model : "");
    }
    if (status === "local_answer") {
      return "Lokale Antwort";
    }
    if (status === "api_key_missing") {
      return "Fallback · OPENAI_API_KEY fehlt in .env";
    }
    if (status === "openai_error") {
      return "Fallback · OpenAI nicht erreichbar";
    }
    if (status === "permission_denied") {
      return "Berechtigung fehlt";
    }
    if (diagnostics && diagnostics.fallback_used) {
      return "Fallback";
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

    lines.forEach((rawLine) => {
      const line = rawLine.trim();
      if (!line) {
        list = null;
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

  function updateAssistantMessage(bubble, text, diagnostics) {
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
  }

  async function askAssistant(message) {
    const token = window.localStorage.getItem("maintenance_access_token");
    if (!token) {
      return {
        answer: "Bitte zuerst einloggen. Danach kann ich die KI-Funktionen nutzen.",
        diagnostics: { status: "permission_denied" }
      };
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

    const data = await response.json();
    const diagnostics = data.diagnostics || {};
    let answer = data.answer || "Ich habe keine Antwort erhalten.";

    if (diagnostics.status === "api_key_missing") {
      answer += "\n- **Hinweis:** Lokaler Fallback, API-Key fehlt";
    }
    if (diagnostics.status === "openai_error") {
      answer += "\n- **Hinweis:** Lokaler Fallback, OpenAI nicht erreichbar";
    }
    if (diagnostics.fallback_used) {
      answer += "\n- **Quelle:** Lokaler Fallback";
    }
    return { answer, diagnostics, prompt: message };
  }

  async function sendFeedback(prompt, response, rating) {
    const token = window.localStorage.getItem("maintenance_access_token");
    if (!token) return;
    await fetch("/api/ai/feedback", {
      method: "POST",
      headers: {
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ prompt, response, rating })
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
    [helpful, notHelpful].forEach((button) => {
      button.className = "chat-feedback-button";
    });
    helpful.addEventListener("click", async () => {
      await sendFeedback(prompt, response, "helpful");
      actions.textContent = "Feedback gespeichert.";
    });
    notHelpful.addEventListener("click", async () => {
      await sendFeedback(prompt, response, "not_helpful");
      actions.textContent = "Feedback gespeichert.";
    });
    actions.append(helpful, notHelpful);
    bubble.appendChild(actions);
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
    const loading = appendMessage(
      "Ich sende deine Frage an den Assistenten und pruefe die freigegebenen Daten...",
      "assistant"
    );

    try {
      const result = await askAssistant(message);
      updateAssistantMessage(loading, result.answer, result.diagnostics);
      addFeedbackButtons(loading, result.prompt || message, result.answer);
    } catch (error) {
      updateAssistantMessage(
        loading,
        "Keine Verbindung zur API. Bitte pruefe, ob der Server laeuft.",
        { status: "openai_error", fallback_used: true }
      );
    }
  });
})();

import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";

import { apiRequest } from "../api/client";
import { hasStoredToken } from "../auth/session";

type ChatMessageRole = "assistant" | "user";

type ShellChatMessage = {
  readonly id: string;
  readonly isLoading?: boolean;
  readonly role: ChatMessageRole;
  readonly text: string;
};

type ShellChatResponse = {
  readonly answer?: string;
  readonly data?: ShellChatResponse;
  readonly diagnostics?: Record<string, unknown>;
  readonly success?: boolean;
};

const CHAT_OPEN_KEY = "maintenance_chat_open";
const CHAT_SESSION_KEY = "maintenance_ai_chat_session_id";
const INITIAL_ASSISTANT_MESSAGE = "Frag mich nach kritischen Störungen, niedriger Sicherheit, veralteten Dokumenten oder heutigen Entscheidungen.";

/**
 * Return a compact random identifier for one browser chat session.
 */
function buildChatSessionId(): string {
  if (window.crypto && typeof window.crypto.randomUUID === "function") {
    return window.crypto.randomUUID();
  }
  return `chat-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

/**
 * Return the current short-term chat session id.
 */
function chatSessionId(): string {
  const existing = window.sessionStorage.getItem(CHAT_SESSION_KEY);
  if (existing) return existing;
  const nextSessionId = buildChatSessionId();
  window.sessionStorage.setItem(CHAT_SESSION_KEY, nextSessionId);
  return nextSessionId;
}

/**
 * Start a new short-term React chat session.
 */
function resetChatSession(): string {
  const nextSessionId = buildChatSessionId();
  window.sessionStorage.setItem(CHAT_SESSION_KEY, nextSessionId);
  return nextSessionId;
}

/**
 * Return a stable local chat message id.
 */
function chatMessageId(prefix: string): string {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

/**
 * Normalize the backend chat response into the answer text shown in the shell widget.
 */
function answerFromPayload(payload: ShellChatResponse): string {
  const data = payload.answer
    ? payload
    : payload.success === true && payload.data
      ? payload.data
      : payload;
  const diagnostics = data.diagnostics || {};
  let answer = data.answer || "Ich habe keine Antwort erhalten.";

  if (diagnostics.status === "api_key_missing") {
    answer += "\n- Hinweis: Lokale Ausweichantwort, AI API-Key fehlt";
  }
  if (diagnostics.status === "openai_error") {
    answer += "\n- Hinweis: Lokale Ausweichantwort, OpenAI nicht erreichbar";
  }
  if (diagnostics.fallback_used) {
    answer += "\n- Quelle: Lokale Ausweichantwort";
  }

  return answer;
}

/**
 * Render one React-owned chat message bubble.
 */
function ShellChatMessageBubble({ message }: { readonly message: ShellChatMessage }): ReactNode {
  const className = [
    "chat-message",
    message.role === "assistant" ? "is-assistant" : "is-user",
    message.isLoading ? "is-loading" : ""
  ].filter(Boolean).join(" ");

  return <div className={className}>{message.text}</div>;
}

/**
 * Render the global AI chat widget hooks and behavior for the future React shell.
 */
export function ShellChatWidget(): ReactNode {
  const [inputValue, setInputValue] = useState("");
  const [isOpen, setIsOpen] = useState(() => window.localStorage.getItem(CHAT_OPEN_KEY) === "true");
  const [isSending, setIsSending] = useState(false);
  const [messages, setMessages] = useState<readonly ShellChatMessage[]>([
    {
      id: "assistant-initial",
      role: "assistant",
      text: INITIAL_ASSISTANT_MESSAGE
    }
  ]);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const widgetClassName = isOpen ? "chat-widget is-open" : "chat-widget";
  const loadingText = "Ich prüfe die freigegebenen Daten und formuliere eine sichere Antwort...";

  useEffect(() => {
    window.localStorage.setItem(CHAT_OPEN_KEY, String(isOpen));
    if (isOpen) {
      window.setTimeout(() => inputRef.current?.focus(), 0);
    }
  }, [isOpen]);

  /**
   * Reset the visible chat and start a new short-term session.
   */
  function clearChat(): void {
    resetChatSession();
    setMessages([
      {
        id: "assistant-initial",
        role: "assistant",
        text: INITIAL_ASSISTANT_MESSAGE
      }
    ]);
    setInputValue("");
  }

  /**
   * Submit a React-owned chat request to the existing AI endpoint.
   */
  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const message = inputValue.trim();
    if (!message || isSending) return;

    const loadingId = chatMessageId("assistant-loading");
    setInputValue("");
    setIsSending(true);
    setMessages((currentMessages) => [
      ...currentMessages,
      { id: chatMessageId("user"), role: "user", text: message },
      { id: loadingId, isLoading: true, role: "assistant", text: loadingText }
    ]);

    try {
      if (!hasStoredToken()) {
        throw new Error("Bitte zuerst einloggen. Danach kann ich die KI-Funktionen nutzen.");
      }

      const payload = await apiRequest<ShellChatResponse>("/api/v1/ai/chat", {
        body: {
          message,
          response_mode: "answer_only",
          session_id: chatSessionId()
        },
        method: "POST"
      });
      const answer = answerFromPayload(payload);
      setMessages((currentMessages) => currentMessages.map((item) => (
        item.id === loadingId ? { id: loadingId, role: "assistant", text: answer } : item
      )));
    } catch (error) {
      const fallbackMessage = error instanceof Error
        ? error.message
        : "Keine Verbindung zur API. Bitte prüfe, ob der Server läuft.";
      setMessages((currentMessages) => currentMessages.map((item) => (
        item.id === loadingId ? { id: loadingId, role: "assistant", text: fallbackMessage } : item
      )));
    } finally {
      setIsSending(false);
      window.setTimeout(() => inputRef.current?.focus(), 0);
    }
  }

  return (
    <section className={widgetClassName} aria-label="AI Chat">
      <button
        className="chat-toggle"
        type="button"
        aria-expanded={isOpen}
        aria-controls="chat-panel"
        onClick={() => setIsOpen((currentValue) => !currentValue)}
      >
        <span aria-hidden="true">AI</span>
      </button>
      <div
        className="chat-panel"
        id="chat-panel"
        role="dialog"
        aria-modal={isOpen}
        aria-labelledby="chat-panel-title"
        aria-hidden={!isOpen}
        tabIndex={-1}
      >
        <div className="chat-panel-header">
          <div>
            <p className="chat-panel-kicker">Maintenance AI</p>
            <h2 className="chat-panel-title" id="chat-panel-title">Lage klären</h2>
          </div>
          <button className="chat-clear" type="button" aria-label="Chat leeren" title="Chat leeren" onClick={clearChat}>
            Neu
          </button>
          <button className="chat-close" type="button" aria-label="Chat schließen" onClick={() => setIsOpen(false)}>
            &times;
          </button>
        </div>
        <div className="chat-panel-body" data-chat-messages role="log" aria-live="polite" aria-relevant="additions text">
          {messages.map((message) => (
            <ShellChatMessageBubble key={message.id} message={message} />
          ))}
        </div>
        <details className="help-disclosure chat-guidance">
          <summary>Worauf basiert die Antwort?</summary>
          <p>Der Assistant nutzt freigegebene App-Daten und, wenn aktiv, passende Dokumentquellen. Quellen, Konfidenz und Unsicherheit werden in der Antwortkarte angezeigt.</p>
        </details>
        <details className="chat-history-panel" data-chat-history-panel hidden>
          <summary className="chat-history-summary" data-chat-history-summary>
            Chat-Historie
            <span data-chat-history-count>0</span>
          </summary>
          <label className="sr-only" htmlFor="chat-history-search-react">Chat-Historie durchsuchen</label>
          <input className="input input-bordered w-full" id="chat-history-search-react" data-chat-history-search autoComplete="off" placeholder="Historie durchsuchen" />
          <div className="chat-history-list" data-chat-history-list />
        </details>
        <div className="chat-suggestions" data-chat-suggestions hidden />
        <form className="chat-panel-form" data-chat-form aria-describedby="chat-input-help-react" aria-busy={isSending} onSubmit={handleSubmit}>
          <label className="sr-only" htmlFor="chat-message-input-react">Nachricht an den AI Assistant</label>
          <input
            className="input input-bordered w-full"
            id="chat-message-input-react"
            name="message"
            autoComplete="off"
            placeholder="z. B. Presse 3 verliert Hydraulik"
            aria-describedby="chat-input-help-react"
            disabled={isSending}
            onChange={(event) => setInputValue(event.currentTarget.value)}
            ref={inputRef}
            value={inputValue}
          />
          <span className="sr-only" id="chat-input-help-react">Der Assistant arbeitet read-only und nutzt nur freigegebene Daten.</span>
          <button className="btn btn-primary" type="submit" disabled={isSending}>
            {isSending ? "Analysiere..." : "Senden"}
          </button>
        </form>
      </div>
    </section>
  );
}

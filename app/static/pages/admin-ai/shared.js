/**
 * Admin AI shared module.
 * Registers view helpers on the shared MaintenanceAdminAI runtime.
 */
(function registerAdminAiModule(AdminAI) {
  const { root, adminView, state, QUALITY_STATUS_OPTIONS } = AdminAI;
  function bind(selector, eventName, handler) {
    const element = root.querySelector(selector);
    if (!element) return;
    element.addEventListener(eventName, handler);
  }

  function token() {
    return window.localStorage.getItem("maintenance_access_token");
  }

  async function api(path, options) {
    const response = await fetch(path, {
      ...options,
      headers: {
        ...(options && options.headers ? options.headers : {}),
        Authorization: "Bearer " + token()
      }
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      const error = new Error("API-Fehler");
      error.status = response.status;
      error.statusText = response.statusText;
      error.path = path;
      error.payload = payload;
      throw error;
    }
    return payload.data || payload;
  }

  function adminAiBackendMessage(status, endpoint) {
    if (status !== 500 || !endpoint.startsWith("/api/v1/admin/ai/")) {
      return "Das Backend konnte die Aktion nicht ausführen.";
    }
    return "Das Backend konnte die Aktion nicht ausführen. Falls dies nach einem Update passiert: Datenbankmigration ausführen.";
  }

  /**
   * Return a user-facing API-Fehler that never exposes tokens, request payloads, or raw backend details.
   */
  function safeErrorMessage(error, context) {
    const status = Number(error && error.status);
    const endpoint = error && error.path ? String(error.path).split("?")[0] : "";
    const messages = {
      400: "Der Request wurde vom Backend abgelehnt.",
      401: "Die Sitzung ist abgelaufen. Bitte neu anmelden.",
      403: "Für diese Aktion fehlt die Berechtigung.",
      404: "Der API-Endpunkt wurde nicht gefunden.",
      409: "Die Aktion kollidiert mit dem aktuellen Datenstand.",
      422: "Die Eingaben passen nicht zum API-Vertrag.",
      429: "Das Rate Limit ist erreicht. Bitte kurz warten.",
      500: "Das Backend konnte die Aktion nicht ausführen.",
      502: "Der KI-Anbieter oder ein Gateway antwortet nicht.",
      503: "Der Service ist gerade nicht verfügbar.",
      504: "Die Aktion hat zu lange gedauert."
    };
    let summary = messages[status] || "Die Aktion konnte nicht abgeschlossen werden.";
    if (status === 500) {
      summary = adminAiBackendMessage(status, endpoint);
    }
    return [
      context || "KI-Administration",
      summary,
      status ? "Status " + status : "",
      endpoint ? "Endpunkt " + endpoint : ""
    ].filter(Boolean).join(" - ");
  }

  /**
   * Hide prompt, answer, and free-text question content in admin overview surfaces.
   */
  function redactSensitiveText(value, fallback) {
    if (value == null || value === "") return fallback || "Inhalt ausgeblendet";
    return fallback || "Aus Datenschutz ausgeblendet";
  }

  /**
   * Return a compact privacy-safe reference for persisted AI records.
   */
  function recordReference(prefix, id, fallback) {
    if (id != null && id !== "") return prefix + " #" + id;
    return fallback || prefix + " ohne ID";
  }

  /**
   * Render a consistent empty state into lists and table bodies.
   */
  function renderAdminEmptyState(target, message, hint) {
    if (!target) return;
    target.innerHTML = "";
    const state = document.createElement("div");
    const title = document.createElement("strong");
    state.className = "admin-empty";
    title.textContent = message;
    state.appendChild(title);
    if (hint) {
      const detail = document.createElement("span");
      detail.textContent = hint;
      state.appendChild(detail);
    }
    if (target.tagName === "TBODY") {
      const row = document.createElement("tr");
      const cellElement = document.createElement("td");
      const headerCount = target.closest("table")
        ? target.closest("table").querySelectorAll("thead th").length
        : 1;
      cellElement.colSpan = Math.max(headerCount, 1);
      cellElement.appendChild(state);
      row.appendChild(cellElement);
      target.appendChild(row);
      return;
    }
    target.appendChild(state);
  }

  function text(value) {
    return value == null || value === "" ? "-" : String(value);
  }

  function numberText(value) {
    if (value == null || value === "") return "0";
    const number = Number(value);
    if (!Number.isFinite(number)) return text(value);
    return number.toLocaleString("de-DE");
  }

  function percentText(value) {
    const number = Number(value || 0);
    return Math.round(number * 100) + "%";
  }

  function msText(value) {
    return numberText(value) + " ms";
  }

  function moneyText(value) {
    const number = Number(value || 0);
    return "$" + number.toLocaleString("de-DE", {
      minimumFractionDigits: 0,
      maximumFractionDigits: 6
    });
  }

  function secondsText(value) {
    const number = Number(value || 0);
    return Math.round(number) + " s";
  }

  function cell(value) {
    const item = document.createElement("td");
    item.textContent = text(value);
    return item;
  }

  function statusPill(label, className) {
    const item = document.createElement("span");
    item.className = "status-pill " + (className || "");
    item.textContent = label;
    return item;
  }

  function pillCell(label, className) {
    const item = document.createElement("td");
    item.appendChild(statusPill(label, className));
    return item;
  }

  function statusRow(label, value) {
    const item = document.createElement("div");
    item.className = "stat-row";
    const labelElement = document.createElement("span");
    labelElement.textContent = label;
    const valueElement = document.createElement("strong");
    valueElement.textContent = text(value);
    item.append(labelElement, valueElement);
    return item;
  }

  function readinessLabel(status) {
    const labels = {
      ok: "bereit",
      warning: "Warnung",
      critical: "kritisch"
    };
    return labels[status] || text(status);
  }

  function healthClass(status) {
    if (status === "ok") return "is-active";
    if (status === "critical") return "is-error";
    return "is-stale";
  }

  function setHealthCard(key, status, detail) {
    const card = root.querySelector('[data-ai-health="' + key + '"]');
    if (!card) return;
    card.classList.remove("is-active", "is-stale", "is-error");
    card.classList.add(healthClass(status));
    const label = card.querySelector("[data-ai-health-label]");
    const detailElement = card.querySelector("[data-ai-health-detail]");
    if (label) label.textContent = readinessLabel(status);
    if (detailElement) detailElement.textContent = detail || "-";
  }

  /**
   * Update one card in the top-level AI status overview.
   */
  function lifecycleStepStatusLabel(status) {
    const labels = {
      available: "vorhanden",
      partial: "teilweise",
      missing: "offen"
    };
    return labels[status] || text(status);
  }

  function dateTimeText(value) {
    if (!value) return "-";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return text(value);
    return date.toLocaleString("de-DE");
  }

  function setAdminMessage(message, isError) {
    const target = root.querySelector("[data-ai-reindex-message]")
      || root.querySelector("[data-ai-admin-message]");
    if (target) {
      target.textContent = message || "";
      target.hidden = !message;
      target.classList.toggle("is-error", Boolean(isError));
    }
    if (message && window.maintenanceFrontend && window.maintenanceFrontend.showInterfaceToast) {
      window.maintenanceFrontend.showInterfaceToast(message, isError ? "error" : "info");
    }
  }

  /**
   * Run an admin data refresh and surface API failures without leaking backend details.
   */
  function runAdminLoad(loader, context) {
    loader().catch((error) => {
      setAdminMessage(safeErrorMessage(error, context), true);
    });
  }

  function setButtonBusy(button, busy, busyText) {
    if (window.maintenanceFrontend && window.maintenanceFrontend.setButtonBusy) {
      window.maintenanceFrontend.setButtonBusy(button, busy, busyText);
      return;
    }
    if (!button) return;
    if (busy) {
      if (!button.dataset.originalText) button.dataset.originalText = button.textContent;
      button.disabled = true;
      button.setAttribute("aria-busy", "true");
      if (busyText) {
        button.dataset.busyText = busyText;
        button.textContent = busyText;
      }
      return;
    }
    button.disabled = false;
    button.removeAttribute("aria-busy");
    if (button.dataset.originalText) {
      if (!button.dataset.busyText || button.textContent === button.dataset.busyText) {
        button.textContent = button.dataset.originalText;
      }
      delete button.dataset.originalText;
      delete button.dataset.busyText;
    }
  }

  function setFormBusy(form, busy, busyText) {
    if (window.maintenanceFrontend && window.maintenanceFrontend.setFormBusy) {
      window.maintenanceFrontend.setFormBusy(form, busy, busyText);
      return;
    }
    if (!form) return;
    setButtonBusy(form.querySelector("button[type='submit']"), busy, busyText);
    form.setAttribute("aria-busy", String(Boolean(busy)));
  }
  Object.assign(AdminAI, { bind, token, api, safeErrorMessage, redactSensitiveText, recordReference, renderAdminEmptyState, text, numberText, percentText, msText, moneyText, secondsText, cell, statusPill, pillCell, statusRow, readinessLabel, healthClass, setHealthCard, lifecycleStepStatusLabel, dateTimeText, setAdminMessage, runAdminLoad, setButtonBusy, setFormBusy });
})(window.MaintenanceAdminAI);

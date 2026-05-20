(function () {
  window.maintenanceShared = window.maintenanceShared || {};

  /**
   * Normalize toast variants used by the app shell.
   *
   * @param {string|undefined} variant Requested variant.
   * @returns {string} Supported variant.
   */
  function toastVariantName(variant) {
    if (variant === "success" || variant === "error" || variant === "info") return variant;
    return "info";
  }

  /**
   * Show a global interface toast through the app shell when available.
   *
   * @param {string} message Message to display.
   * @param {string|object} [variant] Toast variant or app-shell options object.
   * @returns {void}
   */
  function showInterfaceToast(message, variant) {
    if (window.maintenanceFrontend && window.maintenanceFrontend.showInterfaceToast) {
      window.maintenanceFrontend.showInterfaceToast(message, variant);
      return;
    }
    const normalizedVariant = toastVariantName(typeof variant === "string" ? variant : variant && variant.variant);
    let toast = document.querySelector("[data-interface-toast]");
    if (!toast) {
      toast = document.createElement("div");
      toast.className = "interface-toast";
      toast.dataset.interfaceToast = "true";
      toast.setAttribute("role", "status");
      toast.setAttribute("aria-live", "polite");
      document.body.appendChild(toast);
    }
    toast.textContent = message;
    toast.classList.remove("is-success", "is-error", "is-info");
    toast.classList.add("is-" + normalizedVariant);
    toast.hidden = false;
    window.clearTimeout(showInterfaceToast.timeoutId);
    showInterfaceToast.timeoutId = window.setTimeout(() => {
      toast.hidden = true;
    }, (variant && variant.duration) || 2600);

    const liveRegion = document.querySelector("[data-global-live-region]");
    if (liveRegion) liveRegion.textContent = message;
  }

  /**
   * Set inline status text with accessible live-region semantics.
   *
   * @param {Element|null} element Target status element.
   * @param {string} message Message to display.
   * @param {boolean|undefined} isError Whether the message is an error.
   * @returns {void}
   */
  function setStatusMessage(element, message, isError) {
    if (!element) return;
    element.textContent = message || "";
    element.classList.toggle("is-error", Boolean(isError));
    element.classList.toggle("is-success", Boolean(message && !isError));
    element.classList.toggle("is-info", Boolean(message && isError === undefined));
    if (message) {
      element.setAttribute("role", isError ? "alert" : "status");
      element.setAttribute("aria-live", isError ? "assertive" : "polite");
      return;
    }
    element.removeAttribute("role");
    element.removeAttribute("aria-live");
  }

  /**
   * Toggle busy state on a button without losing its original label.
   *
   * @param {HTMLButtonElement|null} button Button to update.
   * @param {boolean} busy Busy state.
   * @param {string} [busyText] Busy label.
   * @returns {void}
   */
  function setButtonBusy(button, busy, busyText) {
    if (window.maintenanceFrontend && window.maintenanceFrontend.setButtonBusy) {
      window.maintenanceFrontend.setButtonBusy(button, busy, busyText);
      return;
    }
    if (!button) return;
    if (busy) {
      if (!button.dataset.originalText) {
        button.dataset.originalText = button.textContent;
      }
      if (!button.dataset.originalDisabled) {
        button.dataset.originalDisabled = button.disabled ? "true" : "false";
      }
      button.disabled = true;
      button.classList.add("is-busy");
      button.setAttribute("aria-busy", "true");
      if (busyText) {
        button.dataset.busyText = busyText;
        button.textContent = busyText;
      }
      return;
    }
    button.disabled = button.dataset.originalDisabled === "true";
    button.classList.remove("is-busy");
    button.removeAttribute("aria-busy");
    if (button.dataset.originalText) {
      if (!button.dataset.busyText || button.textContent === button.dataset.busyText) {
        button.textContent = button.dataset.originalText;
      }
      delete button.dataset.originalText;
      delete button.dataset.busyText;
      delete button.dataset.originalDisabled;
    }
  }

  /**
   * Toggle busy state on a form and its submit button.
   *
   * @param {HTMLFormElement|null} form Form to update.
   * @param {boolean} busy Busy state.
   * @param {string} [busyText] Busy label.
   * @returns {void}
   */
  function setFormBusy(form, busy, busyText) {
    if (window.maintenanceFrontend && window.maintenanceFrontend.setFormBusy) {
      window.maintenanceFrontend.setFormBusy(form, busy, busyText);
      return;
    }
    if (!form) return;
    const submitButton = form.querySelector("button[type='submit']");
    setButtonBusy(submitButton, busy, busyText);
    form.setAttribute("aria-busy", String(Boolean(busy)));
  }

  /**
   * Run an async UI action with busy state, status text, and optional toast.
   *
   * @param {object} options Action options.
   * @param {Function} options.action Async action function.
   * @returns {Promise<unknown|null>} Action result or null on handled error.
   */
  async function runAction(options) {
    const settings = options || {};
    if (window.maintenanceFrontend && window.maintenanceFrontend.runAction) {
      return window.maintenanceFrontend.runAction(settings);
    }
    const control = settings.button || settings.control || null;
    const form = settings.form || null;
    if (form) setFormBusy(form, true, settings.busyText || "Läuft...");
    else setButtonBusy(control, true, settings.busyText || "Läuft...");
    if (settings.pendingMessage) setStatusMessage(settings.statusElement, settings.pendingMessage);
    try {
      const result = await settings.action();
      if (settings.successMessage) {
        setStatusMessage(settings.statusElement, settings.successMessage, false);
        if (settings.toast !== false) showInterfaceToast(settings.successMessage, "success");
      }
      return result;
    } catch (error) {
      const message = error.message || settings.errorMessage || "Aktion fehlgeschlagen.";
      setStatusMessage(settings.statusElement, message, true);
      showInterfaceToast(message, "error");
      if (settings.rethrow) throw error;
      return null;
    } finally {
      if (form) setFormBusy(form, false);
      else setButtonBusy(control, false);
    }
  }

  /**
   * Request text input through the app-shell dialog.
   *
   * @param {object} options Dialog options.
   * @returns {Promise<string|null>} Entered text or null.
   */
  async function requestText(options) {
    if (window.maintenanceFrontend && window.maintenanceFrontend.requestText) {
      return window.maintenanceFrontend.requestText(options);
    }
    showInterfaceToast("Eingabedialog konnte nicht geöffnet werden.", "error");
    return null;
  }

  /**
   * Show an informational dialog through the app shell.
   *
   * @param {object} options Dialog options.
   * @returns {Promise<boolean>} Whether the dialog was acknowledged.
   */
  async function showInfoDialog(options) {
    if (window.maintenanceFrontend && window.maintenanceFrontend.showInfoDialog) {
      return window.maintenanceFrontend.showInfoDialog(options);
    }
    showInterfaceToast((options && options.message) || "Information nicht verfügbar.", "info");
    return true;
  }

  /**
   * Request confirmation through the app-shell dialog.
   *
   * @param {object} options Dialog options.
   * @returns {Promise<boolean>} Whether the action was confirmed.
   */
  async function confirmAction(options) {
    if (window.maintenanceFrontend && window.maintenanceFrontend.confirmAction) {
      return window.maintenanceFrontend.confirmAction(options);
    }
    showInterfaceToast("Bestätigungsdialog konnte nicht geöffnet werden.", "error");
    return false;
  }

  /**
   * Create a guided empty-state element.
   *
   * @param {string} title Empty-state title.
   * @param {string} [hint] Supporting hint text.
   * @param {string} [className] Optional class name.
   * @returns {HTMLDivElement} Empty-state element.
   */
  function emptyState(title, hint, className = "guided-empty-state") {
    const element = document.createElement("div");
    element.className = className;
    const titleElement = document.createElement("strong");
    titleElement.textContent = title || "Keine Daten vorhanden.";
    element.appendChild(titleElement);
    if (hint) {
      const hintElement = document.createElement("p");
      hintElement.textContent = hint;
      element.appendChild(hintElement);
    }
    return element;
  }

  /**
   * Render a table message row spanning the requested number of columns.
   *
   * @param {HTMLTableSectionElement|null} tableBody Table body to update.
   * @param {number} colspan Number of columns to span.
   * @param {string} message Message to display.
   * @param {boolean} [isError=false] Whether the message is an error.
   * @returns {void}
   */
  function renderTableMessage(tableBody, colspan, message, isError = false) {
    if (!tableBody) return;
    tableBody.innerHTML = "";
    const cell = document.createElement("td");
    cell.colSpan = colspan;
    cell.appendChild(emptyState(
      message,
      isError ? "Bitte später erneut versuchen oder die Verbindung prüfen." : ""
    ));
    const tableRow = document.createElement("tr");
    tableRow.appendChild(cell);
    tableBody.appendChild(tableRow);
  }

  window.maintenanceShared.ui = {
    confirmAction,
    emptyState,
    renderTableMessage,
    requestText,
    runAction,
    setButtonBusy,
    setFormBusy,
    setStatusMessage,
    showInfoDialog,
    showInterfaceToast
  };
})();

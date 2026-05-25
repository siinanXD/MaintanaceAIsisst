(function () {
  const STATIC_VERSION = "20260521-task-priority1";
  const WORKFLOW_MODULE_URL = "/static/pages/workflow-loader.js?v=" + STATIC_VERSION;
  const PAGE_MODULE_URLS = {
    "/login": "/static/pages/login.js?v=" + STATIC_VERSION
  };
  window.maintenanceStaticVersion = STATIC_VERSION;
  let workflowImportPromise = null;
  const pageImportPromises = new Map();

  function onReady(callback) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", callback, { once: true });
      return;
    }
    callback();
  }

  function normalizeSearchText(value) {
    return String(value || "")
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "");
  }

  function urlSearchValue() {
    const params = new URLSearchParams(window.location.search);
    return params.get("search") || "";
  }

  function toastVariantName(variant) {
    if (variant === "success" || variant === "error" || variant === "info") return variant;
    return "info";
  }

  function showInterfaceToast(message, options) {
    const settings = typeof options === "string" ? { variant: options } : (options || {});
    const variant = toastVariantName(settings.variant);
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
    toast.classList.add("is-" + variant);
    toast.hidden = false;
    window.clearTimeout(showInterfaceToast.timeoutId);
    showInterfaceToast.timeoutId = window.setTimeout(() => {
      toast.hidden = true;
    }, settings.duration || 3200);

    const liveRegion = document.querySelector("[data-global-live-region]");
    if (liveRegion) liveRegion.textContent = message;
  }

  function setActionStatus(element, message, variant) {
    if (!element) return;
    const normalizedVariant = toastVariantName(variant);
    element.textContent = message || "";
    element.classList.remove("is-success", "is-error", "is-info");
    if (message) element.classList.add("is-" + normalizedVariant);
  }

  function setButtonBusy(button, busy, busyText) {
    if (!button) return;
    if (busy) {
      if (!button.dataset.originalText) button.dataset.originalText = button.textContent;
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
    button.classList.remove("is-busy");
    button.removeAttribute("aria-busy");
    button.disabled = button.dataset.originalDisabled === "true";
    if (button.dataset.originalText && (!button.dataset.busyText || button.textContent === button.dataset.busyText)) {
      button.textContent = button.dataset.originalText;
    }
    delete button.dataset.originalText;
    delete button.dataset.originalDisabled;
    delete button.dataset.busyText;
  }

  function setFormBusy(form, busy, busyText) {
    if (!form) return;
    const controls = Array.from(form.querySelectorAll("button, input, select, textarea"));
    form.classList.toggle("is-busy", Boolean(busy));
    form.setAttribute("aria-busy", String(Boolean(busy)));
    controls.forEach((control) => {
      if (control.matches("button[type='submit']")) {
        setButtonBusy(control, busy, busyText);
        return;
      }
      if (busy) {
        if (!control.dataset.originalDisabled) {
          control.dataset.originalDisabled = control.disabled ? "true" : "false";
        }
        control.disabled = true;
        return;
      }
      control.disabled = control.dataset.originalDisabled === "true";
      delete control.dataset.originalDisabled;
    });
    if (!busy) form.removeAttribute("aria-busy");
  }

  async function runAction(options) {
    const settings = options || {};
    const control = settings.button || settings.control || null;
    const form = settings.form || null;
    const statusElement = settings.statusElement || null;
    const busyText = settings.busyText || "Läuft...";
    if (control && control.disabled) return null;
    if (form) setFormBusy(form, true, busyText);
    else setButtonBusy(control, true, busyText);
    if (settings.pendingMessage) setActionStatus(statusElement, settings.pendingMessage, "info");
    try {
      const result = await settings.action();
      if (settings.successMessage) {
        setActionStatus(statusElement, settings.successMessage, "success");
        if (settings.toast !== false) showInterfaceToast(settings.successMessage, "success");
      }
      return result;
    } catch (error) {
      const message = error && error.message ? error.message : (settings.errorMessage || "Aktion fehlgeschlagen.");
      setActionStatus(statusElement, message, "error");
      showInterfaceToast(message, "error");
      if (settings.rethrow) throw error;
      return null;
    } finally {
      if (form) setFormBusy(form, false);
      else setButtonBusy(control, false);
    }
  }

  function workflowStatusElement() {
    const main = document.querySelector(".app-main");
    if (!main) return null;
    let status = main.querySelector("[data-workflow-status]");
    if (!status) {
      status = document.createElement("div");
      status.className = "workflow-status";
      status.dataset.workflowStatus = "true";
      status.setAttribute("role", "status");
      status.setAttribute("aria-live", "polite");
      main.prepend(status);
    }
    return status;
  }

  function setWorkflowStatus(message, variant) {
    const status = workflowStatusElement();
    if (!status) return;
    setActionStatus(status, message, variant || "info");
    status.hidden = !message;
  }

  function focusableElements(container) {
    return Array.from(container.querySelectorAll(
      "a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])"
    )).filter((element) => element.offsetParent !== null || element === document.activeElement);
  }

  function ensureActionDialog() {
    let overlay = document.querySelector("[data-action-dialog]");
    if (overlay) return overlay;

    overlay = document.createElement("div");
    overlay.className = "modal action-dialog";
    overlay.dataset.actionDialog = "true";
    overlay.hidden = true;
    overlay.innerHTML = [
      '<form class="modal-box action-dialog-box" data-action-dialog-form role="dialog" aria-modal="true" aria-labelledby="action-dialog-title" aria-describedby="action-dialog-message action-dialog-error">',
      '  <div class="panel-header action-dialog-header">',
      '    <div>',
      '      <p class="page-kicker" data-action-dialog-kicker>Aktion</p>',
      '      <h2 class="panel-title" id="action-dialog-title" data-action-dialog-title></h2>',
      '    </div>',
      '  </div>',
      '  <p class="panel-meta action-dialog-message" id="action-dialog-message" data-action-dialog-message></p>',
      '  <label class="field action-dialog-field" data-action-dialog-field>',
      '    <span data-action-dialog-label></span>',
      '    <input class="input input-bordered w-full" aria-describedby="action-dialog-error" data-action-dialog-input>',
      '    <textarea class="textarea textarea-bordered w-full" rows="4" aria-describedby="action-dialog-error" data-action-dialog-textarea></textarea>',
      '  </label>',
      '  <p class="form-message" id="action-dialog-error" data-action-dialog-error role="alert"></p>',
      '  <div class="toolbar action-dialog-actions">',
      '    <button class="btn btn-ghost" type="button" data-action-dialog-cancel>Abbrechen</button>',
      '    <button class="btn btn-primary" type="submit" data-action-dialog-confirm>OK</button>',
      '  </div>',
      '</form>'
    ].join("");
    document.body.appendChild(overlay);
    return overlay;
  }

  function openActionDialog(options) {
    const settings = options || {};
    const mode = settings.mode || "info";
    const overlay = ensureActionDialog();
    const dialog = overlay.querySelector("[data-action-dialog-form]");
    const title = overlay.querySelector("[data-action-dialog-title]");
    const kicker = overlay.querySelector("[data-action-dialog-kicker]");
    const message = overlay.querySelector("[data-action-dialog-message]");
    const field = overlay.querySelector("[data-action-dialog-field]");
    const label = overlay.querySelector("[data-action-dialog-label]");
    const input = overlay.querySelector("[data-action-dialog-input]");
    const textarea = overlay.querySelector("[data-action-dialog-textarea]");
    const error = overlay.querySelector("[data-action-dialog-error]");
    const cancelButton = overlay.querySelector("[data-action-dialog-cancel]");
    const confirmButton = overlay.querySelector("[data-action-dialog-confirm]");
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const usesText = mode === "text";
    const textControl = settings.multiline ? textarea : input;

    title.textContent = settings.title || "Aktion bestätigen";
    kicker.textContent = settings.kicker || (mode === "text" ? "Eingabe" : "Aktion");
    message.textContent = settings.message || "";
    label.textContent = settings.label || "Wert";
    error.textContent = "";
    error.classList.remove("is-error");
    field.hidden = !usesText;
    input.hidden = settings.multiline || !usesText;
    textarea.hidden = !settings.multiline || !usesText;
    input.value = settings.defaultValue || "";
    textarea.value = settings.defaultValue || "";
    input.removeAttribute("aria-invalid");
    textarea.removeAttribute("aria-invalid");
    input.type = settings.inputType || "text";
    input.required = Boolean(settings.required && !settings.multiline);
    textarea.required = Boolean(settings.required && settings.multiline);
    confirmButton.textContent = settings.confirmText || (mode === "confirm" ? "Bestätigen" : "OK");
    cancelButton.textContent = settings.cancelText || "Abbrechen";
    cancelButton.hidden = mode === "info";
    overlay.hidden = false;
    document.body.classList.add("has-open-dialog");

    return new Promise((resolve) => {
      let settled = false;

      function closeDialog(value) {
        if (settled) return;
        settled = true;
        overlay.hidden = true;
        document.body.classList.remove("has-open-dialog");
        dialog.removeEventListener("submit", handleSubmit);
        cancelButton.removeEventListener("click", handleCancel);
        overlay.removeEventListener("click", handleOverlayClick);
        overlay.removeEventListener("keydown", handleKeydown);
        if (previousFocus && previousFocus.focus) previousFocus.focus();
        resolve(value);
      }

      function handleCancel() {
        closeDialog(mode === "confirm" ? false : null);
      }

      function handleOverlayClick(event) {
        if (event.target === overlay) handleCancel();
      }

      function handleKeydown(event) {
        if (event.key === "Escape") {
          event.preventDefault();
          handleCancel();
          return;
        }
        if (event.key !== "Tab") return;
        const focusable = focusableElements(dialog);
        if (!focusable.length) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }

      function handleSubmit(event) {
        event.preventDefault();
        if (mode === "confirm") {
          closeDialog(true);
          return;
        }
        if (mode === "info") {
          closeDialog(true);
          return;
        }
        const value = textControl.value || "";
        if (settings.required && !value.trim()) {
          error.textContent = settings.requiredMessage || "Bitte einen Wert eingeben.";
          error.classList.add("is-error");
          textControl.setAttribute("aria-invalid", "true");
          textControl.focus();
          return;
        }
        textControl.removeAttribute("aria-invalid");
        closeDialog(value);
      }

      dialog.addEventListener("submit", handleSubmit);
      cancelButton.addEventListener("click", handleCancel);
      overlay.addEventListener("click", handleOverlayClick);
      overlay.addEventListener("keydown", handleKeydown);
      window.setTimeout(() => {
        if (usesText) textControl.focus();
        else confirmButton.focus();
      }, 0);
    });
  }

  function confirmAction(options) {
    return openActionDialog({ ...(options || {}), mode: "confirm" });
  }

  function requestText(options) {
    return openActionDialog({ ...(options || {}), mode: "text" });
  }

  function showInfoDialog(options) {
    return openActionDialog({ ...(options || {}), mode: "info" });
  }

  function currentShiftFor(date) {
    const minutes = date.getHours() * 60 + date.getMinutes();
    if (minutes >= 6 * 60 && minutes < 14 * 60) {
      return { key: "early", label: "Frühschicht", time: "06:00 - 14:00" };
    }
    if (minutes >= 14 * 60 && minutes < 22 * 60) {
      return { key: "late", label: "Spätschicht", time: "14:00 - 22:00" };
    }
    return { key: "night", label: "Nachtschicht", time: "22:00 - 06:00" };
  }

  function formatTopbarDate(date) {
    return new Intl.DateTimeFormat("de-DE", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric"
    }).format(date);
  }

  function initTopbarClock() {
    const dateElement = document.querySelector("[data-current-date]");
    const shiftButton = document.querySelector("[data-current-shift]");
    const shiftLabel = document.querySelector("[data-current-shift-label]");
    const shiftTime = document.querySelector("[data-current-shift-time]");
    if (!dateElement && !shiftLabel && !shiftTime) return;

    const render = () => {
      const now = new Date();
      const shift = currentShiftFor(now);
      if (dateElement) {
        dateElement.textContent = formatTopbarDate(now);
        dateElement.title = now.toLocaleDateString("de-DE", { weekday: "long" });
      }
      if (shiftLabel) shiftLabel.textContent = shift.label;
      if (shiftTime) shiftTime.textContent = shift.time;
      if (shiftButton) {
        shiftButton.classList.remove("is-early", "is-late", "is-night");
        shiftButton.classList.add("is-" + shift.key);
        shiftButton.title = "Aktuell: " + shift.label + " (" + shift.time + ")";
        shiftButton.setAttribute("aria-label", "Aktuell laufende Schicht: " + shift.label);
      }
    };

    render();
    window.setInterval(render, 60 * 1000);
  }

  function initAppShellPreferences() {
    const layout = document.querySelector(".app-shell-layout");
    const toggle = document.querySelector("[data-sidebar-toggle]");
    const label = document.querySelector("[data-sidebar-toggle-label]");
    const mobileNav = document.querySelector("[data-nav-root]");
    const storageKey = "maintenance_sidebar_collapsed";

    function applyCollapsedState(collapsed) {
      if (!layout || !toggle) return;
      layout.classList.toggle("is-sidebar-collapsed", collapsed);
      toggle.setAttribute("aria-pressed", String(collapsed));
      toggle.setAttribute("aria-label", collapsed ? "Menü erweitern" : "Menü minimieren");
      if (label) label.textContent = collapsed ? "Menü erweitern" : "Menü minimieren";
    }

    if (layout && toggle) {
      applyCollapsedState(window.localStorage.getItem(storageKey) === "true");
      toggle.addEventListener("click", () => {
        const collapsed = !layout.classList.contains("is-sidebar-collapsed");
        window.localStorage.setItem(storageKey, String(collapsed));
        applyCollapsedState(collapsed);
      });
    }

    if (mobileNav) {
      mobileNav.addEventListener("click", (event) => {
        if (event.target.closest("a[href]")) mobileNav.open = false;
      });
    }
  }

  function initLocalListSearch() {
    const searchInputs = Array.from(document.querySelectorAll("[data-list-search]"));
    searchInputs.forEach((input) => {
      const deepLinkSearch = urlSearchValue();
      if (deepLinkSearch && !input.value) input.value = deepLinkSearch;
      const targetSelector = input.dataset.listSearchTarget;
      if (!targetSelector) return;
      const target = document.querySelector(targetSelector);
      if (!target) return;

      const applyFilter = () => {
        const query = normalizeSearchText(input.value);
        const itemSelector = target.dataset.listSearchItems || (target.tagName === "TBODY" ? "tr" : ":scope > *");
        Array.from(target.querySelectorAll(itemSelector)).forEach((item) => {
          const isEmptyState = item.classList.contains("empty-state");
          const matches = !query || normalizeSearchText(item.textContent).includes(query);
          item.hidden = !isEmptyState && !matches;
        });
      };

      input.addEventListener("input", applyFilter);
      new MutationObserver(applyFilter).observe(target, { childList: true, subtree: true });
      applyFilter();
    });
  }

  function initDeepLinkedSearchInputs() {
    const deepLinkSearch = urlSearchValue();
    if (!deepLinkSearch) return;
    document.querySelectorAll("[data-error-search]").forEach((input) => {
      if (!input.value) input.value = deepLinkSearch;
    });
  }

  function globalSearchTypeLabel(type) {
    const labels = {
      task: "Aufgabe",
      error: "Störung",
      document: "Dokument"
    };
    return labels[type] || "Treffer";
  }

  function globalSearchFallbackUrl(query) {
    return "/tasks?search=" + encodeURIComponent(query);
  }

  function renderGlobalSearchMessage(resultsElement, message, variant) {
    resultsElement.innerHTML = "";
    const item = document.createElement("div");
    item.className = "global-search-empty";
    if (variant) item.classList.add("is-" + variant);
    item.textContent = message;
    resultsElement.appendChild(item);
  }

  function renderGlobalSearchResults(resultsElement, results, query) {
    resultsElement.innerHTML = "";
    if (!results.length) {
      renderGlobalSearchMessage(resultsElement, "Keine Treffer. Enter öffnet die Aufgabensuche.", "info");
      return;
    }

    const groups = results.reduce((accumulator, result) => {
      const type = result.type || "result";
      if (!accumulator.has(type)) accumulator.set(type, []);
      accumulator.get(type).push(result);
      return accumulator;
    }, new Map());

    groups.forEach((groupResults, type) => {
      const group = document.createElement("section");
      group.className = "global-search-group";
      const title = document.createElement("h2");
      title.textContent = globalSearchTypeLabel(type);
      group.appendChild(title);

      groupResults.forEach((result) => {
        const link = document.createElement("a");
        link.className = "global-search-result";
        link.href = result.ui_url || result.url || globalSearchFallbackUrl(query);

        const content = document.createElement("span");
        content.className = "global-search-result-content";
        const resultTitle = document.createElement("strong");
        resultTitle.textContent = result.title || "Ohne Titel";
        content.appendChild(resultTitle);
        if (result.summary) {
          const summary = document.createElement("small");
          summary.textContent = result.summary;
          content.appendChild(summary);
        }
        link.appendChild(content);

        if (result.badge || result.status) {
          const badge = document.createElement("span");
          badge.className = "global-search-result-badge";
          badge.textContent = result.badge || result.status;
          link.appendChild(badge);
        }

        group.appendChild(link);
      });
      resultsElement.appendChild(group);
    });
  }

  function initGlobalSearch() {
    const forms = Array.from(document.querySelectorAll("[data-global-search-form]"));
    if (!forms.length) return;
    forms.forEach((form) => {
      const input = form.querySelector("[data-global-search-input]");
      const panel = form.querySelector("[data-global-search-panel]");
      const resultsElement = form.querySelector("[data-global-search-results]");
      if (!input || !panel || !resultsElement) return;

      let debounceId = null;
      let activeQuery = "";
      let lastResults = [];

      const closePanel = () => {
        panel.hidden = true;
      };
      const openPanel = () => {
        panel.hidden = false;
      };
      const runSearch = async () => {
        const query = input.value.trim();
        activeQuery = query;
        if (query.length < 2) {
          closePanel();
          lastResults = [];
          return;
        }
        if (!window.maintenanceApi || !window.maintenanceAuth || !window.maintenanceAuth.token()) {
          openPanel();
          renderGlobalSearchMessage(resultsElement, "Bitte zuerst anmelden.", "error");
          return;
        }
        openPanel();
        renderGlobalSearchMessage(resultsElement, "Suche läuft...", "info");
        try {
          const payload = await window.maintenanceApi.request(
            "/api/v1/search?q=" + encodeURIComponent(query)
          );
          if (activeQuery !== query) return;
          lastResults = Array.isArray(payload.results) ? payload.results : [];
          renderGlobalSearchResults(resultsElement, lastResults, query);
        } catch (error) {
          console.warn(error);
          lastResults = [];
          renderGlobalSearchMessage(resultsElement, "Suche konnte nicht geladen werden.", "error");
        }
      };

      input.addEventListener("input", () => {
        window.clearTimeout(debounceId);
        debounceId = window.setTimeout(runSearch, 220);
      });
      input.addEventListener("focus", () => {
        if (input.value.trim().length >= 2) runSearch();
      });
      input.addEventListener("keydown", (event) => {
        if (event.key === "Escape") closePanel();
      });
      form.addEventListener("submit", (event) => {
        event.preventDefault();
        const query = input.value.trim();
        if (!query) return;
        const firstResult = lastResults[0];
        window.location.href = firstResult ? (firstResult.ui_url || firstResult.url) : globalSearchFallbackUrl(query);
      });
      document.addEventListener("click", (event) => {
        if (!form.contains(event.target)) closePanel();
      });
    });
  }

  function initHelpDisclosures() {
    document.querySelectorAll(".help-disclosure").forEach((details) => {
      const summary = details.querySelector("summary");
      if (!summary) return;
      summary.setAttribute("aria-expanded", String(details.open));
      details.addEventListener("toggle", () => {
        summary.setAttribute("aria-expanded", String(details.open));
      });
    });
  }

  function initTopbarActions() {
    const workButton = document.querySelector("[data-topbar-work]");
    const dateButton = document.querySelector("[data-topbar-date]");
    const shiftButton = document.querySelector("[data-current-shift]");
    const notificationButton = document.querySelector("[data-topbar-notifications]");

    if (workButton) {
      workButton.addEventListener("click", () => {
        showInterfaceToast("Werk 1 ist aktiv. Weitere Werke sind noch nicht konfiguriert.");
      });
    }
    if (dateButton) {
      dateButton.addEventListener("click", () => {
        window.location.href = "/shiftplans";
      });
    }
    if (shiftButton) {
      shiftButton.addEventListener("click", () => {
        window.location.href = "/shiftplans";
      });
    }
    if (notificationButton) {
      notificationButton.addEventListener("click", () => {
        const briefing = document.querySelector("#daily-briefing");
        if (briefing) {
          briefing.scrollIntoView({ behavior: "smooth", block: "start" });
          showInterfaceToast("Briefing und kritische Hinweise geöffnet.");
          return;
        }
        window.location.href = "/";
      });
    }
  }

  function initMobileCollapsibleSections() {
    const sections = Array.from(document.querySelectorAll("[data-mobile-collapsible]"));
    if (!sections.length || !window.matchMedia) return;

    const mobileQuery = window.matchMedia("(max-width: 639px)");
    let syncing = false;

    function syncSections() {
      syncing = true;
      sections.forEach((section) => {
        if (mobileQuery.matches) {
          if (!section.dataset.mobileTouched) section.open = false;
          return;
        }
        section.open = section.dataset.defaultCollapsed !== "true";
      });
      syncing = false;
    }

    sections.forEach((section) => {
      section.addEventListener("toggle", () => {
        if (syncing) return;
        if (mobileQuery.matches) section.dataset.mobileTouched = "true";
      });
    });

    syncSections();
    if (mobileQuery.addEventListener) {
      mobileQuery.addEventListener("change", syncSections);
    } else if (mobileQuery.addListener) {
      mobileQuery.addListener(syncSections);
    }
  }

  function initAccessibleForms() {
    const interactiveSelector = "input, select, textarea";

    function updateInvalidState(field, forceInvalid) {
      if (!(field instanceof HTMLElement) || !field.matches(interactiveSelector)) return;
      const invalid = forceInvalid || (field.dataset.touched === "true" && field.validity && !field.validity.valid);
      if (invalid) {
        field.setAttribute("aria-invalid", "true");
        return;
      }
      field.removeAttribute("aria-invalid");
    }

    document.addEventListener("invalid", (event) => {
      updateInvalidState(event.target, true);
      showInterfaceToast("Bitte markierte Pflichtfelder prüfen.");
    }, true);

    document.addEventListener("input", (event) => {
      if (!(event.target instanceof HTMLElement)) return;
      event.target.dataset.touched = "true";
      updateInvalidState(event.target, false);
    });

    document.addEventListener("change", (event) => {
      if (!(event.target instanceof HTMLElement)) return;
      event.target.dataset.touched = "true";
      updateInvalidState(event.target, false);
    });
  }

  function tableCaptionText(table) {
    const context = table.closest("section, article, .panel, .app-card, .table-wrap");
    const heading = context
      ? context.querySelector("h1, h2, h3, h4, [data-table-caption]")
      : null;
    const headingText = heading ? heading.textContent.trim() : "";
    return headingText || "Datentabelle";
  }

  function prepareAccessibleTable(table) {
    if (!(table instanceof HTMLTableElement)) return;
    if (!table.querySelector("caption")) {
      const caption = document.createElement("caption");
      caption.className = "sr-only";
      caption.textContent = tableCaptionText(table);
      table.prepend(caption);
    }
    table.querySelectorAll("thead th:not([scope])").forEach((header) => {
      header.setAttribute("scope", "col");
    });
  }

  function initAccessibleTables() {
    const prepareAll = (root) => {
      root.querySelectorAll("table").forEach(prepareAccessibleTable);
    };
    prepareAll(document);
    new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        mutation.addedNodes.forEach((node) => {
          if (!(node instanceof HTMLElement)) return;
          if (node.matches("table")) prepareAccessibleTable(node);
          prepareAll(node);
        });
      });
    }).observe(document.body, { childList: true, subtree: true });
  }

  async function refreshShellCounters() {
    if (!window.maintenanceApi || !window.maintenanceAuth || !window.maintenanceAuth.token()) return;
    const jobs = [];
    const totalFromPayload = (result) => {
      const pagination = result && result.pagination;
      if (pagination && Number.isFinite(Number(pagination.total))) return Number(pagination.total);
      const dataPagination = result && result.data && result.data.pagination;
      if (dataPagination && Number.isFinite(Number(dataPagination.total))) return Number(dataPagination.total);
      const items = Array.isArray(result) ? result : (result && result.data) || [];
      return Array.isArray(items) ? items.length : 0;
    };
    if (window.maintenanceAuth.canView && window.maintenanceAuth.canView("tasks")) {
      jobs.push(
        window.maintenanceApi.request("/api/v1/tasks?limit=1")
          .then((result) => {
            document.querySelectorAll("[data-dashboard-task-count]").forEach((element) => {
              element.textContent = String(totalFromPayload(result));
            });
          })
      );
    }
    if (window.maintenanceAuth.canView && window.maintenanceAuth.canView("errors")) {
      jobs.push(
        window.maintenanceApi.request("/api/v1/errors?limit=1&active=1")
          .then((result) => {
            document.querySelectorAll("[data-dashboard-machine-issue-count]").forEach((element) => {
              element.textContent = String(totalFromPayload(result));
            });
          })
      );
    }
    await Promise.allSettled(jobs);
  }

  function shouldLoadWorkflowModule() {
    const featureRegistry = window.maintenanceFeatures;
    if (!featureRegistry || !featureRegistry.forPath) return false;
    const feature = featureRegistry.forPath(window.location.pathname);
    return Boolean(feature && feature.module === "workflows");
  }

  function pageModuleUrlForPath(pathname) {
    const featureRegistry = window.maintenanceFeatures;
    if (featureRegistry && featureRegistry.forPath) {
      const feature = featureRegistry.forPath(pathname);
      if (feature && feature.module === "page" && feature.moduleUrl) {
        return feature.moduleUrl + "?v=" + STATIC_VERSION;
      }
    }
    return PAGE_MODULE_URLS[pathname] || null;
  }

  function pageModuleRequiresAuth(pathname) {
    if (pathname === "/login") return false;
    const featureRegistry = window.maintenanceFeatures;
    if (!featureRegistry || !featureRegistry.forPath) return true;
    return Boolean(featureRegistry.forPath(pathname));
  }

  async function loadPageModule() {
    const moduleUrl = pageModuleUrlForPath(window.location.pathname);
    if (!moduleUrl) return null;
    if (pageModuleRequiresAuth(window.location.pathname) && (!window.maintenanceAuth || !window.maintenanceAuth.token())) {
      setWorkflowStatus("Sitzung wird geladen. Aktionen werden gleich aktiviert.", "info");
      return null;
    }
    if (!pageImportPromises.has(moduleUrl)) {
      setWorkflowStatus("Seitendaten werden geladen...", "info");
      pageImportPromises.set(moduleUrl, import(moduleUrl).catch((error) => {
        pageImportPromises.delete(moduleUrl);
        setWorkflowStatus("Seitenmodul konnte nicht geladen werden. Bitte Seite neu laden.", "error");
        console.warn(error);
        showInterfaceToast("Seitenmodul konnte nicht geladen werden.", "error");
        throw error;
      }));
    }
    const module = await pageImportPromises.get(moduleUrl);
    setWorkflowStatus("", "info");
    return module;
  }

  async function loadWorkflowModule() {
    if (!shouldLoadWorkflowModule()) return null;
    if (!window.maintenanceAuth || !window.maintenanceAuth.token()) {
      setWorkflowStatus("Sitzung wird geladen. Aktionen werden gleich aktiviert.", "info");
      return null;
    }
    if (!workflowImportPromise) {
      document.body.classList.add("is-workflow-loading");
      setWorkflowStatus("Seitendaten werden geladen...", "info");
      workflowImportPromise = import(WORKFLOW_MODULE_URL).catch((error) => {
        workflowImportPromise = null;
        document.body.classList.remove("is-workflow-loading");
        setWorkflowStatus("Seitendaten konnten nicht geladen werden. Bitte Seite neu laden.", "error");
        console.warn(error);
        showInterfaceToast("Seitendaten konnten nicht geladen werden.", "error");
        throw error;
      });
    }
    const module = await workflowImportPromise;
    document.body.classList.remove("is-workflow-loading");
    setWorkflowStatus("", "info");
    return module;
  }

  async function boot() {
    initAppShellPreferences();
    initMobileCollapsibleSections();
    initDeepLinkedSearchInputs();
    initLocalListSearch();
    initGlobalSearch();
    initHelpDisclosures();
    initAccessibleForms();
    initAccessibleTables();
    initTopbarClock();
    initTopbarActions();

    try {
      if (window.maintenanceAuth && window.maintenanceAuth.ensureReady) {
        await window.maintenanceAuth.ensureReady();
      }
      await refreshShellCounters();
      await Promise.all([
        loadWorkflowModule(),
        loadPageModule()
      ]);
    } catch (error) {
      console.warn(error);
    }
  }

  window.maintenanceFrontend = {
    confirmAction,
    loadWorkflowModule,
    loadPageModule,
    requestText,
    runAction,
    setActionStatus,
    setButtonBusy,
    setFormBusy,
    setWorkflowStatus,
    showInfoDialog,
    showInterfaceToast
  };

  window.addEventListener("maintenance-auth-changed", () => {
    refreshShellCounters().catch((error) => console.warn(error));
    loadWorkflowModule().catch((error) => console.warn(error));
    loadPageModule().catch((error) => console.warn(error));
  });

  onReady(boot);
})();

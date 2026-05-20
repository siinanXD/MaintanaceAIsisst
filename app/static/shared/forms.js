(function () {
  window.maintenanceShared = window.maintenanceShared || {};

  /**
   * Convert form data to a plain object.
   *
   * @param {HTMLFormElement} form Form to read.
   * @returns {object} Plain object with form field values.
   */
  function formDataToObject(form) {
    if (!(form instanceof HTMLFormElement)) {
      throw new TypeError("formDataToObject expects an HTMLFormElement.");
    }
    return Object.fromEntries(new FormData(form).entries());
  }

  /**
   * Build URLSearchParams from a form while skipping empty values.
   *
   * @param {HTMLFormElement} form Form to read.
   * @returns {URLSearchParams} Query parameters.
   */
  function formToQueryParams(form) {
    if (!(form instanceof HTMLFormElement)) {
      throw new TypeError("formToQueryParams expects an HTMLFormElement.");
    }
    const params = new URLSearchParams();
    new FormData(form).forEach((value, key) => {
      if (value !== undefined && value !== null && String(value).trim() !== "") {
        params.set(key, value);
      }
    });
    return params;
  }

  /**
   * Attach a submit handler that prevents the native submit first.
   *
   * @param {HTMLFormElement|null} form Form to bind.
   * @param {Function} handler Async or sync submit handler.
   * @returns {void}
   */
  function bindSubmit(form, handler) {
    if (!form || typeof handler !== "function") return;
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      await handler(event);
    });
  }

  window.maintenanceShared.forms = {
    bindSubmit,
    formDataToObject,
    formToQueryParams
  };
})();

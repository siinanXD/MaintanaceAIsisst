(function () {
  "use strict";

  const loginForm = document.querySelector("[data-login-form]");
  const loginMessage = document.querySelector("[data-login-message]");
  if (!loginForm || !loginMessage) return;

  function setLoginMessage(message, variant) {
    loginMessage.textContent = message || "";
    loginMessage.classList.remove("is-success", "is-error", "is-info");
    if (variant) loginMessage.classList.add("is-" + variant);
  }

  function setFieldValidity(name, invalid) {
    const field = loginForm.elements[name];
    if (!field) return;
    field.setAttribute("aria-invalid", String(Boolean(invalid)));
  }

  function loginDestination(user, nextPath) {
    if (window.maintenanceAuth && window.maintenanceAuth.destinationForUserOrNext) {
      return window.maintenanceAuth.destinationForUserOrNext(user, nextPath);
    }
    return "/";
  }

  function loginPayloadFromForm() {
    const formData = new FormData(loginForm);
    const loginValue = String(formData.get("login") || "").trim();
    const passwordValue = String(formData.get("password") || "");
    return { loginValue, passwordValue };
  }

  async function submitLogin(payload) {
    const loginValue = payload.loginValue;
    const passwordValue = payload.passwordValue;
    setFieldValidity("login", !loginValue);
    setFieldValidity("password", !passwordValue);
    if (!loginValue || !passwordValue) {
      throw new Error("Bitte Benutzername/E-Mail und Passwort eingeben.");
    }

    const response = await fetch("/api/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        login: loginValue,
        password: passwordValue
      })
    });

    const responseData = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(responseData.message || responseData.error || "Anmeldung fehlgeschlagen. Bitte Zugangsdaten prüfen.");
    }

    const data = responseData && responseData.success === true && Object.prototype.hasOwnProperty.call(responseData, "data")
      ? responseData.data
      : responseData;
    window.localStorage.setItem("maintenance_access_token", data.access_token);
    window.localStorage.setItem("maintenance_user", JSON.stringify(data.user));
    window.dispatchEvent(new Event("maintenance-auth-changed"));
    const nextPath = new URLSearchParams(window.location.search).get("next");
    window.location.href = loginDestination(data.user, nextPath);
    return data;
  }

  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const frontend = window.maintenanceFrontend || {};
    const payload = loginPayloadFromForm();
    await frontend.runAction({
      form: loginForm,
      statusElement: loginMessage,
      busyText: "Anmelden...",
      pendingMessage: "Anmeldung wird geprüft...",
      successMessage: "Anmeldung erfolgreich. Du wirst weitergeleitet...",
      errorMessage: "Anmeldung fehlgeschlagen.",
      action: () => submitLogin(payload)
    });
  });
})();

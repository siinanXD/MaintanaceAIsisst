(function () {
  const TOKEN_KEY = "maintenance_access_token";
  const USER_KEY = "maintenance_user";

  function hasToken() {
    return Boolean(window.localStorage.getItem(TOKEN_KEY));
  }

  function isAdminUser(user) {
    return Boolean(user && user.role === "master_admin");
  }

  function destinationForUser(user) {
    return isAdminUser(user) ? "/" : "/tasks";
  }

  function displayName(user) {
    if (!user) return "Benutzer";
    const source = user.username || user.email || "Eingeloggt";
    return source.includes("@") ? source.split("@")[0] : source;
  }

  function currentUser() {
    try {
      return JSON.parse(window.localStorage.getItem(USER_KEY) || "null");
    } catch (error) {
      return null;
    }
  }

  async function refreshUser() {
    const authToken = window.localStorage.getItem(TOKEN_KEY);
    if (!authToken) return null;

    try {
      const response = await fetch("/api/auth/me", {
        headers: { "Authorization": "Bearer " + authToken }
      });
      if (!response.ok) {
        if (response.status === 401 || response.status === 422) clearSession({ redirect: true });
        return null;
      }
      const freshUser = await response.json();
      window.localStorage.setItem(USER_KEY, JSON.stringify(freshUser));
      updateAuthUi();
      return freshUser;
    } catch (error) {
      return currentUser();
    }
  }

  function clearSession(options) {
    window.localStorage.removeItem(TOKEN_KEY);
    window.localStorage.removeItem(USER_KEY);
    window.dispatchEvent(new Event("maintenance-auth-changed"));
    updateAuthUi();
    if (options && options.redirect && window.location.pathname !== "/login") {
      window.location.href = "/login";
    }
  }

  function logout() {
    clearSession({ redirect: true });
  }

  let authReadyPromise;
  let refreshInFlight;

  function refreshUserInBackground() {
    if (!refreshInFlight) {
      refreshInFlight = refreshUser().finally(() => {
        refreshInFlight = null;
      });
    }
    return refreshInFlight;
  }

  async function ensureAuthReady() {
    if (!authReadyPromise) {
      authReadyPromise = (async () => {
        updateAuthUi();
        if (hasToken()) {
          refreshUserInBackground();
        }
        window.dispatchEvent(new Event("maintenance-auth-ready"));
        return currentUser();
      })();
    }
    return authReadyPromise;
  }

  function updateAuthUi() {
    const loggedIn = hasToken();
    const user = currentUser();
    const isAdmin = isAdminUser(user);
    document.body.classList.toggle("is-authenticated", loggedIn);
    document.body.classList.toggle("is-admin", isAdmin);

    document.querySelectorAll("[data-auth-session]").forEach((element) => {
      element.hidden = !loggedIn;
    });

    document.querySelectorAll("[data-session-name]").forEach((element) => {
      element.textContent = displayName(user);
    });

    document.querySelectorAll("[data-auth-login-link]").forEach((element) => {
      element.hidden = loggedIn;
    });

    document.querySelectorAll("[data-admin-only]").forEach((element) => {
      element.hidden = !isAdmin;
    });

    document.querySelectorAll("[data-hr-only]").forEach((element) => {
      element.hidden = !isAdmin;
    });

    document.querySelectorAll("[data-login-form]").forEach((element) => {
      element.hidden = loggedIn;
    });

    document.querySelectorAll("[data-logged-in-panel]").forEach((element) => {
      element.hidden = !loggedIn;
    });

    const limitedPaths = ["/tasks", "/errors", "/login"];
    if (loggedIn && !isAdmin && !limitedPaths.includes(window.location.pathname)) {
      window.location.href = "/tasks";
    }
  }

  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-logout-button]");
    if (button) {
      logout();
    }
  });

  window.addEventListener("storage", updateAuthUi);
  window.addEventListener("maintenance-auth-changed", updateAuthUi);
  document.addEventListener("DOMContentLoaded", ensureAuthReady);

  window.maintenanceAuth = {
    token: () => window.localStorage.getItem(TOKEN_KEY),
    user: currentUser,
    clearSession,
    destinationForUser,
    refreshUser,
    refreshUserInBackground,
    ensureReady: ensureAuthReady,
    isAdmin: () => isAdminUser(currentUser()),
    canManageEmployees: () => {
      const user = currentUser();
      return isAdminUser(user);
    }
  };
})();

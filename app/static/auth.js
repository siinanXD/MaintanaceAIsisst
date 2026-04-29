(function () {
  const TOKEN_KEY = "maintenance_access_token";
  const USER_KEY = "maintenance_user";

  function hasToken() {
    return Boolean(window.localStorage.getItem(TOKEN_KEY));
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
        if (response.status === 401 || response.status === 422) logout();
        return null;
      }
      const freshUser = await response.json();
      window.localStorage.setItem(USER_KEY, JSON.stringify(freshUser));
      return freshUser;
    } catch (error) {
      return currentUser();
    }
  }

  function logout() {
    window.localStorage.removeItem(TOKEN_KEY);
    window.localStorage.removeItem(USER_KEY);
    window.dispatchEvent(new Event("maintenance-auth-changed"));
    window.location.href = "/login";
  }

  let authReadyPromise;

  async function ensureAuthReady() {
    if (!authReadyPromise) {
      authReadyPromise = (async () => {
        if (hasToken()) {
          await refreshUser();
        }
        updateAuthUi();
        window.dispatchEvent(new Event("maintenance-auth-ready"));
        return currentUser();
      })();
    }
    return authReadyPromise;
  }

  function updateAuthUi() {
    const loggedIn = hasToken();
    const user = currentUser();
    document.body.classList.toggle("is-authenticated", loggedIn);
    document.body.classList.toggle("is-admin", Boolean(user && user.role === "master_admin"));

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
      element.hidden = !loggedIn;
    });

    document.querySelectorAll("[data-hr-only]").forEach((element) => {
      element.hidden = !loggedIn;
    });

    document.querySelectorAll("[data-login-form]").forEach((element) => {
      element.hidden = loggedIn;
    });

    document.querySelectorAll("[data-logged-in-panel]").forEach((element) => {
      element.hidden = !loggedIn;
    });
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
    refreshUser,
    ensureReady: ensureAuthReady,
    isAdmin: () => {
      const user = currentUser();
      return Boolean(user && user.role === "master_admin");
    },
    canManageEmployees: () => {
      const user = currentUser();
      return Boolean(user && (user.role === "master_admin" || user.role === "personalabteilung"));
    }
  };
})();

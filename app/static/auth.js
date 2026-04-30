(function () {
  const TOKEN_KEY = "maintenance_access_token";
  const USER_KEY = "maintenance_user";
  const CONTRAST_KEY = "maintenance_high_contrast";

  function hasToken() {
    return Boolean(window.localStorage.getItem(TOKEN_KEY));
  }

  function isAdminUser(user) {
    return Boolean(user && user.role === "master_admin");
  }

  const DASHBOARD_PATHS = {
    "/": "dashboard",
    "/tasks": "tasks",
    "/errors": "errors",
    "/employees": "employees",
    "/shiftplans": "shiftplans",
    "/machines": "machines",
    "/inventory": "inventory",
    "/documents": "documents",
    "/admin/users": "admin_users"
  };

  const DASHBOARD_DESTINATIONS = {
    dashboard: "/",
    tasks: "/tasks",
    errors: "/errors",
    employees: "/employees",
    shiftplans: "/shiftplans",
    machines: "/machines",
    inventory: "/inventory",
    documents: "/documents",
    admin_users: "/admin/users"
  };

  const DASHBOARD_ORDER = [
    "dashboard",
    "tasks",
    "errors",
    "employees",
    "shiftplans",
    "machines",
    "inventory",
    "documents",
    "admin_users"
  ];

  function permissionFor(user, dashboard) {
    if (isAdminUser(user)) return { can_view: true, can_write: true, employee_access_level: "confidential" };
    return (user && user.permissions && user.permissions[dashboard]) || {};
  }

  function canView(user, dashboard) {
    return Boolean(permissionFor(user, dashboard).can_view);
  }

  function canWrite(user, dashboard) {
    return Boolean(permissionFor(user, dashboard).can_write);
  }

  function employeeAccessLevel(user) {
    return permissionFor(user, "employees").employee_access_level || "none";
  }

  function destinationForUser(user) {
    const firstDashboard = DASHBOARD_ORDER.find((dashboard) => canView(user, dashboard));
    return DASHBOARD_DESTINATIONS[firstDashboard] || "/login";
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

  function highContrastEnabled() {
    return window.localStorage.getItem(CONTRAST_KEY) === "true";
  }

  function applyContrastPreference() {
    const enabled = highContrastEnabled();
    document.documentElement.classList.toggle("high-contrast", enabled);
    document.body.classList.toggle("high-contrast", enabled);
    document.querySelectorAll("[data-contrast-toggle]").forEach((button) => {
      button.setAttribute("aria-pressed", String(enabled));
      button.textContent = enabled ? "Standard-Kontrast" : "Hoher Kontrast";
    });
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
    applyContrastPreference();

    document.querySelectorAll("[data-auth-session]").forEach((element) => {
      element.hidden = !loggedIn;
    });

    document.querySelectorAll("[data-session-name]").forEach((element) => {
      element.textContent = displayName(user);
    });

    document.querySelectorAll("[data-auth-login-link]").forEach((element) => {
      element.hidden = loggedIn;
    });

    document.querySelectorAll("[data-dashboard-nav]").forEach((element) => {
      element.hidden = !loggedIn || !canView(user, element.dataset.dashboardNav);
    });

    document.querySelectorAll("[data-permission-view]").forEach((element) => {
      element.hidden = !canView(user, element.dataset.permissionView);
    });

    document.querySelectorAll("[data-permission-write]").forEach((element) => {
      element.hidden = !canWrite(user, element.dataset.permissionWrite);
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

    const requiredDashboard = DASHBOARD_PATHS[window.location.pathname];
    if (loggedIn && requiredDashboard && !canView(user, requiredDashboard)) {
      window.location.href = destinationForUser(user);
    }
  }

  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-logout-button]");
    if (button) {
      logout();
    }

    const contrastButton = event.target.closest("[data-contrast-toggle]");
    if (contrastButton) {
      window.localStorage.setItem(CONTRAST_KEY, String(!highContrastEnabled()));
      applyContrastPreference();
    }
  });

  window.addEventListener("storage", () => {
    updateAuthUi();
    applyContrastPreference();
  });
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
    canView: (dashboard) => canView(currentUser(), dashboard),
    canWrite: (dashboard) => canWrite(currentUser(), dashboard),
    employeeAccessLevel: () => employeeAccessLevel(currentUser()),
    canManageEmployees: () => {
      const user = currentUser();
      return canWrite(user, "employees") && employeeAccessLevel(user) === "confidential";
    }
  };
})();

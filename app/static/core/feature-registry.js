(function () {
  const FEATURES = [
    {
      key: "dashboard",
      permissionKey: "dashboard",
      label: "Dashboard",
      route: "/",
      group: "Arbeit",
      module: "workflows",
      initializers: ["initDashboardShiftRealtime", "initDailyCockpit"],
    },
    {
      key: "tasks",
      permissionKey: "tasks",
      label: "Tasks",
      route: "/tasks",
      group: "Arbeit",
      module: "workflows",
      initializers: ["initDepartments", "initTasks"],
    },
    {
      key: "errors",
      permissionKey: "errors",
      label: "Fehlerliste",
      route: "/errors",
      group: "Arbeit",
      module: "workflows",
      initializers: ["initDepartments", "initErrors"],
    },
    {
      key: "employees",
      permissionKey: "employees",
      label: "Mitarbeiter",
      route: "/employees",
      group: "Ressourcen",
      module: "workflows",
      initializers: ["initDepartments", "initEmployees"],
    },
    {
      key: "machines",
      permissionKey: "machines",
      label: "Maschinen",
      route: "/machines",
      group: "Ressourcen",
      module: "workflows",
      initializers: ["initMachines"],
    },
    {
      key: "inventory",
      permissionKey: "inventory",
      label: "Lager",
      route: "/inventory",
      group: "Ressourcen",
      module: "workflows",
      initializers: ["initInventory"],
    },
    {
      key: "shiftplans",
      permissionKey: "shiftplans",
      label: "Schichtplan",
      route: "/shiftplans",
      group: "Planung & Dokumente",
      module: "page",
      moduleUrl: "/static/pages/shiftplans.js",
    },
    {
      key: "handover",
      permissionKey: "shiftplans",
      label: "Schichtübergabe",
      route: "/handover",
      group: "Planung & Dokumente",
      module: "page",
      moduleUrl: "/static/pages/handover.js",
    },
    {
      key: "vacations",
      permissionKey: "employees",
      label: "Urlaubsplanung",
      route: "/vacations",
      group: "Planung & Dokumente",
      module: "workflows",
      initializers: ["initVacations"],
    },
    {
      key: "documents",
      permissionKey: "documents",
      label: "Dokumente",
      route: "/documents",
      group: "Planung & Dokumente",
      module: "workflows",
      initializers: ["initDocuments"],
    },
    {
      key: "admin_users",
      permissionKey: "admin_users",
      label: "Users",
      route: "/admin/users",
      group: "Administration",
      module: "workflows",
      initializers: ["initUsers"],
    },
    {
      key: "admin_ai",
      permissionKey: "admin_users",
      label: "AI Admin",
      route: "/admin/ai",
      group: "Administration",
      module: "page",
      moduleUrl: "/static/pages/admin-ai.js",
    },
  ];

  const byKey = Object.fromEntries(FEATURES.map((feature) => [feature.key, feature]));
  const byRoute = Object.fromEntries(FEATURES.map((feature) => [feature.route, feature]));

  function getFeature(featureKey) {
    return byKey[featureKey] || null;
  }

  function featureForPath(pathname) {
    return byRoute[pathname] || null;
  }

  function permissionKeyFor(featureKey) {
    const feature = getFeature(featureKey);
    return feature ? feature.permissionKey : featureKey;
  }

  window.maintenanceFeatures = {
    all: FEATURES,
    keys: FEATURES.map((feature) => feature.key),
    get: getFeature,
    forPath: featureForPath,
    permissionKeyFor,
    destinations: Object.fromEntries(
      FEATURES.map((feature) => [feature.key, feature.route])
    ),
  };
})();

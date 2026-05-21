(function () {
  const FEATURES = [
    {
      key: "dashboard",
      permissionKey: "dashboard",
      label: "Cockpit",
      route: "/",
      group: "Cockpit",
      module: "workflows",
      initializers: ["initDashboardShiftRealtime", "initDailyCockpit"],
    },
    {
      key: "tasks",
      permissionKey: "tasks",
      label: "Aufgaben",
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
      group: "Planung & Personal",
      module: "workflows",
      initializers: ["initDepartments", "initEmployees"],
    },
    {
      key: "machines",
      permissionKey: "machines",
      label: "Maschinen",
      route: "/machines",
      routePrefixes: ["/machines/"],
      group: "Wissen & Anlagen",
      module: "workflows",
      initializers: ["initMachines", "initMachineProfile"],
    },
    {
      key: "inventory",
      permissionKey: "inventory",
      label: "Lager",
      route: "/inventory",
      group: "Wissen & Anlagen",
      module: "workflows",
      initializers: ["initInventory"],
    },
    {
      key: "shiftplans",
      permissionKey: "shiftplans",
      label: "Schichtplan",
      route: "/shiftplans",
      group: "Planung & Personal",
      module: "page",
      moduleUrl: "/static/pages/shiftplans.js",
    },
    {
      key: "handover",
      permissionKey: "shiftplans",
      label: "Schichtübergabe",
      route: "/handover",
      group: "Arbeit",
      module: "page",
      moduleUrl: "/static/pages/handover.js",
    },
    {
      key: "vacations",
      permissionKey: "employees",
      label: "Urlaubsplanung",
      route: "/vacations",
      group: "Planung & Personal",
      module: "workflows",
      initializers: ["initVacations"],
    },
    {
      key: "documents",
      permissionKey: "documents",
      label: "Dokumente",
      route: "/documents",
      group: "Wissen & Anlagen",
      module: "workflows",
      initializers: ["initDocuments"],
    },
    {
      key: "admin_users",
      permissionKey: "admin_users",
      label: "Benutzer",
      route: "/admin/users",
      group: "Administration",
      module: "workflows",
      initializers: ["initUsers"],
    },
    {
      key: "admin_ai",
      permissionKey: "admin_users",
      label: "KI-Administration",
      route: "/admin/ai",
      routeAliases: [
        "/admin/ai/models",
        "/admin/ai/retrieval",
        "/admin/ai/knowledge",
        "/admin/ai/training",
        "/admin/ai/diagnostics",
        "/admin/ai/feedback",
        "/admin/ai/indexing"
      ],
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
    const directFeature = byRoute[pathname];
    if (directFeature) return directFeature;
    return FEATURES.find((feature) => {
      if (Array.isArray(feature.routeAliases) && feature.routeAliases.includes(pathname)) {
        return true;
      }
      return Array.isArray(feature.routePrefixes) && feature.routePrefixes.some((prefix) => (
        pathname.startsWith(prefix)
      ));
    }) || null;
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

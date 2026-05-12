(function () {
  const FEATURES = [
    {
      key: "dashboard",
      permissionKey: "dashboard",
      label: "Dashboard",
      route: "/",
      group: "Arbeit",
      initializer: "initDailyCockpit",
    },
    {
      key: "tasks",
      permissionKey: "tasks",
      label: "Tasks",
      route: "/tasks",
      group: "Arbeit",
      initializer: "initTasks",
    },
    {
      key: "errors",
      permissionKey: "errors",
      label: "Fehlerliste",
      route: "/errors",
      group: "Arbeit",
      initializer: "initErrors",
    },
    {
      key: "employees",
      permissionKey: "employees",
      label: "Mitarbeiter",
      route: "/employees",
      group: "Ressourcen",
      initializer: "initEmployees",
    },
    {
      key: "machines",
      permissionKey: "machines",
      label: "Maschinen",
      route: "/machines",
      group: "Ressourcen",
      initializer: "initMachines",
    },
    {
      key: "inventory",
      permissionKey: "inventory",
      label: "Lager",
      route: "/inventory",
      group: "Ressourcen",
      initializer: "initInventory",
    },
    {
      key: "shiftplans",
      permissionKey: "shiftplans",
      label: "Schichtplan",
      route: "/shiftplans",
      group: "Planung & Dokumente",
      initializer: "initShiftPlans",
    },
    {
      key: "handover",
      permissionKey: "shiftplans",
      label: "Schichtübergabe",
      route: "/handover",
      group: "Planung & Dokumente",
      initializer: "initHandover",
    },
    {
      key: "vacations",
      permissionKey: "employees",
      label: "Urlaubsplanung",
      route: "/vacations",
      group: "Planung & Dokumente",
      initializer: "initVacations",
    },
    {
      key: "documents",
      permissionKey: "documents",
      label: "Dokumente",
      route: "/documents",
      group: "Planung & Dokumente",
      initializer: "initDocuments",
    },
    {
      key: "admin_users",
      permissionKey: "admin_users",
      label: "Users",
      route: "/admin/users",
      group: "Administration",
      initializer: "initUsers",
    },
    {
      key: "admin_ai",
      permissionKey: "admin_users",
      label: "AI Admin",
      route: "/admin/ai",
      group: "Administration",
      initializer: "initAdminAi",
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

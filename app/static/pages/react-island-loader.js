const DEFAULT_REACT_MOUNT_TIMEOUT_MS = 900;

/**
 * Return the current static asset version.
 *
 * @returns {string} Static asset cache version.
 */
function staticVersion() {
  return window.maintenanceStaticVersion || "dev";
}

/**
 * Resolve an option that may be static or computed at runtime.
 *
 * @param {Array<string>|Function} value - Static value or resolver function.
 * @returns {Array<string>} Resolved string list.
 */
function resolveList(value) {
  return typeof value === "function" ? value() : value;
}

/**
 * Return true when React has mounted an island.
 *
 * @param {object} options - Island mount options.
 * @param {string} options.mountedFlag - Window flag set by React.
 * @param {string} [options.fallbackSelector] - Optional fallback selector with data-react-mounted.
 * @returns {boolean} Whether React owns the page.
 */
function reactIslandMounted(options) {
  return Boolean(
    window[options.mountedFlag]
      || (
        options.fallbackSelector
        && document.querySelector(options.fallbackSelector + "[data-react-mounted='true']")
      )
  );
}

/**
 * Wait briefly for a React island before falling back to legacy JavaScript.
 *
 * @param {object} options - Island wait options.
 * @param {string} options.mountedFlag - Window flag set by React.
 * @param {string} options.mountEvent - Event dispatched by React after mount.
 * @param {string} [options.fallbackSelector] - Optional fallback selector.
 * @param {number} [options.timeoutMs] - Maximum wait time.
 * @returns {Promise<boolean>} Resolves true when React mounted in time.
 */
function waitForReactIsland(options) {
  if (reactIslandMounted(options)) return Promise.resolve(true);

  return new Promise((resolve) => {
    let settled = false;

    /**
     * Resolve the mount wait once.
     *
     * @param {boolean} mounted - Whether React mounted before timeout.
     * @returns {void}
     */
    const finish = (mounted) => {
      if (settled) return;
      settled = true;
      window.removeEventListener(options.mountEvent, handleMounted);
      resolve(mounted);
    };

    /**
     * Mark React as mounted after the island dispatches its event.
     *
     * @returns {void}
     */
    const handleMounted = () => finish(true);

    window.addEventListener(options.mountEvent, handleMounted, { once: true });
    window.setTimeout(
      () => finish(reactIslandMounted(options)),
      options.timeoutMs || DEFAULT_REACT_MOUNT_TIMEOUT_MS
    );
  });
}

/**
 * Load shared workflow code and requested legacy modules.
 *
 * @param {Array<string>} workflowModules - Legacy workflow module filenames.
 * @returns {Promise<object>} The shared workflow module.
 */
async function loadLegacyWorkflowModules(workflowModules) {
  const version = staticVersion();
  const shared = await import("/static/pages/workflows/shared.js?v=" + version);
  await shared.loadWorkflowShared();
  for (const workflowModule of workflowModules) {
    await import("/static/pages/workflows/" + workflowModule + "?v=" + version);
  }
  return shared;
}

/**
 * Initialize a legacy workflow only if React did not mount.
 *
 * @param {object} options - Fallback configuration.
 * @param {string} options.mountedFlag - Window flag set by React.
 * @param {string} options.mountEvent - Event dispatched by React.
 * @param {string} [options.fallbackSelector] - Optional fallback selector.
 * @param {Array<string>|Function} options.workflowModules - Legacy workflow module filenames.
 * @param {Array<string>|Function} options.initializerNames - Initializer names to run in order.
 * @param {string} options.missingMessage - Error message for missing initializers.
 * @returns {Promise<void>} Resolves after React mount or legacy fallback initialization.
 */
async function initializeReactIslandFallback(options) {
  if (await waitForReactIsland(options)) return;
  const workflowModules = resolveList(options.workflowModules);
  const initializerNames = resolveList(options.initializerNames);
  const shared = await loadLegacyWorkflowModules(workflowModules);
  const initializers = initializerNames.map((initializerName) => (
    shared.resolveWorkflowInitializer(initializerName)
  ));
  if (initializers.some((initializer) => typeof initializer !== "function")) {
    throw new Error(options.missingMessage);
  }
  for (const initializer of initializers) {
    await initializer();
  }
}

/**
 * Wait for a React shell island and then initialize its page runtime.
 *
 * @param {object} options - Shell runtime bridge configuration.
 * @param {string} options.mountedFlag - Window flag set by React.
 * @param {string} options.mountEvent - Event dispatched by React.
 * @param {string} [options.fallbackSelector] - Optional fallback selector.
 * @param {number} [options.timeoutMs] - Maximum wait time before using fallback markup.
 * @param {Function} options.initializeRuntime - Runtime initializer to execute.
 * @returns {Promise<void>} Resolves after the runtime initializer has finished.
 */
async function initializeReactShellRuntime(options) {
  await waitForReactIsland(options);
  await options.initializeRuntime();
}

window.MaintenanceReactIslandLoader = {
  initializeReactIslandFallback,
  initializeReactShellRuntime,
  reactIslandMounted,
  waitForReactIsland
};

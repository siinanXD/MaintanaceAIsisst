const DEFAULT_REACT_MOUNT_TIMEOUT_MS = 900;

/**
 * Return true when React has mounted an island.
 *
 * @param {object} options - Island mount options.
 * @param {string} options.mountedFlag - Window flag set by React.
 * @returns {boolean} Whether React owns the page.
 */
function reactIslandMounted(options) {
  return Boolean(window[options.mountedFlag]);
}

/**
 * Wait briefly for a React island before falling back to legacy JavaScript.
 *
 * @param {object} options - Island wait options.
 * @param {string} options.mountedFlag - Window flag set by React.
 * @param {string} options.mountEvent - Event dispatched by React after mount.
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

window.MaintenanceReactIslandLoader = {
  reactIslandMounted,
  waitForReactIsland
};

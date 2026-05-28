export type ReactIslandMountOptions = {
  readonly fallbackSelector: string;
  readonly mountEvent: string;
  readonly mountedFlag: string;
};

/**
 * Hide a server-rendered fallback after a React island has mounted.
 */
export function hideFallback(fallbackSelector: string): void {
  document.querySelectorAll<HTMLElement>(fallbackSelector).forEach((element) => {
    element.hidden = true;
    element.dataset.reactMounted = "true";
  });
}

/**
 * Publish the mounted state for static fallback loaders.
 */
export function announceMount(mountedFlag: string, mountEvent: string): void {
  (window as unknown as Record<string, unknown>)[mountedFlag] = true;
  window.dispatchEvent(new Event(mountEvent));
}

/**
 * Hide fallback markup and announce that React owns the island.
 */
export function markIslandMounted(options: ReactIslandMountOptions): void {
  hideFallback(options.fallbackSelector);
  announceMount(options.mountedFlag, options.mountEvent);
}

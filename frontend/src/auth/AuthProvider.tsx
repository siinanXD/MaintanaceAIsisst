import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { legacyAuthRuntime } from "../app/runtimeBridge";
import { readStoredSession, type StoredSession } from "./session";

type AuthProviderValue = StoredSession & {
  readonly refresh: () => void;
};

const AuthContext = createContext<AuthProviderValue | null>(null);

/**
 * Read the current browser auth session.
 */
function currentAuthValue(refresh: () => void): AuthProviderValue {
  return {
    ...readStoredSession(),
    refresh
  };
}

/**
 * Provide the localStorage auth contract to React shell components.
 */
export function AuthProvider({ children }: { readonly children: ReactNode }): ReactNode {
  const [session, setSession] = useState<StoredSession>(() => readStoredSession());

  /**
   * Refresh React auth state from the legacy auth storage contract.
   */
  function refresh(): void {
    setSession(readStoredSession());
  }

  useEffect(() => {
    window.addEventListener("maintenance-auth-ready", refresh);
    window.addEventListener("maintenance-auth-changed", refresh);
    window.addEventListener("storage", refresh);
    void legacyAuthRuntime()?.ensureReady?.();

    return () => {
      window.removeEventListener("maintenance-auth-ready", refresh);
      window.removeEventListener("maintenance-auth-changed", refresh);
      window.removeEventListener("storage", refresh);
    };
  }, []);

  const value = useMemo<AuthProviderValue>(() => ({ ...session, refresh }), [session]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

/**
 * Return the React shell auth context, falling back to direct storage reads outside a provider.
 */
export function useAuthContext(): AuthProviderValue {
  const context = useContext(AuthContext);
  if (context) return context;
  return currentAuthValue(() => undefined);
}

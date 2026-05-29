import { useEffect, useState } from "react";

import { readStoredSession, type StoredSession } from "./session";

/**
 * Subscribe to the existing auth runtime events and return the current stored session.
 */
export function useAuthSession(): StoredSession {
  const [session, setSession] = useState<StoredSession>(() => readStoredSession());

  useEffect(() => {
    /**
     * Refresh React auth state from the localStorage contract used by auth.js.
     */
    function refreshSession(): void {
      setSession(readStoredSession());
    }

    window.addEventListener("maintenance-auth-ready", refreshSession);
    window.addEventListener("maintenance-auth-changed", refreshSession);
    window.addEventListener("storage", refreshSession);

    return () => {
      window.removeEventListener("maintenance-auth-ready", refreshSession);
      window.removeEventListener("maintenance-auth-changed", refreshSession);
      window.removeEventListener("storage", refreshSession);
    };
  }, []);

  return session;
}

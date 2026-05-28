export type MaintenanceUser = {
  readonly id?: number;
  readonly username?: string;
  readonly name?: string;
  readonly role?: string;
  readonly permissions?: Record<string, unknown>;
};

export type StoredSession = {
  readonly token: string | null;
  readonly user: MaintenanceUser | null;
  readonly error: string | null;
};

const TOKEN_KEY = "maintenance_access_token";
const USER_KEY = "maintenance_user";

/**
 * Return true when a parsed localStorage value can represent a stored user.
 */
function isMaintenanceUser(value: unknown): value is MaintenanceUser {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/**
 * Parse the existing user object from localStorage without hiding malformed data.
 */
function parseStoredUser(rawUser: string | null): Pick<StoredSession, "user" | "error"> {
  if (!rawUser) {
    return { user: null, error: null };
  }

  try {
    const parsedUser = JSON.parse(rawUser) as unknown;

    if (!isMaintenanceUser(parsedUser)) {
      return { user: null, error: "Gespeicherte Benutzerdaten haben ein ungültiges Format." };
    }

    return { user: parsedUser, error: null };
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unbekannter JSON-Fehler";
    return { user: null, error: `Gespeicherte Benutzerdaten konnten nicht gelesen werden: ${message}` };
  }
}

/**
 * Read the current auth session from the localStorage contract used by auth.js.
 */
export function readStoredSession(): StoredSession {
  const token = window.localStorage.getItem(TOKEN_KEY);
  const parsedUser = parseStoredUser(window.localStorage.getItem(USER_KEY));

  return {
    token,
    user: parsedUser.user,
    error: parsedUser.error
  };
}

/**
 * Return true when the existing frontend has a usable auth token.
 */
export function hasStoredToken(): boolean {
  return Boolean(window.localStorage.getItem(TOKEN_KEY));
}

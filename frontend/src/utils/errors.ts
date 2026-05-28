/**
 * Resolve a safe user-facing message from an unknown error.
 */
export function safeErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }

  return fallback;
}

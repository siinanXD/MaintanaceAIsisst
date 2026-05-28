type DateFormatOptions = Intl.DateTimeFormatOptions & {
  readonly dateOnly?: boolean;
  readonly fallback?: string;
};

/**
 * Parse a date or timestamp value for German UI formatting.
 */
function parseDateValue(value: unknown, dateOnly: boolean): Date | null {
  if (!value) return null;
  const rawValue = String(value);
  const parsed = new Date(dateOnly && !rawValue.includes("T") ? `${rawValue}T00:00:00` : rawValue);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

/**
 * Format a date or timestamp with German locale defaults.
 */
export function formatGermanDate(value: unknown, options: DateFormatOptions = {}): string {
  const { dateOnly = false, fallback = "-", ...formatOptions } = options;
  const parsed = parseDateValue(value, dateOnly);
  if (!parsed) return fallback;
  return parsed.toLocaleDateString("de-DE", formatOptions);
}

/**
 * Format a date or timestamp including time with German locale defaults.
 */
export function formatGermanDateTime(value: unknown, options: DateFormatOptions = {}): string {
  const { dateOnly = false, fallback = "-", ...formatOptions } = options;
  const parsed = parseDateValue(value, dateOnly);
  if (!parsed) return fallback;
  return parsed.toLocaleString("de-DE", formatOptions);
}

/**
 * Return today's local ISO date.
 */
export function todayIsoDate(): string {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}

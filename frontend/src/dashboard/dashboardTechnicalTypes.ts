export type DashboardSeverity = "critical" | "good" | "muted" | "warning";

export type DashboardSignalItem = {
  readonly detail: string;
  readonly href?: string;
  readonly label: string;
  readonly severity: DashboardSeverity;
  readonly value: string;
};

export type DashboardStatusRow = {
  readonly detail: string;
  readonly label: string;
  readonly severity: DashboardSeverity;
  readonly value: string;
};

export type DashboardHeroStatus = {
  readonly className: string;
  readonly label: string;
  readonly meta: string;
  readonly updated: string;
};

import type { ReactNode } from "react";

import { cancelVacationRequest, decideVacationRequest } from "../vacationApi";
import type { MaintenanceUser, MessageState, VacationRequest, VacationSummary } from "../vacationTypes";
import {
  canCancelVacation,
  canDecideVacation,
  formatVacationDate,
  vacationErrorMessage,
  vacationImpactLabel,
  vacationShiftLabel,
  vacationStatusLabel
} from "../vacationUtils";

type VacationRequestCardProps = {
  readonly mode: "pending" | "history";
  readonly onMessageChange: (message: MessageState) => void;
  readonly onMutated: () => Promise<void>;
  readonly request: VacationRequest;
  readonly selectedBalance: VacationSummary | null;
  readonly user: MaintenanceUser | null;
};

/**
 * Render one vacation metric value.
 */
export function VacationMetric({ label, value }: { readonly label: string; readonly value?: string }): ReactNode {
  return (
    <span className="vacation-metric">
      <strong>{value || "-"}</strong>
      <small>{label}</small>
    </span>
  );
}

/**
 * Render one compact meta line.
 */
function VacationMetaLine({ parts }: { readonly parts: readonly (string | undefined | null)[] }): ReactNode {
  return <p className="vacation-card-meta">{parts.filter(Boolean).join(" · ")}</p>;
}

/**
 * Render a vacation status badge.
 */
function VacationStatusBadge({ status }: { readonly status?: string }): ReactNode {
  return <span className={`vacation-status-badge is-${status || "muted"}`}>{vacationStatusLabel(status)}</span>;
}

/**
 * Render a vacation impact badge.
 */
function VacationImpactBadge({ level }: { readonly level?: string }): ReactNode {
  return <span className={`vacation-impact-badge is-${level || "ok"}`}>{vacationImpactLabel(level)}</span>;
}

/**
 * Render one vacation request card with actions.
 */
export function VacationRequestCard(props: VacationRequestCardProps): ReactNode {
  const request = props.request;
  const canDecide = props.mode === "pending" && canDecideVacation(props.user, request);
  const canCancel = canCancelVacation(props.user, request) && ["pending", "approved"].includes(request.status || "");

  /**
   * Approve or reject the selected vacation request.
   */
  async function decide(action: "approve" | "reject"): Promise<void> {
    try {
      props.onMessageChange({ text: "Antrag wird aktualisiert...", type: "" });
      await decideVacationRequest(request.id, action);
      props.onMessageChange({ text: "Antrag wurde aktualisiert.", type: "success" });
      await props.onMutated();
    } catch (error) {
      props.onMessageChange({ text: vacationErrorMessage(error), type: "error" });
    }
  }

  /**
   * Cancel the selected vacation request.
   */
  async function cancel(): Promise<void> {
    try {
      props.onMessageChange({ text: "Antrag wird storniert...", type: "" });
      await cancelVacationRequest(request.id);
      props.onMessageChange({ text: "Antrag wurde storniert.", type: "success" });
      await props.onMutated();
    } catch (error) {
      props.onMessageChange({ text: vacationErrorMessage(error), type: "error" });
    }
  }

  return (
    <article className={`vacation-request-card is-${request.impact_level || "ok"}`}>
      <header>
        <div>
          <h3>{request.employee?.name || String(request.employee_id)}</h3>
          <VacationMetaLine parts={[
            request.department || request.employee?.department,
            `${formatVacationDate(request.start_date)} bis ${formatVacationDate(request.end_date)}`,
            `${request.days_used || 0} Tage`,
            vacationShiftLabel(request.shift_type)
          ]} />
        </div>
        <div className="vacation-card-badges">
          <VacationStatusBadge status={request.status} />
          <VacationImpactBadge level={request.impact_level} />
        </div>
      </header>
      <div className="vacation-card-metrics">
        <VacationMetric label="Verfügbar" value={props.selectedBalance ? String(props.selectedBalance.available || 0) : "-"} />
        <VacationMetric label="Vertreter" value={request.representative?.name || "offen"} />
        <VacationMetric label="Entscheider" value={request.approved_by || "offen"} />
      </div>
      <div className="vacation-card-body">
        {request.reason ? <VacationMetaLine parts={["Grund", request.reason]} /> : null}
        {request.notes ? <VacationMetaLine parts={["Notiz", request.notes]} /> : null}
        {request.impact_summary ? <VacationMetaLine parts={["Auswirkung", request.impact_summary]} /> : null}
      </div>
      <div className="vacation-card-actions">
        {canDecide ? <button className="btn btn-success btn-xs" type="button" onClick={() => decide("approve")}>Genehmigen</button> : null}
        {canDecide ? <button className="btn btn-error btn-xs" type="button" onClick={() => decide("reject")}>Ablehnen</button> : null}
        {canCancel ? <button className="btn btn-outline btn-xs" type="button" onClick={cancel}>Stornieren</button> : null}
        {!canDecide && !canCancel ? <span className="vacation-card-state">{vacationStatusLabel(request.status)}</span> : null}
      </div>
    </article>
  );
}

# AI Governance And Alerting

AI governance alerts are evaluated from existing AI observability data. The
service does not store prompts, answer text, chunk text, API keys or vector-store
secrets.

## Data Sources

- AI observability metrics from audit events and chat metadata.
- Retrieval quality telemetry and SLO metadata.
- Vector-store drift status, including sync failures and fallback state.
- Cost and token windows already exposed by AI observability.

## Alert Rules

Rules are configurable through environment-backed Flask config values:

- `AI_GOVERNANCE_ALERTS_ENABLED`
- `AI_GOVERNANCE_HIGH_NO_SOURCE_RATE_WARNING`
- `AI_GOVERNANCE_HIGH_NO_SOURCE_RATE_CRITICAL`
- `AI_GOVERNANCE_RETRIEVAL_DEGRADATION_WARNING`
- `AI_GOVERNANCE_RETRIEVAL_DEGRADATION_CRITICAL`
- `AI_GOVERNANCE_RETRIEVAL_LATENCY_WARNING`
- `AI_GOVERNANCE_RETRIEVAL_LATENCY_CRITICAL`
- `AI_GOVERNANCE_EXCESSIVE_TOKEN_USAGE_WARNING`
- `AI_GOVERNANCE_EXCESSIVE_TOKEN_USAGE_CRITICAL`
- `AI_GOVERNANCE_HALLUCINATION_RISK_WARNING`
- `AI_GOVERNANCE_HALLUCINATION_RISK_CRITICAL`
- `AI_GOVERNANCE_SYNC_FAILURES_WARNING`
- `AI_GOVERNANCE_SYNC_FAILURES_CRITICAL`
- `AI_GOVERNANCE_ATLAS_ERRORS_WARNING`
- `AI_GOVERNANCE_ATLAS_ERRORS_CRITICAL`
- `AI_GOVERNANCE_ATLAS_UNAVAILABLE_WARNING`
- `AI_GOVERNANCE_ATLAS_UNAVAILABLE_CRITICAL`
- `AI_GOVERNANCE_ATLAS_FALLBACKS_WARNING`
- `AI_GOVERNANCE_ATLAS_FALLBACKS_CRITICAL`
- `AI_GOVERNANCE_ATLAS_SYNC_FAILURES_WARNING`
- `AI_GOVERNANCE_ATLAS_SYNC_FAILURES_CRITICAL`
- `AI_GOVERNANCE_ATLAS_SYNC_DRIFT_WARNING`
- `AI_GOVERNANCE_ATLAS_SYNC_DRIFT_CRITICAL`
- `AI_GOVERNANCE_ATLAS_LATENCY_DEGRADATION_WARNING`
- `AI_GOVERNANCE_ATLAS_LATENCY_DEGRADATION_CRITICAL`
- `AI_GOVERNANCE_ATLAS_RETRIEVAL_DEGRADATION_WARNING`
- `AI_GOVERNANCE_ATLAS_RETRIEVAL_DEGRADATION_CRITICAL`
- `AI_GOVERNANCE_COST_SPIKE_MIN_USD`
- `AI_GOVERNANCE_COST_SPIKE_MULTIPLIER_WARNING`
- `AI_GOVERNANCE_COST_SPIKE_MULTIPLIER_CRITICAL`

## MongoDB Atlas Vector Search

Atlas-specific rules reuse the same governance engine and appear in the existing
`governance.alerts` and root-level `alerts` output:

- `atlas_unavailable`: Atlas is configured but not active or reports a store error.
- `atlas_fallbacks`: the Atlas backend falls back to a local vector path.
- `atlas_sync_drift`: Atlas vector counts, reindex flags or vector mismatch metadata show drift.
- `atlas_latency_degradation`: Atlas average latency exceeds configured thresholds.
- `atlas_retrieval_degradation`: Atlas retrieval hit rate falls below configured thresholds.
- `atlas_errors` and `atlas_sync_failures`: operational Atlas errors or sync failures are present.

When Atlas is the configured backend, generic vector-store fallback/failure rules
are suppressed to avoid duplicate alerts. Atlas alerts use prompt-safe metadata
only; MongoDB URIs, credentials and connection strings must not appear in alert
payloads or logs.

## Admin AI Exposure

`GET /api/v1/admin/ai/observability` returns:

- `governance.status`
- `governance.alerts`
- `governance.alert_count`
- `governance.critical_count`
- `governance.warning_count`
- `alerts` as a root-level compatibility shortcut
- `metrics.governance_*` counters for dashboard cards

The Admin AI technical diagnostics view renders the active alerts with severity,
metric, value, threshold and recommended action.

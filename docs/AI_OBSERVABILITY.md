# AI Observability

## Ziel

Die AI-Observability nutzt bestehende Audit-, Chat- und Retrieval-Telemetrie,
statt Requests doppelt zu zaehlen. Der Admin-Endpunkt bleibt:

```text
GET /api/v1/admin/ai/observability
```

## Primaere Datenquellen

- `AIAuditEvent`: Requests, Erfolg/Fehler, Provider, Modell, Tokens, Kosten und Latenz.
- `ChatMessage`: Antwortqualitaet, Quellenanzahl, Low-Confidence und Top-Fragen.
- Retrieval-Telemetrie: Retrieval-SLOs, No-Source-Signale, Source-Qualitaet und Evaluation.
- Feedback: positives/negatives Feedback und Low-Quality-Hinweise.

## Metriken

Der `metrics`-Block enthaelt weiterhin alle bestehenden Keys und zusaetzlich
kompakte Observability-Container:

- `total_requests`, `successful_requests`, `failed_requests`, `request_success_rate`
- `no_source_answers`, `no_source_answer_rate`
- `low_confidence_answers`, `low_confidence_rate`
- `token_usage`
- `costs`
- `latency`
- `top_questions`
- `frequent_search_terms`

## MongoDB Atlas Vector Search

Atlas Vector Search metrics are read from the existing vector-store drift and
retrieval SLO diagnostics. They do not increment or duplicate AI request
counters such as `total_requests`, `successful_requests` or `failed_requests`.

The Admin AI observability `metrics` block includes:

- `atlas_queries`
- `atlas_errors`
- `atlas_latency`
- `atlas_fallbacks`
- `atlas_sync_failures`
- `atlas_vector_count`
- `atlas_reindex_required`

These values are shown in the Admin AI Technical Dashboard and documented in the
OpenAPI `AIObservability.metrics` schema. MongoDB connection strings and
credentials are not logged or exposed through observability payloads.

Die alten Keys wie `event_count`, `failed_request_count`, `total_tokens`,
`cost_windows`, `average_response_ms`, `p95_response_ms`, `no_source_count` und
`frequent_questions` bleiben erhalten.

## Privacy

Der Admin-Observability-Endpunkt zeigt aggregierte Metriken und begrenzte
Debug-Zeilen. Failed-Request-Zeilen enthalten keine Prompts oder Antworten.
Roh-Chunktexte bleiben ausgeblendet; Source-Details werden als sichere
Metadaten referenziert.

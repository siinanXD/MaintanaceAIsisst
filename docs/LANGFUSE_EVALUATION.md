# Langfuse Evaluation

## Purpose

The Maintenance Assistant sends automatic evaluation scores to Langfuse and
optional bounded input/output for LLM-as-a-Judge evaluators. Internal SQLite
records (`AIAnswerTrace`, `AIFeedback`, `AIAuditEvent`) remain the system of
record. Langfuse is used for trace-level monitoring, filtering, and judge-based
review.

## Environment

Requires `LANGFUSE_ENABLED=true` plus valid API keys.

| Variable | Default | Description |
|----------|---------|-------------|
| `LANGFUSE_EVAL_ENABLED` | `false` | Submit rule-based scores after each traced answer |
| `LANGFUSE_EVAL_CAPTURE_IO` | `false` | Attach bounded question/answer IO for cloud judges |
| `LANGFUSE_EVAL_MAX_QUESTION_CHARS` | `400` | Max user question length in eval IO |
| `LANGFUSE_EVAL_MAX_ANSWER_CHARS` | `800` | Max answer length in eval IO |
| `LANGFUSE_EVAL_INCLUDE_SOURCE_TITLES` | `true` | Include source titles in eval IO (no chunk text) |

Enable `LANGFUSE_EVAL_CAPTURE_IO` only when your data-protection review allows
question and answer text in Langfuse (EU/US region via `LANGFUSE_BASE_URL`).

## Automatic SDK Scores

Submitted after `create_answer_trace` when `LANGFUSE_EVAL_ENABLED=true`:

### Hallucination

| Score | Type | Source |
|-------|------|--------|
| `hallucination-risk` | BOOLEAN | `diagnostics.hallucination_warning` |
| `empty-retrieval` | BOOLEAN | `diagnostics.empty_retrieval` |
| `no-answer` | BOOLEAN | `answer_quality.no_answer` |

### Retrieval quality

| Score | Type | Source |
|-------|------|--------|
| `retrieval-source-count` | NUMERIC | `retrieval_explainability.source_count` |
| `retrieval-explained-count` | NUMERIC | `explained_source_count` |
| `retrieval-avg-final-score` | NUMERIC | `averages.final_score` |
| `retrieval-avg-semantic-similarity` | NUMERIC | `averages.semantic_similarity` |
| `retrieval-duration-ms` | NUMERIC | `retrieval_duration_ms` |
| `retrieval-machine-match-count` | NUMERIC | `machine_match_count` |
| `retrieval-used` | BOOLEAN | `retrieval_used` |
| `source-conflict` | BOOLEAN | `source_conflicts.has_conflicts` |

### Baseline

| Score | Type | Source |
|-------|------|--------|
| `confidence` | NUMERIC 0–1 | confidence score / 100 |
| `answer-quality` | CATEGORICAL | `answer_quality.status` |

## User Feedback Scores

On `POST /api/v1/ai/feedback`, when the linked `ChatMessage` has
`langfuse_trace_id` in `diagnostics_json`:

| Score | Type | Values |
|-------|------|--------|
| `user-feedback` | NUMERIC | `helpful=1.0`, `partially_helpful=0.5`, `not_helpful=0.0` |
| `user-feedback-rating` | CATEGORICAL | rating string |

Comments are truncated to 200 characters. Full prompt/response bodies are not
sent to Langfuse.

## Eval IO Span

When `LANGFUSE_EVAL_CAPTURE_IO=true`, the app adds span `maintenance-ai.eval_io`:

- **Input:** `question`, `context_titles` (optional), `guards` (hallucination flags)
- **Output:** truncated `answer`
- **Never sent:** chunk text, file paths, API keys, private notes

## LLM-as-a-Judge (Langfuse UI)

1. Create an **LLM Connection** with structured-output support.
2. Create evaluators (library or custom):
   - **Faithfulness / Hallucination** for RAG answers
   - **Context-Relevance** for retrieval quality
   - **Helpfulness** (optional) for general chat
3. Target **Live Observations**, filter:
   - Observation name: `maintenance-ai.eval_io` (when using eval IO span)
   - Tags: `rag`, `chat`, `langgraph`
   - Trace name: `maintenance-ai.*`
4. Map variables:
   - `{{input}}` → eval IO input JSON
   - `{{output}}` → eval IO output JSON (`answer`)
5. Set **sampling** to 5–10% in production to control cost.
6. Verify scores on a trace under environment `langfuse-llm-as-a-judge`.

## Code References

- [`app/services/langfuse_eval_score_service.py`](../app/services/langfuse_eval_score_service.py)
- [`app/services/langfuse_service.py`](../app/services/langfuse_service.py)
- [`docs/AI_ANSWER_TRACEABILITY.md`](AI_ANSWER_TRACEABILITY.md)

# AI Retrieval Golden Tests

The golden retrieval tests verify that important AI chat questions keep finding
the expected sources through the real retrieval pipeline. They call
`/api/v1/ai/chat` with seeded test data and do not use retrieval mocks.

## Run

```bash
python -m pytest tests/test_ai_retrieval_golden_questions.py -q
```

For a broader regression run:

```bash
python -m pytest tests/test_ai_retrieval_golden_questions.py tests/test_rag_services.py tests/test_sql_keyword_retrieval.py -q
```

## What Is Measured

Each `GoldenQuestion` defines:

- `question`: the chat question
- `expected_sources`: exact `(type, id)` source pairs that must be retrieved
- `expected_source_types`: source types that must appear
- `min_source_count`: minimum number of returned sources
- `allowed_source_types`: optional stricter source-type allowlist
- `forbidden_sources`: source pairs that must never appear

The test aggregates:

- `Recall@K`: expected source coverage within the top K returned sources
- `MRR`: reciprocal rank of the first expected source
- `no_result_count`: questions with no returned sources
- `forbidden_source_count`: forbidden or disallowed source hits

Current guardrails require no empty retrievals, no forbidden sources,
`Recall@K >= 0.95`, and `MRR >= 0.5`.

## Add A Question

1. Add deterministic fixture data in `_seed_golden_sources` if the current seed
   does not cover the scenario.
2. Add a `GoldenQuestion` in `_golden_questions`.
3. Set exact `expected_sources` using ids from the seed map.
4. Set `expected_source_types`, `min_source_count`, and `forbidden_sources`.
5. Keep the question in one of the covered domains: Tasks, Fehler, Maschinen,
   Materialien, Wartungen, Dokumente, or Schichtuebergaben.
6. Run the golden test locally and inspect failures before changing thresholds.

Only lower thresholds when the product intentionally changes retrieval behavior
and the new behavior is still acceptable.

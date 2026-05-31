# RAG AI Agent Review

Use this skill when reviewing or changing AI, RAG, retrieval, provider, evaluation, or AI observability code.

## Purpose

Keep the app's AI layer professional, permission-aware, testable, and provider-agnostic.

## Instructions

- Preserve provider abstraction for mock, OpenAI, OpenAI-compatible endpoints, and future providers.
- Do not hardcode API keys, model secrets, tenant data, or endpoint credentials.
- Keep CI deterministic with mock providers and local fixtures.
- Ensure retrieval respects user permissions, departments, roles, and source visibility.
- Keep public source metadata prompt-safe.
- Avoid exposing raw prompt text, raw chunk text, unauthorized source content, or private comments in diagnostics.
- Preserve clear no-answer behavior when retrieval is empty, weak, or unsafe.
- Prefer additive metadata fields over breaking response changes.
- Keep `RAG_TOP_K` as final answer context count and candidate-pool settings separate.
- Check that source metadata includes safe fields where available: `source_type`, `source_id`, `title`, `module`, `machine_id`, `role_visibility`, `created_at`, and chunk or section metadata.
- For observability, keep metrics aggregated and prompt-safe.

## Evaluation Expectations

- Add or run golden-question tests when retrieval behavior changes.
- Check Recall@K, MRR, no-result behavior, expected source matching, and permission leak behavior where relevant.
- Run focused tests under `tests/test_rag_services.py`, `tests/test_retrieval_*`, `tests/test_ai_features.py`, and provider-readiness tests when touched.

## What To Report

- Retrieval/provider behavior affected.
- Permission and no-answer behavior.
- Tests run and result.
- Residual risk and exact commit message.

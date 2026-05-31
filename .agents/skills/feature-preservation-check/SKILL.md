# Feature Preservation Check

Use this skill before or after backend or frontend changes that may affect existing behavior.

## Purpose

Prevent regressions in the Maintenance Assistant App while allowing small, focused improvements.

## Instructions

- Identify the existing feature surface before changing code.
- Preserve current Flask routes, API response shapes, templates, permissions, and tests unless the user explicitly asks to change them.
- Check whether the change affects tasks, errors, machines, documents, shift handovers, employees, roles, AI chat, AI admin, or RAG retrieval.
- Treat dirty unrelated files as user work.
- Do not revert unrelated changes.
- Prefer additive response fields over breaking response changes.
- Preserve permission checks and role visibility rules.
- Preserve mock-provider behavior for tests and CI.
- Avoid real external AI calls in tests.

## Minimum Checks

- Run focused pytest tests for touched modules.
- Run related route/API tests when response shape or permissions may be affected.
- Run Ruff for touched Python files when practical.
- Review `git status --short` for the touched files only.

## What To Report

- Existing behavior preserved.
- Tests run and results.
- Any remaining risk or unverified surface.
- Exact commit message suggestion.

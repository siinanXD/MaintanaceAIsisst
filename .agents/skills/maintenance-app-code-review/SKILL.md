# Maintenance App Code Review

Use this skill for code review of Maintenance Assistant App changes.

## Purpose

Find bugs, regressions, permission leaks, AI safety issues, and missing tests before summarizing style concerns.

## Review Priorities

- Data visibility and permission leaks across departments, roles, employees, tasks, errors, machines, documents, and handovers.
- Route and API contract regressions.
- AI/RAG source leakage, raw prompt leakage, raw chunk leakage, and weak no-answer behavior.
- Provider fallback behavior and missing configuration handling.
- Database portability between SQLite development and PostgreSQL-ready production.
- Test determinism and avoiding real LLM calls in CI.
- Broken dark mode, inaccessible UI states, or hidden AI source/confidence information when reviewing frontend work.

## Instructions

- Lead with findings ordered by severity.
- Include exact file and line references.
- Explain the impact and the smallest safe fix.
- Distinguish confirmed bugs from assumptions.
- If no issues are found, say that clearly and mention remaining test gaps.
- Do not rewrite code during review unless the user asks for implementation.

## Checklist

- Permissions and department scoping are preserved.
- Existing routes and response contracts remain compatible.
- AI source metadata is prompt-safe and permission-aware.
- No secrets are committed.
- Tests cover changed behavior and mock AI providers.
- OpenAPI docs match intentional API changes.

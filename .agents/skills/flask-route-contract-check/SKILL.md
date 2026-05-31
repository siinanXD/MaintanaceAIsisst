# Flask Route Contract Check

Use this skill when reviewing or changing Flask routes, API handlers, response payloads, permissions, or OpenAPI documentation.

## Purpose

Keep route behavior stable and documented for the Maintenance Assistant App.

## Instructions

- Do not rename, remove, or repurpose existing routes unless explicitly requested.
- Preserve authentication, authorization, department filtering, and role checks.
- Preserve existing status codes and response envelopes unless the user requests a contract change.
- Prefer additive fields for API evolution.
- Update OpenAPI documentation when response fields or request fields intentionally change.
- Keep route functions thin and delegate business logic to services.
- Do not add database migrations or model changes from a route-contract task unless explicitly requested.
- Avoid real external AI calls in route tests.

## Checks

- Search for existing route tests before editing.
- Run focused tests for the touched route and related API docs.
- Check permission-denied, validation-error, and success paths where relevant.
- Confirm frontend callers or templates are not broken by the response shape.

## What To Report

- Route paths and methods reviewed.
- Response contract changes, if any.
- Tests run and results.
- Remaining compatibility risk.

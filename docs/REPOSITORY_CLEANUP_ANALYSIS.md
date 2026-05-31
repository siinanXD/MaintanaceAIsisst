# Repository Cleanup Analysis

Date: 2026-05-31

This report records the current repository state before cleanup or structure
changes. It is intentionally conservative: production code, migrations,
configuration, CI, tests, and documentation that still supports the product are
kept unless there is strong evidence that they are obsolete.

## Current Baseline

- Application stack: Flask app factory, SQLAlchemy, Alembic migrations,
  Jinja templates, static assets, and React/Vite frontend islands.
- Startup baseline: `create_app()` succeeds in testing mode. The route count is
  environment-dependent because optional Flasgger routes are registered when
  Flasgger is installed: 218 routes in the project `.venv`, 214 routes in the
  fallback environment without Flasgger.
- Public health baseline: `/health` is registered through the public health
  blueprint and should stay available after every cleanup step.
- Dirty worktree observed before this report:
  - `app/ai/chat_answers.py`
  - `app/services/ai_structured_source_service.py`
  - `tests/test_ai_features.py`
  - `app/services/ai_vacation_structured_answer_service.py` as an untracked
    service file
- These existing changes are treated as user work and must not be reverted by
  cleanup work.

## Production-Relevant Files And Directories

Keep these files and directories because they are part of runtime behavior,
deployment, database lifecycle, or required configuration.

| Path | Reason |
| --- | --- |
| `app/` | Flask application package: app factory, routes, services, models, templates, static assets, worker, API docs. |
| `app/config.py` | Runtime configuration and production safety validation. Must not be deleted. |
| `app/models.py` | SQLAlchemy models used by routes, services, and migrations. |
| `app/templates/` | Jinja pages served by the web blueprint. |
| `app/static/` | CSS, JavaScript, page loaders, and generated frontend assets used by templates. |
| `frontend/` | React/Vite source for frontend islands; Docker and CI build it. |
| `migrations/` | Alembic migration history. Required for existing and production databases. |
| `run.py` | WSGI and local development entry point. Docker/Gunicorn uses `run:app`. |
| `app/worker.py` | Background RAG maintenance worker used by Docker Compose. |
| `Dockerfile` | Production image definition. |
| `docker-compose.yml` | PostgreSQL, app, and worker orchestration. |
| `.dockerignore` | Keeps local secrets, caches, data, and build output out of Docker context. |
| `.env.example` | Safe configuration template. Must remain tracked. |
| `.gitignore` | Keeps local secrets, databases, caches, logs, virtualenvs, and generated files out of Git. |
| `requirements.txt` | Python runtime dependencies. |
| `requirements-chroma.txt` | Optional Chroma/vector-store dependencies. |
| `package.json` and `package-lock.json` | Root CSS/build scripts and pinned Node dependencies. |
| `frontend/package.json` and `frontend/package-lock.json` | React/Vite frontend dependencies and scripts. |
| `tailwind.config.js` and `postcss.config.js` | CSS build configuration. |
| `seed.py` | Unified seed entry point. |
| `seed_production.py` | Production-safe baseline seeding. |
| `.github/workflows/ci.yml` | CI gate for linting, frontend build, migrations, startup, tests, secret scan, and Docker build. |
| `README.md` | Main project documentation. Must be updated after structure changes, not deleted. |
| `docs/API_PROTOCOL.md` | Endpoint reference for the current API. |
| `docs/FEATURES.md` | Product feature overview. |
| `docs/screenshots/` | README-linked screenshots. |
| `data/.gitkeep` | Keeps the runtime data directory present without tracking databases or uploads. |

## Development And Test Files That Should Stay

These files are not production runtime files, but they protect production
quality or support local development and should stay for now.

| Path | Reason |
| --- | --- |
| `tests/` | Active pytest suite used by CI. It covers API stability, auth, AI/RAG behavior, documents, machines, inventory, shift plans, worker, and more. Do not delete unless individual tests are proven empty, broken, or obsolete. |
| `pyproject.toml` | Ruff, coverage, and pytest configuration. |
| `CHANGELOG.md` | Release/change history. |
| `seed_demo.py` | Demo dataset bootstrap for local evaluation and presentations. |
| `seed_test.py` | Manual smoke-test users and deterministic local test seed profile. |
| `app/demo_data.py` and `app/demo_seed/` | Demo data implementation used by `seed_demo.py`. |
| `scripts/build_css.mjs` | Used by `npm run build:css`; required for CSS rebuilds. |
| `scripts/generate_industrial_document_dataset.py` | CLI wrapper for the industrial document dataset generator. |
| `scripts/industrial_document_dataset_generator.py` | Tested utility for generating industrial document datasets. Keep unless this utility is intentionally removed together with its tests and docs. |
| `docs/AI_DEMO_QUESTIONS.md` | Demo and validation prompts for source-backed AI behavior. |
| `docs/AI_RETRIEVAL_GOLDEN_TESTS.md` | Retrieval evaluation documentation. |
| `.gitleaks.toml` and `.gitleaksignore` | Secret scanning configuration used by CI/security workflow. |

## Obsolete, Duplicate, Or Truly Unnecessary Candidates

These are cleanup candidates. They should be removed in a dedicated cleanup
commit after confirming they are not needed by the user workflow.

| Path | Recommendation | Reason |
| --- | --- | --- |
| `AGENTS.md` | Remove from product repo unless intentionally used as project policy. | Agent instructions are not application runtime or deployment material. |
| `agent.md` | Remove. | Appears to be local/agent guidance, not production documentation. |
| `.agents/` | Remove from product repo unless the team explicitly wants to version local Codex skills. | Local agent skills do not affect application runtime and make the repo less self-explanatory for product developers. |
| `backend/` | Remove local directory if empty or only ignored temp files. | The real backend is `app/`; an empty `backend/` is misleading. |
| `.coverage` | Do not track; delete locally if present. | Generated coverage artifact. |
| `.pytest_cache/` | Do not track; delete locally if present. | Generated pytest cache. |
| `.ruff_cache/` | Do not track; delete locally if present. | Generated Ruff cache. |
| `.venv/` | Do not track; delete only if intentionally resetting local environment. | Local virtual environment. |
| `node_modules/` and `frontend/node_modules/` | Do not track; keep ignored. | Recreated by `npm ci`. |
| `__pycache__/` folders | Do not track; delete locally if needed. | Generated Python bytecode. |
| `.codex_tmp/`, `.codex_pytest_tmp/`, `.codex_deps/` | Do not track; delete locally if no running tool depends on them. | Local agent/test temporary directories. |
| `.idea/` | Do not track. | Local IDE settings. |
| `tmp/` and `tmp_diag/` | Do not track; delete locally after confirming no active diagnostic run uses them. | Temporary diagnostics/output. |
| `logs/` | Do not track. | Runtime logs. |
| `data/*.db`, `data/*.log`, uploads | Do not track. | Runtime databases, uploads, and diagnostics. |
| `documents/`, `manuals/`, `knowledge/`, `backups/` | Do not track content. | Runtime/persistent storage configured through environment variables and Docker volumes. |

## Risks If Files Are Deleted Or Moved

- Deleting `tests/` removes the main safety net for route contracts, AI/RAG
  fallback behavior, auth, permissions, migrations, and frontend/API stability.
- Deleting or rewriting `migrations/` can break existing SQLite/PostgreSQL
  deployments and make production upgrades unsafe.
- Moving `app/` modules without updating imports, blueprint registration, and
  tests can silently break routes or service dependencies.
- Moving `frontend/` requires changes to Dockerfile, CI, root build scripts,
  Vite config, and README.
- Removing `scripts/build_css.mjs` breaks `npm run build:css`.
- Removing `seed_test.py` or `seed_demo.py` requires coordinated changes in
  `seed.py`, README, Dockerfile, CI compile commands, and any local workflows
  that rely on those seed profiles.
- Removing `.github/workflows/ci.yml` would violate the current cleanup goal
  and remove automated evidence that the app still builds and starts.
- Removing `.env.example` or `.gitignore` would increase the chance of secrets,
  databases, caches, or generated runtime files entering the repository.
- Removing `docs/screenshots/` without updating README would leave broken image
  links.
- Removing `docs/API_PROTOCOL.md` without replacing it would leave users
  without a stable endpoint reference.

## Recommended Step Order

1. Analysis report: keep this document as the baseline for cleanup decisions.
2. Cleanup unnecessary files: remove only `AGENTS.md`, `agent.md`, and
   `.agents/` first. Leave tests, CI, migrations, config, requirements, README,
   `.env.example`, and `.gitignore`.
3. Local ignored cleanup: optionally delete generated local artifacts such as
   caches, bytecode, coverage output, temp directories, logs, and local
   databases. Do not commit these artifacts.
4. Structure improvement: improve documentation and naming first. Avoid moving
   Python packages until route and import coverage is strong.
5. Imports and routes: after any move, run the startup route inventory in the
   project `.venv` and compare against the 218-route baseline. If Flasgger is
   not installed in the environment, compare against the 214-route fallback
   baseline instead.
6. README and `.gitignore`: update README to reflect the cleaned structure;
   update `.gitignore` only if new generated paths are discovered.
7. Verification: run focused startup, route, lint, and test checks.

## Verification Commands For Future Steps

Use these commands after cleanup or structure changes.

```powershell
$env:FLASK_ENV = "testing"
$env:SECRET_KEY = "analysis-secret-key"
$env:JWT_SECRET_KEY = "analysis-jwt-secret-key"
$env:DATABASE_URL = "sqlite:///:memory:"
$env:AI_PROVIDER = "mock"
$env:OPENAI_API_KEY = ""
python - <<'PY'
from app import create_app

app = create_app()
client = app.test_client()
health = client.get("/health")

assert health.status_code == 200
assert health.get_json() == {"status": "ok"}
print("routes:", len(app.url_map._rules))
PY
```

```powershell
python -m compileall app migrations tests seed_demo.py seed_test.py seed.py run.py
python -m ruff check .
python -m ruff format --check .
python -m pytest
npm run check:react
npm run build:react
docker build --tag maintenance-assistant:cleanup-check .
```

## Commit Suggestion

Suggested commit message for this step:

```text
docs: add repository cleanup analysis
```

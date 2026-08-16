# Portfolio proof

This document is the recruiter-facing proof map for the Maintenance AI Assistant. It points to evidence that already exists in the repository and avoids claims that depend on private production credentials.

## What this project demonstrates

- Production-oriented Flask application with SQLAlchemy, JWT authentication, role-aware permissions and audit logging.
- Source-backed RAG with configurable vector stores, retrieval diagnostics, knowledge-quality workflows and local fallbacks.
- Human-governed AI behavior: AI features expose source visibility, provider diagnostics and safe fallback behavior rather than silently failing.
- Deployment-oriented packaging with Docker, Gunicorn, health/readiness endpoints and explicit production configuration.
- Engineering quality gates with pytest, Ruff, compile/type checks and Docker build checks in GitHub Actions.

## Reproducible evaluator path

1. Create a local environment and install `requirements.txt`.
2. Copy `.env.example` to `.env` and keep `OPENAI_API_KEY` empty to use the local fallback.
3. Seed the demo profile with `python seed.py demo`.
4. Start the app with `python run.py --host 127.0.0.1 --port 5050`.
5. Verify `GET /health` and `GET /health/ready`.
6. Use the source-backed prompts in `docs/AI_DEMO_QUESTIONS.md` to inspect the AI/RAG behavior.

## Production-readiness evidence

- `Dockerfile` and Docker Compose profiles provide repeatable app/worker infrastructure.
- `.env.production.example` separates production configuration from development defaults.
- `docs/PRODUCTION_DEPLOYMENT_CHECKLIST.md` covers secrets, migrations, health checks, observability, governance, reindexing, backups and rollback readiness.
- `/health/ready` reports redacted readiness for database, AI and RAG components.
- The repository contains CI configuration for linting, tests, frontend checks and Docker builds.

## Important scope note

This repository intentionally does **not** publish production secrets or make unsupported uptime/usage claims. A public live URL should only be added to the main README when an externally reachable deployment has been verified and is intended to remain available for portfolio review.

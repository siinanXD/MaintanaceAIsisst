# Production Deployment Checklist

Use this checklist before every production release. Keep production secrets in
the deployment environment or secret manager, never in Git.

## 1. Environment Variables

- [ ] Set `FLASK_ENV=production`.
- [ ] Set `FLASK_DEBUG=0`.
- [ ] Set `AUTO_CREATE_DATABASE=false`; production schema changes must run via
  migrations.
- [ ] Set `DATABASE_URL` to the production PostgreSQL database.
- [ ] Set persistent storage paths for `UPLOAD_FOLDER`, `DOCUMENTS_FOLDER`,
  `MANUALS_FOLDER`, `KNOWLEDGE_FOLDER`, `BACKUP_FOLDER` and `LOG_DIR`.
- [ ] Set `ENABLE_API_DOCS=false` unless production API documentation is
  explicitly required.
- [ ] If production API documentation is enabled, keep
  `API_DOCS_REQUIRE_MASTER_ADMIN=true`.
- [ ] Set `MAIL_ENABLED`, SMTP variables and `MAIL_DRY_RUN=false` only after a
  successful mail delivery test.
- [ ] Set `OPERATIONS_HASH_SECRET` to a stable secret distinct from public
  values if operations analytics are used.

## 2. Secret Requirements

- [ ] Generate strong, unique values for `SECRET_KEY` and `JWT_SECRET_KEY`.
- [ ] Keep `POSTGRES_PASSWORD`, `OPENAI_API_KEY`, `LANGFUSE_SECRET_KEY`, mail
  credentials and backup credentials in the secret manager.
- [ ] Confirm `.env.example` contains no real credentials.
- [ ] Confirm logs, diagnostics, health checks and API docs do not expose
  secrets or raw database connection strings.
- [ ] Rotate any key that was shared through chat, tickets, screenshots or
  local test files.

## 3. OpenAI Configuration

- [ ] Set `AI_PROVIDER=openai` for production AI calls, or document why
  `openai_compatible` is intentionally used.
- [ ] Set `OPENAI_API_KEY`.
- [ ] Set `OPENAI_MODEL`, `OPENAI_MODEL_FAST`, `OPENAI_MODEL_BALANCED` and
  `OPENAI_MODEL_QUALITY` to approved models.
- [ ] Set `AI_TIMEOUT_SECONDS` and retry limits to values appropriate for the
  production SLO.
- [ ] Set `EMBEDDING_PROVIDER=openai`.
- [ ] Set `OPENAI_EMBEDDING_MODEL=text-embedding-3-small`.
- [ ] Confirm the active vector index matches the embedding dimensions
  (`1536` for `text-embedding-3-small`).
- [ ] Confirm fallback providers are visible in status diagnostics and are not
  treated as a healthy production state.

## 4. Database Migrations

- [ ] Back up the production database before schema changes.
- [ ] Review pending Alembic migrations.
- [ ] Run migrations in the deployment window.
- [ ] Verify migration output and application startup logs.
- [ ] Run `python seed.py production` only if production bootstrap data or an
  initial admin from environment variables is required.
- [ ] Keep `AUTO_CREATE_DATABASE=false` after deployment.

## 5. Health Checks

- [ ] Verify `/health` returns a basic healthy response.
- [ ] Verify `/health/live` returns liveness without requiring dependencies.
- [ ] Verify `/health/ready` returns readiness only when required dependencies
  are available.
- [ ] Verify `/api/v1/health/operations` with an authorized Master Admin or IT
  user.
- [ ] Verify `/api/v1/health/database` is restricted to authorized IT or Master
  Admin users and does not leak sensitive details to other users.
- [ ] Confirm load balancer and container probes use `/health/live` and
  `/health/ready`, not diagnostic admin endpoints.

## 6. Observability Verification

- [ ] Confirm application logs are written to the configured `LOG_DIR` or the
  platform log collector.
- [ ] Confirm AI request metrics are visible in `/api/v1/admin/ai/observability`.
- [ ] Confirm token usage, cost estimates, latency, failed requests,
  no-source answers and low-confidence answers are visible to Admin, IT or
  Master users as designed.
- [ ] Confirm Langfuse settings if `LANGFUSE_ENABLED=true`.
- [ ] If using Langfuse evaluation: set `LANGFUSE_EVAL_ENABLED=true` and review
      whether `LANGFUSE_EVAL_CAPTURE_IO=true` is allowed for your data policy
      (see `docs/LANGFUSE_EVALUATION.md`).
- [ ] Confirm diagnostics omit raw prompts, raw chunk text, private notes,
  secrets and unauthorized data.
- [ ] Confirm monitoring alerts are connected to the production notification
  channel.

## 7. Governance Verification

- [ ] Confirm AI governance alerts are enabled with
  `AI_GOVERNANCE_ALERTS_ENABLED=true`.
- [ ] Review configured thresholds for no-source rate, retrieval degradation,
  cost spikes, excessive token usage, hallucination risk, sync failures and
  vector store failures.
- [ ] Open the AI Admin area and verify governance status, warning count,
  critical count and recommended actions.
- [ ] Confirm vector-store fallback, sync failures and reindex recommendations
  are surfaced as warnings instead of silent degradation.
- [ ] Confirm only authorized Admin, IT or Master users can inspect governance
  diagnostics.

## 8. Reindex Procedure

- [ ] Reindex Knowledge documents after changing any of these values:
  `EMBEDDING_PROVIDER`, `OPENAI_EMBEDDING_MODEL`, vector store, chunking mode or
  chunking schema.
- [ ] Confirm production OpenAI embedding credentials are available before
  reindexing.
- [ ] Start a full reindex from the AI Admin area or via
  `POST /api/v1/admin/ai/knowledge/reindex`.
- [ ] For a safer partial run, start stale-only reindexing with
  `POST /api/v1/admin/ai/knowledge/reindex?mode=stale`.
- [ ] Track background jobs with `GET /api/v1/admin/jobs?job_type=rag_reindex`
  when using queued reindex jobs.
- [ ] Verify indexed document count, chunk count, vector count, sync status and
  retrieval quality after the job finishes.
- [ ] Do not mix embeddings from different providers or dimensions in one
  production vector index.
- [ ] For MongoDB Atlas retrieval, run `python scripts/rag_atlas_smoke.py` before
  go-live and after reindex/resync.
- [ ] Use `POST /api/v1/admin/ai/knowledge/atlas/resync` when SQL chunks and Atlas
  vectors drift without embedding changes.
- [ ] Set `RAG_STRICT_QUALITY_GATE=true` when only reviewed knowledge should be
  retrievable in production.

## 9. Backup Strategy

- [ ] Take a database backup before deployment and before every migration.
- [ ] Back up uploads, generated documents, manuals, knowledge files, logs and
  backup manifests from persistent storage.
- [ ] Verify the configured `BACKUP_FOLDER` is on persistent storage.
- [ ] Create an application backup from the admin backup workflow when
  appropriate.
- [ ] Download or replicate the backup to storage outside the application host.
- [ ] Test restore in a staging environment on a regular schedule.
- [ ] Define retention periods for database backups, file backups and logs.

## 10. Rollback Strategy

- [ ] Record the currently deployed version, image tag, migration revision and
  configuration snapshot before rollout.
- [ ] Keep the previous application image available.
- [ ] Know whether the migration is backward compatible before deploying.
- [ ] If rollback is needed before irreversible migrations, redeploy the
  previous image and restore the pre-deployment configuration.
- [ ] If rollback is needed after a breaking migration, restore the database and
  persistent files from the pre-deployment backup.
- [ ] Re-run health checks after rollback.
- [ ] Re-run AI Admin observability and governance checks after rollback.
- [ ] Document the incident, root cause, data impact and follow-up actions.

## Final Release Gate

- [ ] Tests and linting for the release branch are green.
- [ ] Production secrets are present and not logged.
- [ ] Migrations completed successfully.
- [ ] Health checks passed.
- [ ] Observability and governance are visible to authorized users.
- [ ] RAG reindexing is complete when required.
- [ ] Backup and rollback paths have been verified.

# MongoDB Atlas Vector Search

MongoDB Atlas Vector Search can be enabled as an external RAG candidate store with
`RAG_VECTOR_STORE=mongodb_atlas`. It is not the default backend; `pgvector`
remains the compatible default unless the environment explicitly selects Atlas.

## Required Configuration

```env
MONGODB_URI=
MONGODB_DB_NAME=maintenance_ai
RAG_VECTOR_STORE=mongodb_atlas
MONGODB_ATLAS_URI=
MONGODB_ATLAS_DATABASE=maintenance_ai
MONGODB_ATLAS_VECTOR_COLLECTION=knowledge_vectors
MONGODB_ATLAS_VECTOR_INDEX=knowledge_vector_index
MONGODB_ATLAS_TIMEOUT_MS=3000
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

`MONGODB_URI` is the primary cluster connection string. `MONGODB_ATLAS_URI`
falls back to it when unset. Set `MONGODB_DB_NAME=maintenance_ai` so the app
bootstraps collections and indexes in a dedicated database on the shared Atlas
cluster. The service never opens or modifies the separate `ai_email` database.

On startup, when `MONGODB_URI` (or `MONGODB_ATLAS_URI`) is configured, the app
creates missing collections (`users`, `roles`, `employees`, `machines`, `tasks`,
`errors`, and related AI/audit collections) and idempotent indexes in
`maintenance_ai` only. Vector chunks for RAG remain in `knowledge_vectors`.

`MONGODB_URI` is a secret. Do not log it, expose it through diagnostics or
copy it into support payloads.

## Atlas Index

Create the Atlas index through infrastructure or the Atlas UI before enabling the
backend:

```text
Collection: knowledge_vectors
Path: embedding
Dimensions: 1536
Similarity: cosine
```

The application does not create or migrate Atlas indexes at startup by default.
Use one of these provisioning paths instead:

```bash
flask --app run:app atlas ensure-index
python scripts/mongodb_init_vector_index.py
docker compose --profile mongodb up --build   # runs mongodb-init automatically
```

## Local Docker Profile

```bash
docker compose --profile mongodb up --build
```

This starts PostgreSQL, MongoDB Atlas Local, a one-shot index init container,
the app and the worker with:

- `RAG_VECTOR_STORE=mongodb_atlas`
- `EMBEDDING_PROVIDER=openai`
- `MONGODB_ATLAS_URI=mongodb://mongodb:27017/?directConnection=true`

Offline development without OpenAI remains available through
`docker compose --profile pgvector up --build`.

## Health And Smoke Checks

```bash
flask --app run:app atlas health
flask --app run:app atlas probe-search
python scripts/rag_atlas_smoke.py
curl http://127.0.0.1:5050/health/ready
```

When Atlas is configured, `/health/ready` marks RAG as degraded if Atlas is in
fallback mode, the vector index is missing, or drift requires reindex/resync.

## Atlas Resync

When SQL chunks and Atlas vectors drift apart, use the Atlas-only resync path
instead of a full re-embed reindex when embeddings are still valid:

```http
POST /api/v1/admin/ai/knowledge/atlas/resync
POST /api/v1/admin/ai/knowledge/atlas/resync/jobs
```

Payload:

```json
{"mode": "drift_only"}
```

Supported modes: `drift_only`, `all`.

## Strict Quality Gate

Production deployments can require reviewed knowledge only:

```env
RAG_STRICT_QUALITY_GATE=true
```

When enabled, only `admin_approved` and `technician_confirmed` documents pass
retrieval quality gates.

## Data Ownership

Atlas stores synchronized retrieval candidates only:

- `record_id`
- `document_id`
- `chunk_id`
- `text`
- `embedding`
- safe flat metadata

SQL remains the system of record for document status, permissions, role
visibility, quality gates and source cards. Atlas candidates are always passed
back through the existing SQL gates before they can be used in answers.

## Reindex Requirement

After changing the embedding provider, embedding model or vector store,
Knowledge documents must be fully reindexed. This is required because vector
dimensions and similarity behavior can change between backends.

## Fallback Behavior

If Atlas is not configured, `pymongo` is missing, Atlas is unreachable or a query
times out, the application falls back to the local SQL vector path. The fallback
is intentionally visible through vector-store diagnostics and Atlas
observability counters.

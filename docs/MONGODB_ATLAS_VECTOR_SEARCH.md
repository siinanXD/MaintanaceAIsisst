# MongoDB Atlas Vector Search

MongoDB Atlas Vector Search can be enabled as an external RAG candidate store with
`RAG_VECTOR_STORE=mongodb_atlas`. It is not the default backend; `pgvector`
remains the compatible default unless the environment explicitly selects Atlas.

## Required Configuration

```env
RAG_VECTOR_STORE=mongodb_atlas
MONGODB_ATLAS_URI=
MONGODB_ATLAS_DATABASE=maintenance_ai
MONGODB_ATLAS_VECTOR_COLLECTION=knowledge_vectors
MONGODB_ATLAS_VECTOR_INDEX=knowledge_vector_index
MONGODB_ATLAS_TIMEOUT_MS=3000
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

`MONGODB_ATLAS_URI` is a secret. Do not log it, expose it through diagnostics or
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

The application does not create or migrate Atlas indexes at startup.

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

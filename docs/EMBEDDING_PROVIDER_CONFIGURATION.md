# Embedding Provider Configuration

## Production Default

RAG embeddings use OpenAI by default:

```env
EMBEDDING_PROVIDER=openai
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

`text-embedding-3-small` returns 1536-dimensional vectors. The application validates known embedding dimensions during indexing so provider or model changes are visible early.

Production deployments should set `OPENAI_API_KEY`. If the key is missing, the
runtime falls back to deterministic hashing so tests, CI and offline development
remain usable, while readiness/status payloads report `fallback_active=true`.

## Provider Abstraction

All embedding callers should use `app.services.embedding_service.get_embedding_provider()`.
The supported providers are:

- `openai`: primary production provider and default.
- `openai_compatible`: OpenAI-compatible endpoint using `AI_BASE_URL`.
- `hashing`: deterministic local provider for tests, CI and offline fallback only.

Direct embedding API calls outside `embedding_service.py` should not be added.

## Fallback Behavior

When OpenAI or OpenAI-compatible embeddings are selected but required configuration is missing, the app falls back to hashing so local tests and offline CI can continue. Status payloads still report the configured provider, the effective fallback provider and the missing configuration action.

Fallback behavior is intentionally visible:

- `provider` remains the configured provider, for example `openai`.
- `effective_provider` becomes `hashing` when fallback is active.
- `fallback_active` is `true` for missing credentials, missing compatible base
  URL or unsupported providers.
- Explicit `EMBEDDING_PROVIDER=hashing` is not a production path and reports
  `production_default=false`.

Hashing uses 384 dimensions by default:

```env
RAG_HASH_EMBEDDING_DIMENSIONS=384
```

## Reindex Requirement

Knowledge documents must be reindexed after changing:

- `EMBEDDING_PROVIDER`
- `OPENAI_EMBEDDING_MODEL`
- `RAG_HASH_EMBEDDING_DIMENSIONS`
- Vector store backend

Do not mix embeddings from different providers or dimensions in the same production index.

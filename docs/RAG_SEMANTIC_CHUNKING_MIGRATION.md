# RAG Semantic Chunking Migration

## Goal

Use semantic structure-aware chunking as the default indexing strategy while keeping the previous fixed-size chunking path available as a temporary fallback.

## Rollout Plan

1. Keep `RAG_CHUNKING_MODE=hybrid_semantic` for normal development and production.
2. Reindex Knowledge documents after deploying this chunking schema so every `KnowledgeChunk` receives hierarchy metadata.
3. Use `RAG_CHUNKING_MODE=legacy_fixed` only if semantic chunking causes an indexing regression during migration.
4. Reindex again after switching between `hybrid_semantic` and `legacy_fixed`; mixed chunk schemas should not be treated as final production state.
5. Remove the fallback only after semantic chunks have been validated on uploaded documents, generated maintenance reports, manuals, error catalog entries, tasks, maintenance plans and shift handovers.

## Metadata Added By Semantic Chunking

- `chunk_schema_version`
- `semantic_strategy`
- `semantic_chunk_type`
- `semantic_boundary`
- `section_level`
- `parent_section_title`
- `chunk_hierarchy`
- `hierarchy_path`
- Existing fields such as `section_title`, `source_section`, `chunk_block_kinds`, `chunk_order` and source metadata remain preserved.

## Reindex Requirement

Knowledge documents must be fully reindexed after changing:

- Chunking mode
- Chunking schema
- Embedding provider
- Embedding model
- Vector store

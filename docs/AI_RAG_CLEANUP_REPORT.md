# AI/RAG Cleanup Report

Date: 2026-06-01

## Removed

- Removed the duplicate private source-card URL resolver from
  `app/services/vector_store_service.py`. Vector metadata now uses the shared
  `source_url(...)` resolver from the knowledge-service facade.
- Removed the unused `MAINTENANCE_SYSTEM_PROMPT` constant from
  `app/services/ai_prompting.py`. Runtime prompt construction continues through
  `text_system_prompt(...)`, `json_system_prompt(...)` and DB-backed prompt
  templates.
- Removed the unused private `_prompt_rules_for_retrieval(...)` wrapper from
  `app/services/rag_service.py`.
- Removed the unused `RAG_PIPELINE_STEPS` compatibility alias from
  `app/services/rag_service.py`. The authoritative node list remains
  `LANGGRAPH_RAG_PIPELINE_STEPS` in `app/services/langgraph_rag_workflow.py`.

## Kept Intentionally

- `app/services/ai_retrieval.py` is still active structured SQL retrieval. It is
  used by structured AI answer services and by `retrieval_service.py`.
- `app/services/sql_keyword_retrieval_service.py` remains a fallback retrieval
  component, not a primary path.
- Vector-store adapters in `app/services/vector_store_service.py` remain because
  they are configuration-selected backends or recovery fallbacks.
- `app/ai/services.py` remains as a compatibility facade for existing imports
  and monkeypatch-based tests.
- `app/services/knowledge_retrieval_service.py` remains because source-card URL
  resolution, legacy chunk search and chat-source helpers are still imported
  through `app.services.knowledge_service`.
- Langfuse helpers remain an external observability sink only. The internal
  `AIAnswerTrace` table remains the authoritative answer-trace record.

## Current Structure

- HTTP/API layer: `app/ai/routes.py`
- AI compatibility facade: `app/ai/services.py`
- RAG facade: `app/services/rag_service.py`
- LangGraph orchestration: `app/services/langgraph_rag_workflow.py`
- Retrieval orchestration: `app/services/retrieval_service.py`
- Structured SQL retrieval component: `app/services/ai_retrieval.py`
- Keyword fallback: `app/services/sql_keyword_retrieval_service.py`
- Vector-store adapters: `app/services/vector_store_service.py`
- Prompt builders and fallback prompts: `app/services/ai_prompting.py`
- Internal answer trace: `app/services/ai_traceability_service.py`
- External trace sink: `app/services/langfuse_service.py`
- AI observability aggregation: `app/services/ai_observability_service.py`
- AI governance alert evaluation: `app/services/ai_governance_service.py`

## Final Audit Notes

- No obsolete retrieval implementation was removed in this pass. The remaining
  retrieval modules are either active components, compatibility facades, or
  required fallbacks covered by imports and tests.
- No vector adapter was removed. Local SQL, pgvector, Chroma and Atlas paths are
  still selected by configuration or used for controlled fallback.
- No governance or observability logic was duplicated in this pass. Governance
  consumes existing observability and vector-drift snapshots instead of writing
  independent counters.
- No prompt templates were removed. Code-level prompt builders and DB-managed
  prompt templates remain the supported prompt paths.

## Residual Cleanup Candidates

- The `app.ai` package still has compatibility-oriented module boundaries. A
  physical package move should be handled separately with route and import tests.
- Some docs contain older encoding artifacts. They were not cleaned here because
  that would create unrelated churn.
- Generated frontend/CSS artifacts are present in the dirty worktree from other
  slices and were not normalized in this cleanup.

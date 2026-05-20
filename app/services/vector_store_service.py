"""Vector-store abstractions for RAG retrieval."""

import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from flask import current_app, has_app_context
from sqlalchemy import or_

from app.extensions import db
from app.models import GeneratedDocument, KnowledgeChunk, KnowledgeDocument
from app.services.chunking_service import token_set
from app.services.embedding_service import get_embedding_provider
from app.services.knowledge_service import can_user_read_knowledge_document, stored_chunk_metadata
from app.services.knowledge_quality_service import retrieval_quality_gate_for_document
from app.services.retrieval_debug_service import empty_retrieval_debug
from app.services.retrieval_scoring_service import HybridRetrievalScorer
from app.services.technical_entity_service import entities_from_json, entities_to_json

logger = logging.getLogger(__name__)

DEFAULT_RAG_TOP_K = 4
DEFAULT_RAG_SCAN_LIMIT = 300
DEFAULT_RAG_KEYWORD_SCAN_LIMIT = 500
DEFAULT_RAG_MAX_KEYWORD_TERMS = 8
DEFAULT_RAG_MIN_SCORE = 1
RETRIEVAL_STOPWORDS = {
    "aber",
    "alle",
    "als",
    "am",
    "an",
    "auf",
    "bei",
    "bitte",
    "das",
    "der",
    "die",
    "ein",
    "eine",
    "fuer",
    "für",
    "hat",
    "hilfe",
    "hilft",
    "ich",
    "ist",
    "mit",
    "nach",
    "nicht",
    "oder",
    "und",
    "von",
    "was",
    "welche",
    "wie",
    "zu",
}


class VectorStoreError(Exception):
    """Raised when a vector store cannot complete an operation."""


@dataclass(frozen=True)
class VectorRecord:
    """One text record prepared for a vector store."""

    text: str
    metadata: dict = field(default_factory=dict)
    record_id: str = ""


@dataclass(frozen=True)
class VectorSearchResult:
    """One vector search result with score and metadata."""

    text: str
    score: float
    metadata: dict = field(default_factory=dict)

    def to_dict(self):
        """Return the search result as a JSON-serializable dictionary."""
        return {
            "text": self.text,
            "score": self.score,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ChunkMetadataProxy:
    """Lightweight chunk object used for metadata reconstruction."""

    id: int | str | None = None
    chunk_index: int | str = 0
    entities_json: str = "{}"
    chunk_metadata: dict = field(default_factory=dict)

    def retrieval_metadata(self):
        """Return section-aware metadata carried by a vector result."""
        return dict(self.chunk_metadata)


class BaseVectorStore(ABC):
    """Define the vector-store contract used by retrieval services."""

    name = "base"

    @abstractmethod
    def add_documents(self, records):
        """Store vector records and return stored record ids."""

    @abstractmethod
    def similarity_search(self, query_text, user=None, limit=None, filters=None):
        """Return vector-search results for query text."""

    def delete_document(self, document_id):
        """Delete records for one knowledge document when the backend supports it."""
        return 0

    def document_vector_count(self, document_id):
        """Return one document's vector count when the backend can report it."""
        return None

    def collection_vector_count(self):
        """Return the total vector count when the backend can report it."""
        return None

    def last_debug(self):
        """Return prompt-safe debug counters for the latest search."""
        return getattr(self, "_last_debug", empty_retrieval_debug(vector_store=self.name))


class SqlAlchemyKnowledgeVectorStore(BaseVectorStore):
    """Use persisted knowledge chunks as the local vector-search backend."""

    name = "local_knowledge"

    def __init__(self, embedding_provider=None):
        """Initialize the local knowledge vector adapter."""
        self.embedding_provider = embedding_provider or get_embedding_provider()
        self._last_debug = empty_retrieval_debug(vector_store=self.name)

    def add_documents(self, records):
        """Reject direct writes because knowledge indexing owns persistence."""
        raise VectorStoreError(
            "SqlAlchemyKnowledgeVectorStore is read-only; use knowledge indexing"
        )

    def similarity_search(self, query_text, user=None, limit=None, filters=None):
        """Return ranked visible knowledge chunks for query text."""
        self._last_debug = empty_retrieval_debug(vector_store=self.name, filters=filters or {})
        if not query_text or user is None:
            return []

        query_tokens = token_set(query_text)
        if not query_tokens:
            return []

        limit_value = _positive_int(limit, _config_value("RAG_TOP_K", DEFAULT_RAG_TOP_K))
        scan_limit = _positive_int(
            _config_value("RAG_SCAN_LIMIT", DEFAULT_RAG_SCAN_LIMIT),
            DEFAULT_RAG_SCAN_LIMIT,
        )
        keyword_scan_limit = _positive_int(
            _config_value("RAG_KEYWORD_SCAN_LIMIT", DEFAULT_RAG_KEYWORD_SCAN_LIMIT),
            DEFAULT_RAG_KEYWORD_SCAN_LIMIT,
        )
        min_score = _positive_int(
            _config_value("RAG_MIN_SCORE", DEFAULT_RAG_MIN_SCORE),
            DEFAULT_RAG_MIN_SCORE,
        )
        query_vector = self.embedding_provider.embed_text(query_text)
        scorer = HybridRetrievalScorer(
            query_text=query_text,
            query_vector=query_vector,
            embedding_provider=self.embedding_provider,
        )
        base_query = (
            KnowledgeChunk.query.join(KnowledgeDocument)
            .filter(KnowledgeDocument.status == "indexed")
        )
        base_query = _apply_db_filters(base_query, filters)
        keyword_chunks, recent_chunks = _candidate_chunk_sets(
            base_query=base_query,
            query_tokens=query_tokens,
            recent_limit=scan_limit,
            keyword_limit=keyword_scan_limit,
        )
        chunks = _deduplicate_chunks([*keyword_chunks, *recent_chunks])

        results = []
        permission_filtered = 0
        score_filtered = 0
        quality_filtered = 0
        for chunk in chunks:
            document = chunk.document
            if not _matches_filters(document, filters):
                continue
            quality_gate = retrieval_quality_gate_for_document(document)
            if not quality_gate.allowed:
                quality_filtered += 1
                continue
            if not can_user_read_knowledge_document(user, document):
                permission_filtered += 1
                continue
            score = scorer.score_chunk(chunk, document)
            if not score.allowed:
                score_filtered += 1
                continue
            if score.final_score < min_score:
                score_filtered += 1
                continue
            results.append(
                VectorSearchResult(
                    text=chunk.text,
                    score=score.final_score,
                    metadata=_knowledge_metadata(
                        document,
                        chunk,
                        score=score,
                    ),
                )
            )

        results.sort(
            key=lambda item: (item.score, item.metadata.get("updated_at", "")),
            reverse=True,
        )
        logger.info(
            "rag_local_retrieval query_tokens=%s candidate_count=%s result_count=%s "
            "permission_filtered=%s quality_filtered=%s score_filtered=%s min_score=%s",
            len(query_tokens),
            len(chunks),
            len(results),
            permission_filtered,
            quality_filtered,
            score_filtered,
            min_score,
        )
        self._last_debug = empty_retrieval_debug(
            keyword_candidates_found=len(keyword_chunks),
            vector_candidates_found=len(results),
            permission_filtered=permission_filtered,
            quality_filtered=quality_filtered,
            score_filtered=score_filtered,
            vector_store=self.name,
            filters=filters or {},
            top_k=limit_value,
        )
        return results[:limit_value]

    def document_vector_count(self, document_id):
        """Return the local persisted chunk count for one knowledge document."""
        try:
            parsed_id = int(document_id)
        except (TypeError, ValueError):
            return None
        return KnowledgeChunk.query.filter_by(document_id=parsed_id).count()

    def collection_vector_count(self):
        """Return the local persisted chunk count for indexed knowledge documents."""
        return (
            KnowledgeChunk.query.join(KnowledgeDocument)
            .filter(KnowledgeDocument.status == "indexed")
            .count()
        )


class ChromaVectorStore(BaseVectorStore):
    """Use Chroma as a persistent vector-store backend."""

    name = "chroma"

    def __init__(self, persist_directory, collection_name, embedding_provider=None):
        """Initialize the Chroma vector store lazily."""
        try:
            import chromadb
        except ImportError as exc:
            raise VectorStoreError("chromadb is not installed") from exc

        if not persist_directory:
            raise VectorStoreError("Chroma persist directory is required")
        if not collection_name:
            raise VectorStoreError("Chroma collection name is required")

        self.embedding_provider = embedding_provider or get_embedding_provider()
        self.client = chromadb.PersistentClient(path=persist_directory)
        self.collection = self.client.get_or_create_collection(name=collection_name)
        self._last_debug = empty_retrieval_debug(vector_store=self.name)

    def add_documents(self, records):
        """Store vector records in Chroma and return their ids."""
        safe_records = [record for record in records if record.text.strip()]
        if not safe_records:
            return []

        ids = [record.record_id or uuid.uuid4().hex for record in safe_records]
        documents = [record.text for record in safe_records]
        embeddings = self.embedding_provider.embed_texts(documents)
        metadatas = [_flat_metadata(record.metadata) for record in safe_records]
        self.collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        return ids

    def delete_document(self, document_id):
        """Delete all Chroma records for one knowledge document id."""
        if document_id is None:
            return 0
        self.collection.delete(where={"id": int(document_id)})
        return 1

    def document_vector_count(self, document_id):
        """Return the Chroma record count for one knowledge document."""
        try:
            parsed_id = int(document_id)
        except (TypeError, ValueError):
            return None
        response = self.collection.get(where={"id": parsed_id})
        return len(response.get("ids") or [])

    def collection_vector_count(self):
        """Return the total Chroma record count for the collection."""
        return int(self.collection.count())

    def similarity_search(self, query_text, user=None, limit=None, filters=None):
        """Return Chroma vector-search results for query text."""
        self._last_debug = empty_retrieval_debug(vector_store=self.name, filters=filters or {})
        if not query_text:
            return []
        limit_value = _positive_int(limit, _config_value("RAG_TOP_K", DEFAULT_RAG_TOP_K))
        query_embedding = self.embedding_provider.embed_text(query_text)
        candidate_limit = max(limit_value * 4, limit_value)
        response = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=candidate_limit,
            where=_flat_metadata(filters or {}) or None,
        )
        debug = empty_retrieval_debug(
            vector_store=self.name,
            filters=filters or {},
            top_k=limit_value,
        )
        results = _filter_visible_results(
            _chroma_results(response),
            query_text=query_text,
            user=user,
            filters=filters,
            limit=limit_value,
            debug=debug,
        )
        self._last_debug = debug
        return results


def get_vector_store():
    """Return the configured vector store with a local fallback."""
    store_name = _config_value("RAG_VECTOR_STORE", "local").lower()
    if store_name in {"local", "sqlalchemy", "knowledge"}:
        return SqlAlchemyKnowledgeVectorStore()
    if store_name == "chroma":
        try:
            return ChromaVectorStore(
                persist_directory=_config_value("CHROMA_PERSIST_DIR", "data/chroma"),
                collection_name=_config_value("CHROMA_COLLECTION", "maintenance_knowledge"),
            )
        except VectorStoreError:
            logger.exception("vector_store_fallback store=chroma")
            return SqlAlchemyKnowledgeVectorStore()
    logger.warning("vector_store_fallback store=%s reason=unsupported_store", store_name)
    return SqlAlchemyKnowledgeVectorStore()


def _knowledge_metadata(document, chunk, score=None):
    """Return metadata for a persisted knowledge chunk."""
    entities = _chunk_entities(chunk)
    metadata = {
        "type": "knowledge",
        "id": document.id,
        "chunk_id": chunk.id,
        "chunk_index": chunk.chunk_index,
        "title": document.title,
        "module": "knowledge",
        "source_type": document.source_type,
        "source_id": document.source_id,
        "document_type": _document_type(document),
        "department": document.department,
        "url": _source_url(document),
        "updated_at": document.updated_at.isoformat(),
        "technical_entities": entities,
        "technical_entities_json": entities_to_json(entities),
    }
    if score is not None:
        score_metadata = score.metadata()
        metadata["score_debug"] = score_metadata
        metadata["score_components"] = score_metadata["components"]
        metadata["score_signals"] = score_metadata["signals"]
        metadata["quality_status"] = score_metadata["signals"].get("quality_status")
        metadata["quality_gate"] = score_metadata["signals"].get("quality_gate")
        metadata["quality_score_multiplier"] = score_metadata["signals"].get(
            "quality_multiplier"
        )
    metadata.update(stored_chunk_metadata(chunk))
    return metadata


def _chunk_entities(chunk):
    """Return technical entities from a real or lightweight chunk object."""
    if hasattr(chunk, "entities"):
        return chunk.entities()
    return entities_from_json(getattr(chunk, "entities_json", "{}"))


def _source_url(document):
    """Return a route hint for a knowledge document source."""
    if document.relative_path and document.relative_path.startswith("/"):
        return document.relative_path
    if document.source_type == "upload":
        return "/admin/ai"
    if document.source_type == "generated_document":
        return "/documents"
    if document.source_type == "error_entry":
        return "/errors"
    if document.source_type == "task":
        return "/tasks"
    if document.source_type == "maintenance_plan":
        return "/machines"
    if document.source_type == "machine_manual":
        return "/documents"
    if document.source_type == "shift_handover":
        return "/handover"
    if document.source_type == "manual_training":
        return "/admin/ai"
    return "/admin/ai"


def _document_type(document):
    """Return a source document type when it can be resolved safely."""
    if document.source_type != "generated_document" or not document.source_id:
        return document.source_type
    generated_document = GeneratedDocument.query.get(document.source_id)
    if not generated_document:
        return document.source_type
    return generated_document.document_type


def _matches_filters(document, filters):
    """Return whether a knowledge document matches optional metadata filters."""
    if not filters:
        return True
    for key, value in filters.items():
        if value in (None, ""):
            continue
        if key == "document_type" and _document_type(document) != value:
            return False
        if key == "department" and document.department != value:
            return False
        if key == "source_type" and document.source_type != value:
            return False
        if key == "source_id" and str(document.source_id) != str(value):
            return False
    return True


def _apply_db_filters(query, filters):
    """Apply safe document-level filters before candidate scanning."""
    if not filters:
        return query
    source_type = filters.get("source_type")
    if source_type not in (None, ""):
        query = query.filter(KnowledgeDocument.source_type == str(source_type))
    department = filters.get("department")
    if department not in (None, ""):
        query = query.filter(KnowledgeDocument.department == str(department))
    source_id = filters.get("source_id")
    if source_id not in (None, ""):
        query = query.filter(KnowledgeDocument.source_id == source_id)
    return query


def _candidate_chunks(base_query, query_tokens, recent_limit, keyword_limit):
    """Return de-duplicated recent and keyword-matched chunks for local hybrid search."""
    keyword_chunks, recent_chunks = _candidate_chunk_sets(
        base_query=base_query,
        query_tokens=query_tokens,
        recent_limit=recent_limit,
        keyword_limit=keyword_limit,
    )
    return _deduplicate_chunks([*keyword_chunks, *recent_chunks])


def _candidate_chunk_sets(base_query, query_tokens, recent_limit, keyword_limit):
    """Return keyword and recent candidate chunks before de-duplication."""
    recent_chunks = (
        base_query.order_by(
            KnowledgeDocument.updated_at.desc(),
            KnowledgeChunk.chunk_index.asc(),
        )
        .limit(recent_limit)
        .all()
    )
    keyword_chunks = _keyword_candidate_chunks(base_query, query_tokens, keyword_limit)
    return keyword_chunks, recent_chunks


def _keyword_candidate_chunks(base_query, query_tokens, keyword_limit):
    """Return chunks matched by informative query tokens before scoring."""
    terms = _informative_query_terms(query_tokens)
    if not terms:
        return []
    filters = [KnowledgeChunk.token_text.ilike(f"%{term}%") for term in terms]
    return (
        base_query.filter(or_(*filters))
        .order_by(KnowledgeDocument.updated_at.desc(), KnowledgeChunk.chunk_index.asc())
        .limit(keyword_limit)
        .all()
    )


def _informative_query_terms(query_tokens):
    """Return bounded query tokens useful for lexical candidate expansion."""
    terms = [
        str(token).lower()
        for token in query_tokens
        if _is_informative_query_token(token)
    ]
    terms.sort(key=lambda token: (not _looks_like_code_token(token), -len(token), token))
    return terms[:DEFAULT_RAG_MAX_KEYWORD_TERMS]


def _is_informative_query_token(token):
    """Return whether a query token is useful enough for DB prefiltering."""
    value = str(token or "").strip().lower()
    if len(value) < 3 or value in RETRIEVAL_STOPWORDS:
        return False
    return True


def _looks_like_code_token(token):
    """Return whether a token looks like an error code or technical identifier."""
    value = str(token or "")
    return any(char.isdigit() for char in value)


def _deduplicate_chunks(chunks):
    """Return chunks without duplicate database ids while preserving order."""
    seen = set()
    unique_chunks = []
    for chunk in chunks:
        key = getattr(chunk, "id", None)
        if key in seen:
            continue
        seen.add(key)
        unique_chunks.append(chunk)
    return unique_chunks


def _flat_metadata(metadata):
    """Return Chroma-compatible primitive metadata."""
    flat = {}
    for key, value in dict(metadata or {}).items():
        if isinstance(value, str | int | float | bool) or value is None:
            flat[str(key)] = value
        else:
            flat[str(key)] = str(value)
    return flat


def _chroma_results(response):
    """Return normalized Chroma query results."""
    documents = (response.get("documents") or [[]])[0]
    metadatas = (response.get("metadatas") or [[]])[0]
    distances = (response.get("distances") or [[]])[0]
    results = []
    for index, document in enumerate(documents):
        distance = distances[index] if index < len(distances) else 0
        metadata = metadatas[index] if index < len(metadatas) else {}
        results.append(
            VectorSearchResult(
                text=document,
                score=max(0.0, 1.0 - float(distance)),
                metadata=metadata or {},
            )
        )
    return results


def _filter_visible_results(results, query_text, user=None, filters=None, limit=None, debug=None):
    """Return Chroma results still visible according to database permissions."""
    scorer = HybridRetrievalScorer(query_text=query_text)
    visible = []
    permission_filtered = 0
    quality_filtered = 0
    score_filtered = 0
    for result in results:
        document_id = result.metadata.get("id")
        try:
            document = db.session.get(KnowledgeDocument, int(document_id))
        except (TypeError, ValueError):
            continue
        if not document or document.status != "indexed":
            continue
        if not _matches_filters(document, filters):
            continue
        quality_gate = retrieval_quality_gate_for_document(document)
        if not quality_gate.allowed:
            quality_filtered += 1
            continue
        if user is not None and not can_user_read_knowledge_document(user, document):
            permission_filtered += 1
            continue
        score = scorer.score_text_result(
            text=result.text,
            document=document,
            chunk_id=result.metadata.get("chunk_id"),
            semantic_similarity=result.score,
        )
        if not score.allowed:
            score_filtered += 1
            continue
        merged_metadata = dict(result.metadata)
        merged_metadata.update(
            _knowledge_metadata(
                document,
                _chunk_for_metadata(result),
                score=score,
            )
        )
        visible.append(
            VectorSearchResult(
                text=result.text,
                score=score.final_score,
                metadata=merged_metadata,
            )
        )
    visible.sort(
        key=lambda item: (item.score, item.metadata.get("updated_at", "")),
        reverse=True,
    )
    if isinstance(debug, dict):
        debug["vector_candidates_found"] = len(visible)
        debug["permission_filtered"] = permission_filtered
        debug["quality_filtered"] = quality_filtered
        debug["score_filtered"] = score_filtered
    return visible[:limit] if limit else visible


def _chunk_for_metadata(result):
    """Return a lightweight object exposing chunk metadata fields."""
    chunk_metadata = {
        key: result.metadata.get(key)
        for key in (
            "chunk_index",
            "chunk_order",
            "source_offset",
            "source_section",
            "section_title",
        )
        if result.metadata.get(key) not in (None, "")
    }
    return ChunkMetadataProxy(
        id=result.metadata.get("chunk_id"),
        chunk_index=result.metadata.get("chunk_index", 0),
        entities_json=result.metadata.get("technical_entities_json", "{}"),
        chunk_metadata=chunk_metadata,
    )


def _config_value(name, default):
    """Return a Flask config value when available, otherwise a default."""
    if has_app_context():
        return current_app.config.get(name, default)
    return default


def _positive_int(value, default):
    """Return a positive integer config value."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default

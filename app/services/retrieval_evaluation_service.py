"""Golden-query evaluation harness for permission-aware RAG retrieval."""

from dataclasses import dataclass, field
from math import log2

from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import RetrievalEvaluationRun
from app.services.golden_retrieval_question_service import runtime_golden_questions
from app.services.retrieval_service import retrieve_context, retrieve_vector_chunks
from app.services.text_normalization_service import normalize_query

REGRESSION_DROP_THRESHOLD = 0.05
REGRESSION_COUNT_INCREASE_THRESHOLD = 1
DEFAULT_HISTORY_LIMIT = 10
MAX_HISTORY_LIMIT = 50
RETRIEVAL_MODE_VECTOR = "vector"
RETRIEVAL_MODE_FULL = "full"


@dataclass(frozen=True)
class GoldenRetrievalQuery:
    """Describe one measurable retrieval expectation."""

    query: str
    expected_source_ids: tuple[int, ...] = ()
    expected_source_types: tuple[str, ...] = ()
    expected_sources: tuple[tuple[str, str], ...] = ()
    forbidden_source_ids: tuple[int, ...] = ()
    forbidden_source_types: tuple[str, ...] = ()
    forbidden_sources: tuple[tuple[str, str], ...] = ()
    allowed_source_types: tuple[str, ...] = ()
    min_source_count: int = 1
    required_permission_context: dict = field(default_factory=dict)
    top_k: int = 4


def evaluate_golden_queries(golden_queries, user, retrieval_mode=RETRIEVAL_MODE_VECTOR):
    """Evaluate golden retrieval queries and return aggregate quality metrics."""
    mode = _retrieval_mode(retrieval_mode)
    query_results = [
        _evaluate_query(_coerce_golden_query(item), user, mode) for item in golden_queries
    ]
    metric_results = [item for item in query_results if item["expected_count"] > 0]
    return {
        "query_count": len(query_results),
        "metric_query_count": len(metric_results),
        "recall_at_k": _average_metric(metric_results, "recall_at_k"),
        "mrr": _average_metric(metric_results, "mrr"),
        "ndcg_at_k": _average_metric(metric_results, "ndcg_at_k"),
        "permission_leak_count": sum(item["permission_leak_count"] for item in query_results),
        "forbidden_source_hit_count": sum(
            item["forbidden_source_hit_count"] for item in query_results
        ),
        "no_result_count": sum(1 for item in query_results if item["no_result"]),
        "queries": query_results,
    }


def evaluate_and_persist_golden_queries(
    golden_queries,
    user,
    commit=True,
    retrieval_mode=RETRIEVAL_MODE_VECTOR,
):
    """Evaluate golden retrieval queries and persist the prompt-safe aggregate run."""
    result = evaluate_golden_queries(
        golden_queries,
        user,
        retrieval_mode=retrieval_mode,
    )
    run = persist_retrieval_evaluation_result(result, commit=commit)
    result["evaluation_run"] = run.to_dict()
    return result


def run_admin_golden_retrieval_evaluation(user, limit=20, commit=True):
    """Run the bounded admin golden evaluation against the full retrieval pipeline."""
    runtime_set = runtime_golden_questions(user=user, limit=limit)
    queries = [
        golden_retrieval_query_from_question(question) for question in runtime_set["questions"]
    ]
    result = evaluate_and_persist_golden_queries(
        queries,
        user,
        commit=commit,
        retrieval_mode=RETRIEVAL_MODE_FULL,
    )
    return _admin_evaluation_payload(
        result,
        question_set=runtime_set["question_set"],
    )


def golden_retrieval_query_from_question(question):
    """Return an evaluation query from a public golden question definition."""
    return GoldenRetrievalQuery(
        query=question.question,
        expected_source_types=tuple(question.expected_source_types),
        expected_sources=tuple(question.expected_sources),
        forbidden_sources=tuple(question.forbidden_sources),
        allowed_source_types=tuple(question.allowed_source_types),
        min_source_count=_positive_int(question.min_source_count, default=1),
        top_k=_positive_int(question.top_k, default=4),
    )


def persist_retrieval_evaluation_result(evaluation_result, commit=True):
    """Persist aggregate retrieval evaluation metrics without query or source details."""
    if not isinstance(evaluation_result, dict):
        raise TypeError("evaluation_result must be a dictionary")
    run = RetrievalEvaluationRun(
        query_count=_nonnegative_int(evaluation_result.get("query_count")),
        recall_at_k=_clamped_metric(evaluation_result.get("recall_at_k")),
        mrr=_clamped_metric(evaluation_result.get("mrr")),
        ndcg_at_k=_clamped_metric(evaluation_result.get("ndcg_at_k")),
        permission_leak_count=_nonnegative_int(evaluation_result.get("permission_leak_count")),
        forbidden_source_hit_count=_nonnegative_int(
            evaluation_result.get("forbidden_source_hit_count")
        ),
        no_result_count=_nonnegative_int(evaluation_result.get("no_result_count")),
    )
    db.session.add(run)
    if commit:
        db.session.commit()
    else:
        db.session.flush()
    return run


def retrieval_evaluation_history(limit=DEFAULT_HISTORY_LIMIT):
    """Return recent prompt-safe golden retrieval evaluation runs and regression signals."""
    try:
        runs = (
            RetrievalEvaluationRun.query.order_by(
                RetrievalEvaluationRun.created_at.desc(),
                RetrievalEvaluationRun.id.desc(),
            )
            .limit(_history_limit(limit))
            .all()
        )
    except SQLAlchemyError as exc:
        db.session.rollback()
        return {
            "runs": [],
            "latest": None,
            "previous": None,
            "regression": detect_retrieval_regression(None, None),
            "unavailable": True,
            "error": exc.__class__.__name__,
            "privacy": _history_privacy_payload(),
        }
    payloads = [run.to_dict() for run in runs]
    latest = payloads[0] if payloads else None
    previous = payloads[1] if len(payloads) > 1 else None
    return {
        "runs": payloads,
        "latest": latest,
        "previous": previous,
        "regression": detect_retrieval_regression(latest, previous),
        "unavailable": False,
        "privacy": _history_privacy_payload(),
    }


def detect_retrieval_regression(current_run, previous_run):
    """Return regression signals between two prompt-safe evaluation run payloads."""
    current = _run_metrics(current_run)
    previous = _run_metrics(previous_run)
    if not current or not previous:
        return {"regressed": False, "signals": []}

    signals = []
    for metric in ("recall_at_k", "mrr", "ndcg_at_k"):
        delta = round(current[metric] - previous[metric], 4)
        if delta <= -REGRESSION_DROP_THRESHOLD:
            signals.append(_regression_signal(metric, current[metric], previous[metric], delta))

    for metric in (
        "permission_leak_count",
        "forbidden_source_hit_count",
        "no_result_count",
    ):
        delta = current[metric] - previous[metric]
        if delta >= REGRESSION_COUNT_INCREASE_THRESHOLD:
            signals.append(_regression_signal(metric, current[metric], previous[metric], delta))

    return {"regressed": bool(signals), "signals": signals}


def _evaluate_query(golden_query, user, retrieval_mode):
    """Evaluate one golden query against the active retrieval stack."""
    top_k = _positive_int(golden_query.top_k, default=4)
    retrieved_sources = _retrieved_sources(golden_query, user, top_k, retrieval_mode)
    expected_units = _expected_units(golden_query)
    relevances, covered_units = _relevance_by_rank(retrieved_sources, expected_units)
    return {
        "query": golden_query.query,
        "normalized_query": normalize_query(golden_query.query),
        "top_k": top_k,
        "retrieval_mode": retrieval_mode,
        "expected_count": len(expected_units),
        "expected_hit_count": len(covered_units),
        "recall_at_k": _recall_at_k(covered_units, expected_units),
        "mrr": _mean_reciprocal_rank(relevances),
        "ndcg_at_k": _ndcg_at_k(relevances, expected_units, top_k),
        "permission_leak_count": _permission_leak_count(
            golden_query.required_permission_context,
            retrieved_sources,
        ),
        "forbidden_source_hit_count": _forbidden_source_hit_count(
            golden_query,
            retrieved_sources,
        ),
        "no_result": not retrieved_sources,
        "retrieved_sources": retrieved_sources,
        "required_permission_context": _serializable_context(
            golden_query.required_permission_context,
        ),
    }


def _coerce_golden_query(value):
    """Return a GoldenRetrievalQuery from a dataclass or dictionary payload."""
    if isinstance(value, GoldenRetrievalQuery):
        return value
    if not isinstance(value, dict):
        raise TypeError("golden query must be a GoldenRetrievalQuery or dict")
    return GoldenRetrievalQuery(
        query=str(value.get("query") or ""),
        expected_source_ids=tuple(_normalized_ints(value.get("expected_source_ids"))),
        expected_source_types=tuple(_normalized_strings(value.get("expected_source_types"))),
        expected_sources=tuple(_normalized_source_pairs(value.get("expected_sources"))),
        forbidden_source_ids=tuple(_normalized_ints(value.get("forbidden_source_ids"))),
        forbidden_source_types=tuple(_normalized_strings(value.get("forbidden_source_types"))),
        forbidden_sources=tuple(_normalized_source_pairs(value.get("forbidden_sources"))),
        allowed_source_types=tuple(_normalized_strings(value.get("allowed_source_types"))),
        min_source_count=_positive_int(value.get("min_source_count"), default=1),
        required_permission_context=dict(value.get("required_permission_context") or {}),
        top_k=_positive_int(value.get("top_k"), default=4),
    )


def _retrieved_sources(golden_query, user, top_k, retrieval_mode):
    """Return retrieved source payloads for the selected evaluation mode."""
    if retrieval_mode == RETRIEVAL_MODE_FULL:
        retrieval = retrieve_context(golden_query.query, user)
        sources = (retrieval.get("sources") or [])[:top_k]
        return [
            _retrieved_public_source(source, rank=index + 1) for index, source in enumerate(sources)
        ]
    results = retrieve_vector_chunks(golden_query.query, user, limit=top_k)
    return [
        _retrieved_vector_source(result, rank=index + 1) for index, result in enumerate(results)
    ]


def _retrieved_public_source(source, rank):
    """Return a compact source payload from one public retrieval source."""
    metadata = dict(source or {})
    return {
        "rank": rank,
        "source_id": _optional_int(metadata.get("id")),
        "source_type": str(metadata.get("type") or ""),
        "source_record_id": _optional_int(metadata.get("source_record_id")),
        "chunk_id": _optional_int(metadata.get("chunk_id")),
        "title": str(metadata.get("title") or ""),
        "score": round(float(metadata.get("score", 0.0) or 0.0), 4),
        "quality_status": metadata.get("quality_status"),
    }


def _retrieved_vector_source(result, rank):
    """Return a compact source payload from one vector result."""
    metadata = dict(getattr(result, "metadata", {}) or {})
    source_type = str(metadata.get("source_type") or metadata.get("document_type") or "")
    return {
        "rank": rank,
        "source_id": _optional_int(metadata.get("id")),
        "source_type": source_type,
        "source_record_id": _optional_int(metadata.get("source_id")),
        "chunk_id": _optional_int(metadata.get("chunk_id")),
        "title": str(metadata.get("title") or ""),
        "score": round(float(getattr(result, "score", 0.0) or 0.0), 4),
        "quality_status": metadata.get("quality_status"),
    }


def _expected_units(golden_query):
    """Return normalized expectation units for matching retrieved sources."""
    expected = {
        ("source_id", source_id) for source_id in _normalized_ints(golden_query.expected_source_ids)
    }
    expected.update(
        ("source_type", source_type)
        for source_type in _normalized_strings(golden_query.expected_source_types)
    )
    expected.update(
        ("source_pair", source_type, source_id)
        for source_type, source_id in _normalized_source_pairs(golden_query.expected_sources)
    )
    return expected


def _source_units(source):
    """Return normalized units represented by one retrieved source."""
    units = set()
    if source["source_id"] is not None:
        units.add(("source_id", source["source_id"]))
    if source["source_type"]:
        units.add(("source_type", source["source_type"]))
    if source["source_id"] is not None and source["source_type"]:
        units.add(("source_pair", source["source_type"], str(source["source_id"])))
    return units


def _relevance_by_rank(retrieved_sources, expected_units):
    """Return binary relevance per rank and covered expectation units."""
    covered_units = set()
    relevances = []
    for source in retrieved_sources:
        new_hits = (_source_units(source) & expected_units) - covered_units
        relevances.append(1 if new_hits else 0)
        covered_units.update(new_hits)
    return relevances, covered_units


def _recall_at_k(covered_units, expected_units):
    """Return Recall@K for one evaluated query."""
    if not expected_units:
        return 0.0
    return round(len(covered_units) / len(expected_units), 4)


def _mean_reciprocal_rank(relevances):
    """Return reciprocal rank for the first relevant result."""
    for index, relevance in enumerate(relevances, start=1):
        if relevance:
            return round(1 / index, 4)
    return 0.0


def _ndcg_at_k(relevances, expected_units, top_k):
    """Return a simple binary nDCG@K for one query."""
    if not expected_units:
        return 0.0
    dcg = sum(
        relevance / log2(index + 1)
        for index, relevance in enumerate(relevances[:top_k], start=1)
        if relevance
    )
    ideal_relevance_count = min(len(expected_units), top_k)
    idcg = sum(1 / log2(index + 1) for index in range(1, ideal_relevance_count + 1))
    if idcg <= 0:
        return 0.0
    return round(min(dcg / idcg, 1.0), 4)


def _permission_leak_count(permission_context, retrieved_sources):
    """Return how many retrieved sources violate the expected permission context."""
    context = dict(permission_context or {})
    forbidden_ids = set(_normalized_ints(context.get("forbidden_source_ids")))
    forbidden_types = set(_normalized_strings(context.get("forbidden_source_types")))
    allowed_ids = set(_normalized_ints(context.get("allowed_source_ids")))
    allowed_types = set(_normalized_strings(context.get("allowed_source_types")))
    leaks = 0
    for source in retrieved_sources:
        source_id = source["source_id"]
        source_type = source["source_type"]
        if source_id in forbidden_ids or source_type in forbidden_types:
            leaks += 1
            continue
        if allowed_ids and source_id not in allowed_ids:
            leaks += 1
            continue
        if allowed_types and source_type not in allowed_types:
            leaks += 1
    return leaks


def _forbidden_source_hit_count(golden_query, retrieved_sources):
    """Return how many forbidden sources appeared in retrieval results."""
    forbidden_ids = set(_normalized_ints(golden_query.forbidden_source_ids))
    forbidden_types = set(_normalized_strings(golden_query.forbidden_source_types))
    forbidden_sources = set(_normalized_source_pairs(golden_query.forbidden_sources))
    allowed_types = set(_normalized_strings(golden_query.allowed_source_types))
    return sum(
        1
        for source in retrieved_sources
        if source["source_id"] in forbidden_ids
        or source["source_type"] in forbidden_types
        or (source["source_type"], str(source["source_id"])) in forbidden_sources
        or (allowed_types and source["source_type"] not in allowed_types)
    )


def _admin_evaluation_payload(result, question_set):
    """Return prompt-safe admin output for a completed evaluation run."""
    return {
        "query_count": _nonnegative_int(result.get("query_count")),
        "metric_query_count": _nonnegative_int(result.get("metric_query_count")),
        "recall_at_k": _clamped_metric(result.get("recall_at_k")),
        "mrr": _clamped_metric(result.get("mrr")),
        "ndcg_at_k": _clamped_metric(result.get("ndcg_at_k")),
        "permission_leak_count": _nonnegative_int(result.get("permission_leak_count")),
        "forbidden_source_hit_count": _nonnegative_int(result.get("forbidden_source_hit_count")),
        "no_result_count": _nonnegative_int(result.get("no_result_count")),
        "evaluation_run": result.get("evaluation_run") or {},
        "question_set": question_set,
        "retrieval_mode": RETRIEVAL_MODE_FULL,
        "privacy": _history_privacy_payload(),
    }


def _average_metric(query_results, key):
    """Return the rounded average metric for evaluated queries."""
    if not query_results:
        return 0.0
    return round(sum(item[key] for item in query_results) / len(query_results), 4)


def _serializable_context(context):
    """Return a JSON-safe copy of the permission context."""
    payload = {}
    for key, value in dict(context or {}).items():
        if isinstance(value, set | tuple | list):
            payload[str(key)] = list(value)
        else:
            payload[str(key)] = value
    return payload


def _normalized_ints(values):
    """Return valid integer values from an optional scalar or sequence."""
    if values in (None, ""):
        return []
    if isinstance(values, int):
        return [values]
    if isinstance(values, str):
        values = [values]
    normalized = []
    for value in values:
        parsed = _optional_int(value)
        if parsed is not None:
            normalized.append(parsed)
    return normalized


def _normalized_strings(values):
    """Return non-empty normalized string values from an optional scalar or sequence."""
    if values in (None, ""):
        return []
    if isinstance(values, str):
        values = [values]
    return [str(value).strip() for value in values if str(value).strip()]


def _normalized_source_pairs(values):
    """Return normalized public source type/id pairs."""
    if values in (None, ""):
        return []
    normalized = []
    for value in values:
        if not isinstance(value, list | tuple) or len(value) != 2:
            continue
        source_type = str(value[0] or "").strip()
        source_id = str(value[1] or "").strip()
        if source_type and source_id:
            normalized.append((source_type, source_id))
    return normalized


def _optional_int(value):
    """Return an integer when value can be parsed, otherwise None."""
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _positive_int(value, default):
    """Return a positive integer or a default fallback."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _clamped_metric(value):
    """Return a bounded zero-to-one evaluation metric."""
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    return round(max(0.0, min(1.0, parsed)), 4)


def _nonnegative_int(value):
    """Return a non-negative integer for persisted evaluation counts."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, parsed)


def _history_limit(value):
    """Return a bounded history limit."""
    return min(MAX_HISTORY_LIMIT, _positive_int(value, default=DEFAULT_HISTORY_LIMIT))


def _retrieval_mode(value):
    """Return a supported retrieval evaluation mode."""
    mode = str(value or RETRIEVAL_MODE_VECTOR).strip().lower()
    if mode in {RETRIEVAL_MODE_VECTOR, RETRIEVAL_MODE_FULL}:
        return mode
    raise ValueError("retrieval_mode must be 'vector' or 'full'")


def _run_metrics(run):
    """Return comparable metrics from a model or dictionary payload."""
    if run is None:
        return {}
    payload = run.to_dict() if hasattr(run, "to_dict") else dict(run)
    return {
        "recall_at_k": _clamped_metric(payload.get("recall_at_k")),
        "mrr": _clamped_metric(payload.get("mrr")),
        "ndcg_at_k": _clamped_metric(payload.get("ndcg_at_k")),
        "permission_leak_count": _nonnegative_int(payload.get("permission_leak_count")),
        "forbidden_source_hit_count": _nonnegative_int(payload.get("forbidden_source_hit_count")),
        "no_result_count": _nonnegative_int(payload.get("no_result_count")),
    }


def _regression_signal(metric, current, previous, delta):
    """Return one prompt-safe regression signal payload."""
    return {
        "metric": metric,
        "current": current,
        "previous": previous,
        "delta": round(delta, 4) if isinstance(delta, float) else delta,
        "status": "warning",
    }


def _history_privacy_payload():
    """Return privacy guarantees for persisted evaluation history."""
    return {
        "stores_query_text": False,
        "stores_expected_sources": False,
        "stores_retrieved_sources": False,
        "source": "retrieval_evaluation_run_metrics",
    }

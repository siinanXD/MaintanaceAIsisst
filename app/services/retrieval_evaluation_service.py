"""Golden-query evaluation harness for permission-aware RAG retrieval."""

from dataclasses import dataclass, field
from math import log2

from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import ErrorEntry, MaintenancePlan, RetrievalEvaluationRun, ShiftHandover, Task
from app.services.golden_retrieval_question_service import runtime_golden_questions
from app.services.query_understanding_service import classify_query
from app.services.retrieval_service import retrieve_context, retrieve_vector_chunks
from app.services.text_normalization_service import normalize_query

REGRESSION_DROP_THRESHOLD = 0.05
REGRESSION_COUNT_INCREASE_THRESHOLD = 1
QUALITY_WARNING_THRESHOLDS = {
    "recall_at_k": 0.75,
    "mrr": 0.5,
    "keyword_hit_rate": 0.6,
    "expected_no_result_success_rate": 0.8,
    "unexpected_no_result_rate": 0.1,
    "min_source_count_pass_rate": 0.8,
    "query_type_accuracy": 0.7,
    "source_pair_coverage_rate": 0.8,
    "metadata_pair_coverage_rate": 0.6,
    "block_metadata_coverage_rate": 0.8,
}
DEFAULT_HISTORY_LIMIT = 10
MAX_HISTORY_LIMIT = 50
RETRIEVAL_MODE_VECTOR = "vector"
RETRIEVAL_MODE_FULL = "full"
SAFE_SOURCE_METADATA_FIELDS = (
    "source_id",
    "source_type",
    "title",
    "module",
    "machine_id",
    "role_visibility",
    "created_at",
)


@dataclass(frozen=True)
class GoldenRetrievalQuery:
    """Describe one measurable retrieval expectation."""

    query: str
    expected_source_ids: tuple[int, ...] = ()
    expected_source_types: tuple[str, ...] = ()
    expected_sources: tuple[tuple[str, str], ...] = ()
    expected_keywords: tuple[str, ...] = ()
    forbidden_source_ids: tuple[int, ...] = ()
    forbidden_source_types: tuple[str, ...] = ()
    forbidden_sources: tuple[tuple[str, str], ...] = ()
    allowed_source_types: tuple[str, ...] = ()
    expected_no_result: bool = False
    min_source_count: int = 1
    required_permission_context: dict = field(default_factory=dict)
    expected_query_type: str = ""
    top_k: int = 4


def evaluate_golden_queries(golden_queries, user, retrieval_mode=RETRIEVAL_MODE_VECTOR):
    """Evaluate golden retrieval queries and return aggregate quality metrics."""
    mode = _retrieval_mode(retrieval_mode)
    query_results = [
        _evaluate_query(_coerce_golden_query(item), user, mode) for item in golden_queries
    ]
    metric_results = [item for item in query_results if item["expected_count"] > 0]
    keyword_results = [
        item for item in query_results if item["expected_keyword_count"] > 0
    ]
    keyword_miss_count = sum(
        len(item.get("missing_keywords") or []) for item in keyword_results
    )
    no_result_count = sum(1 for item in query_results if item["no_result"])
    expected_no_result_count = sum(
        1 for item in query_results if item["expected_no_result"]
    )
    expected_no_result_success_count = sum(
        1 for item in query_results if item["expected_no_result_success"]
    )
    unexpected_no_result_count = sum(
        1 for item in query_results if item["unexpected_no_result"]
    )
    min_source_count_fail_count = sum(
        1 for item in query_results if not item["min_source_count_met"]
    )
    query_type_expected_count = sum(
        1 for item in query_results if item["expected_query_type"]
    )
    query_type_match_count = sum(
        1 for item in query_results if item["query_type_match"]
    )
    return {
        "query_count": len(query_results),
        "metric_query_count": len(metric_results),
        "recall_at_k": _average_metric(metric_results, "recall_at_k"),
        "mrr": _average_metric(metric_results, "mrr"),
        "ndcg_at_k": _average_metric(metric_results, "ndcg_at_k"),
        "keyword_query_count": len(keyword_results),
        "keyword_hit_rate": _average_metric(keyword_results, "keyword_hit_rate"),
        "keyword_miss_count": keyword_miss_count,
        "permission_leak_count": sum(item["permission_leak_count"] for item in query_results),
        "forbidden_source_hit_count": sum(
            item["forbidden_source_hit_count"] for item in query_results
        ),
        "no_result_count": no_result_count,
        "no_result_rate": _rate(no_result_count, len(query_results)),
        "expected_no_result_count": expected_no_result_count,
        "expected_no_result_success_count": expected_no_result_success_count,
        "expected_no_result_success_rate": _rate(
            expected_no_result_success_count,
            expected_no_result_count,
        ),
        "unexpected_no_result_count": unexpected_no_result_count,
        "unexpected_no_result_rate": _rate(
            unexpected_no_result_count,
            len(query_results) - expected_no_result_count,
        ),
        "min_source_count_fail_count": min_source_count_fail_count,
        "min_source_count_pass_rate": _rate(
            len(query_results) - min_source_count_fail_count,
            len(query_results),
        ),
        "query_type_expected_count": query_type_expected_count,
        "query_type_match_count": query_type_match_count,
        "query_type_accuracy": _rate(query_type_match_count, query_type_expected_count),
        "chunk_metadata_coverage": _chunk_metadata_coverage(query_results),
        "source_metadata_coverage": _source_metadata_coverage(query_results),
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
        expected_keywords=tuple(question.expected_keywords),
        forbidden_sources=tuple(question.forbidden_sources),
        allowed_source_types=tuple(question.allowed_source_types),
        expected_no_result=bool(question.expected_no_result),
        min_source_count=_positive_int(question.min_source_count, default=1),
        required_permission_context=dict(question.required_permission_context or {}),
        expected_query_type=str(question.expected_query_type or ""),
        top_k=_positive_int(question.top_k, default=4),
    )


def persist_retrieval_evaluation_result(evaluation_result, commit=True):
    """Persist aggregate retrieval evaluation metrics without query or source details."""
    if not isinstance(evaluation_result, dict):
        raise TypeError("evaluation_result must be a dictionary")
    source_metadata = _safe_source_metadata_coverage(
        evaluation_result.get("source_metadata_coverage")
    )
    run = RetrievalEvaluationRun(
        query_count=_nonnegative_int(evaluation_result.get("query_count")),
        recall_at_k=_clamped_metric(evaluation_result.get("recall_at_k")),
        mrr=_clamped_metric(evaluation_result.get("mrr")),
        ndcg_at_k=_clamped_metric(evaluation_result.get("ndcg_at_k")),
        keyword_query_count=_nonnegative_int(evaluation_result.get("keyword_query_count")),
        keyword_hit_rate=_clamped_metric(evaluation_result.get("keyword_hit_rate")),
        permission_leak_count=_nonnegative_int(evaluation_result.get("permission_leak_count")),
        forbidden_source_hit_count=_nonnegative_int(
            evaluation_result.get("forbidden_source_hit_count")
        ),
        no_result_count=_nonnegative_int(evaluation_result.get("no_result_count")),
        no_result_rate=_clamped_metric(evaluation_result.get("no_result_rate")),
        expected_no_result_count=_nonnegative_int(
            evaluation_result.get("expected_no_result_count")
        ),
        expected_no_result_success_count=_nonnegative_int(
            evaluation_result.get("expected_no_result_success_count")
        ),
        expected_no_result_success_rate=_clamped_metric(
            evaluation_result.get("expected_no_result_success_rate")
        ),
        unexpected_no_result_count=_nonnegative_int(
            evaluation_result.get("unexpected_no_result_count")
        ),
        unexpected_no_result_rate=_clamped_metric(
            evaluation_result.get("unexpected_no_result_rate")
        ),
        min_source_count_fail_count=_nonnegative_int(
            evaluation_result.get("min_source_count_fail_count")
        ),
        min_source_count_pass_rate=_clamped_metric(
            evaluation_result.get("min_source_count_pass_rate")
        ),
        query_type_expected_count=_nonnegative_int(
            evaluation_result.get("query_type_expected_count")
        ),
        query_type_match_count=_nonnegative_int(
            evaluation_result.get("query_type_match_count")
        ),
        query_type_accuracy=_clamped_metric(evaluation_result.get("query_type_accuracy")),
        source_metadata_count=source_metadata["retrieved_source_count"],
        source_id_coverage_rate=source_metadata["source_id_coverage_rate"],
        source_type_coverage_rate=source_metadata["source_type_coverage_rate"],
        source_pair_coverage_rate=source_metadata["source_pair_coverage_rate"],
        metadata_pair_coverage_rate=source_metadata["metadata_pair_coverage_rate"],
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
    payloads = [_with_evaluation_quality_gate(payload) for payload in payloads]
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
    for metric in (
        "recall_at_k",
        "mrr",
        "ndcg_at_k",
        "keyword_hit_rate",
        "min_source_count_pass_rate",
        "query_type_accuracy",
        "source_id_coverage_rate",
        "source_type_coverage_rate",
        "source_pair_coverage_rate",
        "metadata_pair_coverage_rate",
    ):
        delta = round(current[metric] - previous[metric], 4)
        if delta <= -REGRESSION_DROP_THRESHOLD:
            signals.append(_regression_signal(metric, current[metric], previous[metric], delta))

    for metric in (
        "permission_leak_count",
        "forbidden_source_hit_count",
        "no_result_count",
        "unexpected_no_result_count",
        "min_source_count_fail_count",
    ):
        delta = current[metric] - previous[metric]
        if delta >= REGRESSION_COUNT_INCREASE_THRESHOLD:
            signals.append(_regression_signal(metric, current[metric], previous[metric], delta))

    delta = round(current["no_result_rate"] - previous["no_result_rate"], 4)
    if delta >= REGRESSION_DROP_THRESHOLD:
        signals.append(
            _regression_signal(
                "no_result_rate",
                current["no_result_rate"],
                previous["no_result_rate"],
                delta,
            )
        )

    delta = round(current["unexpected_no_result_rate"] - previous["unexpected_no_result_rate"], 4)
    if delta >= REGRESSION_DROP_THRESHOLD:
        signals.append(
            _regression_signal(
                "unexpected_no_result_rate",
                current["unexpected_no_result_rate"],
                previous["unexpected_no_result_rate"],
                delta,
            )
        )

    delta = round(
        current["expected_no_result_success_rate"]
        - previous["expected_no_result_success_rate"],
        4,
    )
    if delta <= -REGRESSION_DROP_THRESHOLD:
        signals.append(
            _regression_signal(
                "expected_no_result_success_rate",
                current["expected_no_result_success_rate"],
                previous["expected_no_result_success_rate"],
                delta,
            )
        )

    return {"regressed": bool(signals), "signals": signals}


def evaluation_quality_gate(run):
    """Return a compact quality gate from prompt-safe retrieval evaluation metrics."""
    metrics = _run_metrics(run)
    if not metrics:
        return {
            "status": "unknown",
            "passed": False,
            "blocking": [],
            "warnings": [],
            "summary": "Keine Retrieval-Evaluation vorhanden.",
        }

    blocking = _quality_gate_blocking_signals(metrics)
    warnings = _quality_gate_warning_signals(metrics)
    if blocking:
        status = "fail"
    elif warnings:
        status = "warning"
    else:
        status = "pass"
    return {
        "status": status,
        "passed": status == "pass",
        "blocking": blocking,
        "warnings": warnings,
        "summary": _quality_gate_summary(status, blocking, warnings),
    }


def _evaluate_query(golden_query, user, retrieval_mode):
    """Evaluate one golden query against the active retrieval stack."""
    top_k = _positive_int(golden_query.top_k, default=4)
    min_source_count = _positive_int(golden_query.min_source_count, default=1)
    retrieved_sources = _retrieved_sources(golden_query, user, top_k, retrieval_mode)
    retrieved_source_count = len(retrieved_sources)
    expected_units = _expected_units(golden_query)
    relevances, covered_units = _relevance_by_rank(retrieved_sources, expected_units)
    expected_keywords = _normalized_strings(golden_query.expected_keywords)
    matched_keywords = _matched_keywords(retrieved_sources, expected_keywords)
    missing_keywords = _missing_keywords(matched_keywords, expected_keywords)
    no_result = not retrieved_sources
    expected_no_result = bool(golden_query.expected_no_result)
    expected_query_type = str(golden_query.expected_query_type or "").strip()
    query_understanding = classify_query(golden_query.query)
    actual_query_type = str(query_understanding.query_type or "")
    return {
        "query": golden_query.query,
        "normalized_query": normalize_query(golden_query.query),
        "top_k": top_k,
        "min_source_count": min_source_count,
        "retrieved_source_count": retrieved_source_count,
        "min_source_count_met": (
            (expected_no_result and no_result) or retrieved_source_count >= min_source_count
        ),
        "retrieval_mode": retrieval_mode,
        "expected_count": len(expected_units),
        "expected_no_result": expected_no_result,
        "expected_no_result_success": expected_no_result and no_result,
        "unexpected_no_result": no_result and not expected_no_result,
        "expected_hit_count": len(covered_units),
        "expected_keyword_count": len(expected_keywords),
        "expected_keyword_hit_count": len(matched_keywords),
        "keyword_hit_rate": _keyword_hit_rate(matched_keywords, expected_keywords),
        "matched_keywords": matched_keywords,
        "missing_keywords": missing_keywords,
        "expected_query_type": expected_query_type,
        "actual_query_type": actual_query_type,
        "query_type_match": (
            bool(expected_query_type) and actual_query_type == expected_query_type
        ),
        "query_type_confidence": round(float(query_understanding.confidence), 4),
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
        "chunk_metadata_coverage": _source_chunk_metadata_coverage(retrieved_sources),
        "source_metadata_coverage": _retrieved_source_metadata_coverage(retrieved_sources),
        "no_result": no_result,
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
        expected_keywords=tuple(_normalized_strings(value.get("expected_keywords"))),
        forbidden_source_ids=tuple(_normalized_ints(value.get("forbidden_source_ids"))),
        forbidden_source_types=tuple(_normalized_strings(value.get("forbidden_source_types"))),
        forbidden_sources=tuple(_normalized_source_pairs(value.get("forbidden_sources"))),
        allowed_source_types=tuple(_normalized_strings(value.get("allowed_source_types"))),
        expected_no_result=_bool_value(value.get("expected_no_result")),
        min_source_count=_positive_int(value.get("min_source_count"), default=1),
        required_permission_context=dict(value.get("required_permission_context") or {}),
        expected_query_type=str(value.get("expected_query_type") or ""),
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
    title = str(metadata.get("title") or "")
    payload = {
        "rank": rank,
        "source_id": _optional_int(metadata.get("id")),
        "source_type": str(metadata.get("type") or ""),
        "metadata_source_id": _optional_int(metadata.get("source_id")),
        "metadata_source_type": str(metadata.get("source_type") or ""),
        "source_record_id": _optional_int(metadata.get("source_record_id")),
        "chunk_id": _optional_int(metadata.get("chunk_id")),
        "title": title,
        "content": _source_search_excerpt(
            _public_source_search_text(metadata, fallback_text=title)
        ),
        "score": round(float(metadata.get("score", 0.0) or 0.0), 4),
        "quality_status": metadata.get("quality_status"),
    }
    payload.update(_retrieved_safe_source_metadata(metadata))
    payload.update(_retrieved_chunk_metadata(metadata))
    return payload


def _public_source_search_text(metadata, fallback_text=""):
    """Return in-memory keyword text for a public retrieval source."""
    source_types = {
        str(metadata.get("type") or ""),
        str(metadata.get("source_type") or ""),
    }
    if "task" in source_types:
        return " ".join(
            part
            for part in (
                fallback_text,
                _task_search_text(metadata),
            )
            if str(part or "").strip()
        )
    if source_types & {"error", "error_entry"}:
        return " ".join(
            part
            for part in (
                fallback_text,
                _error_entry_search_text(metadata),
            )
            if str(part or "").strip()
        )
    if "maintenance_plan" in source_types:
        return " ".join(
            part
            for part in (
                fallback_text,
                _maintenance_plan_search_text(metadata),
            )
            if str(part or "").strip()
        )
    if "shift_handover" in source_types:
        return " ".join(
            part
            for part in (
                fallback_text,
                _shift_handover_search_text(metadata),
            )
            if str(part or "").strip()
    )
    return str(fallback_text or "")


def _task_search_text(metadata):
    """Return searchable task text for full retrieval keyword checks."""
    task_id = _public_record_id(metadata, "task")
    if not task_id:
        return ""
    task = db.session.get(Task, task_id)
    if not task:
        return ""
    return " ".join(
        str(part or "").strip()
        for part in (
            task.title,
            task.description,
            task.blocked_reason,
            task.status.value if task.status else "",
            task.priority.value if task.priority else "",
            task.due_date.isoformat() if task.due_date else "",
            task.department.name if task.department else "",
        )
        if str(part or "").strip()
    )


def _error_entry_search_text(metadata):
    """Return searchable error-entry text for full retrieval keyword checks."""
    entry_id = _public_record_id(metadata, "error", "error_entry")
    if not entry_id:
        return ""
    entry = db.session.get(ErrorEntry, entry_id)
    if not entry:
        return ""
    return " ".join(
        str(part or "").strip()
        for part in (
            entry.machine,
            entry.error_code,
            entry.title,
            entry.description,
            entry.symptoms,
            entry.possible_causes,
            entry.solution,
            entry.status,
            entry.severity,
            entry.cause_category,
            entry.impact,
            entry.department.name if entry.department else "",
        )
        if str(part or "").strip()
    )


def _maintenance_plan_search_text(metadata):
    """Return searchable maintenance-plan text for evaluation keyword metrics."""
    plan_id = _public_record_id(metadata, "maintenance_plan")
    if not plan_id:
        return ""
    plan = db.session.get(MaintenancePlan, plan_id)
    if not plan:
        return ""
    return " ".join(
        str(part or "").strip()
        for part in (
            plan.title,
            plan.description,
            plan.priority.value if plan.priority else "",
            plan.next_due_date.isoformat() if plan.next_due_date else "",
            plan.department.name if plan.department else "",
            plan.machine.name if plan.machine else "",
            "aktiv" if plan.is_active else "inaktiv",
        )
        if str(part or "").strip()
    )


def _shift_handover_search_text(metadata):
    """Return searchable shift-handover text for evaluation keyword metrics."""
    handover_id = _public_record_id(metadata, "shift_handover")
    if not handover_id:
        return ""
    handover = db.session.get(ShiftHandover, handover_id)
    if not handover:
        return ""
    return " ".join(
        str(part or "").strip()
        for part in (
            handover.department,
            handover.area,
            handover.shift_type,
            handover.status,
            handover.content,
            handover.open_tasks,
            handover.machine_notes,
            handover.next_notes,
            handover.safety_notes,
            handover.material_notes,
            handover.cause,
            handover.action_taken,
            handover.follow_up_task,
        )
        if str(part or "").strip()
    )


def _public_record_id(metadata, *source_types):
    """Return the best matching record id from a public retrieval source."""
    expected_types = set(_normalized_strings(source_types))
    public_source_type = str(metadata.get("type") or "")
    metadata_source_type = str(metadata.get("source_type") or "")
    public_source_id = _optional_int(metadata.get("id"))
    metadata_source_id = _optional_int(metadata.get("source_id"))
    source_record_id = _optional_int(metadata.get("source_record_id"))
    if metadata_source_type in expected_types:
        return metadata_source_id or source_record_id or public_source_id
    if public_source_type in expected_types:
        return public_source_id or source_record_id or metadata_source_id
    return source_record_id or metadata_source_id or public_source_id


def _retrieved_vector_source(result, rank):
    """Return a compact source payload from one vector result."""
    metadata = dict(getattr(result, "metadata", {}) or {})
    source_type = str(metadata.get("source_type") or metadata.get("document_type") or "")
    payload = {
        "rank": rank,
        "source_id": _optional_int(metadata.get("id")),
        "source_type": source_type,
        "metadata_source_id": _optional_int(metadata.get("source_id")),
        "metadata_source_type": source_type,
        "source_record_id": _optional_int(metadata.get("source_id")),
        "chunk_id": _optional_int(metadata.get("chunk_id")),
        "title": str(metadata.get("title") or ""),
        "content": _source_search_excerpt(getattr(result, "text", "") or ""),
        "score": round(float(getattr(result, "score", 0.0) or 0.0), 4),
        "quality_status": metadata.get("quality_status"),
    }
    payload.update(_retrieved_safe_source_metadata(metadata))
    payload.update(_retrieved_chunk_metadata(metadata))
    return payload


def _retrieved_safe_source_metadata(metadata):
    """Return prompt-safe source metadata fields for evaluation diagnostics."""
    return {
        "module": str(metadata.get("module") or "")[:80],
        "machine_id": _optional_int(metadata.get("machine_id")),
        "role_visibility": str(metadata.get("role_visibility") or "")[:160],
        "created_at": _safe_created_at(metadata.get("created_at")),
    }


def _retrieved_chunk_metadata(metadata):
    """Return prompt-safe chunk segmentation metadata for evaluation output."""
    return {
        "chunk_char_count": _optional_int(metadata.get("chunk_char_count")),
        "chunk_line_count": _optional_int(metadata.get("chunk_line_count")),
        "chunk_token_count": _optional_int(metadata.get("chunk_token_count")),
        "chunk_block_count": _optional_int(metadata.get("chunk_block_count")),
        "chunk_block_kinds": _chunk_block_kinds(metadata.get("chunk_block_kinds")),
        "chunking_mode": str(metadata.get("chunking_mode") or "")[:80],
        "section_title": str(metadata.get("section_title") or "")[:180],
    }


def _chunk_metadata_coverage(query_results):
    """Return aggregate prompt-safe chunk metadata coverage for an evaluation run."""
    sources = [
        source
        for query_result in query_results
        for source in query_result.get("retrieved_sources", [])
    ]
    return _source_chunk_metadata_coverage(sources)


def _source_chunk_metadata_coverage(retrieved_sources):
    """Return prompt-safe chunk metadata coverage for retrieved sources."""
    chunk_sources = [
        source for source in retrieved_sources if source.get("chunk_id") is not None
    ]
    measured_sources = [
        source for source in chunk_sources if source.get("chunk_char_count") is not None
    ]
    char_counts = [
        source.get("chunk_char_count")
        for source in measured_sources
        if source.get("chunk_char_count") is not None
    ]
    token_counts = [
        source.get("chunk_token_count")
        for source in measured_sources
        if source.get("chunk_token_count") is not None
    ]
    block_counts = [
        source.get("chunk_block_count")
        for source in chunk_sources
        if source.get("chunk_block_count") is not None
    ]
    block_kind_counter = {}
    for source in chunk_sources:
        for block_kind in source.get("chunk_block_kinds") or []:
            block_key = str(block_kind)
            block_kind_counter[block_key] = block_kind_counter.get(block_key, 0) + 1
    return {
        "retrieved_chunk_count": len(chunk_sources),
        "measured_chunk_count": len(measured_sources),
        "coverage_rate": _rate(len(measured_sources), len(chunk_sources)),
        "average_char_count": _average_values(char_counts),
        "average_token_count": _average_values(token_counts),
        "block_metadata_count": len(block_counts),
        "block_metadata_coverage_rate": _rate(len(block_counts), len(chunk_sources)),
        "average_block_count": _average_values(block_counts),
        "block_kind_distribution": block_kind_counter,
    }


def _source_metadata_coverage(query_results):
    """Return aggregate safe source metadata coverage for an evaluation run."""
    sources = [
        source
        for query_result in query_results
        for source in query_result.get("retrieved_sources", [])
    ]
    return _retrieved_source_metadata_coverage(sources)


def _retrieved_source_metadata_coverage(retrieved_sources):
    """Return coverage of safe source IDs and types used for evaluation matching."""
    sources = list(retrieved_sources or [])
    with_source_id = [source for source in sources if _source_ids(source)]
    with_source_type = [source for source in sources if _source_types(source)]
    with_metadata_pair = [
        source
        for source in sources
        if source.get("metadata_source_type") and source.get("metadata_source_id") is not None
    ]
    with_any_pair = [
        source for source in sources if _source_ids(source) and _source_types(source)
    ]
    return {
        "retrieved_source_count": len(sources),
        "with_source_id_count": len(with_source_id),
        "with_source_type_count": len(with_source_type),
        "with_source_pair_count": len(with_any_pair),
        "with_metadata_pair_count": len(with_metadata_pair),
        "source_id_coverage_rate": _rate(len(with_source_id), len(sources)),
        "source_type_coverage_rate": _rate(len(with_source_type), len(sources)),
        "source_pair_coverage_rate": _rate(len(with_any_pair), len(sources)),
        "metadata_pair_coverage_rate": _rate(len(with_metadata_pair), len(sources)),
        "field_coverage": _safe_source_field_coverage(sources),
    }


def _safe_source_field_coverage(sources):
    """Return per-field coverage for safe public source metadata."""
    source_count = len(sources)
    return {
        field: {
            "with_value_count": sum(
                1 for source in sources if _has_metadata_value(source.get(field))
            ),
            "coverage_rate": _rate(
                sum(1 for source in sources if _has_metadata_value(source.get(field))),
                source_count,
            ),
        }
        for field in SAFE_SOURCE_METADATA_FIELDS
    }


def _has_metadata_value(value):
    """Return whether a metadata value is present without treating zero as missing."""
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


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
    if source.get("metadata_source_id") is not None:
        units.add(("source_id", source["metadata_source_id"]))
    if source.get("metadata_source_type"):
        units.add(("source_type", source["metadata_source_type"]))
    for source_type in _source_types(source):
        for source_id in _source_ids(source):
            units.add(("source_pair", source_type, str(source_id)))
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


def _matched_keywords(retrieved_sources, expected_keywords):
    """Return expected keywords found in retrieved title or content text."""
    if not expected_keywords:
        return []
    search_text = normalize_query(
        " ".join(
            " ".join(
                str(source.get(key) or "")
                for key in (
                    "title",
                    "source_type",
                    "metadata_source_type",
                    "quality_status",
                    "content",
                )
            )
            for source in retrieved_sources
        )
    )
    return [
        keyword
        for keyword in expected_keywords
        if normalize_query(keyword) and normalize_query(keyword) in search_text
    ]


def _keyword_hit_rate(matched_keywords, expected_keywords):
    """Return how many expected keywords appeared in retrieved source text."""
    if not expected_keywords:
        return 0.0
    return round(len(set(matched_keywords)) / len(set(expected_keywords)), 4)


def _missing_keywords(matched_keywords, expected_keywords):
    """Return expected keywords that were absent from retrieved source text."""
    matched = {normalize_query(keyword) for keyword in matched_keywords}
    return [
        keyword
        for keyword in expected_keywords
        if normalize_query(keyword) and normalize_query(keyword) not in matched
    ]


def _permission_leak_count(permission_context, retrieved_sources):
    """Return how many retrieved sources violate the expected permission context."""
    context = dict(permission_context or {})
    forbidden_ids = set(_normalized_ints(context.get("forbidden_source_ids")))
    forbidden_types = set(_normalized_strings(context.get("forbidden_source_types")))
    forbidden_visibility = set(_normalized_strings(context.get("forbidden_role_visibility")))
    allowed_ids = set(_normalized_ints(context.get("allowed_source_ids")))
    allowed_types = set(_normalized_strings(context.get("allowed_source_types")))
    allowed_visibility = set(_normalized_strings(context.get("allowed_role_visibility")))
    leaks = 0
    for source in retrieved_sources:
        source_types = _source_types(source)
        role_visibility = _source_role_visibility(source)
        if _source_id_hit(source, forbidden_ids) or source_types & forbidden_types:
            leaks += 1
            continue
        if role_visibility & forbidden_visibility:
            leaks += 1
            continue
        if allowed_ids and not _source_id_hit(source, allowed_ids):
            leaks += 1
            continue
        if allowed_types and not (source_types & allowed_types):
            leaks += 1
            continue
        if allowed_visibility and not (role_visibility & allowed_visibility):
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
        if _source_id_hit(source, forbidden_ids)
        or (_source_types(source) & forbidden_types)
        or _source_pair_hit(source, forbidden_sources)
        or (allowed_types and not (_source_types(source) & allowed_types))
    )


def _source_pair_hit(source, source_pairs):
    """Return whether a retrieved source matches any source type/id pair."""
    source_types = _source_types(source)
    if not source_types:
        return False
    candidate_ids = _source_ids(source)
    return any(
        (source_type, str(candidate_id)) in source_pairs
        for source_type in source_types
        for candidate_id in candidate_ids
    )


def _source_id_hit(source, source_ids):
    """Return whether a retrieved source matches any public or record id."""
    candidate_ids = _source_ids(source)
    return bool(candidate_ids & source_ids)


def _source_ids(source):
    """Return all safe public and metadata source IDs for matching."""
    return {
        source.get("source_id"),
        source.get("metadata_source_id"),
        source.get("source_record_id"),
    } - {None}


def _source_types(source):
    """Return all safe public and metadata source types for matching."""
    return {
        str(source.get("source_type") or ""),
        str(source.get("metadata_source_type") or ""),
    } - {""}


def _source_role_visibility(source):
    """Return prompt-safe role visibility labels for permission checks."""
    return {
        str(source.get("role_visibility") or ""),
        str(source.get("metadata_role_visibility") or ""),
    } - {""}


def _admin_evaluation_payload(result, question_set):
    """Return prompt-safe admin output for a completed evaluation run."""
    payload = {
        "query_count": _nonnegative_int(result.get("query_count")),
        "metric_query_count": _nonnegative_int(result.get("metric_query_count")),
        "recall_at_k": _clamped_metric(result.get("recall_at_k")),
        "mrr": _clamped_metric(result.get("mrr")),
        "ndcg_at_k": _clamped_metric(result.get("ndcg_at_k")),
        "keyword_hit_rate": _clamped_metric(result.get("keyword_hit_rate")),
        "keyword_query_count": _nonnegative_int(result.get("keyword_query_count")),
        "keyword_miss_count": _nonnegative_int(result.get("keyword_miss_count")),
        "permission_leak_count": _nonnegative_int(result.get("permission_leak_count")),
        "forbidden_source_hit_count": _nonnegative_int(result.get("forbidden_source_hit_count")),
        "no_result_count": _nonnegative_int(result.get("no_result_count")),
        "no_result_rate": _clamped_metric(result.get("no_result_rate")),
        "expected_no_result_count": _nonnegative_int(
            result.get("expected_no_result_count")
        ),
        "expected_no_result_success_count": _nonnegative_int(
            result.get("expected_no_result_success_count")
        ),
        "expected_no_result_success_rate": _clamped_metric(
            result.get("expected_no_result_success_rate")
        ),
        "unexpected_no_result_count": _nonnegative_int(
            result.get("unexpected_no_result_count")
        ),
        "unexpected_no_result_rate": _clamped_metric(
            result.get("unexpected_no_result_rate")
        ),
        "min_source_count_fail_count": _nonnegative_int(
            result.get("min_source_count_fail_count")
        ),
        "min_source_count_pass_rate": _clamped_metric(
            result.get("min_source_count_pass_rate")
        ),
        "query_type_expected_count": _nonnegative_int(
            result.get("query_type_expected_count")
        ),
        "query_type_match_count": _nonnegative_int(result.get("query_type_match_count")),
        "query_type_accuracy": _clamped_metric(result.get("query_type_accuracy")),
        "chunk_metadata_coverage": _safe_chunk_metadata_coverage(
            result.get("chunk_metadata_coverage")
        ),
        "source_metadata_coverage": _safe_source_metadata_coverage(
            result.get("source_metadata_coverage")
        ),
        "evaluation_run": result.get("evaluation_run") or {},
        "question_set": question_set,
        "retrieval_mode": RETRIEVAL_MODE_FULL,
        "privacy": _history_privacy_payload(),
    }
    payload["quality_gate"] = evaluation_quality_gate(payload)
    return payload


def _safe_chunk_metadata_coverage(value):
    """Return bounded prompt-safe chunk metadata coverage metrics."""
    payload = dict(value or {}) if isinstance(value, dict) else {}
    return {
        "retrieved_chunk_count": _nonnegative_int(payload.get("retrieved_chunk_count")),
        "measured_chunk_count": _nonnegative_int(payload.get("measured_chunk_count")),
        "coverage_rate": _clamped_metric(payload.get("coverage_rate")),
        "average_char_count": _nonnegative_float(payload.get("average_char_count")),
        "average_token_count": _nonnegative_float(payload.get("average_token_count")),
        "block_metadata_count": _nonnegative_int(payload.get("block_metadata_count")),
        "block_metadata_coverage_rate": _clamped_metric(
            payload.get("block_metadata_coverage_rate")
        ),
        "average_block_count": _nonnegative_float(payload.get("average_block_count")),
        "block_kind_distribution": _safe_string_int_mapping(
            payload.get("block_kind_distribution")
        ),
    }


def _safe_source_metadata_coverage(value):
    """Return bounded prompt-safe source metadata coverage metrics."""
    payload = dict(value or {}) if isinstance(value, dict) else {}
    return {
        "retrieved_source_count": _nonnegative_int(payload.get("retrieved_source_count")),
        "with_source_id_count": _nonnegative_int(payload.get("with_source_id_count")),
        "with_source_type_count": _nonnegative_int(payload.get("with_source_type_count")),
        "with_source_pair_count": _nonnegative_int(payload.get("with_source_pair_count")),
        "with_metadata_pair_count": _nonnegative_int(
            payload.get("with_metadata_pair_count")
        ),
        "source_id_coverage_rate": _clamped_metric(payload.get("source_id_coverage_rate")),
        "source_type_coverage_rate": _clamped_metric(
            payload.get("source_type_coverage_rate")
        ),
        "source_pair_coverage_rate": _clamped_metric(
            payload.get("source_pair_coverage_rate")
        ),
        "metadata_pair_coverage_rate": _clamped_metric(
            payload.get("metadata_pair_coverage_rate")
        ),
        "field_coverage": _safe_field_coverage_payload(payload.get("field_coverage")),
    }


def _safe_field_coverage_payload(value):
    """Return bounded per-field source metadata coverage metrics."""
    payload = dict(value or {}) if isinstance(value, dict) else {}
    return {
        field: {
            "with_value_count": _nonnegative_int(
                (payload.get(field) or {}).get("with_value_count")
                if isinstance(payload.get(field), dict)
                else 0
            ),
            "coverage_rate": _clamped_metric(
                (payload.get(field) or {}).get("coverage_rate")
                if isinstance(payload.get(field), dict)
                else 0.0
            ),
        }
        for field in SAFE_SOURCE_METADATA_FIELDS
    }


def _average_metric(query_results, key):
    """Return the rounded average metric for evaluated queries."""
    if not query_results:
        return 0.0
    return round(sum(item[key] for item in query_results) / len(query_results), 4)


def _average_values(values):
    """Return a rounded average for optional numeric evaluation values."""
    numeric_values = [float(value) for value in values if value is not None]
    if not numeric_values:
        return 0.0
    return round(sum(numeric_values) / len(numeric_values), 4)


def _rate(count, total):
    """Return a rounded zero-to-one rate."""
    if total <= 0:
        return 0.0
    return round(count / total, 4)


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


def _bool_value(value):
    """Return a safe boolean for optional dictionary payload values."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _safe_created_at(value):
    """Return a bounded timestamp string for source metadata diagnostics."""
    if value in (None, ""):
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()[:80]
    return str(value).strip()[:80]


def _chunk_block_kinds(value):
    """Return prompt-safe chunk block kind labels from chunk metadata."""
    if value in (None, ""):
        return []
    raw_values = value if isinstance(value, list | tuple | set) else str(value).split(",")
    kinds = []
    for raw_value in raw_values:
        kind = str(raw_value or "").strip()[:80]
        if kind and kind not in kinds:
            kinds.append(kind)
    return kinds[:12]


def _safe_string_int_mapping(value):
    """Return a bounded string-to-count mapping for diagnostic distributions."""
    if not isinstance(value, dict):
        return {}
    rows = {}
    for key, count in value.items():
        safe_key = str(key or "").strip()[:80]
        if safe_key:
            rows[safe_key] = _nonnegative_int(count)
    return rows


def _source_search_excerpt(text):
    """Return bounded retrieved text for in-memory evaluation keyword checks."""
    return str(text or "").strip()[:1000]


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


def _nonnegative_float(value):
    """Return a non-negative rounded float for prompt-safe diagnostics."""
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    return round(max(0.0, parsed), 4)


def _history_limit(value):
    """Return a bounded history limit."""
    return min(MAX_HISTORY_LIMIT, _positive_int(value, default=DEFAULT_HISTORY_LIMIT))


def _retrieval_mode(value):
    """Return a supported retrieval evaluation mode."""
    mode = str(value or RETRIEVAL_MODE_VECTOR).strip().lower()
    if mode in {RETRIEVAL_MODE_VECTOR, RETRIEVAL_MODE_FULL}:
        return mode
    raise ValueError("retrieval_mode must be 'vector' or 'full'")


def _with_evaluation_quality_gate(payload):
    """Return a run payload enriched with an aggregate quality gate."""
    item = dict(payload or {})
    item["quality_gate"] = evaluation_quality_gate(item)
    return item


def _run_metrics(run):
    """Return comparable metrics from a model or dictionary payload."""
    if run is None:
        return {}
    payload = run.to_dict() if hasattr(run, "to_dict") else dict(run)
    return {
        "query_count": _nonnegative_int(payload.get("query_count")),
        "recall_at_k": _clamped_metric(payload.get("recall_at_k")),
        "mrr": _clamped_metric(payload.get("mrr")),
        "ndcg_at_k": _clamped_metric(payload.get("ndcg_at_k")),
        "keyword_query_count": _nonnegative_int(payload.get("keyword_query_count")),
        "keyword_hit_rate": _clamped_metric(payload.get("keyword_hit_rate")),
        "permission_leak_count": _nonnegative_int(payload.get("permission_leak_count")),
        "forbidden_source_hit_count": _nonnegative_int(payload.get("forbidden_source_hit_count")),
        "no_result_count": _nonnegative_int(payload.get("no_result_count")),
        "no_result_rate": _clamped_metric(payload.get("no_result_rate")),
        "expected_no_result_count": _nonnegative_int(
            payload.get("expected_no_result_count")
        ),
        "expected_no_result_success_rate": _clamped_metric(
            payload.get("expected_no_result_success_rate")
        ),
        "unexpected_no_result_count": _nonnegative_int(
            payload.get("unexpected_no_result_count")
        ),
        "unexpected_no_result_rate": _clamped_metric(
            payload.get("unexpected_no_result_rate")
        ),
        "min_source_count_fail_count": _nonnegative_int(
            payload.get("min_source_count_fail_count")
        ),
        "min_source_count_pass_rate": _clamped_metric(
            payload.get("min_source_count_pass_rate")
        ),
        "query_type_expected_count": _nonnegative_int(
            payload.get("query_type_expected_count")
        ),
        "query_type_accuracy": _clamped_metric(payload.get("query_type_accuracy")),
        "source_metadata_count": _nonnegative_int(payload.get("source_metadata_count")),
        "source_id_coverage_rate": _clamped_metric(payload.get("source_id_coverage_rate")),
        "source_type_coverage_rate": _clamped_metric(
            payload.get("source_type_coverage_rate")
        ),
        "source_pair_coverage_rate": _clamped_metric(
            payload.get("source_pair_coverage_rate")
        ),
        "metadata_pair_coverage_rate": _clamped_metric(
            payload.get("metadata_pair_coverage_rate")
        ),
        "retrieved_chunk_count": _nonnegative_int(
            (payload.get("chunk_metadata_coverage") or {}).get("retrieved_chunk_count")
            if isinstance(payload.get("chunk_metadata_coverage"), dict)
            else payload.get("retrieved_chunk_count")
        ),
        "block_metadata_coverage_rate": _clamped_metric(
            (payload.get("chunk_metadata_coverage") or {}).get(
                "block_metadata_coverage_rate"
            )
            if isinstance(payload.get("chunk_metadata_coverage"), dict)
            else payload.get("block_metadata_coverage_rate")
        ),
    }


def _quality_gate_blocking_signals(metrics):
    """Return security-relevant quality gate failures."""
    blocking = []
    for metric in ("permission_leak_count", "forbidden_source_hit_count"):
        value = metrics[metric]
        if value > 0:
            blocking.append(
                {
                    "metric": metric,
                    "value": value,
                    "threshold": 0,
                    "reason": "retrieved_forbidden_or_invisible_source",
                }
            )
    return blocking


def _quality_gate_warning_signals(metrics):
    """Return non-blocking retrieval quality warnings for admin dashboards."""
    warnings = []
    for metric, threshold in QUALITY_WARNING_THRESHOLDS.items():
        if not _quality_gate_metric_applies(metric, metrics):
            continue
        value = metrics[metric]
        threshold_missed = (
            value > threshold
            if metric == "unexpected_no_result_rate"
            else value < threshold
        )
        if threshold_missed:
            warnings.append(
                {
                    "metric": metric,
                    "value": value,
                    "threshold": threshold,
                    "reason": _quality_gate_warning_reason(metric),
                }
            )
    return warnings


def _quality_gate_metric_applies(metric, metrics):
    """Return whether a quality gate metric has enough support to be useful."""
    if metrics["query_count"] <= 0:
        return False
    if metric == "keyword_hit_rate":
        return metrics["keyword_query_count"] > 0
    if metric == "expected_no_result_success_rate":
        return metrics["expected_no_result_count"] > 0
    if metric == "query_type_accuracy":
        return metrics["query_type_expected_count"] > 0
    if metric in {"source_pair_coverage_rate", "metadata_pair_coverage_rate"}:
        return metrics["source_metadata_count"] > 0
    if metric == "block_metadata_coverage_rate":
        return metrics["retrieved_chunk_count"] > 0
    return True


def _quality_gate_warning_reason(metric):
    """Return a prompt-safe reason label for one quality gate warning."""
    labels = {
        "recall_at_k": "expected_sources_not_recalled",
        "mrr": "relevant_source_ranked_too_low",
        "keyword_hit_rate": "expected_keywords_missing",
        "expected_no_result_success_rate": "expected_no_result_not_respected",
        "unexpected_no_result_rate": "unexpected_empty_retrieval",
        "min_source_count_pass_rate": "insufficient_source_count",
        "query_type_accuracy": "query_type_mismatch",
        "source_pair_coverage_rate": "source_metadata_pair_incomplete",
        "metadata_pair_coverage_rate": "structured_metadata_pair_incomplete",
        "block_metadata_coverage_rate": "chunk_structure_metadata_incomplete",
    }
    return labels.get(metric, "quality_threshold_missed")


def _quality_gate_summary(status, blocking, warnings):
    """Return a compact German admin summary for one evaluation gate."""
    if status == "pass":
        return "Retrieval-Evaluation besteht alle Quality-Gate-Regeln."
    if status == "fail":
        return (
            f"Retrieval-Evaluation blockiert wegen {len(blocking)} "
            "sicherheitsrelevanten Treffern."
        )
    return f"Retrieval-Evaluation hat {len(warnings)} Qualitaetswarnungen."


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
        "stores_expected_keywords": False,
        "stores_retrieved_sources": False,
        "stores_source_ids": False,
        "stores_source_metadata_aggregates": True,
        "stores_chunk_text": False,
        "source": "retrieval_evaluation_run_metrics",
    }

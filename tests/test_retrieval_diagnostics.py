"""Unit tests for retrieval diagnostics helpers."""

from app.services.retrieval_debug_service import (
    merge_retrieval_debug,
    public_retrieval_debug,
    retrieval_debug_decision,
)


def test_retrieval_debug_exposes_structured_counts_and_filters():
    """Verify diagnostics include stable grouped counters and filter aliases."""
    debug = merge_retrieval_debug(
        {
            "sql_candidates_found": 2,
            "keyword_candidates_found": 3,
            "vector_candidates_found": 5,
            "permission_filtered": 1,
            "quality_filtered": 2,
            "score_filtered": 4,
            "decision_trace": [
                retrieval_debug_decision(
                    "score_anchor_filter",
                    "filtered",
                    "insufficient_score_or_relevance_anchor",
                    {"filtered": 4},
                )
            ],
        },
        final_visible_sources=2,
        top_k=4,
        rerank_candidate_limit=20,
    )

    assert debug["candidate_counts"] == {
        "sql": 2,
        "keyword": 3,
        "vector": 5,
        "sql_keyword_fallback": 0,
    }
    assert debug["filtered_by"] == {
        "permissions": 1,
        "quality": 2,
        "score_anchor": 4,
    }
    assert debug["score_anchor_filtered"] == 4
    assert debug["final_visible_sources"] == 2
    assert debug["reranking"] == {
        "candidate_limit": 20,
        "candidate_count": 5,
        "final_top_k": 4,
        "final_source_count": 2,
        "reduction_count": 3,
        "reduction_rate": 0.6,
    }
    assert debug["decision_trace"][0]["step"] == "score_anchor_filter"


def test_public_retrieval_debug_sanitizes_decision_trace():
    """Verify public debug payloads remain bounded and prompt-safe."""
    debug = public_retrieval_debug(
        {
            "decision_trace": [
                {
                    "step": "vector_candidate_scan",
                    "status": "ok",
                    "reason": "x" * 500,
                    "metrics": {"query": "DBG900 Hydraulikdruck", "count": 1},
                }
            ]
        }
    )

    decision = debug["decision_trace"][0]
    assert decision["step"] == "vector_candidate_scan"
    assert len(decision["reason"]) == 160
    assert decision["metrics"]["count"] == 1
    assert "query" not in decision["metrics"]


def test_public_retrieval_debug_sanitizes_nested_metric_lists():
    """Verify nested debug metric lists do not preserve sensitive text fields."""
    debug = public_retrieval_debug(
        {
            "decision_trace": [
                retrieval_debug_decision(
                    "hybrid_candidate_scan",
                    "ok",
                    "bounded_nested_metrics",
                    {
                        "candidate_ids": [1, 2],
                        "examples": ["Sensitive prompt text"],
                        "rows": [
                            {
                                "title": "Sensitive source title",
                                "count": 2,
                                "metrics": {"prompt": "Sensitive prompt", "score": 8.5},
                            }
                        ],
                    },
                )
            ]
        }
    )

    metrics = debug["decision_trace"][0]["metrics"]
    assert metrics["candidate_ids"] == [1, 2]
    assert metrics["rows"][0]["count"] == 2
    assert metrics["rows"][0]["metrics"]["score"] == 8.5
    assert "examples" not in metrics
    assert "title" not in metrics["rows"][0]
    assert "prompt" not in metrics["rows"][0]["metrics"]
    assert "Sensitive" not in str(metrics)

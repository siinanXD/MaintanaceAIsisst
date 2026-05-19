"""Tests for the golden retrieval evaluation harness."""

import json
from datetime import timedelta

from app.domain_models.common import utc_now
from app.extensions import db
from app.models import (
    AssistantTrainingEntry,
    KnowledgeChunk,
    KnowledgeDocument,
    RetrievalEvaluationRun,
    Role,
    User,
)
from app.services.retrieval_evaluation_service import (
    GoldenRetrievalQuery,
    evaluate_and_persist_golden_queries,
    evaluate_golden_queries,
    persist_retrieval_evaluation_result,
    retrieval_evaluation_history,
)


def test_golden_retrieval_evaluation_scores_seeded_queries(
    app,
    make_user,
    set_dashboard_permission,
):
    """Verify golden queries calculate stable retrieval metrics."""
    user_data = make_user(
        username="golden_eval_user",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )
    set_dashboard_permission(user_data["username"], "documents", can_view=True)
    app.config["RAG_ENABLED"] = True
    app.config["RAG_VECTOR_STORE"] = "local"

    with app.app_context():
        user = db.session.get(User, user_data["id"])
        source_ids = _seed_golden_retrieval_documents(user.id)
        result = evaluate_golden_queries(
            (
                GoldenRetrievalQuery(
                    query="GEV900 Filterdruck Messpunkt",
                    expected_source_ids=(source_ids["filter"],),
                    top_k=3,
                ),
                GoldenRetrievalQuery(
                    query="GEV903 Orbit Lagerwelle",
                    expected_source_types=("upload",),
                    top_k=3,
                ),
                GoldenRetrievalQuery(
                    query="GEV901 Kupplungsspiel Trainingshinweis",
                    expected_source_types=("manual_training",),
                    top_k=3,
                ),
                GoldenRetrievalQuery(
                    query="GEV902 Fremdquelle Instandhaltung",
                    forbidden_source_ids=(source_ids["foreign"],),
                    top_k=3,
                ),
                GoldenRetrievalQuery(
                    query="GEV999 Cyanotyp Trefferlos",
                    top_k=3,
                ),
            ),
            user,
        )

    by_query = {item["query"]: item for item in result["queries"]}
    filter_query = by_query["GEV900 Filterdruck Messpunkt"]
    training_query = by_query["GEV901 Kupplungsspiel Trainingshinweis"]
    forbidden_query = by_query["GEV902 Fremdquelle Instandhaltung"]

    assert result["query_count"] == 5
    assert result["metric_query_count"] == 3
    assert result["recall_at_k"] == 1.0
    assert result["mrr"] == 1.0
    assert result["ndcg_at_k"] == 1.0
    assert result["permission_leak_count"] == 0
    assert result["forbidden_source_hit_count"] == 0
    assert result["no_result_count"] == 2
    assert filter_query["normalized_query"] == "gev900 filterdruck messpunkt"
    assert filter_query["retrieved_sources"][0]["source_id"] == source_ids["filter"]
    assert training_query["retrieved_sources"][0]["source_type"] == "manual_training"
    assert source_ids["foreign"] not in {
        source["source_id"] for source in forbidden_query["retrieved_sources"]
    }


def test_golden_retrieval_evaluation_counts_manual_training_permission_context(
    app,
    make_user,
    set_dashboard_permission,
):
    """Verify manual training does not leak without the required dashboard permission."""
    user_data = make_user(
        username="golden_eval_no_docs_user",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )
    set_dashboard_permission(user_data["username"], "documents", can_view=False)
    app.config["RAG_ENABLED"] = True
    app.config["RAG_VECTOR_STORE"] = "local"

    with app.app_context():
        user = db.session.get(User, user_data["id"])
        _seed_golden_retrieval_documents(user.id)
        result = evaluate_golden_queries(
            (
                GoldenRetrievalQuery(
                    query="GEV901 Kupplungsspiel Trainingshinweis",
                    forbidden_source_types=("manual_training",),
                    required_permission_context={
                        "requires_dashboards": ("documents",),
                        "forbidden_source_types": ("manual_training",),
                    },
                    top_k=3,
                ),
            ),
            user,
        )

    query_result = result["queries"][0]
    assert result["permission_leak_count"] == 0
    assert result["forbidden_source_hit_count"] == 0
    assert result["no_result_count"] == 1
    assert query_result["retrieved_sources"] == []
    assert query_result["required_permission_context"]["requires_dashboards"] == ["documents"]


def test_golden_retrieval_evaluation_reports_missing_expected_results(
    app,
    make_user,
    set_dashboard_permission,
):
    """Verify misses and empty result sets produce stable zero metrics."""
    user_data = make_user(
        username="golden_eval_miss_user",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )
    set_dashboard_permission(user_data["username"], "documents", can_view=True)
    app.config["RAG_ENABLED"] = True
    app.config["RAG_VECTOR_STORE"] = "local"

    with app.app_context():
        user = db.session.get(User, user_data["id"])
        source_ids = _seed_golden_retrieval_documents(user.id)
        result = evaluate_golden_queries(
            (
                GoldenRetrievalQuery(
                    query="GEV902 Fremdquelle Instandhaltung",
                    expected_source_ids=(source_ids["foreign"],),
                    forbidden_source_ids=(source_ids["foreign"],),
                    top_k=3,
                ),
            ),
            user,
        )

    assert result["metric_query_count"] == 1
    assert result["recall_at_k"] == 0.0
    assert result["mrr"] == 0.0
    assert result["ndcg_at_k"] == 0.0
    assert result["forbidden_source_hit_count"] == 0
    assert result["no_result_count"] == 1


def test_golden_retrieval_evaluation_persists_prompt_safe_run(
    app,
    make_user,
    set_dashboard_permission,
):
    """Verify golden evaluation runs persist only aggregate quality metrics."""
    user_data = make_user(
        username="golden_eval_persist_user",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )
    set_dashboard_permission(user_data["username"], "documents", can_view=True)
    app.config["RAG_ENABLED"] = True
    app.config["RAG_VECTOR_STORE"] = "local"

    with app.app_context():
        user = db.session.get(User, user_data["id"])
        source_ids = _seed_golden_retrieval_documents(user.id)
        result = evaluate_and_persist_golden_queries(
            (
                GoldenRetrievalQuery(
                    query="GEV900 Filterdruck Messpunkt",
                    expected_source_ids=(source_ids["filter"],),
                    top_k=3,
                ),
                GoldenRetrievalQuery(
                    query="GEV999 Cyanotyp Trefferlos",
                    top_k=3,
                ),
            ),
            user,
        )
        run = RetrievalEvaluationRun.query.one()
        run_payload = run.to_dict()

    assert result["evaluation_run"]["id"] == run_payload["id"]
    assert run_payload["query_count"] == 2
    assert run_payload["recall_at_k"] == result["recall_at_k"]
    assert run_payload["mrr"] == result["mrr"]
    assert run_payload["ndcg_at_k"] == result["ndcg_at_k"]
    assert run_payload["permission_leak_count"] == result["permission_leak_count"]
    assert run_payload["forbidden_source_hit_count"] == result["forbidden_source_hit_count"]
    assert run_payload["no_result_count"] == result["no_result_count"]
    assert "GEV900" not in json.dumps(run_payload, ensure_ascii=True)
    assert "Filterdruck" not in json.dumps(run_payload, ensure_ascii=True)


def test_retrieval_evaluation_history_detects_regression(app):
    """Verify persisted evaluation history reports quality regressions."""
    with app.app_context():
        previous = persist_retrieval_evaluation_result(
            {
                "query_count": 5,
                "recall_at_k": 1.0,
                "mrr": 1.0,
                "ndcg_at_k": 1.0,
                "permission_leak_count": 0,
                "forbidden_source_hit_count": 0,
                "no_result_count": 0,
            },
            commit=False,
        )
        previous.created_at = utc_now() - timedelta(minutes=5)
        current = persist_retrieval_evaluation_result(
            {
                "query_count": 5,
                "recall_at_k": 0.7,
                "mrr": 0.8,
                "ndcg_at_k": 0.75,
                "permission_leak_count": 1,
                "forbidden_source_hit_count": 0,
                "no_result_count": 2,
            },
            commit=False,
        )
        current.created_at = utc_now()
        db.session.commit()
        current_id = current.id
        previous_id = previous.id

        history = retrieval_evaluation_history(limit=5)

    regression = history["regression"]
    signal_metrics = {signal["metric"] for signal in regression["signals"]}
    assert history["latest"]["id"] == current_id
    assert history["previous"]["id"] == previous_id
    assert regression["regressed"] is True
    assert "recall_at_k" in signal_metrics
    assert "mrr" in signal_metrics
    assert "ndcg_at_k" in signal_metrics
    assert "permission_leak_count" in signal_metrics
    assert "no_result_count" in signal_metrics


def test_admin_retrieval_evaluation_history_endpoint_is_admin_only(
    app,
    client,
    make_user,
    auth_headers,
):
    """Verify admins can read prompt-safe retrieval evaluation history."""
    regular = make_user(username="retrieval_eval_history_user")
    admin = make_user(username="retrieval_eval_history_admin", role=Role.MASTER_ADMIN)
    with app.app_context():
        persist_retrieval_evaluation_result(
            {
                "query_count": 2,
                "recall_at_k": 0.5,
                "mrr": 0.5,
                "ndcg_at_k": 0.5,
                "permission_leak_count": 0,
                "forbidden_source_hit_count": 0,
                "no_result_count": 1,
            },
        )

    forbidden_response = client.get(
        "/api/v1/admin/ai/retrieval-evaluations?limit=5",
        headers=auth_headers(regular["username"]),
    )
    admin_response = client.get(
        "/api/v1/admin/ai/retrieval-evaluations?limit=5",
        headers=auth_headers(admin["username"]),
    )
    payload = admin_response.get_json()["data"]
    assert forbidden_response.status_code == 403
    assert admin_response.status_code == 200
    assert payload["latest"]["query_count"] == 2
    assert payload["latest"]["recall_at_k"] == 0.5
    assert payload["privacy"]["stores_query_text"] is False
    assert payload["unavailable"] is False


def _seed_golden_retrieval_documents(user_id):
    """Create deterministic knowledge documents for golden retrieval tests."""
    training = AssistantTrainingEntry(
        title="GEV901 Kupplungsspiel Training",
        question="Wie wird GEV901 geprueft?",
        answer="GEV901 Kupplungsspiel mit Lehre messen und Ergebnis dokumentieren.",
        keywords="GEV901, Kupplungsspiel, Training",
        department="Produktion",
        is_active=True,
        priority=90,
        created_by=user_id,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.session.add(training)
    db.session.flush()

    documents = {
        "filter": _create_indexed_document(
            title="GEV900 Filterdruck Upload",
            text="GEV900 Filterdruck am Messpunkt pruefen und Druckverlust notieren.",
            created_by=user_id,
        ),
        "orbit": _create_indexed_document(
            title="GEV903 Orbit Lagerwelle",
            text="GEV903 Orbit Lagerwelle reinigen und Schmierfilm kontrollieren.",
            created_by=user_id,
        ),
        "training": _create_indexed_document(
            title="GEV901 Kupplungsspiel Training",
            text="GEV901 Kupplungsspiel mit Lehre messen und Ergebnis dokumentieren.",
            created_by=user_id,
            source_type="manual_training",
            source_id=training.id,
        ),
        "foreign": _create_indexed_document(
            title="GEV902 Fremdquelle Instandhaltung",
            text="GEV902 Fremdquelle nur fuer Instandhaltung sichtbar.",
            created_by=user_id,
            department="Instandhaltung",
        ),
    }
    db.session.commit()
    return {key: document.id for key, document in documents.items()}


def _create_indexed_document(
    title,
    text,
    created_by,
    department="Produktion",
    source_type="upload",
    source_id=None,
):
    """Create one indexed knowledge document with a single chunk."""
    timestamp = utc_now()
    document = KnowledgeDocument(
        source_type=source_type,
        source_id=source_id,
        title=title,
        original_filename=f"{title}.txt",
        relative_path=f"uploads/{title}.txt",
        content_type="text/plain",
        department=department,
        status="indexed",
        quality_status="admin_approved",
        is_public=True,
        chunk_count=1,
        created_by=created_by,
        created_at=timestamp,
        updated_at=timestamp,
    )
    db.session.add(document)
    db.session.flush()
    db.session.add(
        KnowledgeChunk(
            document_id=document.id,
            chunk_index=0,
            text=text,
            token_text=text.lower(),
            created_at=timestamp,
        )
    )
    return document

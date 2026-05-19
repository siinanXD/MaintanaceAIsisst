"""Tests for the golden retrieval evaluation harness."""

from app.domain_models.common import utc_now
from app.extensions import db
from app.models import AssistantTrainingEntry, KnowledgeChunk, KnowledgeDocument, Role, User
from app.services.retrieval_evaluation_service import (
    GoldenRetrievalQuery,
    evaluate_golden_queries,
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

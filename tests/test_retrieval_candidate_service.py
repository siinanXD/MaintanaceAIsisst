"""Tests for unified retrieval candidate ranking across app data and RAG chunks."""

from app.domain_models.common import utc_now
from app.extensions import db
from app.models import KnowledgeChunk, KnowledgeDocument, Role, User
from app.services.retrieval_service import retrieve_context


def test_retrieval_candidates_rank_structured_and_rag_sources_together(
    app,
    make_user,
    make_task,
    set_dashboard_permission,
):
    """Verify structured records and RAG chunks share normalized ranking metadata."""
    user_data = make_user(
        username="candidate_rank_user",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )
    set_dashboard_permission(user_data["username"], "tasks", can_view=True)
    set_dashboard_permission(user_data["username"], "documents", can_view=True)
    make_task(
        "UC900 Pumpenfilter Aufgabe",
        creator_username=user_data["username"],
        department_name="Produktion",
        description="UC900 Pumpenfilter reinigen und Dichtung pruefen.",
    )

    with app.app_context():
        user = db.session.get(User, user_data["id"])
        _create_candidate_knowledge_document(
            title="UC900 Pumpenfilter Wissen",
            text="UC900 Pumpenfilter reinigen und Dichtung nach Wartungsplan pruefen.",
            created_by=user.id,
        )
        db.session.commit()

        payload = retrieve_context(
            "UC900 Pumpenfilter Dichtung pruefen",
            user,
            requested_scopes={"tasks", "documents"},
        )

    ranked_sources = [
        source for source in payload["sources"] if source["type"] in {"task", "knowledge"}
    ]
    source_types = {source["type"] for source in ranked_sources}
    scores = [source["normalized_score"] for source in ranked_sources]
    assert {"task", "knowledge"} <= source_types
    assert scores == sorted(scores, reverse=True)
    assert all(0 <= source["normalized_score"] <= 100 for source in ranked_sources)
    assert all("raw_score" in source for source in ranked_sources)


def test_candidate_ranking_keeps_rag_quality_gate_active(
    app,
    make_user,
    set_dashboard_permission,
):
    """Verify rejected RAG documents do not enter the unified candidate ranking."""
    user_data = make_user(
        username="candidate_quality_gate_user",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )
    set_dashboard_permission(user_data["username"], "documents", can_view=True)

    with app.app_context():
        user = db.session.get(User, user_data["id"])
        _create_candidate_knowledge_document(
            title="UC901 erlaubtes Wissen",
            text="UC901 Hydraulik Sequenz freigegeben pruefen.",
            created_by=user.id,
            quality_status="admin_approved",
        )
        _create_candidate_knowledge_document(
            title="UC901 abgelehntes Wissen",
            text="UC901 Hydraulik Sequenz abgelehnt pruefen.",
            created_by=user.id,
            quality_status="rejected",
        )
        db.session.commit()

        payload = retrieve_context(
            "UC901 Hydraulik Sequenz",
            user,
            requested_scopes={"documents"},
        )

    titles = {source["title"] for source in payload["sources"]}
    assert "UC901 erlaubtes Wissen" in titles
    assert "UC901 abgelehntes Wissen" not in titles


def test_candidate_ranking_keeps_permission_filter_active(
    app,
    make_user,
    make_task,
    set_dashboard_permission,
):
    """Verify invisible RAG chunks cannot enter the unified candidate list."""
    user_data = make_user(
        username="candidate_permission_user",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )
    set_dashboard_permission(user_data["username"], "tasks", can_view=True)
    set_dashboard_permission(user_data["username"], "documents", can_view=False)
    make_task(
        "UC902 sichtbarer Task",
        creator_username=user_data["username"],
        department_name="Produktion",
        description="UC902 strukturierte Quelle bleibt sichtbar.",
    )

    with app.app_context():
        user = db.session.get(User, user_data["id"])
        _create_candidate_knowledge_document(
            title="UC902 gesperrtes Wissen",
            text="UC902 RAG Chunk darf ohne Dokumentenrecht nicht sichtbar sein.",
            created_by=user.id,
        )
        db.session.commit()

        payload = retrieve_context(
            "UC902 Quelle",
            user,
            requested_scopes={"tasks", "documents"},
        )

    assert any(source["type"] == "task" for source in payload["sources"])
    assert all(source["type"] != "knowledge" for source in payload["sources"])


def test_candidate_ranking_is_stable_for_repeated_retrieval(
    app,
    make_user,
    make_task,
    set_dashboard_permission,
):
    """Verify repeated retrieval produces stable candidate order and scores."""
    user_data = make_user(
        username="candidate_stable_user",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )
    set_dashboard_permission(user_data["username"], "tasks", can_view=True)
    set_dashboard_permission(user_data["username"], "documents", can_view=True)
    make_task(
        "UC903 stabiler Task",
        creator_username=user_data["username"],
        department_name="Produktion",
        description="UC903 stabiler Ranking Kontext.",
    )

    with app.app_context():
        user = db.session.get(User, user_data["id"])
        _create_candidate_knowledge_document(
            title="UC903 stabiles Wissen",
            text="UC903 stabiler Ranking Kontext fuer RAG.",
            created_by=user.id,
        )
        db.session.commit()

        first = retrieve_context(
            "UC903 stabiler Ranking Kontext",
            user,
            requested_scopes={"tasks", "documents"},
        )
        second = retrieve_context(
            "UC903 stabiler Ranking Kontext",
            user,
            requested_scopes={"tasks", "documents"},
        )

    first_keys = [
        (source["type"], source["id"], source.get("chunk_id"), source["score"])
        for source in first["sources"]
    ]
    second_keys = [
        (source["type"], source["id"], source.get("chunk_id"), source["score"])
        for source in second["sources"]
    ]
    assert first_keys == second_keys


def _create_candidate_knowledge_document(
    *,
    title,
    text,
    created_by,
    quality_status="admin_approved",
):
    """Create one indexed knowledge document for candidate ranking tests."""
    now = utc_now()
    document = KnowledgeDocument(
        source_type="upload",
        title=title,
        original_filename=f"{title}.txt",
        relative_path=f"uploads/{title}.txt",
        content_type="text/plain",
        department="Produktion",
        status="indexed",
        quality_status=quality_status,
        is_public=True,
        chunk_count=1,
        created_by=created_by,
        created_at=now,
        updated_at=now,
    )
    db.session.add(document)
    db.session.flush()
    db.session.add(
        KnowledgeChunk(
            document_id=document.id,
            chunk_index=0,
            text=text,
            token_text=" ".join(text.lower().split()),
            created_at=now,
        )
    )
    return document

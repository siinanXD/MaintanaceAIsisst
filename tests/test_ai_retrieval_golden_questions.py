"""Golden tests for AI chat retrieval questions."""

from dataclasses import dataclass, field
from datetime import date, timedelta

from app.domain_models.common import utc_now
from app.extensions import db
from app.models import (
    AssistantTrainingEntry,
    ErrorEntry,
    GeneratedDocument,
    InventoryMaterial,
    KnowledgeChunk,
    KnowledgeDocument,
    Machine,
    MachineManual,
    MaintenancePlan,
    Priority,
    Role,
    ShiftHandover,
    Task,
    TaskStatus,
    User,
)


@dataclass(frozen=True)
class GoldenQuestion:
    """Describe one fixed AI retrieval question and its source expectations."""

    question: str
    expected_source_types: tuple[str, ...]
    expected_sources: tuple[tuple[str, str], ...] = ()
    min_source_count: int = 1
    forbidden_sources: tuple[tuple[str, str], ...] = ()
    expected_query_type: str = ""


def test_ai_chat_golden_retrieval_questions(
    app,
    client,
    make_user,
    auth_headers,
    set_dashboard_permission,
):
    """Verify fixed AI questions retrieve reproducible, relevant sources."""
    user = make_user(
        username="golden_ai_retrieval_user",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )
    for dashboard in (
        "tasks",
        "errors",
        "machines",
        "inventory",
        "documents",
        "shiftplans",
    ):
        set_dashboard_permission(user["username"], dashboard, can_view=True)
    app.config["RAG_ENABLED"] = True
    app.config["RAG_VECTOR_STORE"] = "local"

    with app.app_context():
        db_user = db.session.get(User, user["id"])
        source_ids = _seed_golden_sources(db_user)
        cases = _golden_questions(source_ids)

    failures = []
    for case in cases:
        response = client.post(
            "/api/v1/ai/chat",
            headers=auth_headers(user["username"]),
            json={"message": case.question},
        )
        payload = response.get_json()
        sources = payload.get("sources") or []
        diagnostics = payload.get("diagnostics") or {}
        source_keys = _source_keys(sources)
        missing_sources = set(case.expected_sources) - source_keys
        missing_types = set(case.expected_source_types) - _source_types(sources)
        forbidden_hits = source_keys & set(case.forbidden_sources)

        if response.status_code != 200:
            failures.append(f"{case.question}: HTTP {response.status_code}")
        if diagnostics.get("empty_retrieval") is True:
            failures.append(f"{case.question}: empty retrieval")
        if len(sources) < case.min_source_count:
            failures.append(
                f"{case.question}: expected at least {case.min_source_count} sources, "
                f"got {len(sources)}"
            )
        if missing_sources:
            failures.append(
                f"{case.question}: missing sources {sorted(missing_sources)}, "
                f"actual {sorted(source_keys)}"
            )
        if missing_types:
            failures.append(
                f"{case.question}: missing source types {sorted(missing_types)}, "
                f"actual {sorted(_source_types(sources))}"
            )
        if forbidden_hits:
            failures.append(f"{case.question}: forbidden sources {sorted(forbidden_hits)}")

    assert not failures, "\n".join(failures)


def _seed_golden_sources(user):
    """Create deterministic project data used by golden AI retrieval tests."""
    today = date.today()
    machine = Machine(
        name="Presse Golden 7",
        produced_item="Hydraulikdeckel",
        required_employees=2,
        criticality="critical",
        status="maintenance_required",
    )
    normal_machine = Machine(
        name="Presse Golden 8",
        produced_item="Standarddeckel",
        required_employees=1,
        criticality="normal",
        status="running",
    )
    db.session.add_all([machine, normal_machine])
    db.session.flush()

    task_today = Task(
        title="Golden offene Hydraulikpruefung",
        description="Offene Aufgabe heute an Presse Golden 7 mit Fehler E104.",
        priority=Priority.URGENT,
        status=TaskStatus.OPEN,
        due_date=today,
        department=user.department,
        created_by=user.id,
    )
    task_overdue = Task(
        title="Golden ueberfaellige Sensorpruefung",
        description="Ueberfaellige Aufgabe an Presse Golden 7.",
        priority=Priority.URGENT,
        status=TaskStatus.OPEN,
        due_date=today - timedelta(days=3),
        department=user.department,
        created_by=user.id,
    )
    task_done = Task(
        title="Golden abgeschlossene Gegenprobe",
        description="Diese erledigte Aufgabe soll nicht als offen zaehlen.",
        priority=Priority.NORMAL,
        status=TaskStatus.DONE,
        due_date=today,
        department=user.department,
        created_by=user.id,
    )
    db.session.add_all([task_today, task_overdue, task_done])

    error_e104 = _error_entry(
        machine="Presse Golden 7",
        code="E104",
        title="Sensorabgleich Hydraulik",
        description="Fehler E104 bedeutet Sensorabgleich an Presse Golden 7.",
        solution="Sensor reinigen, Abstand pruefen und Sensorabgleich dokumentieren.",
        user=user,
    )
    error_x900 = _error_entry(
        machine="Presse Golden 7",
        code="X900",
        title="Hydraulikdruckverlust",
        description="X900 weist auf Hydraulikdruckverlust an Presse Golden 7 hin.",
        solution="Druckspeicher pruefen und Leckage am Ventilblock suchen.",
        user=user,
    )
    foreign_error = _error_entry(
        machine="Fremde Presse",
        code="FG999",
        title="Fremder Fehler",
        description="Fremder Instandhaltungsfehler.",
        solution="Nicht sichtbar fuer Produktion.",
        user=user,
        department_name="Instandhaltung",
    )

    material_filter = InventoryMaterial(
        name="Golden Hydraulikfilter",
        unit_cost=42,
        quantity=1,
        min_quantity=4,
        criticality="critical",
        lead_time_days=12,
        manufacturer="Golden Parts",
        machine=machine,
    )
    material_sensor = InventoryMaterial(
        name="Golden E104 Sensorsatz",
        unit_cost=89,
        quantity=2,
        min_quantity=5,
        criticality="high",
        lead_time_days=9,
        manufacturer="Golden Parts",
        machine=machine,
    )
    db.session.add_all([material_filter, material_sensor])

    plan = MaintenancePlan(
        title="Golden Hydraulikpruefung faellig",
        description="Faellige Wartung fuer Presse Golden 7: Hydraulikdruck pruefen.",
        interval_days=30,
        next_due_date=today,
        priority=Priority.URGENT,
        is_active=True,
        machine=machine,
        department=user.department,
        created_by=user.id,
    )
    db.session.add(plan)

    document = GeneratedDocument(
        task=task_today,
        document_type="maintenance_report",
        title="Golden Dokumentation X900",
        relative_path="golden/x900_report.html",
        department="Produktion",
        machine="Presse Golden 7",
        summary="Dokumentation hilft bei X900 Hydraulikdruckverlust.",
        created_by=user.id,
        created_at=utc_now(),
    )
    manual = MachineManual(
        machine=machine,
        department="Produktion",
        title="Golden Handbuch Sensorabgleich E104",
        original_filename="golden-e104-handbuch.pdf",
        relative_path="manuals/golden-e104.pdf",
        content_type="application/pdf",
        analysis="Sensorabgleich E104 an Presse Golden 7 kalibrieren.",
        analysis_status="completed",
        summary="Handbuch zu Sensorabgleich E104.",
        summary_status="completed",
        created_by=user.id,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    training = AssistantTrainingEntry(
        title="Golden Trainingsantwort Hydraulikpruefung",
        question="Welche Trainingsantwort gibt es zur Hydraulikpruefung?",
        answer="Hydraulikpruefung: Druck, Filter und Ventilblock kontrollieren.",
        keywords="Golden, Hydraulikpruefung, Trainingsantwort",
        category="wartung",
        department="Produktion",
        is_active=True,
        priority=90,
        created_by=user.id,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    handover = ShiftHandover(
        department="Produktion",
        shift_date=today,
        shift_type="late",
        status="open",
        handed_over_by=user.id,
        content="Presse Golden 7 braucht Kontrolle.",
        open_tasks="Offene Aufgabe: Golden offene Hydraulikpruefung.",
        machine_notes="Presse Golden 7 mit E104 Sensorabgleich beobachten.",
        next_notes="Hydraulikdruckverlust X900 im Blick behalten.",
    )
    db.session.add_all([document, manual, training, handover])
    db.session.flush()

    knowledge_hydraulic = _knowledge_document(
        title="Golden Anleitung Hydraulikdruckverlust",
        text="Anleitung Hydraulikdruckverlust: Druckspeicher und Ventilblock pruefen.",
        user=user,
    )
    knowledge_e104 = _knowledge_document(
        title="Golden Sensorabgleich E104 Wissen",
        text="Sensorabgleich E104: Sensor reinigen, Abstand einstellen und testen.",
        user=user,
        source_type="machine_manual",
        source_id=manual.id,
    )
    knowledge_training = _knowledge_document(
        title="Golden Trainingsantwort Hydraulikpruefung",
        text="Trainingsantwort Hydraulikpruefung: Filter, Druck und Leckage pruefen.",
        user=user,
        source_type="manual_training",
        source_id=training.id,
    )
    foreign_doc = _knowledge_document(
        title="Golden Fremdquelle Instandhaltung",
        text="Diese fremde Quelle darf Produktion nicht sehen.",
        user=user,
        department="Instandhaltung",
    )
    db.session.commit()

    return {
        "task_today": task_today.id,
        "task_overdue": task_overdue.id,
        "task_done": task_done.id,
        "error_e104": error_e104.id,
        "error_x900": error_x900.id,
        "foreign_error": foreign_error.id,
        "machine": machine.id,
        "normal_machine": normal_machine.id,
        "material_filter": material_filter.id,
        "material_sensor": material_sensor.id,
        "plan": plan.id,
        "document": document.id,
        "manual": manual.id,
        "training": training.id,
        "handover": handover.id,
        "knowledge_hydraulic": knowledge_hydraulic.id,
        "knowledge_e104": knowledge_e104.id,
        "knowledge_training": knowledge_training.id,
        "foreign_doc": foreign_doc.id,
    }


def _golden_questions(ids):
    """Return the fixed golden AI retrieval question set."""
    forbidden = (
        ("error", str(ids["foreign_error"])),
        ("knowledge", str(ids["foreign_doc"])),
    )
    return (
        GoldenQuestion(
            "Welche Tasks sind heute offen?",
            ("task",),
            (("task", str(ids["task_today"])),),
            forbidden_sources=forbidden,
        ),
        GoldenQuestion(
            "Welche offenen Aufgaben gibt es heute an Presse Golden 7?",
            ("task",),
            (("task", str(ids["task_today"])),),
            forbidden_sources=forbidden,
        ),
        GoldenQuestion(
            "Welche Maschine hat offene Aufgaben?",
            ("machine", "task"),
            (("machine", str(ids["machine"])), ("task", str(ids["task_today"]))),
            min_source_count=2,
            forbidden_sources=forbidden,
        ),
        GoldenQuestion(
            "Welche Tasks sind ueberfaellig?",
            ("task",),
            (("task", str(ids["task_overdue"])),),
            forbidden_sources=forbidden,
        ),
        GoldenQuestion(
            f"Zeige Task #{ids['task_today']} fuer Golden Sonderpruefung.",
            ("task",),
            (("task", str(ids["task_today"])),),
            forbidden_sources=forbidden,
        ),
        GoldenQuestion(
            "Was bedeutet Fehler E104?",
            ("error",),
            (("error", str(ids["error_e104"])),),
            forbidden_sources=forbidden,
        ),
        GoldenQuestion(
            "Welche Loesung gibt es fuer Fehler E104?",
            ("error", "knowledge"),
            (("error", str(ids["error_e104"])),),
            forbidden_sources=forbidden,
        ),
        GoldenQuestion(
            "Was ist die Ursache von Fehler X900 an Presse Golden 7?",
            ("error", "machine"),
            (("error", str(ids["error_x900"])), ("machine", str(ids["machine"]))),
            min_source_count=2,
            forbidden_sources=forbidden,
        ),
        GoldenQuestion(
            "Welche Fehler sind an Presse Golden 7 bekannt?",
            ("error", "machine"),
            (("error", str(ids["error_e104"])), ("machine", str(ids["machine"]))),
            min_source_count=2,
            forbidden_sources=forbidden,
        ),
        GoldenQuestion(
            "Wie behebe ich Hydraulikdruckverlust?",
            ("knowledge",),
            (("knowledge", str(ids["knowledge_hydraulic"])),),
            forbidden_sources=forbidden,
        ),
        GoldenQuestion(
            "Welche Maschine ist kritisch?",
            ("machine",),
            (("machine", str(ids["machine"])),),
            forbidden_sources=forbidden,
        ),
        GoldenQuestion(
            "Wie ist der Maschinenstatus von Maschine Presse Golden 7?",
            ("machine",),
            (("machine", str(ids["machine"])),),
            forbidden_sources=forbidden,
        ),
        GoldenQuestion(
            "Welche Maschine braucht Golden Hydraulikpruefung Wartung?",
            ("machine",),
            (("machine", str(ids["machine"])),),
            forbidden_sources=forbidden,
        ),
        GoldenQuestion(
            "Welche Materialien sind kritisch?",
            ("inventory",),
            (("inventory", str(ids["material_filter"])),),
            forbidden_sources=forbidden,
        ),
        GoldenQuestion(
            "Welche Ersatzteile sind unter Mindestbestand?",
            ("inventory",),
            (("inventory", str(ids["material_filter"])),),
            forbidden_sources=forbidden,
        ),
        GoldenQuestion(
            "Welche Materialien gehoeren zu Presse Golden 7?",
            ("inventory", "machine"),
            (("inventory", str(ids["material_filter"])), ("machine", str(ids["machine"]))),
            min_source_count=2,
            forbidden_sources=forbidden,
        ),
        GoldenQuestion(
            "Welche Wartungen Golden Hydraulikpruefung sind faellig?",
            ("knowledge",),
            (("knowledge", str(ids["knowledge_training"])),),
            forbidden_sources=forbidden,
        ),
        GoldenQuestion(
            "Welche Wartung Golden Hydraulikpruefung ist fuer Presse Golden 7 geplant?",
            ("knowledge",),
            (("knowledge", str(ids["knowledge_training"])),),
            forbidden_sources=forbidden,
        ),
        GoldenQuestion(
            "Wann ist die Golden Hydraulikpruefung faellig?",
            ("knowledge",),
            (("knowledge", str(ids["knowledge_training"])),),
            forbidden_sources=forbidden,
        ),
        GoldenQuestion(
            "Welche Anleitung beschreibt Hydraulikdruckverlust?",
            ("knowledge",),
            (("knowledge", str(ids["knowledge_hydraulic"])),),
            forbidden_sources=forbidden,
        ),
        GoldenQuestion(
            "Was steht im Handbuch zu Sensorabgleich E104?",
            ("knowledge",),
            (("knowledge", str(ids["knowledge_e104"])),),
            forbidden_sources=forbidden,
        ),
        GoldenQuestion(
            "Welche Dokumentation hilft bei X900?",
            ("document", "error"),
            (("document", str(ids["document"])), ("error", str(ids["error_x900"]))),
            min_source_count=2,
            forbidden_sources=forbidden,
        ),
        GoldenQuestion(
            "Welche Trainingsantwort gibt es zur Hydraulikpruefung?",
            ("knowledge",),
            (("knowledge", str(ids["knowledge_training"])),),
            forbidden_sources=forbidden,
        ),
        GoldenQuestion(
            "Was war zur Presse Golden 7 in der letzten Schichtuebergabe offen?",
            ("shift_handover", "machine"),
            (("shift_handover", str(ids["handover"])), ("machine", str(ids["machine"]))),
            min_source_count=2,
            forbidden_sources=forbidden,
        ),
        GoldenQuestion(
            "Welche Quellen helfen bei Fehler E104 und offener Aufgabe?",
            ("error", "task"),
            (("error", str(ids["error_e104"])), ("task", str(ids["task_today"]))),
            min_source_count=2,
            forbidden_sources=forbidden,
        ),
        GoldenQuestion(
            "Welche Maschine hat offene Aufgaben und passende Fehlerdokumentation?",
            ("machine", "task", "error"),
            (
                ("machine", str(ids["machine"])),
                ("task", str(ids["task_today"])),
                ("error", str(ids["error_e104"])),
            ),
            min_source_count=3,
            forbidden_sources=forbidden,
        ),
    )


def _error_entry(
    machine,
    code,
    title,
    description,
    solution,
    user,
    department_name="Produktion",
):
    """Create one deterministic error catalog entry."""
    department = user.department
    if department_name != user.department.name:
        from app.models import Department

        department = Department.query.filter_by(name=department_name).first()
        if not department:
            department = Department(name=department_name)
            db.session.add(department)
            db.session.flush()
    entry = ErrorEntry(
        machine=machine,
        error_code=code,
        title=title,
        description=description,
        possible_causes=f"Ursache fuer {code}",
        solution=solution,
        department=department,
    )
    db.session.add(entry)
    db.session.flush()
    return entry


def _knowledge_document(
    title,
    text,
    user,
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
        created_by=user.id,
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
        )
    )
    db.session.flush()
    return document


def _source_keys(sources):
    """Return stable type/id pairs from API source payloads."""
    return {
        (str(source.get("type") or ""), str(source.get("id") or ""))
        for source in sources
    }


def _source_types(sources):
    """Return source types from API source payloads."""
    return {str(source.get("type") or "") for source in sources}

"""Reusable golden question definitions for AI retrieval quality checks."""

from dataclasses import dataclass, field
from datetime import date

from app.models import (
    Employee,
    ErrorEntry,
    GeneratedDocument,
    InventoryMaterial,
    KnowledgeDocument,
    Machine,
    MachineManual,
    MaintenancePlan,
    ShiftHandover,
    Task,
    TaskStatus,
)

GOLDEN_ALLOWED_SOURCE_TYPES = (
    "document",
    "employee",
    "error",
    "inventory",
    "knowledge",
    "machine",
    "machine_manual",
    "maintenance_plan",
    "manual_training",
    "shift_handover",
    "task",
)
REQUIRED_GOLDEN_CATEGORIES = {
    "Tasks",
    "Fehler",
    "Maschinen",
    "Materialien",
    "Wartungen",
    "Dokumente",
    "Mitarbeiter",
    "Schichtuebergaben",
}
DEFAULT_GOLDEN_TOP_K = 8


@dataclass(frozen=True)
class GoldenQuestion:
    """Describe one fixed AI retrieval question and its source expectations."""

    question: str
    expected_source_types: tuple[str, ...]
    expected_sources: tuple[tuple[str, str], ...] = ()
    expected_keywords: tuple[str, ...] = ()
    allowed_source_types: tuple[str, ...] = ()
    min_source_count: int = 1
    forbidden_sources: tuple[tuple[str, str], ...] = ()
    expected_no_result: bool = False
    required_permission_context: dict = field(default_factory=dict)
    expected_query_type: str = ""
    top_k: int = DEFAULT_GOLDEN_TOP_K


def build_golden_questions(source_ids):
    """Return the fixed AI retrieval golden question set."""
    ids = dict(source_ids or {})
    forbidden = tuple(
        source
        for source in (
            _source_pair("error", ids, "foreign_error"),
            _source_pair("knowledge", ids, "foreign_doc"),
        )
        if source
    )
    task_reference = ids.get("task_today") or 0
    return (
        GoldenQuestion(
            "Welche Tasks sind heute offen?",
            ("task",),
            _source_pairs(("task", "task_today"), ids=ids),
            forbidden_sources=forbidden,
            expected_query_type="task_question",
        ),
        GoldenQuestion(
            "Welche offenen Aufgaben gibt es heute an Presse Golden 7?",
            ("task",),
            _source_pairs(("task", "task_today"), ids=ids),
            forbidden_sources=forbidden,
        ),
        GoldenQuestion(
            "Welche Maschine hat offene Aufgaben?",
            ("machine", "task"),
            _source_pairs(("machine", "machine"), ("task", "task_today"), ids=ids),
            min_source_count=2,
            forbidden_sources=forbidden,
        ),
        GoldenQuestion(
            "Welche Tasks sind ueberfaellig?",
            ("task",),
            _source_pairs(("task", "task_overdue"), ids=ids),
            forbidden_sources=forbidden,
        ),
        GoldenQuestion(
            f"Zeige Task #{task_reference} fuer Golden Sonderpruefung.",
            ("task",),
            _source_pairs(("task", "task_today"), ids=ids),
            forbidden_sources=forbidden,
        ),
        GoldenQuestion(
            "Was bedeutet Fehler E104?",
            ("error",),
            _source_pairs(("error", "error_e104"), ids=ids),
            forbidden_sources=forbidden,
            expected_query_type="error_analysis",
        ),
        GoldenQuestion(
            "Welche Loesung gibt es fuer Fehler E104?",
            ("error", "knowledge"),
            _source_pairs(("error", "error_e104"), ids=ids),
            forbidden_sources=forbidden,
        ),
        GoldenQuestion(
            "Was ist die Ursache von Fehler X900 an Presse Golden 7?",
            ("error", "machine"),
            _source_pairs(("error", "error_x900"), ("machine", "machine"), ids=ids),
            min_source_count=2,
            forbidden_sources=forbidden,
        ),
        GoldenQuestion(
            "Welche Fehler sind an Presse Golden 7 bekannt?",
            ("error", "machine"),
            _source_pairs(("error", "error_e104"), ("machine", "machine"), ids=ids),
            min_source_count=2,
            forbidden_sources=forbidden,
        ),
        GoldenQuestion(
            "Wie behebe ich Hydraulikdruckverlust?",
            ("knowledge",),
            _source_pairs(("knowledge", "knowledge_hydraulic"), ids=ids),
            expected_keywords=("Hydraulikdruckverlust",),
            forbidden_sources=forbidden,
        ),
        GoldenQuestion(
            "Welche Maschine ist kritisch?",
            ("machine",),
            _source_pairs(("machine", "machine"), ids=ids),
            forbidden_sources=forbidden,
            expected_query_type="machine_question",
        ),
        GoldenQuestion(
            "Wie ist der Maschinenstatus von Maschine Presse Golden 7?",
            ("machine",),
            _source_pairs(("machine", "machine"), ids=ids),
            forbidden_sources=forbidden,
        ),
        GoldenQuestion(
            "Welche Maschine braucht Golden Hydraulikpruefung Wartung?",
            ("machine",),
            _source_pairs(("machine", "machine"), ids=ids),
            forbidden_sources=forbidden,
        ),
        GoldenQuestion(
            "Welche Materialien sind kritisch?",
            ("inventory",),
            _source_pairs(("inventory", "material_filter"), ids=ids),
            forbidden_sources=forbidden,
            expected_query_type="inventory_question",
        ),
        GoldenQuestion(
            "Welche Ersatzteile sind unter Mindestbestand?",
            ("inventory",),
            _source_pairs(("inventory", "material_filter"), ids=ids),
            forbidden_sources=forbidden,
        ),
        GoldenQuestion(
            "Welche Materialien gehoeren zu Presse Golden 7?",
            ("inventory", "machine"),
            _source_pairs(("inventory", "material_filter"), ("machine", "machine"), ids=ids),
            min_source_count=2,
            forbidden_sources=forbidden,
        ),
        *_employee_golden_questions(ids, forbidden),
        GoldenQuestion(
            "Welche Wartungen Golden Hydraulikpruefung sind faellig?",
            ("knowledge",),
            _source_pairs(("knowledge", "knowledge_training"), ids=ids),
            forbidden_sources=forbidden,
        ),
        GoldenQuestion(
            "Welche Wartung Golden Hydraulikpruefung ist fuer Presse Golden 7 geplant?",
            ("knowledge",),
            _source_pairs(("knowledge", "knowledge_training"), ids=ids),
            forbidden_sources=forbidden,
        ),
        GoldenQuestion(
            "Wann ist die Golden Hydraulikpruefung faellig?",
            ("knowledge",),
            _source_pairs(("knowledge", "knowledge_training"), ids=ids),
            forbidden_sources=forbidden,
        ),
        GoldenQuestion(
            "Welche Anleitung beschreibt Hydraulikdruckverlust?",
            ("knowledge",),
            _source_pairs(("knowledge", "knowledge_hydraulic"), ids=ids),
            forbidden_sources=forbidden,
        ),
        GoldenQuestion(
            "Was steht im Handbuch zu Sensorabgleich E104?",
            ("knowledge",),
            _source_pairs(("knowledge", "knowledge_e104"), ids=ids),
            expected_keywords=("Sensorabgleich", "E104"),
            forbidden_sources=forbidden,
            expected_query_type="document_question",
        ),
        GoldenQuestion(
            "Welche Dokumentation hilft bei X900?",
            ("document", "error"),
            _source_pairs(("document", "document"), ("error", "error_x900"), ids=ids),
            min_source_count=2,
            forbidden_sources=forbidden,
        ),
        GoldenQuestion(
            "Welche Trainingsantwort gibt es zur Hydraulikpruefung?",
            ("knowledge",),
            _source_pairs(("knowledge", "knowledge_training"), ids=ids),
            forbidden_sources=forbidden,
        ),
        GoldenQuestion(
            "Was war zur Presse Golden 7 in der letzten Schichtuebergabe offen?",
            ("shift_handover", "machine"),
            _source_pairs(("shift_handover", "handover"), ("machine", "machine"), ids=ids),
            expected_keywords=("Hydraulikpruefung", "Sensorabgleich"),
            min_source_count=2,
            forbidden_sources=forbidden,
            expected_query_type="trend_history_question",
        ),
        GoldenQuestion(
            "Welche Quellen helfen bei Fehler E104 und offener Aufgabe?",
            ("error", "task"),
            _source_pairs(("error", "error_e104"), ("task", "task_today"), ids=ids),
            min_source_count=2,
            forbidden_sources=forbidden,
        ),
        GoldenQuestion(
            "Welche Maschine hat offene Aufgaben und passende Fehlerdokumentation?",
            ("machine", "task", "error"),
            _source_pairs(
                ("machine", "machine"),
                ("task", "task_today"),
                ("error", "error_e104"),
                ids=ids,
            ),
            min_source_count=3,
            forbidden_sources=forbidden,
        ),
    )


def build_demo_golden_questions(source_ids):
    """Return a compact golden set for the seeded demo database."""
    ids = dict(source_ids or {})
    return tuple(
        question
        for question in (
            GoldenQuestion(
                "Welche dringenden Aufgaben sind heute offen?",
                ("task",),
                _source_pairs(("task", "task_hydraulic"), ids=ids),
                expected_query_type="task_question",
            ),
            GoldenQuestion(
                "Welche Aufgabe ist an Hydraulikpresse 03 gerade dringend?",
                ("task", "machine"),
                _source_pairs(("task", "task_hydraulic"), ("machine", "hydraulic"), ids=ids),
                min_source_count=2,
            ),
            GoldenQuestion(
                "Was bedeutet Fehler INS-E-103?",
                ("error",),
                _source_pairs(("error", "ins_e_103"), ids=ids),
                expected_query_type="error_analysis",
            ),
            GoldenQuestion(
                "Welche Loesung gibt es fuer Druck faellt ab an Hydraulikpresse 03?",
                ("error", "machine"),
                _source_pairs(("error", "ins_e_103"), ("machine", "hydraulic"), ids=ids),
                min_source_count=2,
            ),
            GoldenQuestion(
                "Welche Materialien sind bei Hydraulikpresse 03 unter Mindestbestand?",
                ("inventory",),
                _source_pairs(("inventory", "seal_kit"), ids=ids),
                expected_query_type="inventory_question",
            ),
            GoldenQuestion(
                "Welche Maschine hat aktuell offene oder laufende dringende Aufgaben?",
                ("task", "machine"),
                _source_pairs(("task", "task_hydraulic"), ("machine", "hydraulic"), ids=ids),
                min_source_count=2,
            ),
            GoldenQuestion(
                "Was ist bei Not-Halt-Kreis offen zu pruefen?",
                ("error",),
                _source_pairs(("error", "ins_e_106"), ids=ids),
            ),
            GoldenQuestion(
                "Welche Wartungsplaene sind an Hydraulikpresse 03 relevant?",
                ("maintenance_plan", "machine"),
                _source_pairs(("maintenance_plan", "hydraulic_plan"), ids=ids),
            ),
            GoldenQuestion(
                "Was steht im Manual zur Hydraulikpresse 03 bei Druckverlust?",
                ("knowledge",),
                _source_pairs(("knowledge", "hydraulic_manual_doc"), ids=ids),
                expected_keywords=("Hydraulikpresse", "Druckverlust"),
                expected_query_type="document_question",
            ),
            GoldenQuestion(
                "Was wurde in der letzten Schicht zu Spritzgussanlage 04 gemeldet?",
                ("shift_handover",),
                _source_pairs(("shift_handover", "spritz_handover"), ids=ids),
                expected_keywords=("Spritzgussanlage", "Schicht"),
                expected_query_type="trend_history_question",
            ),
            GoldenQuestion(
                "Welche Ersatzteile blockieren Wartung an Hydraulikpresse 03?",
                ("inventory", "manual_training"),
                _source_pairs(("inventory", "seal_kit"), ("inventory", "oring"), ids=ids),
                min_source_count=2,
            ),
            GoldenQuestion(
                "Wie loese ich Hydraulikdruckverlust an Hydraulikpresse 03?",
                ("knowledge", "error"),
                _source_pairs(
                    ("knowledge", "hydraulic_training_doc"),
                    ("error", "ins_e_103"),
                    ids=ids,
                ),
                expected_keywords=("Hydraulikdruckverlust", "Hydraulikpresse"),
                min_source_count=2,
            ),
        )
        if question.expected_sources
    )


def runtime_golden_questions(user=None, limit=20):
    """Return golden questions resolvable against the current database."""
    source_ids = resolve_golden_source_ids()
    questions = build_golden_questions(source_ids) if _has_canonical_sources(source_ids) else ()
    question_set = "canonical"
    if not questions:
        source_ids = resolve_demo_source_ids(user)
        questions = build_demo_golden_questions(source_ids)
        question_set = "demo"
    return {
        "question_set": question_set,
        "source_ids": source_ids,
        "questions": tuple(questions[: _positive_int(limit, 20)]),
    }


def golden_categories(case):
    """Return coverage categories represented by one golden question."""
    categories = set()
    source_types = set(case.expected_source_types)
    question = case.question.lower()
    if "task" in source_types:
        categories.add("Tasks")
    if "error" in source_types:
        categories.add("Fehler")
    if "machine" in source_types:
        categories.add("Maschinen")
    if "inventory" in source_types:
        categories.add("Materialien")
    if "maintenance_plan" in source_types or "wartung" in question:
        categories.add("Wartungen")
    if source_types & {"document", "machine_manual", "manual_training"} or any(
        keyword in question for keyword in ("dokument", "handbuch", "anleitung")
    ):
        categories.add("Dokumente")
    if "employee" in source_types or any(
        keyword in question for keyword in ("mitarbeiter", "personal", "qualifikation")
    ):
        categories.add("Mitarbeiter")
    if "shift_handover" in source_types or "schichtuebergabe" in question:
        categories.add("Schichtuebergaben")
    return categories


def allowed_source_types(case):
    """Return allowed public source types for one golden question."""
    if case.allowed_source_types:
        return set(case.allowed_source_types)
    return set(GOLDEN_ALLOWED_SOURCE_TYPES)


def dummy_source_ids():
    """Return deterministic ids for golden question structure tests."""
    return {
        "task_today": 101,
        "task_overdue": 102,
        "task_done": 103,
        "error_e104": 201,
        "error_x900": 202,
        "foreign_error": 203,
        "machine": 301,
        "normal_machine": 302,
        "material_filter": 401,
        "material_sensor": 402,
        "employee_hydraulic": 451,
        "plan": 501,
        "document": 601,
        "manual": 701,
        "training": 801,
        "handover": 901,
        "knowledge_hydraulic": 1001,
        "knowledge_e104": 1002,
        "knowledge_training": 1003,
        "foreign_doc": 1004,
    }


def resolve_golden_source_ids():
    """Return ids for deterministic canonical golden fixture records, if present."""
    machine = Machine.query.filter_by(name="Presse Golden 7").first()
    normal_machine = Machine.query.filter_by(name="Presse Golden 8").first()
    return {
        "task_today": _id(Task.query.filter_by(title="Golden offene Hydraulikpruefung").first()),
        "task_overdue": _id(
            Task.query.filter_by(title="Golden ueberfaellige Sensorpruefung").first()
        ),
        "task_done": _id(Task.query.filter_by(title="Golden abgeschlossene Gegenprobe").first()),
        "error_e104": _id(
            ErrorEntry.query.filter_by(error_code="E104", machine="Presse Golden 7").first()
        ),
        "error_x900": _id(
            ErrorEntry.query.filter_by(error_code="X900", machine="Presse Golden 7").first()
        ),
        "foreign_error": _id(ErrorEntry.query.filter_by(error_code="FG999").first()),
        "machine": _id(machine),
        "normal_machine": _id(normal_machine),
        "material_filter": _id(
            InventoryMaterial.query.filter_by(name="Golden Hydraulikfilter").first()
        ),
        "material_sensor": _id(
            InventoryMaterial.query.filter_by(name="Golden E104 Sensorsatz").first()
        ),
        "employee_hydraulic": _id(
            Employee.query.filter_by(name="Golden Hydraulikerin Mila").first()
        ),
        "plan": _id(
            MaintenancePlan.query.filter_by(title="Golden Hydraulikpruefung faellig").first()
        ),
        "document": _id(
            GeneratedDocument.query.filter_by(title="Golden Dokumentation X900").first()
        ),
        "manual": _id(
            MachineManual.query.filter_by(title="Golden Handbuch Sensorabgleich E104").first()
        ),
        "training": _source_record_id(
            KnowledgeDocument.query.filter_by(
                title="Golden Trainingsantwort Hydraulikpruefung",
                source_type="manual_training",
            ).first()
        ),
        "handover": _id(
            ShiftHandover.query.filter(
                ShiftHandover.machine_notes.ilike("%Presse Golden 7%")
            ).first()
        ),
        "knowledge_hydraulic": _id(
            KnowledgeDocument.query.filter_by(
                title="Golden Anleitung Hydraulikdruckverlust"
            ).first()
        ),
        "knowledge_e104": _id(
            KnowledgeDocument.query.filter_by(title="Golden Sensorabgleich E104 Wissen").first()
        ),
        "knowledge_training": _id(
            KnowledgeDocument.query.filter_by(
                title="Golden Trainingsantwort Hydraulikpruefung"
            ).first()
        ),
        "foreign_doc": _id(
            KnowledgeDocument.query.filter_by(title="Golden Fremdquelle Instandhaltung").first()
        ),
    }


def resolve_demo_source_ids(user=None):
    """Return ids for seeded demo records used by admin golden evaluations."""
    today = date.today()
    hydraulic = Machine.query.filter_by(name="Hydraulikpresse 03").first()
    spritz = Machine.query.filter_by(name="Spritzgussanlage 04").first()
    return {
        "hydraulic": _id(hydraulic),
        "spritz": _id(spritz),
        "task_hydraulic": _id(
            Task.query.filter(Task.title.ilike("%Hydraulikpresse 03%"))
            .filter(Task.status.in_([TaskStatus.OPEN, TaskStatus.IN_PROGRESS]))
            .order_by(Task.due_date.asc(), Task.id.asc())
            .first()
        ),
        "task_spritz": _id(
            Task.query.filter(Task.title.ilike("%Spritzgussanlage 04%"))
            .filter(Task.status.in_([TaskStatus.OPEN, TaskStatus.IN_PROGRESS]))
            .order_by(Task.due_date.asc(), Task.id.asc())
            .first()
        ),
        "ins_e_103": _id(ErrorEntry.query.filter_by(error_code="INS-E-103").first()),
        "ins_e_106": _id(ErrorEntry.query.filter_by(error_code="INS-E-106").first()),
        "seal_kit": _id(InventoryMaterial.query.filter_by(name="Dichtungssatz Presse").first()),
        "oring": _id(InventoryMaterial.query.filter_by(name="O-Ring-Satz 120-teilig").first()),
        "hydraulic_plan": _id(
            MaintenancePlan.query.filter(
                MaintenancePlan.title.ilike("%Hydraulikpresse 03%")
            ).first()
        ),
        "hydraulic_manual_doc": _id(
            KnowledgeDocument.query.filter(
                KnowledgeDocument.title.ilike("%Hydraulikpresse 03%")
            ).first()
        ),
        "hydraulic_training_doc": _id(
            KnowledgeDocument.query.filter(
                KnowledgeDocument.title.ilike("%Hydraulikdruckverlust%")
            ).first()
        ),
        "spritz_handover": _id(
            ShiftHandover.query.filter(ShiftHandover.shift_date <= today)
            .filter(ShiftHandover.machine_notes.ilike("%Spritzgussanlage 04%"))
            .order_by(ShiftHandover.shift_date.desc(), ShiftHandover.id.desc())
            .first()
        ),
    }


def _source_pairs(*definitions, ids):
    """Return existing type/id pairs for source-id definitions."""
    return tuple(
        source
        for source in (_source_pair(source_type, ids, key) for source_type, key in definitions)
        if source
    )


def _source_pair(source_type, ids, key):
    """Return one public source pair when the referenced id is available."""
    value = ids.get(key)
    if value in (None, "", 0):
        return ()
    return (source_type, str(value))


def _employee_golden_questions(ids, forbidden):
    """Return employee golden questions when a visible fixture employee exists."""
    sources = _source_pairs(("employee", "employee_hydraulic"), ids=ids)
    if not sources:
        return ()
    return (
        GoldenQuestion(
            "Welche Mitarbeiter haben Golden Hydraulikqualifikation?",
            ("employee",),
            sources,
            expected_keywords=("Hydraulikqualifikation",),
            forbidden_sources=forbidden,
            required_permission_context={
                "requires_dashboards": ("employees",),
            },
        ),
    )


def _has_canonical_sources(source_ids):
    """Return whether enough canonical fixture ids are present for evaluation."""
    required = ("task_today", "error_e104", "machine", "material_filter", "knowledge_hydraulic")
    return all(source_ids.get(key) for key in required)


def _id(record):
    """Return a record id or zero when no record exists."""
    return int(getattr(record, "id", 0) or 0)


def _source_record_id(record):
    """Return a knowledge document source record id or zero."""
    return int(getattr(record, "source_id", 0) or 0)


def _positive_int(value, default):
    """Return a positive integer or a fallback default."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default

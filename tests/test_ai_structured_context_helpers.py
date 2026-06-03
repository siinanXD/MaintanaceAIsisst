"""Tests for shared structured AI context helpers."""

from app.services.ai_structured_context_helpers import (
    build_structured_context,
    should_defer_structured_scope_follow_up,
)
from app.services.conversation_context_service import ConversationContext


def test_build_structured_context_keeps_supported_fields():
    """Verify structured context payloads stay compact and field-safe."""
    context = build_structured_context(
        "inventory",
        query="inventory_low_stock",
        machine="Hydraulikpresse 03",
        department="Instandhaltung",
    )
    assert context == {
        "entity_type": "inventory",
        "department": "Instandhaltung",
        "machine": "Hydraulikpresse 03",
        "query": "inventory_low_stock",
    }


def test_should_defer_structured_scope_follow_up_for_domain_context():
    """Verify task routing defers when prior context belongs to another domain."""
    context = ConversationContext(
        session_id="inventory-followup",
        reference_detected=True,
        structured_scope={
            "entity_type": "inventory",
            "query": "inventory_low_stock",
        },
    )
    assert should_defer_structured_scope_follow_up("Welche davon?", context) is True

    task_context = ConversationContext(
        session_id="task-followup",
        reference_detected=True,
        structured_scope={"entity_type": "tasks", "status": "open"},
    )
    assert should_defer_structured_scope_follow_up("Welche davon?", task_context) is False

    explicit_task = ConversationContext(
        session_id="inventory-explicit-task",
        reference_detected=True,
        structured_scope={"entity_type": "inventory", "query": "inventory_low_stock"},
    )
    assert (
        should_defer_structured_scope_follow_up(
            "Welche offenen Tasks davon?",
            explicit_task,
        )
        is False
    )

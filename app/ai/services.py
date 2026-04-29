import re
from datetime import date

from flask import current_app

from app.errors.services import search_errors
from app.extensions import db
from app.models import ChatMessage, ErrorEntry, Task
from app.tasks.services import visible_tasks_query


def looks_like_today_tasks_question(message):
    """Check whether a message asks for today's visible tasks."""
    text = message.lower()
    task_words = ["task", "tasks", "aufgabe", "aufgaben"]
    today_words = ["heute", "today", "anstehend"]
    return any(word in text for word in task_words) and any(word in text for word in today_words)


def extract_error_query(message):
    """Extract a likely error code or machine reference from a user message."""
    code_match = re.search(r"\b[A-Z]?\d{2,5}\b", message.upper())
    if code_match:
        return code_match.group(0)

    machine_match = re.search(r"(maschine|machine)\s+[\w-]+", message, re.IGNORECASE)
    if machine_match:
        return machine_match.group(0)
    return message


def format_tasks_today(user):
    """Return a formatted answer and structured data for today's visible tasks."""
    tasks = (
        visible_tasks_query(user)
        .filter(Task.due_date == date.today())
        .order_by(Task.priority.asc(), Task.id.desc())
        .all()
    )
    if not tasks:
        return "Für heute sind keine Tasks in deinem Bereich eingetragen.", []

    lines = ["Heute stehen diese Tasks an:"]
    for task in tasks:
        lines.append(
            f"- {task.title} ({task.priority.value}, {task.status.value}, Bereich: {task.department.name})"
        )
    return "\n".join(lines), [task.to_dict() for task in tasks]


def build_error_context(entries):
    """Build a text context block from matching error catalog entries."""
    if not entries:
        return ""
    blocks = []
    for entry in entries:
        blocks.append(
            "\n".join(
                [
                    f"Maschine: {entry.machine}",
                    f"Fehlercode: {entry.error_code}",
                    f"Titel: {entry.title}",
                    f"Beschreibung: {entry.description}",
                    f"Mögliche Ursachen: {entry.possible_causes}",
                    f"Lösung: {entry.solution}",
                    f"Bereich: {entry.department.name}",
                ]
            )
        )
    return "\n\n".join(blocks)


def build_task_context(user):
    """Build a text context block from the user's visible tasks."""
    tasks = visible_tasks_query(user).order_by(Task.due_date.asc(), Task.id.desc()).limit(20).all()
    if not tasks:
        return "Keine sichtbaren Tasks vorhanden."
    lines = []
    for task in tasks:
        lines.append(
            " | ".join(
                [
                    f"Titel: {task.title}",
                    f"Status: {task.status.value}",
                    f"Prioritaet: {task.priority.value}",
                    f"Faellig: {task.due_date.isoformat()}",
                    f"Bereich: {task.department.name}",
                    f"Beschreibung: {task.description}",
                ]
            )
        )
    return "\n".join(lines)


def build_catalog_context(user, preferred_entries):
    """Build a combined error catalog context for the AI assistant."""
    entries = list(preferred_entries)
    seen = {entry.id for entry in entries}
    query = ErrorEntry.query
    if not user.is_admin:
        query = query.filter(ErrorEntry.department_id == user.department_id)
    for entry in query.order_by(ErrorEntry.created_at.desc()).limit(20).all():
        if entry.id not in seen:
            entries.append(entry)
            seen.add(entry.id)
    return build_error_context(entries) or "Keine sichtbaren Fehlerkatalogeintraege vorhanden."


def fallback_error_answer(entries):
    """Return a local fallback answer when no OpenAI response is available."""
    if not entries:
        return (
            "Ich habe dazu keinen passenden Eintrag im Fehlerkatalog gefunden. "
            "Lege den Fehler im Katalog an, wenn ihr die Ursache geklärt habt."
        )

    entry = entries[0]
    return (
        f"Der Fehler {entry.error_code} an {entry.machine} passt zu: {entry.title}.\n\n"
        f"Mögliche Ursachen: {entry.possible_causes or 'keine Ursachen hinterlegt'}\n"
        f"Empfohlene Prüfung: {entry.solution or 'keine Lösung hinterlegt'}"
    )


def openai_error_answer(message, error_context, task_context):
    """Generate an AI answer using OpenAI and the provided maintenance context."""
    api_key = current_app.config.get("OPENAI_API_KEY")
    if not api_key:
        return None

    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    completion = client.chat.completions.create(
        model=current_app.config.get("OPENAI_MODEL", "gpt-4o-mini"),
        messages=[
            {
                "role": "system",
                "content": (
                    "Du bist ein Wartungsassistent. Nutze ausschließlich den "
                    "bereitgestellten Fehlerkatalog und die sichtbaren Tasks. "
                    "Wenn etwas nicht im Kontext steht, sage das klar."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Fehlerkatalog:\n{error_context}\n\n"
                    f"Tasks:\n{task_context}\n\n"
                    f"Frage:\n{message}"
                ),
            },
        ],
        temperature=0.2,
    )
    return completion.choices[0].message.content


def answer_chat(message, user):
    """Route the user message to the correct assistant behavior."""
    if looks_like_today_tasks_question(message):
        answer, data = format_tasks_today(user)
        return {"type": "tasks_today", "answer": answer, "data": data}

    entries = search_errors(extract_error_query(message), user)
    error_context = build_catalog_context(user, entries)
    task_context = build_task_context(user)
    answer = openai_error_answer(message, error_context, task_context) or fallback_error_answer(entries)
    return {
        "type": "error_help",
        "answer": answer,
        "data": [entry.to_dict() for entry in entries],
    }


def save_chat_message(user, message, response):
    """Persist a chat message and its assistant response in the database."""
    chat = ChatMessage(user_id=user.id, message=message, response=response)
    db.session.add(chat)
    db.session.commit()

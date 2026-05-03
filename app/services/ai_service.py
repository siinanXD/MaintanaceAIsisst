import json
import logging
import re
from abc import ABC, abstractmethod
from datetime import date

from flask import current_app
from openai import OpenAI, OpenAIError


logger = logging.getLogger(__name__)


class AIServiceError(Exception):
    """Raised when an AI provider cannot return a usable result."""


class BaseAIProvider(ABC):
    """Define the provider contract for AI-assisted workflows."""

    name = "base"

    @abstractmethod
    def suggest_task(self, text, user_context=None):
        """Return a structured task suggestion for free text."""

    @abstractmethod
    def analyze_error(self, text, user_context=None):
        """Return a structured error analysis for free text."""

    @abstractmethod
    def generate_document_text(self, data):
        """Return generated maintenance report text."""

    @abstractmethod
    def answer_question(self, question, context):
        """Return a natural-language answer for a question and context."""

    @abstractmethod
    def prioritize_tasks(self, tasks, context=None):
        """Return structured prioritization results for visible tasks."""

    @abstractmethod
    def review_document(self, html_text, metadata=None):
        """Return a structured quality review for a maintenance document."""

    @abstractmethod
    def error_assistant_query(self, query, matches):
        """Return AI-enhanced causes and fixes for a fault description.

        Args:
            query:   The raw user fault description string.
            matches: List of similarity-scored catalog match dicts already
                     found by the local search.  Each dict has keys
                     ``entry``, ``score``, and ``reason``.

        Returns:
            dict with keys ``causes`` (list[str]), ``fixes`` (list[str]),
            and optionally ``summary`` (str) — or ``None`` to skip
            enhancement and keep local results unchanged.
        """


class MockAIProvider(BaseAIProvider):
    """Provide deterministic local AI-like results without external services."""

    name = "mock"

    def suggest_task(self, text, user_context=None):
        """Return a deterministic task suggestion from free text."""
        department = _department_from_text(text, user_context)
        priority = "urgent" if _contains_any(text, ["not-halt", "stillstand"]) else "soon"
        machine = _extract_machine(text)
        title = _short_title(text, prefix="Pruefung")
        return {
            "title": title,
            "description": text.strip(),
            "department": department,
            "priority": priority,
            "status": "open",
            "possible_cause": _cause_from_text(text),
            "recommended_action": (
                f"{machine} sicher pruefen, Befund dokumentieren und "
                "bei Bedarf Instandhaltung informieren."
            ),
        }

    def analyze_error(self, text, user_context=None):
        """Return a deterministic error analysis from free text."""
        machine = _extract_machine(text)
        return {
            "machine": machine,
            "title": _short_title(text, prefix="Stoerung"),
            "description": text.strip(),
            "possible_causes": _cause_from_text(text),
            "solution": (
                "Anlage sichern, Sichtpruefung durchfuehren, betroffene "
                "Komponenten pruefen und Ergebnis im Fehlerkatalog dokumentieren."
            ),
            "department": _department_from_text(text, user_context),
        }

    def generate_document_text(self, data):
        """Return a deterministic maintenance report text."""
        return (
            f"Wartungsbericht fuer Task {data.get('task_id')}: "
            f"{data.get('title')}. Ergebnis: {data.get('result') or 'erledigt'}."
        )

    def answer_question(self, question, context):
        """Return a cautious local answer for a question and context."""
        if not context.strip():
            return (
                "## Ergebnis\n"
                "- **Status:** Keine passende Grundlage gefunden\n"
                "- **Naechster Schritt:** Daten oder Suchbegriff pruefen"
            )
        return (
            "## Ergebnis\n"
            "- **Status:** Freigegebene Daten geprueft\n"
            "- **Hinweis:** Frage bitte konkreter nach Task, Fehler oder Mitarbeiterdaten"
        )

    def prioritize_tasks(self, tasks, context=None):
        """Return deterministic task priorities without external services."""
        priorities = [_score_task_priority(task) for task in tasks]
        return {"priorities": priorities}

    def review_document(self, html_text, metadata=None):
        """Return a simple placeholder document review for local mode."""
        return {
            "quality_score": 0,
            "status": "incomplete",
            "findings": [],
            "recommendations": [],
        }

    def error_assistant_query(self, query, matches):
        """Return None — local similarity results are sufficient in mock mode."""
        return None


class OpenAIProvider(BaseAIProvider):
    """Use OpenAI for AI-assisted workflows."""

    name = "openai"

    def __init__(self, api_key, model):
        """Initialize the OpenAI provider."""
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def suggest_task(self, text, user_context=None):
        """Return a structured task suggestion for free text."""
        prompt = {
            "task": "Generate a German maintenance task suggestion as JSON.",
            "input": text,
            "user_context": user_context or {},
            "schema": {
                "title": "string",
                "description": "string",
                "department": "string",
                "priority": "urgent|soon|normal",
                "status": "open",
                "possible_cause": "string",
                "recommended_action": "string",
            },
        }
        return self._json_completion(prompt)

    def analyze_error(self, text, user_context=None):
        """Return a structured error analysis for free text."""
        prompt = {
            "task": "Analyze a German machine fault and return JSON.",
            "input": text,
            "user_context": user_context or {},
            "schema": {
                "machine": "string",
                "title": "string",
                "description": "string",
                "possible_causes": "string",
                "solution": "string",
                "department": "string",
            },
        }
        return self._json_completion(prompt)

    def generate_document_text(self, data):
        """Return generated maintenance report text."""
        messages = [
            {
                "role": "system",
                "content": "Du formulierst kurze, sachliche Wartungsberichte.",
            },
            {
                "role": "user",
                "content": json.dumps(data, ensure_ascii=True),
            },
        ]
        return self._text_completion(messages)

    def answer_question(self, question, context):
        """Return a natural-language answer for a question and context."""
        messages = [
            {
                "role": "system",
                "content": (
                    "Du bist ein Wartungsassistent. Antworte nur anhand des "
                    "bereitgestellten Kontextes. Antworte auf Deutsch, kurz "
                    "und uebersichtlich. Nutze maximal eine kurze Markdown-"
                    "Ueberschrift und 3 bis 5 Bulletpoints. Markiere wichtige "
                    "Labels fett, zum Beispiel **Status:**. Nenne nur relevante "
                    "Daten und keine langen Erklaerungen. Keine Tabellen, keine "
                    "Einleitung, keine Wiederholung der Frage."
                ),
            },
            {
                "role": "user",
                "content": f"Kontext:\n{context}\n\nFrage:\n{question}",
            },
        ]
        return self._text_completion(messages)

    def prioritize_tasks(self, tasks, context=None):
        """Return AI-generated task priorities as structured JSON."""
        prompt = {
            "task": (
                "Priorisiere sichtbare Wartungsaufgaben auf Deutsch. Nutze nur "
                "die bereitgestellten Tasks und keine Mitarbeiterdaten."
            ),
            "tasks": tasks,
            "context": context or {},
            "schema": {
                "priorities": [
                    {
                        "task_id": "integer",
                        "score": "integer 0-100",
                        "risk_level": "low|medium|high|critical",
                        "reason": "short German reason",
                        "recommended_action": "short German next action",
                    }
                ]
            },
        }
        return self._json_completion(prompt)

    def error_assistant_query(self, query, matches):
        """Return AI-enhanced causes and fixes for a fault description."""
        prompt = {
            "task": (
                "Given a machine fault description and matching catalog entries, "
                "return concise German causes and fix instructions as JSON."
            ),
            "query": query,
            "catalog_matches": [m["entry"] for m in matches[:3]],
            "schema": {
                "causes": ["string — one German cause per item"],
                "fixes": ["string — one German fix instruction per item"],
                "summary": "string — one-sentence German summary of the fault",
            },
        }
        return self._json_completion(prompt)

    def review_document(self, html_text, metadata=None):
        """Return an AI-generated maintenance document quality review."""
        prompt = {
            "task": (
                "Pruefe einen deutschen Wartungsbericht als JSON. Bewerte, "
                "ob Maschine, Ursache, durchgefuehrte Massnahme, Ergebnis "
                "und Notizen vollstaendig und konkret sind."
            ),
            "metadata": metadata or {},
            "html_text": html_text[:12000],
            "schema": {
                "quality_score": "integer 0-100",
                "status": "good|needs_review|incomplete",
                "findings": [
                    {
                        "field": "string",
                        "severity": "info|warning|critical",
                        "message": "short German message",
                    }
                ],
                "recommendations": ["short German recommendation"],
            },
        }
        return self._json_completion(prompt)

    def _json_completion(self, prompt):
        """Call OpenAI and parse a JSON object response."""
        logger.info(
            "ai_call provider=%s model=%s mode=json task=%s",
            self.name,
            self.model,
            prompt.get("task", "unknown"),
        )
        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "Return only valid JSON without markdown.",
                    },
                    {
                        "role": "user",
                        "content": json.dumps(prompt, ensure_ascii=True),
                    },
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )
            return json.loads(completion.choices[0].message.content)
        except (OpenAIError, TypeError, json.JSONDecodeError) as exc:
            logger.exception(
                "ai_call_failed provider=%s model=%s mode=json",
                self.name,
                self.model,
            )
            raise AIServiceError("AI provider failed to return valid JSON") from exc

    def _text_completion(self, messages):
        """Call OpenAI and return text content."""
        logger.info(
            "ai_call provider=%s model=%s mode=text message_count=%s",
            self.name,
            self.model,
            len(messages),
        )
        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.2,
            )
            return completion.choices[0].message.content
        except OpenAIError as exc:
            logger.exception(
                "ai_call_failed provider=%s model=%s mode=text",
                self.name,
                self.model,
            )
            raise AIServiceError("AI provider failed to return text") from exc


def get_ai_provider():
    """Return the configured AI provider with mock fallback."""
    provider_name = current_app.config.get("AI_PROVIDER", "openai").lower()
    api_key = current_app.config.get("OPENAI_API_KEY", "")
    model = current_app.config.get("OPENAI_MODEL", "gpt-4o-mini")
    if provider_name == "mock":
        return MockAIProvider()
    if not api_key:
        logger.warning("ai_fallback provider=openai reason=api_key_missing")
        return MockAIProvider()
    if provider_name == "openai":
        return OpenAIProvider(api_key=api_key, model=model)
    return MockAIProvider()


def _contains_any(text, needles):
    """Return whether text contains any of the provided needles."""
    lowered = text.lower()
    return any(needle in lowered for needle in needles)


def _extract_machine(text):
    """Extract a simple machine label from free text."""
    match = re.search(r"(maschine|anlage)\s*[\w-]+", text, re.IGNORECASE)
    if match:
        return match.group(0).strip()
    return "Unbekannte Maschine"


def _department_from_text(text, user_context=None):
    """Infer a responsible department from text or user context."""
    lowered = text.lower()
    if _contains_any(lowered, ["lager", "geraeusch", "leck", "motor", "sensor"]):
        return "Instandhaltung"
    if user_context and user_context.get("department"):
        return user_context["department"]
    return "Produktion"


def _cause_from_text(text):
    """Infer a plausible cause from free text."""
    lowered = text.lower()
    if "sensor" in lowered:
        return "Sensor verschmutzt, falsch ausgerichtet oder Kabelverbindung gestoert."
    if "lager" in lowered or "geraeusch" in lowered:
        return "Lager verschlissen, Schmierung unzureichend oder mechanische Unwucht."
    if "leck" in lowered or "druck" in lowered:
        return "Leckage, Dichtung defekt oder Druckversorgung instabil."
    return "Ursache noch unklar; strukturierte Sichtpruefung erforderlich."


def _short_title(text, prefix):
    """Create a short German title from free text."""
    cleaned = " ".join(text.strip().split())
    if not cleaned:
        return f"{prefix} erforderlich"
    return f"{prefix}: {cleaned[:80]}"


def _score_task_priority(task):
    """Return a local priority score for a serialized task."""
    score = 0
    reasons = []
    text = f"{task.get('title', '')} {task.get('description', '')}".lower()

    priority_score, priority_reason = _priority_score(task.get("priority"))
    score += priority_score
    reasons.append(priority_reason)

    status_score, status_reason = _status_score(task.get("status"))
    score += status_score
    reasons.append(status_reason)

    due_score, due_reason = _due_date_score(task.get("due_date"))
    score += due_score
    if due_reason:
        reasons.append(due_reason)

    keyword_score, keyword_reason = _keyword_score(text)
    score += keyword_score
    if keyword_reason:
        reasons.append(keyword_reason)

    normalized_score = max(0, min(100, score))
    risk_level = _risk_level(normalized_score)
    return {
        "task_id": task.get("id"),
        "score": normalized_score,
        "risk_level": risk_level,
        "reason": "; ".join(reasons[:3]),
        "recommended_action": _recommended_priority_action(risk_level),
    }


def _priority_score(priority):
    """Return score contribution and reason for a task priority."""
    if priority == "urgent":
        return 45, "Prioritaet urgent"
    if priority == "soon":
        return 30, "Prioritaet soon"
    return 15, "Prioritaet normal"


def _status_score(status):
    """Return score contribution and reason for a task status."""
    if status == "in_progress":
        return 15, "Task ist bereits in Arbeit"
    if status == "open":
        return 10, "Task ist offen"
    return 0, f"Status {status or 'unbekannt'}"


def _due_date_score(due_date_value):
    """Return score contribution and reason for the due date."""
    if not due_date_value:
        return 0, ""
    try:
        days_until_due = (date.fromisoformat(due_date_value) - date.today()).days
    except ValueError:
        return 0, ""

    if days_until_due < 0:
        return 25, "Faelligkeit ist ueberfaellig"
    if days_until_due == 0:
        return 18, "Faelligkeit ist heute"
    if days_until_due <= 2:
        return 10, "Faelligkeit innerhalb von zwei Tagen"
    if days_until_due <= 7:
        return 5, "Faelligkeit innerhalb einer Woche"
    return 0, ""


def _keyword_score(text):
    """Return score contribution and reason for risk keywords."""
    keyword_groups = [
        (
            ["not-halt", "stillstand", "ausfall", "steht"],
            25,
            "kritischer Anlagenzustand",
        ),
        (["leck", "druck", "hydraulik", "pneumatik"], 18, "Leckage oder Druckproblem"),
        (["sensor", "lichttaster", "signal"], 12, "Sensorik betroffen"),
        (["lager", "geraeusch", "motor", "unwucht"], 10, "mechanische Symptome"),
    ]
    for keywords, score, reason in keyword_groups:
        if _contains_any(text, keywords):
            return score, reason
    return 0, ""


def _risk_level(score):
    """Return the risk level for a numeric task score."""
    if score >= 85:
        return "critical"
    if score >= 65:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def _recommended_priority_action(risk_level):
    """Return a German next-action recommendation for a risk level."""
    actions = {
        "critical": "Sofort pruefen, Anlage sichern und Instandhaltung informieren.",
        "high": "Zeitnah einplanen und Ursache vor Schichtende dokumentieren.",
        "medium": "Im Tagesplan beruecksichtigen und Befund erfassen.",
        "low": "Nach aktuellen dringenden Tasks bearbeiten.",
    }
    return actions[risk_level]

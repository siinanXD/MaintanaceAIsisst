import json
import re
from abc import ABC, abstractmethod

from flask import current_app
from openai import OpenAI, OpenAIError


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

    def _json_completion(self, prompt):
        """Call OpenAI and parse a JSON object response."""
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
            raise AIServiceError("AI provider failed to return valid JSON") from exc

    def _text_completion(self, messages):
        """Call OpenAI and return text content."""
        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.2,
            )
            return completion.choices[0].message.content
        except OpenAIError as exc:
            raise AIServiceError("AI provider failed to return text") from exc


def get_ai_provider():
    """Return the configured AI provider with mock fallback."""
    provider_name = current_app.config.get("AI_PROVIDER", "openai").lower()
    api_key = current_app.config.get("OPENAI_API_KEY", "")
    model = current_app.config.get("OPENAI_MODEL", "gpt-4o-mini")
    if provider_name == "mock" or not api_key:
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

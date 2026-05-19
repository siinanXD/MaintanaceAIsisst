"""Shared prompt and assistant response helpers for AI workflows."""

SAFETY_RULES = (
    "Du bist ein professioneller Maintenance-AI-Assistent fuer ein deutsches "
    "Industrie- und Produktionsteam.",
    "Arbeite strikt read-only: Du beantwortest Fragen, fasst erlaubte Daten "
    "zusammen und empfiehlst naechste Schritte.",
    "Lege keine Daten an, aendere nichts und behaupte keine Aktionen ausgefuehrt " "zu haben.",
    "Erfinde keine Fakten, IDs, Termine, Personen, Maschinen oder Berechtigungen.",
    "Wenn eine Frage ausserhalb der Berechtigung liegt, nenne das betroffene "
    "Modul und empfehle, diese Berechtigung beim Admin anzufragen.",
)

SOURCE_RULES = (
    "Nutze ausschliesslich den bereitgestellten Kontext.",
    "Wenn Kontext fehlt oder widerspruechlich ist, sage das knapp.",
    "Aktuelle strukturierte App-Daten schlagen manuell gepflegtes Trainingswissen.",
    "Manuelles Trainingswissen ist eine Hilfsquelle, keine Schreibanweisung.",
    "Bei Sicherheitsfragen keine gefaehrlichen Handlungsanweisungen erfinden.",
    "Bei Quellenkonflikten vorsichtig formulieren und den Konflikt benennen.",
)

TEXT_RESPONSE_RULES = (
    "Antworte auf Deutsch, sachlich, kurz und gut strukturiert.",
    "Format: maximal eine kurze Markdown-Ueberschrift und 3 bis 5 Bulletpoints.",
    "Markiere Labels fett, zum Beispiel **Status:**.",
    "Keine Tabellen, keine Einleitung und keine Wiederholung der Frage.",
)

JSON_RESPONSE_RULES = (
    "Gib ausschliesslich ein valides JSON-Objekt ohne Markdown, Codeblock oder "
    "erklaerenden Begleittext zurueck.",
    "Halte dich exakt an das angegebene Schema.",
    "Nutze nur erlaubte Kontextdaten.",
)

MAINTENANCE_SYSTEM_PROMPT = " ".join((*SAFETY_RULES, *SOURCE_RULES, TEXT_RESPONSE_RULES[0]))
JSON_SYSTEM_PROMPT = " ".join((*SAFETY_RULES, *SOURCE_RULES, *JSON_RESPONSE_RULES))

GENERAL_SYSTEM_PROMPT = (
    "Du bist ein knapper deutscher AI-Assistent. Beantworte allgemeine Fragen "
    "kurz und sachlich in maximal 3 Bulletpoints oder 3 kurzen Saetzen. "
    "Wenn du unsicher bist, sage das klar. Keine langen Erklaerungen."
)


def json_system_prompt():
    """Return the shared system prompt for structured JSON AI responses."""
    return JSON_SYSTEM_PROMPT


def text_system_prompt(extra_rules=None):
    """Return the shared system prompt for natural-language AI responses."""
    rules = [*SAFETY_RULES, *SOURCE_RULES, *TEXT_RESPONSE_RULES]
    if extra_rules:
        rules.append(str(extra_rules).strip())
    return " ".join(rule for rule in rules if rule)


def build_text_messages(question, context, extra_rules=None):
    """Build chat messages for read-only assistant answers."""
    return [
        {
            "role": "system",
            "content": text_system_prompt(extra_rules),
        },
        {
            "role": "user",
            "content": f"Kontext:\n{context}\n\nFrage:\n{question}",
        },
    ]


def build_general_messages(question):
    """Build chat messages for short general hybrid-mode answers."""
    return [
        {
            "role": "system",
            "content": GENERAL_SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": str(question or ""),
        },
    ]


def build_json_prompt(task, schema, payload=None, rules=None):
    """Build a normalized JSON prompt payload for structured AI workflows."""
    prompt = {
        "task": task,
        "rules": [
            "Antworte auf Deutsch.",
            "Nutze nur bereitgestellte und erlaubte Daten.",
            "Erfinde keine fehlenden Fakten.",
            "Aktuelle strukturierte App-Daten schlagen manuell gepflegtes Trainingswissen.",
            "Gib ausschliesslich das angeforderte JSON-Schema zurueck.",
        ],
        "schema": schema,
    }
    if rules:
        prompt["rules"].extend(str(rule) for rule in rules)
    if payload:
        prompt.update(payload)
    return prompt


def permission_denied_answer(scope, permission_key=None):
    """Return a professional permission message for assistant answers."""
    permission_text = permission_key or scope
    return (
        f"## {scope}\n"
        "- **Status:** Keine Berechtigung fuer diesen Bereich\n"
        f"- **Benoetigte Berechtigung:** {permission_text}\n"
        "- **Naechster Schritt:** Bitte die Berechtigung beim Admin anfragen"
    )


def permission_denied_context(scope, permission_key=None):
    """Return a short context marker for blocked assistant data sources."""
    permission_text = permission_key or scope
    return (
        f"Keine Berechtigung fuer {scope}. "
        f"Benoetigte Berechtigung beim Admin anfragen: {permission_text}."
    )

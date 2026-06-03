# Masterschool – Provider- und Prompt-Vergleich

Diese Tabelle ist für die **Woche 5–8 Assignment** in Notion gedacht. Trage die Spalten „Output (Auszug)“ und „Kosten/Latenz“ nach echten Läufen in deiner Umgebung ein (mit gesetztem `OPENAI_API_KEY`).

## Test-Prompt (für alle Provider gleich)

**System (Kurzfassung):** Du bist ein Wartungsassistent. Antworte auf Deutsch, nur mit Informationen aus dem Kontext, nenne Unsicherheit und Quellen.

**User:**

```text
Welche offenen Wartungsaufgaben sind heute in Produktion kritisch, und welche Maschine hat die meisten Störungen?
```

**Structured-Output-Ziel (JSON):**

```json
{
  "summary": "string",
  "top_machine": "string",
  "open_task_count": 0,
  "confidence": "low|medium|high",
  "sources": ["string"]
}
```

---

## Vergleichstabelle (Vorlage)

| # | Provider / Modus | Prompt-Variante | Temperature | max_tokens | Output (Auszug) | Latenz (ms) | Kosten (Schätzung) | Notizen |
|---|------------------|-----------------|-------------|------------|-----------------|-------------|-------------------|---------|
| 1 | `AI_PROVIDER=mock` | Standard-Wartungs-Prompt | 0.2 | 800 | Regelbasierte Antwort, keine API-Kosten | &lt;50 | 0 € | CI und Offline-Demo |
| 2 | `AI_PROVIDER=openai` / `gpt-4o-mini` | Standard + JSON-Schema | 0.2 | 800 | *(nach Live-Run einfügen)* | | | Produktionsnah |
| 3 | `AI_PROVIDER=openai` / `gpt-4o-mini` | „Streng“ (nur Kontext, sonst ablehnen) | 0.0 | 600 | *(nach Live-Run einfügen)* | | | Weniger Halluzination |
| 4 | `AI_PROVIDER=openai_compatible` (lokal, z. B. Ollama) | Gleicher Prompt wie #2 | 0.2 | 800 | *(optional)* | | | Entspricht Notion „lokal deploy“ |
| 5 | `AI_PROVIDER=gemini` | – | – | – | **Geplant** – fällt aktuell auf `mock` zurück | – | – | In README dokumentiert |
| 6 | `AI_PROVIDER=groq` | – | – | – | **Geplant** – noch kein Adapter | – | – | Optional für Notion |

---

## Prompt-Techniken im Projekt (bereits umgesetzt)

| Technik | Wo im Repo | Wirkung |
|---------|------------|---------|
| System + User Prompt getrennt | `app/services/ai_prompting.py`, Admin Prompt-FAQ | Stabile Rolle und Ton |
| Strukturierter Scope (ohne LLM) | `app/services/ai_*_structured_answer_service.py` | Schnelle, berechtigte Antworten mit Quellen |
| RAG-Kontext + No-Answer | `app/services/rag_service.py`, `build_rag_context` | Antwort nur mit Evidenz |
| Temperature pro Workflow | `app/config.py`, Workflow-Profile in Tests | z. B. niedrig für Fakten, höher für Formulierung |
| Sicherheits-Gate | `app/services/ai_safety_service.py` | Keine riskanten Anweisungen ohne Kontext |
| Mock-Fallback | `AI_PROVIDER=mock` | Deterministische CI ohne API-Key |

---

## So führst du einen dokumentierten Live-Vergleich durch

1. Gleiche Testdaten: `flask --app run:app db upgrade` und Demo-Seed bzw. deine Produktions-Kopie.
2. Drei Läufe mit identischem User-Chat: `POST /api/v1/ai/chat` mit obigem Prompt.
3. In Notion pro Zeile: Prompt-Text, Antwort-Auszug (max. 5 Zeilen), `diagnostics` aus der API (Status, `source_count`, Provider).
4. Kosten: OpenAI Usage Dashboard oder Langfuse (`LANGFUSE_ENABLED=true`), falls konfiguriert.

---

## Bezug zur Produkt-Vergleichstabelle (Notion)

| Klassisches System | Maintenance AI Assistant (dieses Repo) |
|--------------------|----------------------------------------|
| Manuelle Aufgabenverwaltung | KI-gestützte Vorschläge, Priorisierung, strukturierte Task-Antworten |
| Erfahrungsbasierte Fehleranalyse | RAG + Fehlerkatalog + Maschinenkontext |
| Manuelle Priorisierung | Dringlichkeits-Scoring, Briefings |
| Eingeschränktes Dashboard | Dynamisches Dashboard + Admin-AI-Status |
| Seltene API | REST + OpenAPI, JWT, Rollen |
| Teilweise Rollen | Dashboard-Permissions + Employee-Tiers |
| Geringe Erweiterbarkeit | Modular (Provider, Vector Store, LangGraph-RAG optional) |

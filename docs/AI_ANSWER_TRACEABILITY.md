# AI Answer Traceability

## Zweck

Jede gespeicherte Chat-Antwort kann einen metadata-only Trace erhalten. Der
Trace macht nachvollziehbar, welches Modell genutzt wurde, welche Quellen und
Chunks die Antwort gestuetzt haben, welche Scores vorlagen und welche
Nutzungs-/Kostenmetadaten bekannt sind.

## Gespeicherte Felder

`AIAnswerTrace` speichert:

- `answer_id`: oeffentliche Trace-ID fuer Lookup.
- `chat_message_id`: Verbindung zur gespeicherten Antwort.
- `audit_event_id`: Verbindung zum bestehenden AI-Audit-Event.
- `model`, `model_tier`, `provider`, `workflow`.
- `timestamp` ueber `created_at`.
- Token-Nutzung: Input, Output, Cached, Total.
- `estimated_cost_usd`.
- Confidence Score und Level.
- Prompt-sichere Source Cards.
- Prompt-sichere Chunk-Referenzen mit Similarity-/Relevanzscores.

## Privacy und Security

Traces speichern keine Rohprompts, keine Antworten, keine Roh-Chunktexte und
keine privaten Dateipfade. Source- und Chunkdaten werden ueber eine Whitelist in
`app/services/ai_traceability_service.py` serialisiert. Bekannte sensitive Felder
wie `text`, `content`, `description`, `relative_path`, `prompt`, `response` und
interne Notizen werden verworfen.

Trace-Details sind ueber API nur fuer Admin, Master Admin und IT sichtbar:

```text
GET /api/v1/ai/answers/{answer_id}/trace
GET /api/v1/ai/chat/{chat_message_id}/trace
```

Normale Rollen erhalten `403`.

## Beziehung zu bestehendem Audit

`AIAuditEvent` bleibt der aggregierbare metadata-only Audit- und Analytics-Datensatz.
`AIAnswerTrace` ist der detailliertere Antwortbeleg fuer einzelne Antworten und
verweist auf `AIAuditEvent` und `ChatMessage`.

## Langfuse

Langfuse ist ein externer Observability-Sink und nicht die autoritative
Trace-Datenbank. Der interne `AIAnswerTrace` bleibt System of Record fuer
Antwortbelege, Quellen, Chunks, Scores, Token-Nutzung, Kosten und Confidence.
Langfuse-Metadaten dienen nur zum Filtern und Korrelieren externer Traces.

Wenn `LANGFUSE_ENABLED=true` ist, werden vor dem Modellaufruf nur kurze,
sanitisierte Attribute propagiert:

- `user_id` als pseudonyme App-ID, zum Beispiel `user:42`.
- `session_id`, sofern ein Chat-Session-Identifier vorhanden ist.
- `userrole`, Workflow, Modell, Modell-Tier, Environment, Release und
  Repository-/Commit-Metadaten.
- Zaehlwerte wie `sourcecount`.

Nach dem Speichern des internen `AIAnswerTrace` wird, sofern ein
`langfuse_trace_id` vorhanden ist, ein kleiner Link-Span an denselben
Langfuse-Trace angehaengt. Dieser Span enthaelt nur Referenzen:

- `answerid`
- `answertraceid`
- `chatmessageid`
- `userid`
- `userrole`
- `sessionid`
- `workflow`
- `model`
- `modeltier`
- `sourcecount`
- `chunkcount`
- `retrievalused`
- `inputtokens`
- `outputtokens`
- `cachedtokens`
- `totaltokens`
- `estimatedcostusd`
- `latencyms`
- `confidencescore`
- `confidencelevel`

Langfuse erhaelt keine Rohprompts, keine Rohantworten, keine Chunktexte, keine
privaten Dateipfade, keine Notes, keine Loesungstexte und keine Secrets. Diese
Felder werden durch `app/services/langfuse_service.py` verworfen, bevor
Metadaten an die Langfuse-SDK-Integration gehen.

### Evaluationsscores

Mit `LANGFUSE_EVAL_ENABLED=true` sendet die App regelbasierte Scores
(Halluzination, Retrieval, Confidence) an den verknuepften Trace. Nutzer-
Feedback wird als `user-feedback`-Scores geschrieben. Optionales
`LANGFUSE_EVAL_CAPTURE_IO=true` fuegt einen begrenzten `maintenance-ai.eval_io`-
Span fuer LLM-as-a-Judge hinzu. Details: [`LANGFUSE_EVALUATION.md`](LANGFUSE_EVALUATION.md).

Audit-Ergebnis: User-, Rollen- und Session-Attribute werden vor dem Modellaufruf
propagiert; Chat-/Answer-Referenzen und Betriebswerte werden erst nach dem
Speichern des internen `AIAnswerTrace` als kleiner Link-Span ergaenzt. Fehlende
Langfuse-Konfiguration deaktiviert nur den externen Sink und darf AI Requests
nicht blockieren.

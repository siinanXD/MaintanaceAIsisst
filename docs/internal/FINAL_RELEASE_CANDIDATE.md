# Final Release Candidate

## Aktueller Stand

- Backend, RAG, AI Admin, Dokumentenindexierung, Schichtplanung und React-Typecheck sind fuer den Release Candidate verifiziert.
- Die vier RC-Blocker sind behoben: RAG Golden Questions, Manual Upload Indexing, Shift Rotation State und sichtbare UI-Textartefakte.
- Produktive Flask-Routen, Templates, Workflows, Rollen-/Berechtigungssystem und RAG-Fallbacks bleiben erhalten.
- Swagger/OpenAPI ist in Produktion deaktiviert oder nicht oeffentlich erreichbar.

## Startanleitung

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
flask --app run:app db upgrade
python run.py --host 127.0.0.1 --port 5050
```

Production-Container sollten `AUTO_CREATE_DATABASE=false` setzen und Migrationen vor dem Start ausfuehren. React-Assets werden mit `npm run build:react` gebaut, der Typecheck mit `npm run check:react`.

## Wichtige Env-Werte

```env
FLASK_ENV=production
SECRET_KEY=<strong-random-secret>
JWT_SECRET_KEY=<strong-random-secret>
DATABASE_URL=<postgresql-or-sqlite-url>
AI_PROVIDER=openai
OPENAI_API_KEY=<secret>
OPENAI_CHAT_MODEL=gpt-4o-mini
EMBEDDING_PROVIDER=openai
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
RAG_VECTOR_STORE=local
RAG_TOP_K=4
RAG_RERANK_CANDIDATE_LIMIT=20
ENABLE_API_DOCS=false
API_DOCS_REQUIRE_MASTER_ADMIN=true
```

Bei Atlas-RAG:

```env
RAG_VECTOR_STORE=mongodb_atlas
MONGODB_ATLAS_URI=<secret>
MONGODB_ATLAS_DATABASE=<database>
MONGODB_ATLAS_VECTOR_COLLECTION=knowledge_vectors
MONGODB_ATLAS_VECTOR_INDEX=knowledge_vector_index
MONGODB_ATLAS_TIMEOUT_MS=3000
```

Nach Aenderung von Embedding Provider, Embedding Modell oder Vector Store muessen Knowledge-Dokumente vollstaendig neu indexiert werden.

## Bekannte Risiken

- OpenAI wurde im RC-Smoke nicht mit echten Produktions-Secrets gegen die reale API getestet.
- MongoDB Atlas Vector Search wurde im RC-Smoke nicht mit echter Atlas-Infrastruktur getestet.
- Echte Produktionsdaten, Netzwerklatenzen, Rate Limits, Atlas-Indexstatus und Provider-Kosten muessen im Deployment-Umfeld separat validiert werden.

## Finaler Smoke-Test

Zuletzt verifiziert:

```bash
python -m pytest
python -m ruff check app tests
npm run check:react
```

Ergebnis:

- `python -m pytest`: 680 passed
- Nach dem finalen Query-get-Fix: betroffene Regressionstests 75 passed, keine `.query.get(` Treffer mehr in `app`/`tests`
- `python -m ruff check app tests`: passed
- `npm run check:react`: passed
- Production Startup Smoke mit `FLASK_ENV=production`, starken Secrets, `EMBEDDING_PROVIDER=openai`, `OPENAI_EMBEDDING_MODEL=text-embedding-3-small` und `RAG_VECTOR_STORE=local`: App startet, 213 Routen
- Health: `/health`, `/health/live`, `/health/ready` liefern `200`
- Sensible Routen liefern unauthentifiziert `401`
- OpenAPI/Swagger-Pfade liefern in Produktion `404`

# Paperless-NGX Cortex Manual

Diese Datei ist jetzt der Einstiegspunkt in die aufgeteilte Dokumentation.

## Für Benutzer

Das vollständige Benutzerhandbuch liegt unter:

- [docs/manual/README.md](docs/manual/README.md)

Besonders relevant:

- [docs/manual/14-tages-checkliste.md](docs/manual/14-tages-checkliste.md)
- [docs/manual/12-similar-workflow.md](docs/manual/12-similar-workflow.md)
- [docs/manual/13-team-policy.md](docs/manual/13-team-policy.md)

## Für Admins und Betreiber

Die wichtigsten Betriebsdokumente:

- [docs/manual/15-admin-und-betrieb.md](docs/manual/15-admin-und-betrieb.md)
- [docs/manual/16-settings-und-live-model-provider.md](docs/manual/16-settings-und-live-model-provider.md)
- [docs/architecture-overview.md](docs/architecture-overview.md)
- [docs/config-reference.md](docs/config-reference.md)

## Quickstart

### Voraussetzungen

- Python `>=3.13`
- Node.js `>=20.19` (20.x) oder `>=22.12`
- Paperless-ngx mit API-Token
- PostgreSQL
- Redis für Queue-Betrieb
- Qdrant oder Weaviate als Vector Store
- OpenAI-kompatibler LLM-Endpunkt

### Backend

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
```

### Worker

```bash
cd backend
uv run python -m app.worker
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Weitere wichtige Dateien

- [README.md](README.md) für Projektüberblick und Setup
- [CHANGELOG.md](CHANGELOG.md) für granulare Änderungshistorie
- [agents.md](agents.md) für aktuellen Projektstatus

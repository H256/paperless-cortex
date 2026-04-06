# Konfigurationsreferenz

Diese Seite ist eine kompakte Betriebsreferenz für die wichtigsten Konfigurationsgruppen. Sie ergänzt `.env.example`, ersetzt sie aber nicht.

## 1. Grundsatz

Die produktive Konfiguration kommt primär aus:

- [`.env.example`](E:\workspace\python\paperless-intelligence\.env.example)
- [backend/app/config.py](E:\workspace\python\paperless-intelligence\backend\app\config.py)

Diese Referenz erklärt die Gruppen und den praktischen Zweck der Variablen.

## 2. Pflichtwerte für einen echten Betrieb

Mindestens relevant sind:

- `PAPERLESS_BASE_URL`
- `PAPERLESS_API_TOKEN`
- `DATABASE_URL`
- `VECTOR_STORE_PROVIDER`
- entweder Qdrant- oder Weaviate-Konfiguration
- `LLM_BASE_URL`
- `TEXT_MODEL`
- `EMBEDDING_MODEL`

Zusätzlich für Queue-Betrieb:

- `QUEUE_ENABLED=1`
- `REDIS_HOST`

Zusätzlich für echten Writeback:

- `WRITEBACK_EXECUTE_ENABLED=1`

## 3. Konfigurationsgruppen

### Paperless

Wichtige Variablen:

- `PAPERLESS_BASE_URL`
- `PAPERLESS_API_TOKEN`

Zweck:

- Verbindung zur Paperless-Instanz
- Authentifizierung für Lesen und Writeback

### Datenbank

Wichtige Variable:

- `DATABASE_URL`

Zweck:

- lokaler Persistenzspeicher für Dokumentzustand, Suggestions, OCR-Zusatzdaten, Task-Runs und Review-Daten

### Vector Store

Wichtige Variablen:

- `VECTOR_STORE_PROVIDER`
- `VECTOR_STORE_URL`
- `VECTOR_STORE_API_KEY`
- `VECTOR_STORE_COLLECTION`
- `VECTOR_STORE_CENTROID_COLLECTION`

Provider-spezifisch:

- Qdrant: `QDRANT_URL`, `QDRANT_API_KEY`, `QDRANT_COLLECTION`
- Weaviate: `WEAVIATE_HTTP_*`, `WEAVIATE_GRPC_*`, `WEAVIATE_API_KEY`, `WEAVIATE_COLLECTION`, `WEAVIATE_CENTROID_COLLECTION`

Zweck:

- Embeddings speichern
- Search/Similarity/Chat Retrieval ermöglichen

### Queue und Worker

Wichtige Variablen:

- `QUEUE_ENABLED`
- `REDIS_HOST`
- `WORKER_MAX_RETRIES`
- `WORKER_SUGGESTIONS_MAX_CHARS`

Zweck:

- Hintergrundverarbeitung
- Retry-Verhalten
- stabile Worker-Orchestrierung

### LLM und Modelle

Wichtige Variablen:

- `LLM_BASE_URL`
- `LLM_API_KEY`
- `TEXT_MODEL`
- `CHAT_MODEL`
- `EMBEDDING_MODEL`
- `RUNTIME_SETTINGS_MASTER_KEY`

Zweck:

- Textmodell für Suggestions, Summaries und Fallback-Chat
- separates Chatmodell optional
- Embeddingmodell
- Schutz von Runtime-Overrides für Provider-Keys

#### `RUNTIME_SETTINGS_MASTER_KEY`

Diese Variable schützt gespeicherte API-Key-Overrides aus der Settings-Seite.

Wichtig:

- sie muss gesetzt sein, wenn Laufzeit-API-Keys gespeichert werden sollen
- sie muss ein gültiger Fernet-Key sein
- beliebiger Text oder ein normales Passwort reichen nicht

Beispiel aus den `.env`-Dateien:

- PowerShell:
  `$key = [Convert]::ToBase64String((1..32 | ForEach-Object { Get-Random -Minimum 0 -Maximum 256 }))`
  anschließend URL-safe umformen
- Python:
  `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`

Praktische Folge:

- ohne gültigen Key können API-Key-Overrides nicht korrekt verschlüsselt gespeichert werden
- bei einem ungültigen Key schlägt die Laufzeitverwendung fehl
- derselbe Key muss konsistent für die beteiligten Prozesse verfügbar sein, insbesondere Backend und Worker

#### Laufzeit-API-Key-Änderungen

Die Settings-Seite schützt bestehende gespeicherte Keys vor versehentlichem Überschreiben.

Das bedeutet:

- ein leer gelassenes API-Key-Feld ersetzt einen bestehenden Key nicht automatisch
- `Clear key` ist der bewusste Löschpfad
- `Replace key` beziehungsweise `Set key` öffnet das Eingabefeld bewusst für Änderungen

### Embedding und Chunking

Wichtige Variablen:

- `EMBEDDING_BATCH_SIZE`
- `EMBEDDING_TIMEOUT_SECONDS`
- `EMBEDDING_MAX_CHUNKS_PER_DOC`
- `EMBEDDING_MAX_INPUT_TOKENS`
- `EMBED_ON_SYNC`
- `CHUNK_MODE`
- `CHUNK_MAX_CHARS`
- `CHUNK_OVERLAP`
- `CHUNK_SIMILARITY_THRESHOLD`

Zweck:

- Steuerung der Vektorisierung
- Begrenzung großer Dokumente
- Chunkgröße und Überlappung

### OCR und Vision

Wichtige Variablen:

- `ENABLE_PDF_PAGE_EXTRACT`
- `ENABLE_VISION_OCR`
- `VISION_MODEL`
- `VISION_OCR_PROMPT`
- `VISION_OCR_PROMPT_PATH`
- `VISION_OCR_TIMEOUT_SECONDS`
- `VISION_OCR_MAX_DIM`
- `VISION_OCR_TARGET_DIM`
- `VISION_OCR_BATCH_PAGES`
- `VISION_OCR_MIN_CHARS`
- `VISION_OCR_MIN_SCORE`
- `VISION_OCR_MAX_NONALNUM_RATIO`
- `VISION_OCR_MAX_PAGES`

Zweck:

- zusätzliche OCR-Verarbeitung
- Qualitätsgrenzen und Laufzeitbudgets
- Bildgrößensteuerung

### Suggestions und Summary

Wichtige Variablen:

- `SUGGESTIONS_PROMPT_PATH`
- `SUGGESTIONS_DEBUG`
- `SUGGESTIONS_MAX_INPUT_CHARS`
- `LARGE_DOC_PAGE_THRESHOLD`
- `PAGE_NOTES_TIMEOUT_SECONDS`
- `PAGE_NOTES_MAX_OUTPUT_TOKENS`
- `SUMMARY_SECTION_PAGES`
- `SECTION_SUMMARY_MAX_INPUT_TOKENS`
- `SECTION_SUMMARY_TIMEOUT_SECONDS`
- `GLOBAL_SUMMARY_MAX_INPUT_TOKENS`
- `GLOBAL_SUMMARY_TIMEOUT_SECONDS`
- `SUMMARY_MAX_OUTPUT_TOKENS`

Zweck:

- Prompt- und Budgetsteuerung
- Umschaltung auf große-Dokumente-Pfade
- Summary-/Page-Notes-Limits

### OCR-Scoring und Evidenz

Wichtige Variablen:

- `OCR_CHAT_BASE`
- `OCR_VISION_BASE`
- `OCR_SCORE_MODEL`
- `OCR_THRESH_BAD`
- `OCR_THRESH_BORDERLINE`
- `OCR_ENABLE_LOGPROB_PPL`
- `OCR_PPL_MAX_PROMPT_CHARS`
- `OCR_PPL_CHUNK_CHARS`
- `OCR_PPL_TIMEOUT_SEC`
- `OCR_VISION_TIMEOUT_SEC`
- `OCR_VISION_MAX_TOKENS`
- `EVIDENCE_MAX_PAGES`
- `EVIDENCE_MIN_SNIPPET_CHARS`

Zweck:

- OCR-Bewertung
- Grenzwerte für schlechte bzw. grenzwertige OCR
- Evidenzauflösung für Belegstellen

### Logging, HTTP und Status

Wichtige Variablen:

- `LOG_LEVEL`
- `LOG_JSON`
- `API_SLOW_REQUEST_LOG_MS`
- `HTTPX_VERIFY_TLS`
- `STATUS_STREAM_INTERVAL_SECONDS`
- `STATUS_LLM_MODELS_TTL_SECONDS`

Zweck:

- Laufzeitbeobachtung
- langsame Requests sichtbar machen
- TLS-Verifikation
- Statusstreaming

### Writeback

Wichtige Variable:

- `WRITEBACK_EXECUTE_ENABLED`

Zweck:

- Schutzschalter für echten Writeback

Wenn diese Variable nicht aktiviert ist, sollte der Betrieb nur Dry-Run oder Vorschau erlauben.

## 4a. Laufzeit-Settings-Seite

Die Anwendung besitzt zusätzlich eine Live-Settings-Oberfläche für Model-Provider.

Sie erlaubt pro Rolle:

- Base URL ändern
- Modell ändern
- API-Key hinterlegen, ersetzen oder löschen
- Modelllisten vom Provider laden

Die Seite ist für kontrollierte Laufzeitwechsel gedacht, ersetzt aber nicht die Basis-Konfiguration in `.env`.

## 5. Praktische Minimalprofile

### Lokale Basis ohne Queue

Geeignet für:

- Entwicklung
- kleine Testumgebungen

Typisch:

- `QUEUE_ENABLED=0`
- direkte API-Nutzung
- Qdrant lokal
- Vision optional aus

### Standardbetrieb mit Queue

Geeignet für:

- regulären täglichen Einsatz

Typisch:

- `QUEUE_ENABLED=1`
- Redis aktiv
- Worker separat laufend
- Embeddings und Suggestions asynchron

### Erweiterter Betrieb mit Vision und großen Dokumenten

Geeignet für:

- schwierige Scans
- höhere Retrieval-Qualität
- große Dokumente

Typisch:

- `ENABLE_VISION_OCR=1`
- passende Vision-Modelle
- großzügigere Laufzeit- und Budgetwerte

## 6. Wichtige Sicherheitsregeln

- `.env` nicht committen
- API-Keys nur lokal oder in sicherer Deployment-Konfiguration halten
- `WRITEBACK_EXECUTE_ENABLED` bewusst setzen
- TLS-Prüfung nicht ohne Grund deaktivieren
- Runtime-Master-Key sicher erzeugen und verwahren
- denselben Runtime-Master-Key konsistent für Backend und Worker setzen

## 7. Häufige Fehlkonfigurationen

### Queue aktiviert, aber Redis fehlt

Folge:

- Queue/Worker-Funktionen schlagen fehl oder bleiben stehen

### Vector-Store-Provider passt nicht zur Umgebung

Folge:

- Embeddings, Search und Similarity funktionieren nicht sauber

### Vision aktiviert, aber Modell oder Endpunkt unpassend

Folge:

- Vision OCR bleibt leer, langsam oder fehlerhaft

### Writeback nicht freigeschaltet

Folge:

- Vorschau funktioniert, echter Writeback aber nicht

### `RUNTIME_SETTINGS_MASTER_KEY` ist ungültig oder fehlt

Folge:

- API-Key-Overrides aus der Settings-Seite lassen sich nicht sicher verwenden
- gespeicherte Laufzeit-Providerkonfiguration kann fehlschlagen
- Backend und Worker verhalten sich inkonsistent, wenn nicht derselbe gültige Key verwendet wird

## 8. Empfohlene Lesereihenfolge für Betreiber

1. [docs/architecture-overview.md](E:\workspace\python\paperless-intelligence\docs\architecture-overview.md)
2. [docs/config-reference.md](E:\workspace\python\paperless-intelligence\docs\config-reference.md)
3. [docs/manual/15-admin-und-betrieb.md](E:\workspace\python\paperless-intelligence\docs\manual\15-admin-und-betrieb.md)
4. [docs/manual/16-settings-und-live-model-provider.md](E:\workspace\python\paperless-intelligence\docs\manual\16-settings-und-live-model-provider.md)
5. [`.env.example`](E:\workspace\python\paperless-intelligence\.env.example)

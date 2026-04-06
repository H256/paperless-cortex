# Suche und Chat

Zurück zur Übersicht: [Benutzerhandbuch](./README.md)

## 1. Semantic Search (`Search`)

Die Suchansicht ist für semantische Suche gedacht. Anders als eine reine Volltextsuche arbeitet sie auf Basis von Embeddings und zeigt Treffer mit Kontext an.

### 1.1 Eingabefelder und Optionen

Die wichtigsten Elemente sind:

- `Query`
- `Top K`
- `Source`
- `Min quality`
- `Only vision OCR`
- `Dedupe`
- `Rerank`

### 1.2 Bedeutung der Optionen

- `Query`: Ihre Suchfrage oder ein freier Suchsatz.
- `Top K`: wie viele Treffer maximal zurückkommen sollen.
- `Source`: Einschränkung auf `Vision OCR`, `Paperless OCR` oder `PDF text`.
- `Min quality`: blendet Treffer mit schlechter Textqualität aus.
- `Only vision OCR`: erzwingt Suche nur auf Vision-OCR-Daten.
- `Dedupe`: reduziert doppelte oder sehr ähnliche Treffer.
- `Rerank`: ordnet Treffer nach zusätzlicher Bewertung neu.

### 1.3 Suchergebnisse lesen

Ein Treffer zeigt typischerweise:

- Dokument-ID
- Seite
- Quelle
- Score
- Qualitätswert
- Dokumenttitel
- Datum
- Korrespondent
- Snippet

Zusätzliche Aktionen pro Treffer:

- `Open details`
- `Copy details link`
- `Copy snippet`
- `Open in Paperless`

### 1.4 Wann welche Quelle sinnvoll ist

- `Paperless OCR`: gut für Standarddokumente mit bereits brauchbarem OCR-Text.
- `Vision OCR`: gut für schwierige Scans, Fotos oder schlecht erkannte Vorlagen.
- `PDF text`: gut, wenn im PDF bereits verwertbarer eingebetteter Text steckt.

### 1.5 Tastaturkürzel in `Search`

- `/`: fokussiert das Suchfeld
- `Ctrl+Enter`: startet die Suche
- `Ctrl+Shift+Enter`: öffnet den ersten Treffer

### 1.6 Gute Arbeitsweise

Wenn die Trefferqualität schwach ist:

1. filtern Sie auf eine Quelle,
2. erhöhen Sie `Min quality`,
3. deaktivieren oder aktivieren Sie `Rerank`,
4. und prüfen Sie im Dokument selbst den Tab `Text & quality`.

## 2. Globaler Chat (`Chat`)

Die Chat-Ansicht beantwortet Fragen über Ihren Dokumentbestand und liefert Belege.

### 2.1 Bedienelemente

Die wichtigsten Einstellungen sind:

- `Question`
- `Top K`
- `Source`
- `Min quality`
- `Relationship`
- `Only vision OCR`
- `Streaming`
- `Follow-up context`
- `Turns`

### 2.2 Bedeutung der Chat-Optionen

- `Top K`: wie viele relevante Textquellen in die Antwort einfließen.
- `Source`: Einschränkung auf bestimmte Datenquellen.
- `Min quality`: schließt schlechte OCR-Layer aus.
- `Relationship`: steuert Beziehungen zwischen Funden, zum Beispiel `chrono`.
- `Streaming`: zeigt die Antwort fortlaufend an.
- `Follow-up context`: bezieht frühere Gesprächsrunden ein.
- `Turns`: legt fest, wie viele frühere Turns berücksichtigt werden.

### 2.3 Gespräche verwalten

Die Chatansicht unterstützt Gesprächsverläufe:

- `New thread` startet einen neuen Gesprächskontext.
- `Clear` leert die aktuelle lokale Unterhaltung.
- die `Conversation id` kann kopiert werden.

Das ist nützlich, wenn Sie thematisch getrennte Recherchen führen wollen.

### 2.4 Antworten und Belege

Jede Antwort zeigt:

- die ursprüngliche Frage,
- die erzeugte Antwort,
- mögliche Folgefragen,
- und Quellenhinweise.

Die Quellen sind klickbar und führen direkt zum betreffenden Dokument oder zur passenden Stelle.

### 2.5 Folgefragen

Nach einer Antwort können Sie:

- direkt `Follow-up` wählen,
- vorgeschlagene Folgefragen anklicken,
- oder mit aktivem `Follow-up context` den Gesprächsfaden fortsetzen.

Das ist besonders hilfreich bei zusammenhängenden Fallrecherchen.

### 2.6 Tastaturkürzel in `Chat`

- `/`: fokussiert das Fragefeld
- `Ctrl+Enter`: sendet die Frage
- `Ctrl+Shift+Enter`: öffnet die erste Quelle der letzten Antwort

## 3. Unterschied zwischen `Search` und `Chat`

`Search` ist besser, wenn Sie gezielt Fundstellen sehen wollen.

`Chat` ist besser, wenn Sie:

- eine zusammenfassende Antwort möchten,
- mehrere Quellen verbinden wollen,
- oder sich Folgefragen ableiten lassen möchten.

In der Praxis ergänzen sich beide Bereiche:

1. erst über `Search` gute Treffer finden,
2. dann über `Chat` eine zusammenhängende Antwort erzeugen,
3. und schließlich über die Detailansicht die einzelnen Dokumente prüfen.

Weiter mit: [Verarbeitung, Queue und Writeback](./04-verarbeitung-queue-und-writeback.md)

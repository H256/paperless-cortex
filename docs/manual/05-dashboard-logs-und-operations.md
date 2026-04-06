# Dashboard, Logs und Operations

Zurück zur Übersicht: [Benutzerhandbuch](./README.md)

## 1. Dashboard

Das `Dashboard` ist die Übersichtsseite für den Gesamtzustand des Systems.

Es eignet sich besonders für:

- morgendlichen Statuscheck,
- Sicht auf Verarbeitungsfortschritt,
- grobe Last- und Bestandsabschätzung,
- Erkennen von Schwerpunkten bei Korrespondenten, Tags oder Dokumenttypen.

### 1.1 Was dort typischerweise sichtbar ist

- Gesamtzahl der Dokumente
- vollständig verarbeitete Dokumente
- unvollständig verarbeitete Dokumente
- Embeddings
- Vision-OCR-Abdeckung
- Suggestions
- Prozentbalken für den Verarbeitungsstand
- Top-Tags
- Seitenzahlverteilung
- Korrespondentenverteilungen
- monatliche Verarbeitungsentwicklung
- Dokumenttypen

### 1.2 Wofür das Dashboard nicht gedacht ist

Das Dashboard ist keine Detail- oder Fehleransicht. Wenn Sie konkrete Ursachen, einzelne Dokumente oder konkrete Worker-Fehler prüfen wollen, wechseln Sie besser zu:

- `Documents`
- `Queue`
- `Logs`

## 2. Logs

`Logs` ist die präzisere Analyseansicht für Worker-Läufe, Fehlertypen und wiederkehrende Probleme.

### 2.1 Error type reference

Im aufklappbaren Referenzbereich finden Sie bekannte Fehlercodes mit:

- Code
- Retry-Fähigkeit
- Kategorie
- Beschreibung

Das hilft bei der Einordnung, ob ein Fehler eher vorübergehend oder fachlich/technisch grundsätzlich ist.

### 2.2 Filter

Die Logansicht bietet Filter für:

- Dokument-ID
- Task
- Status
- Fehlertyp
- Limit
- Auto Refresh

Zusätzlich können Presets gespeichert und wiederverwendet werden.

### 2.3 Quick Filter

Vorhandene Schnellfilter sind besonders nützlich für:

- nur fehlgeschlagene Läufe,
- aktuell retryende Läufe,
- typische Embedding-Überläufe.

### 2.4 Export

Wenn aktuell Treffer vorliegen, können Sie die Logdaten exportieren als:

- JSON
- CSV

Das ist praktisch für externe Analyse oder spätere Nachverfolgung.

### 2.5 Wann Sie eher `Logs` statt `Queue` nutzen sollten

Nutzen Sie `Logs`, wenn Sie:

- Fehlerklassifikationen brauchen,
- gezielte Ursachenforschung betreiben,
- Filter dauerhaft speichern möchten,
- oder Laufdaten exportieren wollen.

Nutzen Sie `Queue`, wenn Sie:

- Prioritäten ändern,
- wartende Aufgaben sehen,
- DLQ-Einträge requeueen,
- oder die aktuelle Arbeitsreihenfolge beeinflussen möchten.

## 3. Operations

`Operations` ist die Administrations- und Wartungsansicht. Hier gibt es bewusst auch destruktive Funktionen.

### 3.1 Wichtiger Sicherheitshinweis

Viele Aktionen in `Operations` löschen lokale Daten oder setzen Zustände zurück. Nutzen Sie diese Ansicht nur, wenn Sie die Auswirkungen verstehen.

Paperless selbst bleibt bei vielen Aktionen unangetastet, aber lokale Analyseergebnisse können verloren gehen.

### 3.2 Reprocess all documents

Diese Aktion:

- löscht lokale Intelligenzdaten,
- stößt danach aber einen vollständigen Neuaufbau an.

Verwenden Sie sie nur, wenn eine vollständige Neuindizierung oder ein grundlegender Rebuild nötig ist.

### 3.3 Wipe local data

Diese Aktion entfernt:

- lokale Dokumente,
- Embeddings,
- Suggestions,
- Vision-OCR-Daten

ohne anschließende Reprocess-Kette.

Das ist ein harter Reset und nur für Ausnahmefälle sinnvoll.

### 3.4 Einzelne Bereinigungsaktionen

Weitere Wartungsaktionen entfernen gezielt:

- Vision OCR
- Suggestions
- Embeddings
- Similarity Index

Diese Funktionen sind sinnvoll, wenn nur ein bestimmter Teilbestand erneuert werden muss.

### 3.5 Audit missing vector chunks

Diese Prüfung vergleicht lokale Embedding-Zustände mit dem aktiven Vektor-Backend. Sie hilft, wenn:

- Suchergebnisse unerwartet schwach sind,
- Dokumente lokal als eingebettet gelten,
- aber tatsächlich Vektordaten fehlen oder unvollständig sind.

### 3.6 Cleanup page texts

Diese Funktion bereinigt gespeicherte Seitentexte und baut technische Hilfsfelder neu auf.

Sie ist nützlich, wenn:

- sich Textaufbereitung geändert hat,
- Inhalte auffällig schmutzig aussehen,
- oder technische Page-Text-Felder neu berechnet werden sollen.

### 3.7 Sync correspondents / Sync tags

Diese Aktionen ziehen Stammdaten erneut aus Paperless in den lokalen Cache.

Sinnvoll, wenn:

- neue Korrespondenten oder Tags in Paperless angelegt wurden,
- oder lokale Auswahlfelder nicht aktuell wirken.

### 3.8 Runtime- und Worker-Lock-Bereich

Im Runtime-Bereich können Sie technische Zustände prüfen. Der Worker-Lock-Reset ist nur für Sonderfälle gedacht, etwa wenn ein verwaister Lock einen Workerstart blockiert.

Wenn Sie diesen Bereich nutzen, sollten Sie genau wissen, warum ein Worker blockiert ist.

## 4. Empfohlene Nutzung der Betriebsansichten

Für normale Anwender reicht meist:

1. `Dashboard` für den Gesamtblick,
2. `Queue` für aktive Arbeit,
3. `Logs` für Probleme,
4. `Operations` nur für gezielte Wartung.

## 5. Troubleshooting in Kurzform

Wenn etwas nicht wie erwartet funktioniert, gehen Sie in dieser Reihenfolge vor:

1. `Documents`: Ist das Dokument überhaupt da und welcher Status wird angezeigt?
2. `Document Detail > Operations`: Welche Schritte fehlen?
3. `Continue processing`: Lässt sich fehlende Arbeit gesammelt anstoßen?
4. `Queue`: Wird die Arbeit geplant oder blockiert?
5. `Logs`: Welcher Fehlertyp liegt vor?
6. `Operations`: Nur wenn wirklich ein Reset oder Wartungsschritt nötig ist.

Zurück zur Übersicht: [Benutzerhandbuch](./README.md)

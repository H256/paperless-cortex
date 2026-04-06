# Admin und Betrieb

Zurück zur Übersicht: [Benutzerhandbuch](./README.md)

Diese Seite richtet sich an Benutzer mit Betriebs- oder Administrationsverantwortung.

## 1. Ziel dieser Seite

Sie beschreibt, welche UI-Bereiche für den Betrieb wichtig sind und in welcher Reihenfolge man bei technischen Problemen vorgeht.

## 2. Wichtige Betriebsansichten

### Dashboard

Für den groben Überblick:

- Gesamtbestand
- verarbeitete vs. offene Dokumente
- Verteilungen und Trends

### Queue

Für die operative Steuerung:

- wartende Aufgaben
- laufende Aufgaben
- Delayed Retries
- DLQ
- Priorisierung einzelner Tasks

### Logs

Für Ursachenanalyse:

- Task-Runs
- Fehlertypen
- Retry-Verhalten
- Export von Laufdaten

### Operations

Für bewusste Wartungsmaßnahmen:

- Reprocess all
- Wipe local data
- einzelne Bereinigungen
- Similarity-Index-Reset
- Sync von Tags und Korrespondenten
- Worker-Lock-Prüfung und Reset

### Settings

Für live änderbare Modell- und Provider-Konfiguration:

- Base URLs pro Rolle
- Modelle pro Rolle
- verschlüsselt gespeicherte API-Key-Overrides
- Modell-Discovery ohne Neustart

## 3. Empfohlene Reihenfolge bei technischen Problemen

Wenn Verarbeitung oder Suchqualität nicht stimmen:

1. betroffenes Dokument öffnen
2. `Document Detail > Operations` prüfen
3. `Queue` prüfen
4. `Logs` prüfen
5. erst danach `Operations`

## 4. Queue-Betrieb

Die Queue ist die zentrale Stelle für den Worker-Durchsatz.

Prüfen Sie regelmäßig:

- wächst die Queue-Länge dauerhaft?
- gibt es laufende Aufgaben?
- stehen Aufgaben nur auf `pending`?
- häufen sich Delayed Retries?
- füllt sich die DLQ?

Warnsignale:

- Queue wächst, aber nichts läuft
- viele identische Fehlertypen
- viele DLQ-Einträge
- dieselben Dokumente scheitern wiederholt

## 5. Umgang mit DLQ

Die DLQ ist kein normaler Puffer, sondern ein Fehlerindikator.

Regeln:

- nicht pauschal alles requeueen
- zuerst Fehlertyp in `Logs` prüfen
- Ursache verstehen
- dann gezielt requeueen

## 6. Umgang mit `Reprocess all`

`Reprocess all` ist eine schwere Maßnahme.

Nur sinnvoll, wenn:

- ein grundlegender Neuaufbau nötig ist
- ein großer Datenbestand inkonsistent geworden ist
- oder nach größeren technischen Änderungen ein kompletter Rebuild beabsichtigt ist

Nicht sinnvoll für:

- einzelne problematische Dokumente
- normale Queue-Fehler
- kleine Datenkorrekturen

## 7. Umgang mit `Wipe local data`

Das ist ein harter Reset der lokalen Datenbasis.

Nur sinnvoll für Ausnahmefälle, zum Beispiel:

- Test- oder Umbauphasen
- bewusstes Neuaufsetzen des lokalen Bestands

Diese Maßnahme ist nicht die Standardantwort auf Betriebsprobleme.

## 8. Similarity-Index-Reset

Diese Maßnahme ist nur dann sinnvoll, wenn:

- Similar-Ergebnisse unplausibel sind
- doc-level Similarity sauber neu aufgebaut werden soll
- oder ein technischer Neuaufbau der Similarity-Daten geplant ist

Nicht jede schlechte Similar-Liste rechtfertigt sofort einen Reset. Erst OCR, Embeddings und Logs prüfen.

## 9. Worker-Lock

Ein Lock-Reset ist nur bei einem verwaisten oder blockierenden Lock sinnvoll.

Vorher prüfen:

- läuft wirklich kein aktiver Worker?
- blockiert der Lock den Neustart?

Wenn ein aktiver Worker existiert, sollte der Lock nicht blind zurückgesetzt werden.

## 10. Betriebs-Kurzregel

Für Admins gilt:

1. erst beobachten
2. dann Ursache eingrenzen
3. dann gezielt eingreifen
4. destruktive Maßnahmen nur bewusst und selten einsetzen

## 11. Empfohlene tägliche Admin-Kontrolle

1. `Dashboard` prüfen
2. `Queue` auf Stau prüfen
3. `Logs` auf gehäufte Fehlertypen prüfen
4. `Settings` nur bewusst für Laufzeit-Providerwechsel nutzen
5. `Operations` nur bei echtem Bedarf nutzen

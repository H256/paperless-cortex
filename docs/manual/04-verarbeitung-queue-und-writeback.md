# Verarbeitung, Queue und Writeback

Zurück zur Übersicht: [Benutzerhandbuch](./README.md)

## 1. Continue Processing

Die Ansicht `Continue Processing` dient dazu, fehlende Verarbeitungsschritte gesammelt zu erkennen und nur die wirklich fehlende Arbeit in die Queue zu stellen.

Sie erreichen sie:

- aus `Documents`,
- aus Leermeldungen in der Dokumentliste,
- oder aus `Operations` eines einzelnen Dokuments.

### 1.1 Wofür die Ansicht gedacht ist

Sie ist ideal, wenn:

- viele Dokumente noch nicht vollständig verarbeitet sind,
- neue Daten importiert wurden,
- ein Teil der Pipeline nachgeholt werden soll,
- oder Sie nach Fehlern gezielt Lücken schließen wollen.

### 1.2 Typische Optionen

Die Oberfläche zeigt unter anderem:

- Vorschau fehlender Arbeit
- Strategieauswahl
- Batch-Größe
- optionalen Sync-Einschluss
- Fortschritts- und Queue-Informationen

### 1.3 Strategien

Je nach Stand der Anwendung können Strategien wie diese sichtbar sein:

- `balanced`
- `paperless_only`
- `vision_first`
- `max_coverage`

Die Grundidee:

- `balanced` ist der vernünftige Standard.
- `paperless_only` ist schneller und konservativer.
- `vision_first` bevorzugt Vision-basierte Verarbeitung.
- `max_coverage` versucht die breiteste Abdeckung, braucht aber mehr Ressourcen.

### 1.4 Vorschau lesen

Die Vorschau zeigt typischerweise:

- wie viele Dokumente Lücken haben,
- welche Teilbereiche fehlen,
- und welche Verarbeitung mit der gewählten Strategie angestoßen wird.

Typische Zähler sind:

- fehlende Vision-OCR
- fehlende Embeddings
- fehlende Page Notes
- fehlende hierarchische Zusammenfassungen
- fehlende Suggestions

### 1.5 Typischer Ablauf

1. `Continue Processing` öffnen.
2. Strategie und Batch-Größe wählen.
3. Vorschau prüfen.
4. Verarbeitung starten.
5. anschließend `Queue` und `Logs` beobachten.

## 2. Queue

Die `Queue` zeigt die tatsächliche Worker-Arbeitsliste und ihre Historie.

Sie ist vor allem für Benutzer wichtig, die nachvollziehen wollen:

- was gerade läuft,
- was als Nächstes dran ist,
- wo Fehler auftreten,
- und ob Aufgaben erneut angestoßen werden müssen.

### 2.1 Übersicht

Im oberen Bereich sehen Sie üblicherweise:

- Status
- Queue-Länge
- laufende Aufgaben
- letzte Aktualisierung
- Bedienelemente zum Aktualisieren oder Steuern der Queue

### 2.2 Upcoming items

In `Upcoming items` sehen Sie die nächsten geplanten Aufgaben.

Sie können dort:

- nach Dokument-ID filtern,
- die Anzahl angezeigter Einträge begrenzen,
- die Queue laden,
- Einträge nach oben oder unten verschieben,
- oder einzelne Aufgaben entfernen.

Das ist nützlich, wenn ein wichtiges Dokument priorisiert werden soll.

### 2.3 Task run history

Hier sehen Sie bereits gestartete oder abgeschlossene Aufgabenläufe mit:

- Dokument-ID
- Task-Name
- Status
- Fehlertyp
- Fehlermeldung
- Checkpoint
- Dauer
- Startzeit

Außerdem können Sie gefilterte fehlgeschlagene Läufe gesammelt erneut anstoßen.

### 2.4 Delayed retries

Dieser Bereich zeigt Aufgaben, die wegen Backoff noch warten. Hier sehen Sie:

- welche Aufgabe betroffen ist,
- für welches Dokument,
- wann der nächste Retry fällig ist.

### 2.5 Dead-letter queue

Die DLQ enthält Aufgaben, die nach mehreren Versuchen nicht erfolgreich waren.

Wichtige Regeln:

- requeue nur dann, wenn die Ursache verstanden oder behoben ist,
- `Clear DLQ` nur bewusst verwenden,
- lieber zuerst `Logs` prüfen, bevor Sie stumpf neu einreihen.

## 3. Writeback

`Writeback` ist der kontrollierte Übergang vom lokalen Bearbeitungsstand zurück nach Paperless.

Die Ansicht ist in drei Bereiche gegliedert:

- `Preview`
- `Queue`
- `History`

### 3.1 Tab `Preview`

Hier prüfen Sie vor dem Rückschreiben die geplanten Änderungen pro Dokument.

Sie sehen:

- Dokument-ID
- ob Änderungen vorliegen
- welche Felder betroffen sind
- Originalwert
- neuen Wert

Sie können:

- nur geänderte Dokumente anzeigen,
- Vorschau neu laden,
- einzelne oder alle geänderten Dokumente auswählen,
- und aus der Auswahl einen Writeback-Job erzeugen.

### 3.2 Wie man die Vorschau sinnvoll prüft

Gehen Sie Feld für Feld durch, besonders bei:

- Titel
- Datum
- Korrespondent
- Tags
- Notiz oder Zusammenfassung

Prüfen Sie dabei:

- ob die fachliche Bedeutung stimmt,
- ob kein OCR-Fehler übernommen wurde,
- und ob die Notiz für Paperless wirklich sinnvoll ist.

### 3.3 Tab `Queue`

Hier liegen die geplanten Writeback-Jobs.

Sie können zwischen zwei Modi unterscheiden:

- `Dry-run`
- `Real writeback`

Empfehlung:

- zuerst `Dry-run` verwenden,
- dann erst `Execute`, wenn die Vorschau fachlich geprüft wurde.

Pro Job sehen Sie:

- Job-ID
- Status
- Modus
- Anzahl ausgewählter und tatsächlich geänderter Dokumente
- Zahl der geplanten oder ausgeführten Aufrufe

Aktionen:

- einzelnen Job dry-run oder echt ausführen,
- alle pending Jobs gesammelt ausführen,
- pending Jobs entfernen,
- Ergebnisse des letzten Sammellaufs prüfen.

### 3.4 Tab `History`

Hier sehen Sie abgeschlossene Writeback-Läufe.

Das ist hilfreich für:

- Nachvollziehbarkeit,
- Kontrolle nach einer größeren Änderungsserie,
- und Fehlersuche bei unerwarteten Resultaten in Paperless.

## 4. Der Unterschied zwischen lokalem Anwenden und Writeback

Das ist einer der wichtigsten Punkte der gesamten Anwendung:

- In der Detailansicht übernehmen Sie Vorschläge zunächst lokal.
- In `Writeback` entscheiden Sie später, welche lokalen Änderungen wirklich nach Paperless gehen.

Damit können Sie ruhig iterieren, ohne sofort Produktivdaten zu verändern.

## 5. Empfohlener sicherer Workflow

1. Vorschläge pro Dokument lokal übernehmen.
2. Dokumente fachlich prüfen.
3. `Writeback > Preview` öffnen.
4. nur die wirklich sauberen Dokumente auswählen.
5. zuerst dry-run ausführen.
6. Ergebnis prüfen.
7. anschließend echten Writeback starten.

Weiter mit: [Dashboard, Logs und Operations](./05-dashboard-logs-und-operations.md)

# Troubleshooting und FAQ

Zurück zur Übersicht: [Benutzerhandbuch](./README.md)

Diese Seite hilft bei typischen Bedien- und Prozessproblemen.

## 1. Ein Dokument taucht in `Documents` nicht auf

Prüfen Sie in dieser Reihenfolge:

1. Wurde bereits ein `Sync` durchgeführt?
2. Ist das Dokument in Paperless vorhanden?
3. Filtern Sie die Liste versehentlich zu stark?
4. Ist ein Datums-, Tag- oder Korrespondentenfilter aktiv?
5. Ist `Running only` aktiv?

Wenn weiterhin nichts erscheint:

- öffnen Sie `Operations`, wenn ein globaler Sync oder Rebuild nötig sein könnte,
- oder prüfen Sie den technischen Zustand mit `Logs`, falls der Sync fehlschlägt.

## 2. Ein Dokument ist sichtbar, aber `Search` findet es nicht

Häufige Ursachen:

- Embeddings fehlen noch.
- Die falsche Quelle ist im Filter gewählt.
- `Min quality` ist zu hoch.
- Das Dokument hat schwache OCR-Daten.

Vorgehen:

1. Öffnen Sie das Dokument.
2. Prüfen Sie in `Operations`, ob `Embeddings` fehlen.
3. Prüfen Sie in `Text & quality`, wie gut die Textbasis ist.
4. Starten Sie bei Bedarf `Continue missing processing`.
5. Suchen Sie erneut ohne harte Quellfilter.

## 3. `Chat` liefert schlechte oder keine brauchbaren Antworten

Häufige Ursachen:

- Die Textbasis ist unvollständig.
- Das falsche Quellmaterial ist gewählt.
- Zu wenige Treffer werden einbezogen.
- Das Dokument ist fachlich komplex und braucht Folgefragen.

Vorgehen:

1. Erhöhen Sie `Top K`.
2. Prüfen Sie, ob `Source` zu stark eingeschränkt ist.
3. Senken Sie `Min quality`, wenn die Datenlage dünn ist.
4. Aktivieren Sie `Follow-up context`, wenn Sie Anschlussfragen stellen.
5. Kontrollieren Sie die Belege in der Detailansicht.

## 4. `Writeback` zeigt keine Dokumente an

Häufige Ursachen:

- Es gibt keine lokalen Änderungen.
- Dokumente wurden zwar geprüft, aber ohne neue lokale Werte.
- Die Vorschau wurde noch nicht neu geladen.
- `Changed documents only` blendet alles aus.

Vorgehen:

1. Öffnen Sie ein betroffenes Dokument.
2. Prüfen Sie, ob tatsächlich lokale Änderungen angewendet wurden.
3. Öffnen Sie `Writeback > Preview`.
4. Laden Sie die Vorschau neu.
5. Deaktivieren Sie testweise `Changed documents only`.

## 5. Ein Dokument steht auf `Needs review`

Das bedeutet in der Regel:

- es gibt offene lokale Vorschläge oder Änderungen,
- oder der lokale Stand weicht relevant vom Remote-Stand ab.

Empfohlener Ablauf:

1. Öffnen Sie das Dokument.
2. Prüfen Sie `Suggestions`.
3. Prüfen Sie aktuelle Werte in `Metadata`.
4. Entscheiden Sie bewusst, was lokal bleiben oder verworfen werden soll.
5. Markieren Sie das Dokument erst danach als reviewed.

## 6. Ein Dokument bleibt technisch unvollständig

Typische Anzeichen:

- fehlende Badges
- unvollständiger `Processing status`
- wiederkehrende Fehler in der `Processing timeline`

Vorgehen:

1. Öffnen Sie `Document Detail > Operations`.
2. Starten Sie `Continue missing processing`.
3. Falls nötig, starten Sie einen Einzel-Task gezielt.
4. Prüfen Sie `Queue`.
5. Prüfen Sie bei Fehlern `Logs`.

## 7. Aufgaben bleiben in der Queue hängen

Prüfen Sie:

- ob der Worker läuft,
- ob die Queue nicht pausiert ist,
- ob die Queue-Länge steigt, ohne dass `running` zunimmt,
- ob viele Delayed Retries oder DLQ-Einträge vorliegen.

Praktisches Vorgehen:

1. `Queue` öffnen.
2. Überblick prüfen.
3. `Upcoming items` und `Task run history` ansehen.
4. Falls viele Fehler sichtbar sind, `Logs` öffnen.
5. Erst nach Ursachenklärung DLQ-Einträge requeueen.

## 8. Es gibt viele DLQ-Einträge

Die DLQ ist kein normaler Arbeitsstau, sondern ein Hinweis auf systematische Probleme.

Empfohlen:

1. Nicht sofort alles requeueen.
2. Erst Fehlertypen in `Logs` prüfen.
3. Gemeinsamkeiten feststellen, etwa immer derselbe Task oder Fehlertyp.
4. Ursache beheben.
5. Dann gezielt requeueen.

## 9. Wann nutze ich welchen Bereich?

### Ich will ein einzelnes Dokument prüfen

Nutzen Sie `Documents` und dann die Detailansicht.

### Ich will fehlende Arbeit für viele Dokumente nachholen

Nutzen Sie `Continue processing`.

### Ich will die konkrete Reihenfolge oder wartende Tasks sehen

Nutzen Sie `Queue`.

### Ich will Fehlertypen und Laufdaten analysieren

Nutzen Sie `Logs`.

### Ich will Daten löschen, reindizieren oder Wartung machen

Nutzen Sie `Operations`.

### Ich will Änderungen nach Paperless übertragen

Nutzen Sie `Writeback`.

## 10. Wann sollte ich `Operations` nicht sofort verwenden?

Vermeiden Sie übereilte Wartungsaktionen, wenn ein Problem wahrscheinlich auch einfacher lösbar ist.

Beispiele:

- Fehlende Embeddings sind meist kein Fall für `Wipe local data`.
- Ein einzelnes problematisches Dokument braucht meist keinen globalen Reprocess.
- Leere Suchergebnisse bedeuten nicht automatisch, dass der Similarity Index zurückgesetzt werden muss.

Prüfen Sie zuerst immer:

1. die Detailansicht,
2. `Continue processing`,
3. `Queue`,
4. `Logs`.

## 11. FAQ in Kurzform

### Muss ich nach dem Übernehmen eines Vorschlags sofort Writeback ausführen?

Nein. Lokales Anwenden und Writeback sind getrennt.

### Bedeutet `Reviewed`, dass Paperless schon aktualisiert wurde?

Nein. `Reviewed` ist ein lokaler Prüfstatus.

### Sollte ich immer `max_coverage` wählen?

Nicht unbedingt. `balanced` ist meist der bessere Standard.

### Sollte ich bei jedem Fehler `Reprocess all` verwenden?

Nein. Das ist eine schwere Wartungsmaßnahme und nur für echte Grundsatzprobleme sinnvoll.

### Sollte ich DLQ-Einträge pauschal neu einreihen?

Nein. Erst Ursache prüfen, dann gezielt requeueen.

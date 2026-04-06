# Typische Arbeitsabläufe

Zurück zur Übersicht: [Benutzerhandbuch](./README.md)

Diese Seite beschreibt empfohlene Bedienabläufe für typische Alltagssituationen.

## 1. Neue Dokumente sichten und priorisieren

Ziel: schnell erkennen, welche Dokumente neu oder noch unvollständig sind.

Empfohlener Ablauf:

1. Öffnen Sie `Documents`.
2. Nutzen Sie das Preset `Inbox (new)` oder `Unreviewed`.
3. Aktivieren Sie bei Bedarf `Not analyzed`.
4. Schalten Sie auf Kartenansicht um, wenn Sie mobil arbeiten oder wenige Dokumente genauer überfliegen wollen.
5. Öffnen Sie interessante Dokumente direkt in der Detailansicht.

Worauf Sie achten sollten:

- `Needs review`
- fehlende Verarbeitungs-Badges wie `Embeddings` oder `Vision OCR`
- ungewöhnliche Titel oder leere Metadaten

## 2. Fehlende Verarbeitung gesammelt nachholen

Ziel: nur die wirklich fehlenden Schritte für viele Dokumente anstoßen.

Empfohlener Ablauf:

1. Starten Sie `Continue processing` aus `Documents`.
2. Lassen Sie die Vorschau berechnen.
3. Wählen Sie `balanced`, wenn Sie keinen Sonderfall haben.
4. Begrenzen Sie die Batch-Größe, wenn das System knapp dimensioniert ist.
5. Starten Sie die Verarbeitung.
6. Beobachten Sie danach `Queue` und bei Problemen `Logs`.

Wann Sie eine andere Strategie wählen sollten:

- `paperless_only`, wenn Vision-Verarbeitung gerade nicht gewünscht oder nicht verfügbar ist
- `vision_first`, wenn Paperless-OCR häufig schwach ist
- `max_coverage`, wenn Sie die breiteste Datengrundlage aufbauen wollen und Laufzeit zweitrangig ist

## 3. Ein einzelnes Dokument fachlich prüfen

Ziel: einen belastbaren lokalen Stand herstellen.

Empfohlener Ablauf:

1. Öffnen Sie das Dokument aus `Documents`.
2. Prüfen Sie `Metadata`.
3. Öffnen Sie `Suggestions` und vergleichen Sie Vorschläge mit den aktuellen Werten.
4. Öffnen Sie bei Zweifel `Pages` oder `Text & quality`.
5. Nutzen Sie `Similar`, um ähnliche Dokumente zum Vergleich heranzuziehen.
6. Nutzen Sie `Chat`, wenn Sie inhaltliche Rückfragen haben.
7. Markieren Sie das Dokument lokal als reviewed, wenn Sie sicher sind.

## 3a. Stück-für-Stück-Workflow über `Unreviewed` und `Similar`

Dieser Ablauf passt besonders gut, wenn Sie sich dokumentweise durch die Arbeitsliste bewegen und ähnliche Dokumente direkt als Nächstes mitnehmen wollen.

Empfohlener Ablauf:

1. Öffnen Sie `Documents`.
2. Filtern Sie auf `Unreviewed`.
3. Öffnen Sie das nächste Dokument.
4. Ergänzen oder korrigieren Sie fehlende Felder.
5. Führen Sie den `Writeback` aus, sobald das Dokument fachlich sauber ist.
6. Wechseln Sie danach in den Tab `Similar`.
7. Prüfen Sie dort, welche ähnlichen Dokumente noch nicht reviewed sind.
8. Öffnen Sie eines dieser ähnlichen Dokumente.
9. Wiederholen Sie den Ablauf Stück für Stück.

Warum dieser Ablauf gut funktioniert:

- ähnliche Dokumente haben oft dieselben Muster,
- Korrespondent, Datum, Tags und Notizlogik lassen sich leichter vergleichen,
- und Sie bleiben fachlich in einem zusammenhängenden Kontext.

Hinweis zur Begrifflichkeit:

- Im Arbeitsalltag sprechen Teams oft vom "reviewed Tag".
- In der Oberfläche ist damit meistens der lokale `Review`-Status gemeint, also `Unreviewed`, `Needs review` oder `Reviewed`.
- Beim Prüfen im Tab `Similar` sollten Sie deshalb vor allem auf den Review-Status achten.

## 4. KI-Vorschläge sicher übernehmen

Ziel: Vorschläge nutzen, ohne fehlerhafte Daten zu veröffentlichen.

Empfohlener Ablauf:

1. Prüfen Sie zuerst die Quelle des Vorschlags.
2. Übernehmen Sie einzelne Felder lokal statt blind alles auf einmal.
3. Bevorzugen Sie bei kritischen Feldern wie Datum oder Korrespondent die plausibelste Quelle.
4. Prüfen Sie Notiz- oder Summary-Texte besonders sorgfältig.
5. Lassen Sie unklare Felder unangetastet.

Besonders kritisch sind:

- Datum
- Korrespondent
- Tags mit fachlicher Bedeutung
- frei generierte Notiztexte

## 5. Ein Dokument hat noch Lücken

Ziel: fehlende Schritte gezielt nachholen, ohne alles neu aufzubauen.

Empfohlener Ablauf:

1. Öffnen Sie das Dokument.
2. Wechseln Sie zu `Operations`.
3. Prüfen Sie `Processing status`.
4. Nutzen Sie zuerst `Continue missing processing`.
5. Wenn nur ein ganz bestimmter Schritt fehlt, starten Sie gezielt den passenden Einzel-Task.
6. Beobachten Sie die `Processing timeline`.

Einzel-Tasks sind sinnvoll, wenn Sie bewusst nur einen Teil neu erzeugen wollen, zum Beispiel:

- `Vision OCR`
- `Baseline embeddings`
- `Vision embeddings`
- `AI suggestions`
- `similarity index`

## 6. Ähnliche Dokumente zum Validieren nutzen

Ziel: Metadaten an echten Vergleichsdokumenten prüfen.

Empfohlener Ablauf:

1. Öffnen Sie ein Dokument mit unsicheren Vorschlägen.
2. Wechseln Sie zu `Similar`.
3. Prüfen Sie die ähnlichsten Treffer.
4. Öffnen Sie die Vergleichsdokumente.
5. Übernehmen Sie Vorschläge erst, wenn sich Muster bestätigen.

Das ist besonders wirksam bei:

- wiederkehrenden Rechnungen
- Serienbriefen
- Standardkorrespondenz
- mehrfach eingehenden Formularen

## 7. Suche und Chat für Fachprüfung kombinieren

Ziel: Aussagen aus Dokumenten schneller überprüfen.

Empfohlener Ablauf:

1. Nutzen Sie `Search`, um Fundstellen zu finden.
2. Öffnen Sie Treffer direkt in der Detailansicht.
3. Nutzen Sie anschließend `Chat`, um zusammenhängende Fragen zu stellen.
4. Öffnen Sie Quellen aus der Antwort.
5. Prüfen Sie die Aussage im PDF-Viewer.

## 8. Writeback sicher ausführen

Ziel: nur geprüfte Änderungen nach Paperless zurückschreiben.

Empfohlener Ablauf:

1. Prüfen Sie mehrere Dokumente lokal.
2. Öffnen Sie `Writeback > Preview`.
3. Aktivieren Sie `Changed documents only`.
4. Wählen Sie nur fachlich saubere Dokumente aus.
5. Queueen Sie die Auswahl.
6. Führen Sie zuerst `Dry-run` aus.
7. Prüfen Sie die Ergebnisse.
8. Wechseln Sie erst dann zu echtem `Execute`.

## 8a. Kompakte Routine für den Alltag

Wenn Sie dokumentweise arbeiten, lässt sich der Ablauf auf diese Schleife verkürzen:

1. `Documents` mit Filter `Unreviewed`
2. Dokument öffnen
3. fehlende Felder ergänzen
4. `Writeback`
5. `Similar` prüfen
6. nächstes noch nicht reviewed Dokument öffnen
7. wiederholen

Diese Routine ist besonders effizient bei wiederkehrenden Belegarten wie Rechnungen, Standardschreiben oder ähnlichen Serien von Dokumenten.

## 9. Fehlerfall im Alltag

Wenn ein Dokument nicht sauber verarbeitet wird:

1. Prüfen Sie `Document Detail > Operations`.
2. Sehen Sie in die `Processing timeline`.
3. Öffnen Sie `Queue`, wenn Aufgaben noch warten.
4. Öffnen Sie `Logs`, wenn Fehler oder Wiederholungen sichtbar sind.
5. Nur wenn nötig, nutzen Sie `Operations` für Wartungsmaßnahmen.

Weiter mit: [Glossar und Statusbegriffe](./07-glossar-und-statusbegriffe.md)

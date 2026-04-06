# Schnellstart und Grundprinzipien

Zurück zur Übersicht: [Benutzerhandbuch](./README.md)

## 1. Aufbau der Navigation

Die Hauptnavigation enthält folgende Bereiche:

- `Dashboard`
- `Documents`
- `Search`
- `Writeback`
- `Chat`
- `Queue`
- `Logs`
- `Operations`

Je nach Bildschirmbreite liegen nicht alle Punkte direkt sichtbar in der Hauptleiste. Ein Teil kann im Menü `More` erscheinen.

## 2. Grundlogik der Anwendung

Die Oberfläche trennt bewusst zwischen Analyse und Rückschreiben:

- Zuerst werden Dokumente aus Paperless lokal synchronisiert.
- Danach werden lokale Verarbeitungsschritte ausgeführt, zum Beispiel OCR-Erweiterung, Embeddings, Zusammenfassungen oder Vorschläge.
- Benutzer prüfen die Ergebnisse in der Oberfläche.
- Erst danach werden Änderungen manuell per `Writeback` nach Paperless übertragen.

Das ist wichtig, weil lokale Analyseergebnisse nicht automatisch die Daten in Paperless verändern.

## 3. Was lokal passiert und was in Paperless bleibt

Lokal in Paperless Intelligence:

- Verarbeitungsstatus
- KI-Vorschläge
- OCR-Zusatzdaten
- Embeddings und Ähnlichkeitssuche
- lokale Review-Zustände
- Writeback-Vorschau

In Paperless als führendes System:

- eigentliche Dokumentmetadaten
- Dokumenttitel, Datum, Korrespondent, Tags
- Notizen, sobald Writeback ausgeführt wurde

## 4. Empfohlener Einstieg für neue Benutzer

Wenn Sie die Anwendung zum ersten Mal benutzen, gehen Sie in dieser Reihenfolge vor:

1. Öffnen Sie `Documents`.
2. Verschaffen Sie sich mit Filtern und Suchfeld einen Überblick.
3. Öffnen Sie ein einzelnes Dokument.
4. Prüfen Sie dort die Tabs `Metadata`, `Suggestions`, `Pages` und `Operations`.
5. Wechseln Sie anschließend zu `Search` und `Chat`, um die Recherchefunktionen kennenzulernen.
6. Sehen Sie sich zum Schluss `Writeback` an, bevor Sie echte Änderungen an Paperless auslösen.

## 5. Typischer Arbeitsablauf

Ein normaler Bedienablauf sieht meistens so aus:

1. Neue oder unvollständig verarbeitete Dokumente in `Documents` finden.
2. Fehlende Verarbeitung über `Continue processing` starten.
3. Einzelne Dokumente in der Detailansicht prüfen.
4. Vorschläge übernehmen oder bewusst verwerfen.
5. Dokumente lokal als geprüft markieren.
6. Änderungen gesammelt in `Writeback` kontrollieren.
7. Erst dann nach Paperless schreiben.

## 6. Wichtige Statusbegriffe

Sie werden in der Oberfläche immer wieder auf diese Begriffe stoßen:

- `Unreviewed`: noch nicht fachlich geprüft.
- `Needs review`: es gibt lokale Abweichungen oder offene Prüfbedarfe.
- `Reviewed`: lokal als geprüft markiert.
- `Analyzed`: die nötigen Analyse-Schritte sind bereits vorhanden.
- `Not analyzed`: wichtige Verarbeitung fehlt noch.
- `Local overrides`: es gibt lokale Änderungen, die noch nicht nach Paperless geschrieben wurden.

## 7. Verhalten auf kleinen Bildschirmen

Die Oberfläche ist auch für kleinere Displays ausgelegt. Dabei gilt:

- Listen wechseln teilweise in Kartenansichten.
- Navigationselemente wandern eher in `More`.
- Tabellen werden an mehreren Stellen als kompaktere Karten dargestellt.

Wenn Sie mobil arbeiten, ist die Dokumentliste oft in der Kartenansicht leichter bedienbar.

## 8. Sicherheitsprinzip bei Änderungen

Bevor Sie mit Metadaten arbeiten, sollten Sie sich ein Prinzip merken:

- `Apply` oder ähnliche Aktionen in der Detailansicht ändern zunächst den lokalen Stand.
- `Writeback` ist der eigentliche Schritt, der Paperless aktualisiert.

Dadurch können Sie Ergebnisse erst prüfen und später gesammelt veröffentlichen.

Weiter mit: [Dokumentliste und Detailansicht](./02-dokumente-und-detailansicht.md)

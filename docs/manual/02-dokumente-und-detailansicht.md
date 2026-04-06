# Dokumentliste und Detailansicht

Zurück zur Übersicht: [Benutzerhandbuch](./README.md)

## 1. Die Dokumentliste (`Documents`)

`Documents` ist die wichtigste Arbeitsansicht. Hier sehen Sie alle synchronisierten Dokumente und können filtern, sortieren, prüfen und in die Detailansicht wechseln.

### 1.1 Kopfbereich

Im oberen Bereich sehen Sie:

- Anzahl der sichtbaren Dokumente
- Gesamtzahl synchronisierter Dokumente
- eine kompakte Verarbeitungsübersicht
- Schaltflächen für `Continue processing`, `Queue` und `Logs`

Wenn aktuell viel verarbeitet wird, sehen Sie dort zusätzlich Fortschritt, ETA und Queue-Status.

### 1.2 Filterbereich

Die Liste besitzt einen kompakten und einen erweiterten Filterbereich.

Sofort sichtbar sind:

- `Quick search`
- `Sort`
- `Correspondent`
- `Tag`
- `Analysis`
- `Review`

Über `Advanced` kommen weitere Filter hinzu:

- `From`
- `To`
- `Model`
- `Page size`

### 1.3 Wofür die wichtigsten Filter gut sind

- `Quick search`: durchsucht schnell Dokument-ID, Titel und in der Regel sichtbare Dokumentinhalte.
- `Analysis`: trennt zwischen bereits analysierten und noch unvollständigen Dokumenten.
- `Review`: trennt ungeprüfte, prüfbedürftige und geprüfte Dokumente.
- `Correspondent` und `Tag`: helfen beim fachlichen Zuschneiden einer Arbeitsmenge.
- `Model`: nützlich, wenn Sie Dokumente nach verwendeter Modellinformation eingrenzen wollen.

### 1.4 Presets und Schnellaktionen

Unter den Filtern gibt es zusätzliche Hilfen:

- Presets wie `Unreviewed`, `Needs review`, `Not analyzed` und `Inbox (new)`
- Schnellumschaltung zwischen Tabellen- und Kartenansicht
- `Running only`, um nur Dokumente mit laufender Verarbeitung zu sehen
- direkte Sprünge zu `Writeback` oder `Continue processing`

Diese Kombination ist besonders praktisch für tägliche Triage.

### 1.5 Tabellen- oder Kartenansicht

Die Listenansicht kann zwischen Tabelle und Karten umschalten:

- Tabellenansicht ist besser für viele Dokumente und schnelles Vergleichen.
- Kartenansicht ist besser auf kleinen Bildschirmen oder bei kompakter Einzelprüfung.

### 1.6 Was Sie aus der Liste direkt tun können

Je nach sichtbaren Bedienelementen können Sie:

- ein Dokument öffnen,
- direkt zu seinen `Operations` springen,
- direkt zu seinen `Suggestions` springen,
- sortieren,
- blättern,
- oder eine Seite direkt anspringen.

## 2. Die Detailansicht eines Dokuments

Wenn Sie ein Dokument öffnen, landen Sie in der zentralen Prüfansicht für dieses einzelne Dokument.

Oben sehen Sie typischerweise:

- Titel
- Dokument-ID
- synchronisierte Zeit
- Review-Status
- Link zu Paperless
- Aktionen wie `Mark reviewed`, `Writeback` und `Reload`

Unterhalb befindet sich eine Tab-Leiste.

## 3. Tab `Metadata`

Hier sehen Sie den zusammengeführten Metadatenstand, unter anderem:

- Titel
- Ausstellungsdatum
- Korrespondent
- Dokumenttyp
- Tags
- Originaldateiname
- Zeitstempel
- Notizen

Diese Ansicht ist gut, um den aktuellen lokalen Stand vor oder nach dem Anwenden von Vorschlägen zu prüfen.

## 4. Tab `Text & quality`

Dieser Bereich ist wichtig, wenn Sie die Textqualität einschätzen wollen.

Sie sehen dort:

- den zusammengeführten Dokumenttext,
- Qualitätsinformationen,
- OCR-Scores,
- und eine Trennung zwischen Paperless-OCR und Vision-OCR, soweit vorhanden.

Nutzen Sie diesen Tab, wenn Vorschläge seltsam wirken oder Suchergebnisse unplausibel erscheinen. Häufig liegt die Ursache in einer schwachen Texterkennung.

## 5. Tab `Suggestions`

Hier werden KI-Vorschläge für Felder wie Titel, Datum, Korrespondent, Tags und Notiz angezeigt.

Typische Quellen sind:

- `Paperless OCR`
- `Vision OCR`
- `Similar docs`

Wichtige Bedienideen:

- Sie können Vorschläge pro Quelle aktualisieren.
- Varianten werden direkt unter dem jeweiligen Feld gezeigt.
- Sie können einzelne Varianten lokal anwenden.
- Sie können Vorschläge direkt auf das Dokument übernehmen.

Praktischer Ablauf:

1. Prüfen Sie erst, welche Quelle am plausibelsten ist.
2. Vergleichen Sie aktuelle Werte mit vorgeschlagenen Werten.
3. Übernehmen Sie nur die Felder, die fachlich sauber sind.
4. Lassen Sie zweifelhafte Felder lieber offen.

## 6. Tab `Pages`

Dieser Tab zeigt die Seitenstruktur und Seitentexte.

Typische Anwendungsfälle:

- einzelne Seiten prüfen,
- zu einer PDF-Seite springen,
- OCR-Probleme lokalisieren,
- kontrollieren, ob Vision-OCR oder Seitenextraktion vollständig vorliegt.

Wenn Sie auf eine Seite springen, wird der PDF-Viewer darunter entsprechend aktualisiert.

## 7. Tab `Similar`

Hier finden Sie ähnliche Dokumente und mögliche Duplikate.

Das ist nützlich für:

- Vergleich mit ähnlichen Rechnungen, Schreiben oder Serienbriefen,
- Plausibilitätsprüfung von Metadaten,
- Erkennen von Dopplungen,
- Ableitung sinnvoller Tags oder Korrespondenten.

Sie können den Ähnlichkeitsschwellenwert anpassen und ähnliche Dokumente direkt öffnen.

## 8. Tab `Chat`

Dieser Chat ist auf das aktuell geöffnete Dokument bezogen. Er eignet sich für Fragen wie:

- Worum geht es in dem Dokument?
- Welche Beträge oder Fristen kommen vor?
- Welche Aussagen sind auf Seite X zu finden?

Die Antworten werden mit Zitaten bzw. Belegen verknüpft. Von dort können Sie wieder in die passende Detailstelle springen.

## 9. Tab `Operations`

Dieser Tab ist die technische Steuerzentrale für das einzelne Dokument.

Sie sehen dort:

- `Continue missing processing`
- den aktuellen Verarbeitungsstatus
- nachgelagerte Aufgaben (`Downstream fan-out`)
- eine Timeline aller Task-Runs
- Einzelaktionen für gezielte Verarbeitungsschritte
- Dokument-Reset und vollständige Neuverarbeitung

Besonders nützlich ist `Continue missing processing`, wenn nur einzelne Schritte fehlen und Sie nicht das ganze Dokument neu anstoßen wollen.

## 10. Lokales Prüfen und Markieren

Wenn Sie den lokalen Stand fachlich geprüft haben, können Sie das Dokument als reviewed markieren. Das ist ein lokaler Prüfstatus und hilft, Ihre Arbeitsmenge sauber zu organisieren.

Wichtig:

- `Reviewed` bedeutet nicht automatisch, dass schon nach Paperless geschrieben wurde.
- Für den tatsächlichen Abgleich nach Paperless brauchen Sie anschließend `Writeback`.

## 11. PDF-Viewer

Unterhalb der Tabs befindet sich der PDF-Viewer.

Er unterstützt die Arbeit mit:

- Seitenwechseln,
- Sprüngen aus Seitentexten,
- Sprüngen aus Suche oder Chat,
- und Hervorhebungen, wenn Treffer mit Seitenbezug vorliegen.

## 12. Empfehlenswerter Prüfablauf für ein einzelnes Dokument

1. `Metadata` ansehen.
2. `Suggestions` prüfen und nur gute Vorschläge lokal übernehmen.
3. Bei Unsicherheit `Pages` oder `Text & quality` öffnen.
4. Für Rückfragen `Similar` oder `Chat` nutzen.
5. In `Operations` offene Verarbeitung kontrollieren.
6. Dokument lokal als reviewed markieren.
7. Später gesammelt über `Writeback` nach Paperless schreiben.

Weiter mit: [Suche und Chat](./03-suche-und-chat.md)

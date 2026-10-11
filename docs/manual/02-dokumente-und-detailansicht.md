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
- Zusätzliche Filter-Presets, die andere Filter (z. B. `Unreviewed`) beibehalten und sich ein- und ausschalten lassen:
  - `No correspondent` (`Alt+5`): nur Dokumente ohne Korrespondent.
  - `Issue date = import date` (`Alt+6`): Dokumente, deren Ausstellungsdatum auf den Importtag fällt, bei denen Paperless also vermutlich kein Datum erkannt hat.
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

### 5.1 Nur ausgewählte Felder übernehmen (`Apply selected`)

KI-Vorschläge sind manchmal Unsinn. Deshalb wird nie etwas automatisch oder gesammelt übernommen:

- Jedes Feld und jede Quelle hat eine Checkbox. Es ist **nichts vorausgewählt**.
- Pro Feld kann nur eine Quelle gewählt werden. Bei Tags wählen Sie einzelne Tag-Chips.
- Unten erscheint eine Leiste mit der Vorschau `vorher → nachher`, `Apply selected (n)` und `Clear`.
- Geschrieben werden ausschließlich die angehakten Felder, und zwar lokal. Nach Paperless gelangt erst etwas über den normalen `Writeback`.
- Bei Tags gilt: vorhandene Tags + ausstehende Tags + gewählte Vorschlags-Tags. Es wird nichts ersetzt.
- `Apply selected` springt nie zum nächsten Dokument.

### 5.2 `Candidates from text`

Datum und Absender werden von der KI nicht immer zuverlässig erkannt. Darum zeigt der Tab einen Block `Candidates from text` mit Treffern, die direkt aus dem OCR-Text gelesen werden (ohne KI, ohne Nebenwirkungen):

- **Datum:** erkennt auch andere Formate und Sprachen (z. B. `20.09.2026`, `2026-09-20`, `20 de septiembre de 2026`, `September 20, 2026`). Das Datum wird nach dem nächstgelegenen Stichwort eingeordnet (Rechnungsdatum, Lieferdatum, Fälligkeit, Zeitraum). Geburtsdaten, sehr alte und weit in der Zukunft liegende Daten werden verworfen.
- **Absender:** bekannte Korrespondenten werden im Kopfbereich des Textes gesucht (auch unscharf). Ein unbekannter Name kann einmal vorgeschlagen werden und ist dann als neu gekennzeichnet.
- Ein Klick wählt den Kandidaten für das Feld aus. Danach läuft er durch denselben `Apply selected`-Ablauf. Es wird nie etwas automatisch gesetzt.

### 5.3 Presets in der Suggestions-Ansicht

Zwei Schnellaktionen für häufige Fälle:

- `No correspondent`: entfernt den Korrespondenten (und einen ausstehenden Korrespondenten).
- `Issue date = import date`: setzt das Ausstellungsdatum auf den Importtag des Dokuments. Das ist nur sinnvoll, wenn kein besseres Datum im Dokument steht.

### 5.4 `Guidance for "Suggest new"`

Wenn ein Vorschlag nicht passt, können Sie die KI gezielt noch einmal fragen. Das Modell sieht nur den Text, nicht das Seitenlayout. Hinweise wie "oben rechts" helfen deshalb nicht. Nützlich sind:

- **Hint:** eine kurze Anweisung, z. B. "Rechnungsdatum, nicht Lieferdatum".
- **Markierte Textpassage:** markieren Sie im angezeigten Text die Stelle mit der Antwort und klicken Sie `Use selected text as focus`. Mit `Clear` entfernen Sie den Fokus wieder.
- **Text the model reads:** Auswahl zwischen `Paperless OCR` und `Vision OCR`. Das Feld erscheint nur, wenn beide Texte vorliegen.
- Bereits angezeigte Varianten werden beim erneuten Fragen als "nicht wiederholen" mitgegeben. So kommen neue Werte statt derselben.

`Suggest new` wendet nie etwas an und ist unabhängig von Ihrer Auswahl.

### 5.5 Gelernte Absender-Regeln

Hat ein Dokument einen Korrespondenten und gibt es bereits geprüfte Dokumente desselben Korrespondenten, werden deren häufigste Tags und Dokumenttypen dem Modell als starke Orientierung mitgegeben. Was das Dokument selbst aussagt, hat Vorrang. Es gibt dafür keine Einstellung und keine Anzeige. Der Effekt ist, dass Tags und Dokumenttyp bei Serien (z. B. Rechnungen eines Lieferanten) konsistenter vorgeschlagen werden.

Praktischer Ablauf:

1. Prüfen Sie erst, welche Quelle am plausibelsten ist.
2. Schauen Sie in `Candidates from text`, besonders bei Datum und Absender.
3. Vergleichen Sie aktuelle Werte mit vorgeschlagenen Werten.
4. Haken Sie nur die Felder an, die fachlich sauber sind, und wählen Sie `Apply selected`.
5. Lassen Sie zweifelhafte Felder offen oder nutzen Sie `Suggest new` mit Hint oder markierter Passage.

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

Mit `Hide reviewed documents` blenden Sie bereits geprüfte Dokumente aus. Dann bleiben nur ähnliche Dokumente übrig, die noch zu bearbeiten sind.

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

## 10a. Review-Modus (vor und zurück in der Arbeitsliste)

Wenn Sie ein Dokument aus einer gefilterten Liste (z. B. `Unreviewed` oder `Needs review`) öffnen, merkt sich die Oberfläche die Reihenfolge der Liste. In der Detailansicht können Sie dann direkt weiterblättern:

- `Previous` / `Next` mit Position (z. B. `3 / 20+`).
- Tastatur: `k` = vorheriges, `j` = nächstes Dokument. Die Tasten sind beim Tippen in Eingabefeldern ohne Wirkung.
- `Auto-advance`: springt nach `Mark reviewed` oder `Writeback` automatisch zum nächsten Dokument, aber nur, wenn das Dokument danach tatsächlich `reviewed` ist.
- Die aktive Tab (z. B. `Suggestions`) und der Rückweg zur Liste bleiben erhalten.
- Das Weiterblättern geht über Listenseiten hinaus. Weitere Dokumente werden im Hintergrund nachgeladen, das nächste Dokument wird vorab geholt.
- Bei `Unreviewed` und `Needs review` verschwinden geprüfte Dokumente aus der Liste. Darum wird dort nur vorwärts nachgeladen und nicht rückwärts geblättert.
- Mit `Running only` ist kein Nachladen möglich, weil sich der Zustand laufend ändert.
- Dokumente, die nicht aus der Liste geöffnet wurden (direkter Link, `Similar`), zeigen keine Navigation.

Karten und Tabellenzeilen sind echte Links. Mit Strg/Cmd-Klick oder Mittelklick öffnen Sie ein Dokument in einem neuen Tab.

## 11. PDF-Viewer

Unterhalb der Tabs befindet sich der PDF-Viewer.

Er unterstützt die Arbeit mit:

- Seitenwechseln,
- Sprüngen aus Seitentexten,
- Sprüngen aus Suche oder Chat,
- und Hervorhebungen, wenn Treffer mit Seitenbezug vorliegen.

## 12. Empfehlenswerter Prüfablauf für ein einzelnes Dokument

1. `Metadata` ansehen.
2. `Suggestions` prüfen (auch `Candidates from text`) und nur gute Vorschläge über `Apply selected` lokal übernehmen.
3. Bei Unsicherheit `Pages` oder `Text & quality` öffnen.
4. Für Rückfragen `Similar` oder `Chat` nutzen.
5. In `Operations` offene Verarbeitung kontrollieren.
6. Dokument lokal als reviewed markieren.
7. Später gesammelt über `Writeback` nach Paperless schreiben.

Weiter mit: [Suche und Chat](./03-suche-und-chat.md)

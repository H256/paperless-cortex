# Glossar und Statusbegriffe

Zurück zur Übersicht: [Benutzerhandbuch](./README.md)

## 1. Grundbegriffe

### Paperless

Das führende DMS. Änderungen werden dort erst sichtbar, wenn `Writeback` ausgeführt wurde.

### Local overrides

Lokale Metadaten weichen vom Stand in Paperless ab. Das ist ein Hinweis auf noch nicht zurückgeschriebene Änderungen.

### Writeback

Kontrollierte, manuelle Rückschreibung lokaler Änderungen nach Paperless.

### Review

Lokaler Prüfstatus eines Dokuments. Er dient der internen Arbeitsorganisation.

## 2. Review- und Arbeitsstatus

### Unreviewed

Das Dokument wurde lokal noch nicht als geprüft markiert.

### Needs review

Es gibt offene lokale Änderungen oder einen Prüfbedarf. Das Dokument sollte vor einem Writeback noch einmal angeschaut werden.

### Reviewed

Das Dokument wurde lokal als geprüft markiert. Das bedeutet nicht automatisch, dass die Änderungen schon nach Paperless geschrieben wurden.

## 3. Dokument-Badges in der Liste

### Embeddings

Vektordaten für Suche und Chat sind vorhanden oder fehlen noch.

### Vision OCR

Zusätzliche OCR auf Seitenebene wurde erzeugt oder fehlt.

### Suggestions (paperless)

KI-Vorschläge auf Basis der vorhandenen Paperless-OCR wurden erzeugt.

### Suggestions (vision)

KI-Vorschläge auf Basis von Vision-OCR wurden erzeugt.

### Local cache

Das Dokument liegt lokal in der Anwendungsdatenbasis vor. Fehlt dieser Zustand, kann eine Synchronisation oder lokale Wiederherstellung nötig sein.

## 4. Quellenbegriffe

### paperless_ocr

Textbasis aus Paperless bzw. dessen OCR-/Inhaltsdaten.

### vision_ocr

Zusätzliche, lokal erzeugte OCR auf Seitenbasis, nützlich bei schwierigen Scans.

### pdf_text

Text, der direkt aus dem PDF stammt, wenn dort bereits maschinenlesbarer Inhalt eingebettet ist.

### similar_docs

Hinweise oder Vorschläge, die aus ähnlichen Dokumenten abgeleitet werden.

## 5. Pipeline-Begriffe

### Sync

Abgleich lokaler Dokumente mit Paperless. Dabei werden neue Dokumente geholt und entfernte oder geänderte Zustände erkannt.

### Vision OCR

OCR-Verarbeitung pro Seite auf Basis eines Vision-Modells oder eines entsprechenden OCR-Pfads.

### Baseline embeddings

Embeddings aus der normalen Textbasis, meist `paperless_ocr`.

### Vision embeddings

Embeddings aus der Vision-OCR-Textbasis.

### Suggestions

KI-generierte Vorschläge für Dokumentfelder wie Titel, Datum, Korrespondent, Tags oder Notiz.

### Field variants

Alternative Werte für ein einzelnes Feld, meist zur feineren Auswahl eines Vorschlags.

### Similarity index

Vektorbasierte Ähnlichkeitsbasis für ähnliche Dokumente und Dublettenerkennung.

### Page notes

Seitenspezifische Notizen oder Analyseergebnisse für große Dokumente.

### Hierarchical summary

Mehrstufig erzeugte Zusammenfassung, besonders für große Dokumente.

## 6. Queue- und Laufstatus

### Pending

Eine Aufgabe wurde eingeplant, aber noch nicht ausgeführt.

### Running

Die Aufgabe wird aktuell vom Worker bearbeitet.

### Retrying

Die Aufgabe ist zuvor fehlgeschlagen und wird erneut versucht.

### Completed / Done

Die Aufgabe wurde erfolgreich abgeschlossen.

### Failed

Die Aufgabe ist fehlgeschlagen.

### Delayed retry

Die Aufgabe wartet noch auf ihren nächsten Wiederholungszeitpunkt.

### Dead-letter queue (DLQ)

Sammelbereich für Aufgaben, die auch nach Wiederholungen nicht erfolgreich waren.

## 7. Continue-processing-Strategien

### balanced

Standardstrategie mit gutem Verhältnis aus Abdeckung und Aufwand.

### paperless_only

Nutzt bevorzugt nur die Paperless-basierte Pipeline.

### vision_first

Bevorzugt Vision-basierte Verarbeitung.

### max_coverage

Versucht die breiteste Abdeckung über mehrere Quellen hinweg.

## 8. Warum diese Begriffe wichtig sind

Viele Bedienentscheidungen hängen davon ab, ob ein Dokument:

- nur lokal geändert wurde,
- noch Verarbeitungslücken hat,
- technisch blockiert ist,
- oder fachlich schon freigegeben wurde.

Wenn Sie diese Begriffe sicher lesen können, finden Sie schneller den richtigen Bereich in der Oberfläche.

Weiter mit: [Troubleshooting und FAQ](./08-troubleshooting-und-faq.md)

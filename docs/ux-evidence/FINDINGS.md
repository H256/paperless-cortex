# UX-Befunde: vom neuen Dokument zum korrekten Writeback

Stand: 2026-10-31. Datenbasis: `suggestion_audit` und `task_runs` von Januar bis Oktober 2026, nur lesend abgefragt.
Kennzeichnung: **[G]** gemessen, **[A]** abgeleitet, **[V]** vermutet.

## Nachrechnen

```bash
backend/.venv/Scripts/python.exe docs/ux-evidence/run_sql.py docs/ux-evidence/01_funnel.sql
```

Dasselbe gilt für `02_review_behavior.sql`, `03_backlog_and_trend.sql` und `05_stale_runs.sql`. Die Ausgaben liegen als `*.out.txt` daneben.
Der Browserlauf steht in `frontend/e2e-ux/audit.spec.ts`, das Ergebnis in `04_a11y_stubbed.json`.

## Kernaufgaben und Funnel

Aus den Daten abgeleitet **[A]**:

1. Vorschläge erzeugen
2. Felder prüfen und übernehmen
3. Falschen Vorschlag korrigieren (Neugenerierung oder Override)
4. Zurückschreiben
5. Hängende oder fehlgeschlagene Verarbeitung erkennen

Funnel **[G]**: 2239 Dokumente, 2239 mit Vorschlag, 857 mit Nutzeraktion (38 %), 855 zurückgeschrieben.
Der Abbruch liegt also fast vollständig zwischen Vorschlag und Review. Nach dem Review läuft der Writeback praktisch immer durch.

## Befunde, nach Kosten sortiert

### 1. Niemand weiß, ob schnelleres Review auch korrektes Review ist

- **Beleg [G]:** Seit dem 2026-10-11 sank die Zeit pro Dokument (gewichtet) von 110,5 auf 84,9 s. Gleichzeitig sank die Korrekturquote von 20,5 % auf 8,5 %. 81 % der geprüften Dokumente (698 von 857) wurden ohne Korrektur übernommen.
- **Ursache [A]:** Beide Zahlen passen zu besseren Vorschlägen und ebenso zu blindem Durchwinken. Die Daten trennen das nicht, weil das Audit bei `apply_to_document:*` keinen Wert speichert und `document_suggestions` vermutlich bei jeder Neugenerierung überschrieben wird.
- **Hypothese:** In der Stichprobe „ohne Korrektur“ sind höchstens 5 % der Dokumente in einem Feld falsch. Über 10 % gilt die Geschwindigkeit als auf Kosten der Korrektheit erkauft. Die Hypothese ist widerlegt, wenn die Quote nach dem 2026-10-11 höher liegt als davor.
- **Kleinste Änderung:** Blindprüfung der Stichprobe unten, und ab sofort den angenommenen Wert im Audit speichern. Keine UI-Änderung.
- **Einschränkung:** Nach dem Stichtag gibt es nur 6 Sitzungen mit 145 Dokumenten, und mehrere Funktionen kamen gleichzeitig. Ein Kausalschluss ist nicht möglich.

### 2. 62 % der Dokumente sind ungeprüft, und das Review läuft in Schüben

- **Beleg [G]:** 1382 Dokumente sind offen. Medianzeit vom Vorschlag bis zur ersten Übernahme: 23 Tage. Dokumente pro Monat: 375 im Februar, 5 im September, 142 im Oktober. Median je Sitzung: 2 Dokumente.
- **Kosten [A]:** Bei 66 bis 85 s pro Dokument sind das rund 25 bis 33 Stunden Restarbeit.
- **Ursache [V]:** Jedes Dokument kostet gleich viel Aufmerksamkeit, egal wie sicher der Vorschlag ist. Die Warteschlange ist nicht nach Risiko sortiert.
- **Hypothese:** Werden Dokumente mit übereinstimmenden Quellen gebündelt, sinkt deren Zeit um mindestens 40 %, ohne dass die Fehlerquote aus Befund 1 steigt.
- **Kleinste Änderung:** Erst nach Befund 1. Ein Preset „Quellen stimmen überein“, kein neuer Massenknopf.

### 3. Korrespondent ist das Feld, dem am wenigsten zu trauen ist

- **Beleg [G]:** Eingriffe (Neugenerierungen plus Overrides) je Dokument mit übernommenem Feld: Korrespondent 123/147 = 0,84, Tags 166/701 = 0,24, Datum 24/144 = 0,17, Titel 102/760 = 0,13.
- **Ursache [V]:** Das Modell kennt die vorhandene Korrespondentenliste möglicherweise zu schlecht, oder falsche Treffer lassen sich schwer beurteilen. Die Issues #373 und #359 zeigen, dass das Thema schon bearbeitet wurde.
- **Einschränkung:** Korrespondent und Datum werden nur bei 17 % der geprüften Dokumente übernommen. Ob sie sonst schon stimmen oder übersehen werden, ist offen und Teil der Blindprüfung.
- **Hypothese:** Zeigt die Vorschlagszeile die Fundstelle im Dokument und den Abgleich mit dem bestehenden Korrespondenten, sinken die Eingriffe je Dokument auf unter 0,4.
- **Kleinste Änderung:** Nur diese eine Zeile im Korrespondentenfeld.

### 4. 56 tote Tasks gelten im Frontend weiter als aktiv

- **Beleg [G]:** 54 Läufe stehen auf `retrying`, 2 auf `running`, alle seit über einem Tag, die ältesten seit Februar. 55 davon wurden durch einen späteren abgeschlossenen Lauf überholt.
- **Beleg [A]:** `useDocumentProcessingState.ts:96-102` und `useRunningTaskProgress.ts:24` werten jede solche Zeile ohne Altersgrenze als aktiv. In der geprüften Queue-Route und `task_runs.py` fand ich keine Bereinigung.
- **Noch nicht verifiziert:** Ob ein Dokument dadurch sichtbar dauerhaft „in Arbeit“ wirkt, wurde nicht in der echten App beobachtet. `useRunningTaskProgress` lädt nur 500 Zeilen, ältere fallen dort vermutlich heraus.
- **Hypothese:** Nach der Bereinigung gibt es 0 aktive Läufe, die älter als ein Tag oder überholt sind.
- **Kleinste Änderung:** Überholte Läufe beim Abschluss eines neueren Laufs oder beim Worker-Start schließen. Vorab Dokument 1 einer solchen Zeile im Browser ansehen.

### 5. Die Dokumentliste hat Formularfelder ohne Namen und eine lange Tab-Strecke

- **Beleg [G], gestubbte API:** Auf `/documents` meldet axe 5 × `select-name` und 1 × `label` (beide kritisch) sowie `color-contrast`. Auf dem Desktop kommt 2 × `nested-interactive` dazu. Bis zur ersten Dokumentzeile sind es 36 Tab-Schritte auf dem Desktop und 33 mobil. Verlust des Fokusrings wurde nicht festgestellt.
- **Hypothese:** Mit Skip-Link und benannten Feldern sinkt die Zahl auf höchstens 3 Schritte und axe meldet dort 0 kritische Verstöße.
- **Kleinste Änderung:** Skip-Link und `aria-label` an den Filtern.
- **Einschränkung:** Die Tabelle und der Review-Bereich mit echten Vorschlägen wurden so nicht geprüft, weil die Stubs keine Vorschläge enthalten.

## Was wir nicht tun sollten

- **Mobile-Polish als Hauptfokus:** Die Daten stützen ihn nicht. Es gibt keine Geräteinformation, und auf den 4 geprüften gestubbten Routen tritt bei 375 px kein horizontaler Überlauf auf. Erst die Nutzung erfassen, sonst bleibt die Priorität eine Annahme.
- **Weitere Beschleuniger für das Review vor Befund 1:** Sie könnten Fehler schneller durchlassen.
- **UI-Arbeit wegen der 3554 `similarity_index`-Fehler:** Sie stammen alle aus dem März, und 3537 davon haben den Typ `VECTOR_CHUNKS_MISSING`. Das ist ein abgeschlossener Einzelfall.

## Nicht durchgeführt

- **Echte Aufgabenzeiten mit Playwright und KLM-Vergleich:** Die App müsste laufen. Mit der `.env` hinge sie an der echten Datenbank und an Paperless, die Freigabe gilt aber nur für Lesezugriffe. Die Zeiten oben stammen aus Audit-Abständen und sind eine Näherung.
- **Gedrosselter Lauf und Think-Aloud:** Beides braucht ebenfalls die echte App, Think-Aloud zusätzlich Personen.
- **Blindprüfung und Cohens Kappa:** Das Urteil muss von Menschen kommen, möglichst von zweien.

## Grenzen der Messung

- Sitzungen sind Ereignisfolgen mit Abständen unter 30 Minuten. Das ist eine Heuristik.
- Die Prüfzeit des jeweils ersten Dokuments einer Sitzung ist nicht enthalten, die Zeiten liegen also eher zu niedrig.
- Sammelübernahmen lassen sich nicht von Einzelprüfungen trennen und können „ohne Korrektur“ erhöhen.
- Neugenerierungen sind nur ein indirektes Signal für Misstrauen, und die Daten stammen vermutlich von sehr wenigen Nutzern.

## Stichprobe für die Blindprüfung (fester Seed)

Pro Dokument in Paperless jedes Feld gegen das Original prüfen und richtig oder falsch notieren, ohne die Gruppe vorher zu kennen. Die Listen dazu mischen.

- **Ohne Korrektur (40):** 979, 2023, 1826, 833, 1973, 1768, 1566, 1914, 427, 1771, 1410, 334, 2193, 150, 598, 1522, 1916, 2099, 2178, 910, 944, 44, 1761, 961, 1523, 568, 311, 1571, 99, 954, 403, 660, 793, 1817, 2199, 1723, 1722, 2022, 906, 1737
- **Mit Korrektur (20):** 1934, 89, 1853, 2028, 1899, 80, 657, 133, 1920, 1924, 84, 484, 2167, 1950, 1988, 1923, 911, 431, 1781, 1992

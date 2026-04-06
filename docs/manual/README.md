# Benutzerhandbuch zur Oberfläche

Diese Anleitung beschreibt die Bedienung der Weboberfläche von Paperless Intelligence aus Sicht von Anwendern. Sie konzentriert sich auf die tatsächlichen Arbeitsbereiche der UI und auf typische Abläufe im Alltag.

Wichtige Grundsätze der Anwendung:

- Paperless bleibt das führende System.
- Paperless Intelligence erzeugt lokale Analysen, OCR-Erweiterungen, Embeddings, Vorschläge und Hilfswerkzeuge.
- Änderungen werden nicht automatisch nach Paperless zurückgeschrieben.
- Writeback ist immer ein bewusster, manueller Schritt.

## Inhalt

- [Schnellstart und Grundprinzipien](./01-schnellstart-und-grundprinzipien.md)
- [Dokumentliste und Detailansicht](./02-dokumente-und-detailansicht.md)
- [Suche und Chat](./03-suche-und-chat.md)
- [Verarbeitung, Queue und Writeback](./04-verarbeitung-queue-und-writeback.md)
- [Dashboard, Logs und Operations](./05-dashboard-logs-und-operations.md)
- [Typische Arbeitsabläufe](./06-typische-arbeitsablaeufe.md)
- [Glossar und Statusbegriffe](./07-glossar-und-statusbegriffe.md)
- [Troubleshooting und FAQ](./08-troubleshooting-und-faq.md)
- [Feldregeln](./09-feldregeln.md)
- [Review-Regeln](./10-review-regeln.md)
- [Problemfälle und Sonderlagen](./11-problemfaelle-und-sonderlagen.md)
- [Similar-Workflow](./12-similar-workflow.md)
- [Team-Policy](./13-team-policy.md)
- [Tages-Checkliste](./14-tages-checkliste.md)
- [Admin und Betrieb](./15-admin-und-betrieb.md)
- [Settings und Live-Model-Provider](./16-settings-und-live-model-provider.md)

## Für wen diese Anleitung gedacht ist

Die Anleitung ist für Benutzer gedacht, die:

- Dokumente sichten und prüfen,
- KI-Vorschläge übernehmen,
- fehlende Verarbeitung nachstarten,
- Such- und Chatfunktionen nutzen,
- kontrolliert nach Paperless zurückschreiben,
- oder Betriebszustände der Anwendung nachvollziehen wollen.

## Empfohlene Lesereihenfolge

1. [Schnellstart und Grundprinzipien](./01-schnellstart-und-grundprinzipien.md)
2. [Dokumentliste und Detailansicht](./02-dokumente-und-detailansicht.md)
3. [Verarbeitung, Queue und Writeback](./04-verarbeitung-queue-und-writeback.md)
4. [Suche und Chat](./03-suche-und-chat.md)
5. [Dashboard, Logs und Operations](./05-dashboard-logs-und-operations.md)
6. [Typische Arbeitsabläufe](./06-typische-arbeitsablaeufe.md)
7. [Glossar und Statusbegriffe](./07-glossar-und-statusbegriffe.md)
8. [Troubleshooting und FAQ](./08-troubleshooting-und-faq.md)
9. [Feldregeln](./09-feldregeln.md)
10. [Review-Regeln](./10-review-regeln.md)
11. [Problemfälle und Sonderlagen](./11-problemfaelle-und-sonderlagen.md)
12. [Similar-Workflow](./12-similar-workflow.md)
13. [Team-Policy](./13-team-policy.md)
14. [Tages-Checkliste](./14-tages-checkliste.md)
15. [Admin und Betrieb](./15-admin-und-betrieb.md)
16. [Settings und Live-Model-Provider](./16-settings-und-live-model-provider.md)

## Empfohlener Tagesablauf in Kurzform

1. Öffnen Sie `Documents`.
2. Filtern Sie auf unreviewte oder noch nicht analysierte Dokumente.
3. Öffnen Sie ein Dokument und ergänzen Sie fehlende Felder.
4. Führen Sie den `Writeback` aus, sobald das Dokument fachlich sauber ist.
5. Wechseln Sie zu `Similar` und prüfen Sie dort weitere noch nicht reviewed Dokumente.
6. Arbeiten Sie sich so Stück für Stück durch die Liste.

Dieser dokumentweise Similar-Workflow ist ausführlich in [Typische Arbeitsabläufe](./06-typische-arbeitsablaeufe.md) beschrieben.

## Begriffe

- `Documents`: zentrale Arbeitsliste aller synchronisierten Dokumente.
- `Document Detail`: Detailansicht eines einzelnen Dokuments.
- `Continue processing`: sammelt fehlende Verarbeitungsschritte und stellt sie gesammelt in die Queue.
- `Queue`: zeigt geplante und laufende Worker-Aufgaben.
- `Logs`: zeigt Task-Runs, Fehlerarten und Verlaufsdaten.
- `Writeback`: Vorschau und kontrollierte Rückschreibung nach Paperless.

## Hinweis zum Gültigkeitsbereich

Diese Anleitung beschreibt die aktuell im Projekt vorhandene Oberfläche. Einzelne Detailtexte, Farben oder Reihenfolgen können sich später ändern, die grundlegenden Arbeitsabläufe bleiben aber gleich.

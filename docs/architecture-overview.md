# Architekturüberblick

Diese Seite beschreibt die technische Architektur von Paperless Intelligence auf hoher Ebene.

## 1. Zielbild

Die Anwendung ist eine lokale Intelligenzschicht vor oder neben Paperless-ngx.

Wichtige Architekturprinzipien:

- Paperless bleibt das führende System.
- AI-Verarbeitung geschieht lokal oder über konfigurierbare Modellendpunkte.
- Ergebnisse werden zunächst nur lokal gespeichert.
- Rückschreiben nach Paperless ist immer ein bewusster, manueller Schritt.
- Verarbeitung soll beobachtbar, wiederholbar und bei großen Dokumenten robust sein.

## 2. Hauptkomponenten

### Paperless-ngx

Quelle für:

- Dokumentmetadaten
- Dokumentdateien
- bestehende OCR-/Inhaltsdaten

Paperless wird synchronisiert, aber nicht automatisch verändert.

### Backend API

Das Backend ist die zentrale Orchestrierungsschicht.

Es ist zuständig für:

- Sync mit Paperless
- lokale Datenhaltung
- OCR-/Text-/Embedding-/Suggestion-Orchestrierung
- Queue- und Worker-Steuerung
- Such- und Chat-Endpunkte
- Writeback-Vorschau und Writeback-Ausführung

### Frontend

Das Frontend ist eine Vue-basierte Weboberfläche.

Es ist zuständig für:

- Review-Workflow
- Dokumentliste und Detailansicht
- Suche und Chat
- Queue-/Log-/Operations-Ansichten
- kontrollierten Writeback

### Datenbank

Die relationale Datenbank speichert den lokalen Arbeitsstand, zum Beispiel:

- synchronisierte Dokumentdaten
- lokale Änderungen
- Vorschläge
- OCR-Zusatzdaten
- Task-Runs und Audit-/Statusinformationen

### Redis / Queue

Redis dient für:

- Queueing
- Worker-Koordination
- Retry-/Backoff-Abläufe
- Laufzustände und Sperren

### Worker

Der Worker verarbeitet Hintergrundaufgaben, etwa:

- Sync-Folgeschritte
- Vision OCR
- Embeddings
- Suggestions
- große Dokumentpfade
- Reprocess- und Bereinigungsjobs

### Vector Store

Der aktive Vektor-Store ist über eine Provider-Schicht abstrahiert.

Derzeit vorgesehen:

- Qdrant
- Weaviate

Die Anwendung verwendet diese Schicht für:

- semantische Suche
- Similarity
- chatgestützte Retrieval-Pfade

## 3. Datenfluss

Der typische Datenfluss ist:

1. Sync von Paperless
2. lokale Speicherung von Metadaten und Basistextebene
3. optional Vision OCR
4. Embeddings auf einer oder mehreren Textquellen
5. Suggestions
6. bei großen Dokumenten zusätzliche Seiten- und Summary-Schritte
7. lokale Review-Entscheidung
8. manueller Writeback

## 4. Schichtenmodell

Vereinfacht lässt sich das System so lesen:

- `frontend/`
  UI und Bedienlogik
- `backend/app/routes/`
  HTTP-Endpunkte
- `backend/app/services/`
  eigentliche Fach- und Orchestrierungslogik
- `backend/app/`
  Konfiguration, App-Start, Worker, Infrastruktur
- DB / Redis / Vector Store
  Persistenz- und Laufzeitdienste

## 5. Warum die Service-Schicht wichtig ist

Das Projekt bewegt sich aktuell bewusst in Richtung stärkerer Trennung von:

- Route-Logik
- Service-Orchestrierung
- Provider- und Infrastrukturdetails

Ziele dieser Trennung:

- kleinere Route-Module
- besser testbare Orchestrierung
- weniger Kopplung an konkrete Vector-Backends
- robustere Weiterentwicklung von Queue, Writeback und Pipeline

## 6. Sync und lokaler Zustand

Paperless bleibt Source of Truth, aber lokal entsteht ein eigener Arbeitszustand.

Dieser lokale Zustand umfasst:

- Review-Status
- lokale Feldänderungen
- Suggestions
- technische Verarbeitungszustände
- Writeback-Kandidaten

Dadurch können Benutzer Dokumente prüfen, ohne sofort Daten in Paperless zu verändern.

## 7. Queue- und Verarbeitungskonzept

Das System trennt bewusst zwischen:

- synchroner UI-Bedienung
- und asynchroner Dokumentverarbeitung

Vorteile:

- große Dokumente blockieren nicht die Oberfläche
- Fehlversuche lassen sich sauber retryn
- Task-Runs sind sichtbar
- Verarbeitung kann dokumentweise oder gesammelt nachgestartet werden

## 8. Such- und Chatarchitektur

Suche und Chat basieren nicht nur auf einem einzelnen Textlayer.

Je nach Konfiguration und Dokumentzustand können folgende Quellen relevant sein:

- `paperless_ocr`
- `vision_ocr`
- `pdf_text`

Der Chat nutzt Retrieval mit Belegen und kann je nach UI-Konfiguration Gesprächskontext mitführen.

## 9. Writeback-Architektur

Writeback ist absichtlich zweistufig:

1. lokale Änderungen sammeln und prüfen
2. explizit gegen Paperless ausführen

Diese Trennung reduziert das Risiko, ungeprüfte KI-Ergebnisse direkt produktiv zu machen.

## 10. Vektor-Store-Abstraktion

Die Anwendung bereitet Vector Storage hinter Adaptergrenzen vor, damit Aufrufer in Routes und Services nicht direkt an Qdrant oder Weaviate gekoppelt sind.

Das ist wichtig für:

- Provider-Wechsel
- Tests
- robustere Infrastrukturtrennung

## 11. Große Dokumente

Große Dokumente werden nicht wie kleine Standarddokumente behandelt.

Es gibt zusätzliche Pfade für:

- Seitennotizen
- hierarchische Zusammenfassungen
- beobachtbare und resumierbare Verarbeitung

Das verhindert, dass große Eingaben denselben simplen Pipeline-Annahmen folgen wie kurze Belege.

## 12. Betriebsphilosophie

Bei technischen Problemen gilt architektonisch:

- erst den Zustand sichtbar machen
- dann gezielt eingreifen
- destruktive Maßnahmen zuletzt

Deshalb gibt es eigene Ansichten für:

- Queue
- Logs
- Operations

## 13. Verwandte Dokumentation

- [docs/manual/README.md](E:\workspace\python\paperless-intelligence\docs\manual\README.md)
- [docs/manual/15-admin-und-betrieb.md](E:\workspace\python\paperless-intelligence\docs\manual\15-admin-und-betrieb.md)
- [README.md](E:\workspace\python\paperless-intelligence\README.md)

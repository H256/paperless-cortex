# Settings und Live-Model-Provider

Zurück zur Übersicht: [Benutzerhandbuch](./README.md)

Diese Seite beschreibt die Oberfläche `Settings`. Dort können Model-Provider zur Laufzeit geändert werden, ohne Container oder Prozesse neu zu starten.

## 1. Wofür die Seite gedacht ist

Die Settings-Seite dient dazu, die aktiven Provider für diese Rollen live zu ändern:

- `Text`
- `Chat`
- `Embedding`
- `Vision / OCR`

Typische Anwendungsfälle:

- anderes Modell testen
- anderen Base-URL-Endpunkt verwenden
- API-Key für einen Provider hinterlegen oder austauschen
- Modellliste eines Endpunkts neu laden

## 2. Was dort geändert werden kann

Pro Rolle gibt es typischerweise:

- `URL`
- `Model`
- `API Key`
- `Refresh models`
- `Clear key`

Zusätzlich zeigt die Seite den aktuellen Runtime-Zustand an.

## 3. Wichtiger Unterschied zu `.env`

Die Settings-Seite schreibt Laufzeit-Overrides in den lokalen Zustand der Anwendung.

Das bedeutet:

- die Änderung wirkt zur Laufzeit,
- neue Tasks verwenden die neuen Werte,
- laufende Tasks behalten ihren Startzustand,
- und `.env` bleibt weiterhin die Basis-Konfiguration.

## 4. Verhalten beim API-Key-Feld

Das API-Key-Feld ist bewusst vorsichtig gestaltet.

Wichtig:

- der gespeicherte Key wird nicht im Klartext angezeigt,
- das Feld bleibt verborgen, bis Sie ausdrücklich `Set key` oder `Replace key` wählen,
- wenn bereits ein Key hinterlegt ist und Sie das Feld leer lassen, bleibt der bestehende Key erhalten,
- `Clear key` löscht den gespeicherten Key bewusst,
- ein leeres Eingabefeld ersetzt einen bestehenden Key nicht automatisch.

Das schützt vor versehentlichem Überschreiben oder Löschen bei normalen Settings-Änderungen.

## 5. Modelle neu laden

Mit `Refresh models` versucht die Anwendung, vom eingetragenen Endpunkt eine Modellliste zu laden.

Das ist nützlich, wenn:

- Sie eine neue Base URL eingetragen haben,
- Sie einen anderen API-Key testen,
- oder Sie die verfügbaren Modelle des Providers sehen möchten.

## 6. Wann Änderungen gespeichert werden

Die Seite zeigt pro Karte, ob ungespeicherte Änderungen vorliegen.

Erst `Save changes` speichert die Laufzeit-Overrides.

Bis dahin bleiben die Änderungen lokal auf der Seite und wirken noch nicht global.

## 7. Voraussetzungen für API-Key-Speicherung

Damit API-Key-Overrides gespeichert werden können, muss `RUNTIME_SETTINGS_MASTER_KEY` gesetzt sein.

Wichtig:

- der Wert muss ein gültiger Fernet-Key sein,
- beliebiger Freitext reicht nicht,
- ohne gültigen Fernet-Key können verschlüsselte Laufzeit-Keys nicht sauber gespeichert werden.

Siehe dazu:

- [docs/config-reference.md](E:\workspace\python\paperless-intelligence\docs\config-reference.md)
- [`.env.example`](E:\workspace\python\paperless-intelligence\.env.example)
- [`.env.worker.example`](E:\workspace\python\paperless-intelligence\.env.worker.example)

## 8. Empfohlene sichere Arbeitsweise

1. Base URL setzen oder prüfen
2. Modell auswählen oder manuell eintragen
3. API-Key nur dann ersetzen, wenn das wirklich beabsichtigt ist
4. Modellliste aktualisieren
5. Änderungen speichern
6. danach Funktion über Search, Chat, OCR oder Verarbeitung prüfen

## 9. Wann diese Seite nicht der richtige Ort ist

Die Settings-Seite ist nicht für grundlegende Infrastrukturreparaturen gedacht.

Wenn Probleme eher systemisch wirken, prüfen Sie zuerst:

- `Queue`
- `Logs`
- `Operations`
- und die Basis-Konfiguration in `.env`

Weiter mit: [Admin und Betrieb](./15-admin-und-betrieb.md)

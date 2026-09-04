# Betrieb und Kommandozeile

[Projektübersicht und Schnellstart](../README.md) · [Dokumentationsübersicht](README.md)

Die folgenden Befehle werden bei nativer Installation mit aktivierter
Python-Umgebung im Projektverzeichnis ausgeführt. Für Container siehe
[Docker-Befehle](docker.md#status-manuelle-befehle-und-updates).
Nur eine Scheduler-Instanz darf dieselben Laufzeitdaten verwenden. Stoppe sie
vor schreibenden manuellen Befehlen und starte sie anschließend wieder.

## CLI

```text
wb-announcer --config config.yaml weather-update
wb-announcer --config config.yaml run
wb-announcer --config config.yaml serve --interval-seconds 60
wb-announcer --config config.yaml generate-half-hour
wb-announcer --config config.yaml generate-full-hour
wb-announcer --config config.yaml generate-location wittstock
wb-announcer --config config.yaml generate-all
wb-announcer --config config.yaml generate-time wittstock full_hour --at 2026-08-18T14:00:00+02:00
wb-announcer --config config.yaml cleanup-generated
wb-announcer --config config.yaml cleanup-generated --older-than-days 30
wb-announcer --config config.yaml status
```

`run` ist für den regelmäßigen systemd-Aufruf vorgesehen. Die Anwendung prüft
selbst, welche Ansagen innerhalb des konfigurierten Vorbereitungshorizonts liegen.
`serve` führt sofort einen Durchlauf aus und wartet anschließend jeweils die
angegebene Anzahl Sekunden (Standard: 60). Durchläufe laufen nacheinander;
Fehler einzelner Ansagen werden weiterhin über den Scheduler erneut versucht.
SIGTERM und SIGINT beenden den Dauerbetrieb nach dem laufenden Durchlauf;
während der Wartezeit wird sofort beendet. Konfigurationsänderungen erfordern
einen Neustart von `serve`.
Manuelle Generierungsbefehle behandeln alle Standorte unabhängig und liefern pro
Ansage einen Erfolg oder Fehler zurück; bei Erfolg werden alle konfigurierten
Ausgabeformate veröffentlicht.

`status` gibt den Zustand als JSON aus. Bei einem neuen Start mit leerem
Wettercache ist `degraded` zunächst normal. `generate-all` erzeugt beide
Ansagearten sofort für die jeweils nächsten Wiedergabezeitpunkte und lädt bei
Bedarf Wetterdaten nach. `serve` erzeugt dagegen nur innerhalb des
Vorbereitungshorizonts fällige Ansagen.

## Ausgabe

Bei einer Ansage für Wittstock entstehen beispielsweise:

```text
var/generated/wittstock/2026-08-18/14-00-full.mp3
var/generated/wittstock/2026-08-18/14-00-full.flac
var/generated/wittstock/2026-08-18/14-00-full.opus
var/public/wittstock/full-hour.mp3
var/public/wittstock/full-hour.flac
var/public/wittstock/full-hour.opus
```

Nur die stabilen Dateien unter `public_dir` werden durch Caddy oder nginx
ausgeliefert. Python stellt selbst keinen öffentlichen Webserver bereit.

Mit `output.generated_retention_days` kann eine Aufbewahrungsdauer für Dateien
unter `generated_dir` festgelegt werden. Vor jedem `run` löscht Weatherbox
Dateien, deren letzter Änderungszeitpunkt weiter zurückliegt, und entfernt danach
leere Unterverzeichnisse. Der Wert `30` entspricht dabei 30 Tagen. Fehlt die
Einstellung oder ist sie `null`, ist die automatische Bereinigung deaktiviert.
`cleanup-generated` löst die Bereinigung manuell aus; mit
`--older-than-days` lässt sich die konfigurierte Frist einmalig überschreiben.
Dateien unter `public_dir` werden dabei nicht verändert.

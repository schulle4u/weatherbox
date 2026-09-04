# Dokumentation

Für einen ersten Start genügt die [Projekt-README](../README.md).
Hier stehen die Details zum Anpassen und Betreiben von Weatherbox.

| Thema | Inhalt |
| --- | --- |
| [Installation und Linux-Dienst](installation.md) | Native Installation, Windows, systemd und HTTP-Auslieferung |
| [Docker](docker.md) | Compose, persistente Daten, Updates, eigene Dateien und Piper |
| [Konfiguration](configuration.md) | Aufbau der YAML-Datei, Standorte, Wetterquellen, Stimmen und Audio |
| [Templates und Sprachen](templates.md) | Ansagetexte, alle Platzhalter und eigene Sprachdateien |
| [Betrieb und Kommandozeile](operations.md) | Manuelle Erzeugung, Dauerbetrieb, Status und Aufbewahrung |
| [Entwicklung](development.md) | Entwicklungsinstallation, Tests und Architektur |

Konfigurationsvorlagen zum Kopieren:

- [Schnellstart](config.quickstart.yaml): Open-Meteo und gTTS, ohne Modelle oder Jingles.
- [Umfangreiches Beispiel](config.example.yaml): mehrere Wetterquellen, Piper-Fallback und Audioelemente; vor Verwendung anpassen.
- [Docker-Beispiel](../deploy/docker/config.example.yaml): Containerpfade und lokaler eSpeak-Fallback.

Die ausführliche `config.example.yaml` liegt jetzt in `docs/`.
Ausführbare Deployment-Dateien bleiben unter `deploy/` beziehungsweise im
Projektverzeichnis: [systemd-Service](../deploy/systemd/weatherbox.service),
[systemd-Timer](../deploy/systemd/weatherbox.timer),
[Caddy-Beispiel](../deploy/Caddyfile.example), [Compose](../compose.yaml) und
[Dockerfile](../Dockerfile).

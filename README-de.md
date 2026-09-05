# Weatherbox

[English](README.md) | Deutsch

Weatherbox erstellt automatisch gesprochene oder statische Wetterberichte für deine Standorte –
zum Beispiel für ein Webradio oder einen Raspberry Pi als Abspielgerät.
Die Ansagen werden zur vollen und halben Stunde vorbereitet und als fertige
Audio- oder HTML-Dateien bereitgestellt. Du spielst oder zeigst sie mit deiner
eigenen Radioautomation, einem Audioplayer oder Browser. Bereits
heruntergeladene Ansagen bleiben auch bei unterbrochener Internetverbindung
verfügbar.

Du kannst mehrere Orte einrichten, deutsche oder englische Ansagetexte verwenden
und auf Wunsch eigene Intros, Outros und Hintergrundmusik hinzufügen.
Wetterdaten kommen von Open-Meteo und/oder dem Deutschen Wetterdienst;
Sprachausgabe ist über gTTS, Piper oder eSpeak NG möglich.
Die Ausgabe erfolgt standardmäßig als MP3; weitere Audioformate und
lesefreundliche HTML-Assets sind verfügbar.

## Installation wählen

| Möglichkeit | Geeignet für |
| --- | --- |
| [Docker Compose](#schnellstart-mit-docker-compose) | Schneller Start und Dauerbetrieb mit wenigen Befehlen |
| [Direkt mit Python](#schnellstart-mit-python) | Lokal ausprobieren oder auf einem eigenen Rechner betreiben |
| [Linux-Dienst mit systemd](#als-linux-dienst-betreiben) | Automatischer Betrieb auf einem Server oder Raspberry Pi |

Lade das Repository herunter oder klone es mit Git. Die folgenden Befehle
werden im Projektverzeichnis ausgeführt:

```bash
git clone https://github.com/schulle4u/weatherbox.git
cd weatherbox
```

## Schnellstart mit Docker Compose

Voraussetzung: Docker mit Linux-Containern und Docker Compose.
Python und Audio-Werkzeuge sind bereits im Image enthalten.

1. **Konfiguration kopieren.**

   ```bash
   mkdir docker-config
   cp deploy/docker/config.example.yaml docker-config/config.yaml
   ```

2. **Standort anpassen.** Öffne `docker-config/config.yaml` und trage unter
   `locations` Ortsname, Breitengrad, Längengrad und Zeitzone ein.
   Zum Ausprobieren kannst du den Beispielort Wittstock übernehmen.

3. **Erste Ansagen erzeugen und Dauerbetrieb starten.**

   ```bash
   docker compose build --pull
   docker compose run --rm weatherbox generate-all
   docker compose up -d
   ```

Die MP3-Dateien liegen im Datenvolume unter
`/var/lib/weatherbox/public/wittstock/`. Zum Probehören kannst du sie kopieren:

```bash
docker compose cp weatherbox:/var/lib/weatherbox/public ./weatherbox-audio
```

Bei einer eigenen Standort-ID ersetzt du `wittstock` entsprechend.
Fortschritt und Fehler siehst du mit `docker compose logs -f weatherbox`.
Die Beispielkonfiguration benötigt Internetzugang für Wetterdaten und gTTS.
Details zu Updates, eigenen Stimmen und Dateizugriff stehen in der
[Docker-Anleitung](docs/docker.md).

## Schnellstart mit Python

Voraussetzung: Python ab 3.11 und FFmpeg einschließlich FFprobe im Suchpfad.
Die Befehle unten gelten für Linux/macOS; Hinweise zur Einrichtung und die
PowerShell-Befehle stehen in der [Installationsanleitung](docs/installation.md).

1. **Weatherbox installieren.**

   ```bash
   python3 -m venv .venv
   . .venv/bin/activate
   python -m pip install .
   ```

2. **Konfiguration kopieren und Standort anpassen.**

   ```bash
   cp docs/config.quickstart.yaml config.yaml
   ```

   Öffne `config.yaml` und passe unter `locations` Ortsname, Koordinaten und
   Zeitzone an. Zum Ausprobieren kannst du Wittstock übernehmen.
   Diese Vorlage braucht Internetzugang, aber keine zusätzlichen Stimmen oder
   Audiodateien.

3. **Ansagen erzeugen und anhören.**

   ```bash
   wb-announcer --config config.yaml generate-all
   ```

   Öffne anschließend `var/public/wittstock/full-hour.mp3` oder
   `half-hour.mp3` in deinem Audioplayer. Bei einer eigenen Standort-ID heißt
   das Unterverzeichnis entsprechend anders.

Für fortlaufende Erzeugung starte `wb-announcer --config config.yaml serve`.
Der Prozess läuft bis zum Beenden mit `Strg+C`; für automatischen Start nach
einem Neustart verwende Docker Compose oder systemd.

## Als Linux-Dienst betreiben

1. **Installieren:** Weatherbox mit Python unter `/opt/weatherbox` einrichten.
2. **Konfigurieren:** Dienstbenutzer, Konfiguration und Datenverzeichnis anlegen.
3. **Aktivieren:** Die mitgelieferten systemd-Dateien installieren und den Timer starten.

Die kopierbaren Befehle stehen in der
[Anleitung für den Linux-Dienst](docs/installation.md#linux-service-with-systemd).

## Ansagen verwenden und anpassen

Weatherbox erzeugt Audio- und optional HTML-Dateien; die zeitgesteuerte Nutzung
übernimmt dein Abspielgerät, deine Radioautomation oder ein Mensch in einer
Livesendung. Für den Abruf über das Netzwerk kannst du die Dateien über einen
[Webserver bereitstellen](docs/installation.md#serving-files-over-http).

Die technische Dokumentation ist auf Englisch verfügbar.
Weitere Einstellungen findest du in der [Dokumentationsübersicht](docs/README.md):
[Konfiguration und Stimmen](docs/configuration.md),
[Ansagetexte und Sprachen](docs/templates.md),
[Betrieb und Befehle](docs/operations.md) sowie
[Entwicklung](docs/development.md).

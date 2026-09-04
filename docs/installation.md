# Installation und Linux-Dienst

[Projektübersicht und Schnellstart](../README.md) · [Dokumentationsübersicht](README.md)

## Voraussetzungen für die native Installation

Benötigt werden Python ab 3.11 sowie `ffmpeg` und `ffprobe` im Suchpfad.
gTTS wird mit Weatherbox installiert. Die Schnellstart-Konfiguration nutzt
Open-Meteo und gTTS und benötigt ausgehenden Internetzugang.
Piper oder eSpeak NG werden nur benötigt, wenn sie als primäre oder
ersatzweise Sprachausgabe konfiguriert sind.

Beispiel für Debian/Ubuntu beziehungsweise Raspberry Pi OS mit Python ab 3.11:

```bash
sudo apt update
sudo apt install python3 python3-venv ffmpeg
```

Für den optionalen lokalen eSpeak-Provider zusätzlich `espeak-ng` installieren.
Unter macOS Python und FFmpeg über die bevorzugte Paketverwaltung installieren.
Unter Windows müssen die Verzeichnisse mit `ffmpeg.exe` und `ffprobe.exe` im
`PATH` stehen; alternativ lassen sich deren Pfade in der
[Konfiguration](configuration.md) unter `audio.ffmpeg` und `audio.ffprobe` setzen.

## Linux und macOS

Im heruntergeladenen oder geklonten Projektverzeichnis:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
cp docs/config.quickstart.yaml config.yaml
```

`config.yaml` öffnen und unter `locations` Name, Koordinaten und Zeitzone
anpassen. Dann die ersten Ansagen erzeugen:

```bash
wb-announcer --config config.yaml generate-all
```

Die Dateien liegen unter `var/public/<standort-id>/`. Für Dauerbetrieb
`wb-announcer --config config.yaml serve` starten; `Strg+C` beendet den Prozess.

## Windows mit PowerShell

Im Projektverzeichnis ist keine Aktivierung der virtuellen Umgebung nötig:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install .
Copy-Item docs/config.quickstart.yaml config.yaml
```

Auch hier zuerst den Standort in `config.yaml` anpassen. Anschließend:

```powershell
.\.venv\Scripts\wb-announcer.exe --config config.yaml generate-all
.\.venv\Scripts\wb-announcer.exe --config config.yaml serve
```

Der zweite Befehl startet den Dauerbetrieb im Terminal. Für Docker unter
Windows gelten die Schritte aus der [Docker-Anleitung](docker.md).

## Linux-Dienst mit systemd

Die mitgelieferten Units erwarten das Projekt unter `/opt/weatherbox`, eine
virtuelle Python-Umgebung unter `/opt/weatherbox/.venv`, die Konfiguration unter
`/etc/weatherbox/config.yaml` und schreibbare Daten unter `/var/lib/weatherbox`.
Die folgenden Schritte beschreiben eine neue Installation. Bei bestehenden
Installationen Benutzer und Verzeichnisse wiederverwenden und die vorhandene
Konfiguration beibehalten.

### 1. Programm und Dienstbenutzer einrichten

Nach Installation der oben genannten Systemabhängigkeiten und von Git:

```bash
sudo git clone https://github.com/schulle4u/weatherbox.git /opt/weatherbox
cd /opt/weatherbox
sudo python3 -m venv .venv
sudo .venv/bin/python -m pip install .
sudo useradd --system --user-group --home-dir /var/lib/weatherbox --no-create-home weatherbox
sudo install -d -m 0755 /etc/weatherbox
sudo install -d -o weatherbox -g weatherbox -m 0755 /var/lib/weatherbox
sudo install -m 0644 docs/config.quickstart.yaml /etc/weatherbox/config.yaml
```

### 2. Konfiguration anpassen und ausprobieren

`/etc/weatherbox/config.yaml` mit Administratorrechten bearbeiten: den Standort
anpassen und den gesamten `output`-Abschnitt durch Folgendes ersetzen. Relative
Pfade würden sonst auf das schreibgeschützte Konfigurationsverzeichnis zeigen.

```yaml
output:
  cache_dir: /var/lib/weatherbox/cache
  generated_dir: /var/lib/weatherbox/generated
  generated_retention_days: 30
  public_dir: /var/lib/weatherbox/public
  state_dir: /var/lib/weatherbox/state
```

Dann als Dienstbenutzer einen Probelauf durchführen:

```bash
sudo -u weatherbox /opt/weatherbox/.venv/bin/wb-announcer --config /etc/weatherbox/config.yaml generate-all
```

Die Audiodateien liegen unter `/var/lib/weatherbox/public/<standort-id>/`.
Eigene Modelle, Sprachdateien und Jingles müssen für den Benutzer `weatherbox`
lesbar sein. Die Service-Unit sperrt den Zugriff auf Home-Verzeichnisse;
verwende beispielsweise Unterverzeichnisse von `/etc/weatherbox` für diese Dateien.

### 3. Timer aktivieren

```bash
sudo install -m 0644 deploy/systemd/weatherbox.service deploy/systemd/weatherbox.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now weatherbox.timer
systemctl list-timers weatherbox.timer
sudo journalctl -u weatherbox.service -n 50
```

Der Timer startet jede Minute einen kurzen `run`-Durchlauf. Weatherbox entscheidet
anhand der Konfiguration, welche Ansagen fällig sind und erneut versucht werden.
Betreibe keinen zusätzlichen `serve`-Prozess oder Docker-Scheduler mit denselben
Daten. Für schreibende manuelle Befehle zunächst den Timer stoppen und einen
laufenden Service-Durchlauf abwarten; anschließend den Timer wieder starten.

## Dateien per HTTP bereitstellen

Weatherbox enthält keinen öffentlichen Webserver. Caddy oder nginx können die
Audiodateien an Abspielgeräte ausliefern. Als Dokumentenwurzel ausschließlich
`public_dir` verwenden, beim Linux-Dienst also `/var/lib/weatherbox/public`.
Cache und Scheduler-Status gehören nicht in dieses Verzeichnis.

Das [Caddy-Beispiel](../deploy/Caddyfile.example) enthält die Dokumentenwurzel
und Cache-Header für die unterstützten Audioformate. Ersetze darin
`audio.example.org` durch deine Domain und übernimm die Einstellungen in deinen
Caddy-Betrieb. Die Ansagen sind dann beispielsweise unter
`https://audio.example.org/wittstock/full-hour.mp3` abrufbar.
Für Docker beschreibt die [Docker-Anleitung](docker.md#konfiguration-dateien-und-persistente-daten)
den Zugriff auf das Datenvolume.

Die Dateien werden vor ihrem Wiedergabezeitpunkt ersetzt. Abspielgeräte müssen
sie rechtzeitig herunterladen und die Wiedergabe selbst planen.

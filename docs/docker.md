# Docker-Betrieb

[Projektübersicht und Schnellstart](../README.md) · [Dokumentationsübersicht](README.md)

Docker ist eine zusätzliche Deploy-Option zum [systemd-Timer](installation.md#linux-dienst-mit-systemd). Benötigt werden
Docker mit Linux-Containern und das
[Compose-Plugin](https://docs.docker.com/compose/). Alle folgenden Befehle werden
im Repository-Verzeichnis ausgeführt. Das Image enthält Python 3.14, FFmpeg,
FFprobe, eSpeak NG, CA-Zertifikate und Zeitzonendaten; gTTS wird mit Weatherbox
installiert. Auf dem Host ist keine Python- oder Audio-Tool-Installation nötig.

## Start mit Compose

```bash
mkdir docker-config
cp deploy/docker/config.example.yaml docker-config/config.yaml
# Jetzt docker-config/config.yaml anpassen, insbesondere Standorte und Templates.
docker compose config
docker compose build --pull
docker compose run --rm weatherbox status
docker compose up -d
docker compose logs -f weatherbox
```

In PowerShell kann für das Kopieren `Copy-Item` statt `cp` verwendet werden.
Die [Docker-Beispielkonfiguration](../deploy/docker/config.example.yaml) verwendet Open-Meteo sowie gTTS mit lokalem
eSpeak-Fallback und benötigt keine zusätzlichen Modelle oder Jingles. Ein
anfänglich als `degraded` gemeldeter Status ist bei leerem Wettercache normal.
Wetterdaten und gTTS benötigen ausgehenden Internetzugang. Für lokale
Spracherzeugung `tts.provider: espeak-ng` und `tts.fallback_provider: null` setzen.

Der Container startet `serve`: sofort ein Scheduler-Durchlauf, danach jeweils
60 Sekunden Pause. Vorbereitungshorizont, Wiederholungsversuche und Bereinigung
werden über YAML gesteuert. Das Polling-Intervall lässt sich in einer
`compose.override.yaml` anpassen:

```yaml
services:
  weatherbox:
    command: ["serve", "--interval-seconds", "30"]
```

Nur eine Scheduler-Instanz darf dieselben Laufzeitdaten verwenden; einen
bisherigen systemd-Timer dafür vor dem Umstieg stoppen und deaktivieren.
`docker compose stop` wartet bis zu zwei Minuten auf den laufenden Durchlauf.
Bei vielen Standorten oder langsamer Synthese `stop_grace_period` entsprechend
erhöhen, damit Docker den Prozess nicht vorzeitig beendet. Compose startet den
Dienst nach einem Fehler oder Docker-Neustart erneut, sofern er nicht manuell
gestoppt wurde. Einzelheiten stehen in der
[Compose-Service-Referenz](https://docs.docker.com/reference/compose-file/services/).

## Konfiguration, Dateien und persistente Daten

`docker-config/` wird schreibgeschützt nach `/etc/weatherbox` eingebunden und ist
von Git und vom Image-Build ausgeschlossen. Die Datei
`docker-config/config.yaml` muss vor dem Start existieren. Relative Pfade in
dieser Datei beziehen sich auf `/etc/weatherbox`, beispielsweise:

| Datei auf dem Host | Pfad in der YAML-Konfiguration |
| --- | --- |
| `docker-config/assets/intro.wav` | `assets/intro.wav` |
| `docker-config/models/stimme.onnx` | `models/stimme.onnx` |
| `docker-config/lang/de.yaml` | `localization.directory: lang` |

Für eigene Sprachdateien gilt weiterhin das vollständige Sprachschema. Nach
Konfigurationsänderungen `docker compose restart weatherbox` ausführen.
Eine bestehende native Konfiguration kann übernommen werden; dabei insbesondere
die vier Ausgabepfade auf die absoluten Containerpfade aus dem Docker-Beispiel
umstellen und benötigte Audio- und Modelldateien unter `docker-config/` ablegen.

Cache, Scheduler-Status, versionierte Audiodateien und öffentliche Dateien liegen
unter `/var/lib/weatherbox` im benannten Volume `weatherbox-data` (Compose ergänzt
den Projektnamen). Sie bleiben bei Container-Neuerstellung und
`docker compose down` erhalten. **`docker compose down -v` löscht dieses Volume
einschließlich aller Laufzeitdaten.** Konfiguration und Volume gemeinsam sichern.
Das Image läuft als unprivilegierter Benutzer mit UID/GID `10001:10001`;
Docker übernimmt die Schreibrechte beim ersten Anlegen des leeren Volumes.

Für direkten Host-Zugriff, etwa mit dem vorhandenen Caddy oder nginx, kann der
Volume-Eintrag für `/var/lib/weatherbox` in `compose.yaml` durch einen Bind-Mount
ersetzt werden:

```yaml
      - type: bind
        source: ./var/docker
        target: /var/lib/weatherbox
        bind:
          create_host_path: false
```

Das Verzeichnis vorher anlegen und unter Linux für UID/GID `10001:10001`
schreibbar machen, zum Beispiel mit
`sudo install -d -o 10001 -g 10001 -m 0755 var/docker`.
Konfiguration und Assets müssen für diesen Benutzer lesbar sein. Der Wechsel
des Mounts übernimmt vorhandene Daten nicht automatisch; bei einer Migration
den Scheduler stoppen und Cache, Status und Audioverzeichnisse mitnehmen.

Weatherbox öffnet keinen Netzwerkport. Für HTTP-Auslieferung einen separaten
Webserver ausschließlich auf das Unterverzeichnis `public` ausrichten, bei
obigem Bind-Mount also `var/docker/public` auf dem Host. Ein Webserver-Container
kann das Datenvolume schreibgeschützt einbinden und als Dokumentenwurzel
`/var/lib/weatherbox/public` verwenden. Cache und Status gehören nicht in die
öffentliche Dokumentenwurzel. Die Header aus [deploy/Caddyfile.example](../deploy/Caddyfile.example) gelten
auch für diese Variante.

## Status, manuelle Befehle und Updates

```bash
docker compose exec weatherbox wb-announcer --config /etc/weatherbox/config.yaml status

# Für schreibende manuelle Befehle den Scheduler zuerst stoppen.
docker compose stop weatherbox
docker compose run --rm weatherbox weather-update
docker compose run --rm weatherbox generate-all
docker compose up -d

# Nach Aktualisierung des Quellcodes das Image neu bauen und den Dienst ersetzen.
docker compose build --pull
docker compose up -d

# Container entfernen; Laufzeitdaten bleiben erhalten.
docker compose down
```

Weitere CLI-Befehle funktionieren analog, etwa
`docker compose run --rm weatherbox cleanup-generated --older-than-days 30`.
Compose begrenzt Containerlogs auf drei Dateien mit jeweils 10 MB.

## Optional: Piper im Image

Die zusätzliche [Piper-Installation](https://github.com/OHF-Voice/piper1-gpl)
wird beim Build aktiviert. Dazu im Repository eine `.env` mit folgendem Inhalt
anlegen beziehungsweise die vorhandene Datei ergänzen:

```dotenv
INSTALL_PIPER=true
```

Anschließend `docker compose build --pull` ausführen. Das Dockerfile installiert
dafür `piper-tts==1.7.0`; passende Pakete müssen für die verwendete
Linux-Architektur verfügbar sein. Das gewünschte `.onnx`-Modell samt zugehöriger
`.onnx.json`-Datei unter `docker-config/models/` ablegen und YAML anpassen:

```yaml
tts:
  provider: piper
  fallback_provider: espeak-ng
  piper:
    executable: piper
    model: models/de_DE-thorsten-medium.onnx
```

Alternativ kann Piper als Fallback für gTTS dienen. Modelle werden nicht
automatisch heruntergeladen. Danach `docker compose up -d --force-recreate`
ausführen, damit sowohl das neue Image als auch die Konfiguration aktiv werden.

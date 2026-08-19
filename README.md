# Weatherbox

Weatherbox erzeugt standortbezogene Wetteransagen als vollständig vorproduzierte
Stereo-MP3-Dateien. Die Dateien werden vor ihrem Wiedergabezeitpunkt atomar
veröffentlicht und können von Raspberry-Pi-Clients vorab lokal gecacht werden.
Während der Wiedergabe besteht keine Abhängigkeit zum TTS- oder Wetterdienst.

## Funktionsumfang

- beliebig viele Standorte ausschließlich über YAML konfigurierbar
- halbstündliche und stündliche Ansagen mit standortspezifischen Templates
- YAML-basierte deutsche und englische Sprachausgabe je Standort
- Forecast für den geplanten Wiedergabezeitpunkt über Open-Meteo
- atomarer JSON-Wettercache mit konfigurierbarem Höchstalter
- gTTS-Cloudausgabe sowie Piper und espeak-ng, frei als Primär- und Fallback-Provider kombinierbar
- optionale Jingles, Stereo-Konvertierung, Loudness-Normalisierung und MP3-Encoding
- technische MP3-Prüfung mit FFprobe vor jeder Veröffentlichung
- versionierte Assets und stabile öffentliche Dateinamen
- Scheduler mit Vorbereitungshorizont, Retry-Intervall und persistentem Status
- unabhängige Fehlerbehandlung pro Standort

## Installation

Vorausgesetzt werden Python 3.11 oder neuer sowie die Systemprogramme `ffmpeg`,
`ffprobe` sowie – je nach Konfiguration – Piper und/oder `espeak-ng`. gTTS wird
als Python-Abhängigkeit mitinstalliert und benötigt zur Erzeugung Internetzugang.

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
cp config.example.yaml config.yaml
```

In `config.yaml` müssen insbesondere der TTS-Provider, gegebenenfalls das
Piper-Modell, Jingle-Pfade und die
Ausgabeverzeichnisse angepasst werden. Nicht gewünschte Jingles können durch
Entfernen der jeweiligen YAML-Werte deaktiviert werden.
Standort-IDs sind URL- und dateisystemsichere Slugs aus Buchstaben, Zahlen,
Bindestrichen und Unterstrichen (zum Beispiel `wittstock_nord`).

## Template-Variablen

Templates verwenden Platzhalter in geschweiften Klammern, zum Beispiel
`Es ist {time} in {location}. Die Temperatur beträgt {temperature} Grad.`
Derzeit sind folgende Variablen implementiert:

| Variable | Inhalt und Ausgabeformat |
| --- | --- |
| `{time}` | Geplante Wiedergabezeit in Wörtern der Standortsprache, zum Beispiel `vierzehn Uhr dreißig` |
| `{hour}` | Stunde der geplanten Wiedergabe in Wörtern der Standortsprache, zum Beispiel `vierzehn` |
| `{minute}` | Minute der geplanten Wiedergabe als Zahl, zum Beispiel `30` |
| `{date}` | Lokalisiertes Datum der geplanten Wiedergabe, zum Beispiel `18. August 2026` |
| `{location}` | Konfigurierter Anzeigename des Standorts |
| `{latitude}` | Breitengrad des Standorts |
| `{longitude}` | Längengrad des Standorts |
| `{temperature}` | Vorhergesagte Temperatur in Grad Celsius |
| `{apparent_temperature}` | Vorhergesagte gefühlte Temperatur in Grad Celsius |
| `{dew_point}` | Vorhergesagter Taupunkt in Grad Celsius |
| `{humidity}` | Relative Luftfeuchtigkeit in Prozent |
| `{pressure}` | Luftdruck an der Oberfläche in Hektopascal |
| `{weather_description}` | Lokalisierte Beschreibung des Open-Meteo-Wettercodes, zum Beispiel `teilweise bewölkt` |
| `{weather_code}` | Numerischer Open-Meteo-Wettercode |
| `{cloud_cover}` | Bewölkungsgrad in Prozent |
| `{wind_speed}` | Windgeschwindigkeit in Kilometern pro Stunde |
| `{wind_direction}` | Windrichtung als lokalisierte Himmelsrichtung, zum Beispiel `Südwesten` |
| `{wind_direction_degrees}` | Windrichtung in Grad |
| `{wind_gusts}` | Geschwindigkeit der Windböen in Kilometern pro Stunde |
| `{precipitation}` | Vorhergesagte Niederschlagsmenge in Millimetern |
| `{precipitation_probability}` | Niederschlagswahrscheinlichkeit in Prozent |
| `{sunrise}` | Sonnenaufgang in den Zeitwörtern der Standortsprache, zum Beispiel `fünf Uhr achtundvierzig` |
| `{sunset}` | Sonnenuntergang in den Zeitwörtern der Standortsprache |
| `{forecast_time}` | Zeitpunkt der verwendeten Wetterdaten in den Zeitwörtern der Standortsprache |

Numerische Werte werden auf eine Nachkommastelle gerundet, überflüssige
Nachkommastellen werden entfernt und das Dezimaltrennzeichen wird lokalisiert.
Eine unbekannte Variable, eine Formatangabe wie `{temperature:.1f}` oder ein im
konkreten Forecast nicht verfügbarer verwendeter Wert bricht die Generierung
kontrolliert ab. Das bisher veröffentlichte Audio-Asset bleibt dabei erhalten.

## Sprachen und Aussprachewörterbücher

Weatherbox liefert die Sprachen Deutsch (`de`) und Englisch (`en`) mit. Die
zugehörigen YAML-Wörterbücher liegen unter `src/weatherbox/lang/`. Sie enthalten:

- Zahlen von null bis neunzehn und die Zehner bis fünfzig
- Regeln und Ausnahmen für zusammengesetzte Zahlen
- kontextabhängige Formen wie `ein Uhr` gegenüber `eins`
- Zeit- und Datumsmuster sowie Monatsnamen
- Dezimaltrennzeichen
- Beschreibungen der Open-Meteo-Wettercodes
- 16 Windrichtungen

Die Sprache kann für jeden Standort separat gewählt werden:

```yaml
localization:
  default_language: de
  # Optional: eigene vollständige YAML-Sprachdateien aus diesem Verzeichnis laden
  directory: lang

locations:
  wittstock:
    name: Wittstock
    latitude: 53.16
    longitude: 12.48
    timezone: Europe/Berlin
    language: de

  london:
    name: London
    latitude: 51.51
    longitude: -0.13
    timezone: Europe/London
    language: en
    announcements:
      full_hour:
        template: >
          It is {time} in {location}. The temperature is {temperature} degrees.
          Conditions are {weather_description}.
```

Eigene Sprachdateien müssen das vollständige Schema einer eingebauten Datei
besitzen. Eine Datei im konfigurierten `localization.directory` überschreibt eine
eingebaute Sprache mit demselben `code`; neue Codes ergänzen den Katalog. Über
`numbers.overrides` können unregelmäßige Zahlen vollständig überschrieben werden.
`time.hour_mode` unterstützt eine 12- oder 24-Stunden-Ausgabe. Ungültige oder
unvollständige Sprachdateien werden bereits beim Programmstart abgelehnt.

Templates werden bewusst nicht automatisch übersetzt. Für einen anderssprachigen
Standort muss daher ein passendes Standort-Template konfiguriert werden.

## Cloud-Sprachausgabe mit gTTS

Für die einfachste Cloud-Ausgabe verwendet Weatherbox die Python-API von gTTS
direkt; `gtts-cli` wird nicht als Unterprozess gestartet. gTTS greift auf den
Text-to-Speech-Dienst von Google Translate zu und liefert MP3-Daten. Es handelt
sich nicht um die kostenpflichtige Google-Cloud-Text-to-Speech-API und es wird
kein API-Schlüssel benötigt. Da der zugrunde liegende Dienst nicht von gTTS
garantiert wird, empfiehlt sich ein lokaler Fallback:

```yaml
tts:
  provider: gtts
  fallback_provider: piper
  gtts:
    language: de
    tld: de
    slow: false
    timeout_seconds: 15
  piper:
    executable: piper
    model: models/de_DE-kerstin-low.onnx
```

`language` ist der gTTS-Sprachcode. `tld` wählt die Google-Domain und kann die
regionale Aussprache beeinflussen. Bei Netzwerk-, Timeout- oder Dienstfehlern
wird automatisch der konfigurierte Fallback verwendet.

Damit gTTS, Piper beziehungsweise espeak-ng die richtige Stimme verwenden,
können die TTS-Einstellungen ebenfalls je Sprache überschrieben werden:

```yaml
tts:
  provider: gtts
  fallback_provider: piper
  gtts:
    language: de
    tld: de
  piper:
    model: models/de_DE-kerstin-low.onnx
  espeak-ng:
    voice: de
  languages:
    en:
      piper:
        model: models/en_GB-alba-medium.onnx
      espeak-ng:
        voice: en-gb
      gtts:
        language: en
        tld: co.uk
```

Fehlt eine sprachabhängige TTS-Einstellung, wird der globale Wert verwendet.
Nur bei gTTS wird `language` automatisch aus der Standortsprache übernommen;
ein expliziter sprachabhängiger Wert kann diese Zuordnung überschreiben.

## CLI

```text
wb-announcer --config config.yaml weather-update
wb-announcer --config config.yaml run
wb-announcer --config config.yaml generate-half-hour
wb-announcer --config config.yaml generate-full-hour
wb-announcer --config config.yaml generate-location wittstock
wb-announcer --config config.yaml generate-all
wb-announcer --config config.yaml generate-time wittstock full_hour --at 2026-08-18T14:00:00+02:00
wb-announcer --config config.yaml status
```

`run` ist für den regelmäßigen systemd-Aufruf vorgesehen. Die Anwendung prüft
selbst, welche Ansagen innerhalb des konfigurierten Vorbereitungshorizonts liegen.
Manuelle Generierungsbefehle behandeln alle Standorte unabhängig und liefern pro
Asset einen Erfolg oder Fehler zurück.

## Ausgabe

Bei einer Ansage für Wittstock entstehen beispielsweise:

```text
var/generated/wittstock/2026-08-18/14-00-full.mp3
var/public/wittstock/full-hour.mp3
```

Nur die stabilen Dateien unter `public_dir` werden durch Caddy oder nginx
ausgeliefert. Python stellt selbst keinen öffentlichen Webserver bereit.

## Tests

```bash
pytest
```

## Linux-Betrieb

Beispiele liegen unter `deploy/`:

- `deploy/systemd/weatherbox.service`
- `deploy/systemd/weatherbox.timer`
- `deploy/Caddyfile.example`

Für die Beispiel-Units werden ein unprivilegierter Benutzer `weatherbox`, der
Programmstand unter `/opt/weatherbox`, die Konfiguration unter
`/etc/weatherbox/config.yaml` und schreibbare Laufzeitdaten unter
`/var/lib/weatherbox` erwartet. Der Timer startet jede Minute einen kurzen
One-shot-Lauf; Retries und Fälligkeit entscheidet Weatherbox selbst.

## Architekturregel

Weatherbox erzeugt keine Live-Audioausgabe. Eine neue Datei wird erst nach
erfolgreicher TTS-Erzeugung, Audioverarbeitung und FFprobe-Validierung atomar an
die stabile öffentliche Stelle verschoben. Schlägt ein Schritt fehl, bleibt das
bisherige öffentliche Asset unverändert.

Die TTS-Implementierung liegt im Paket `src/weatherbox/tts/`:

- `piper.py`, `espeak_ng.py` und `gtts.py` enthalten jeweils genau einen Provider
- `fallback.py` steuert die primäre und sekundäre Ausgabe
- `factory.py` übersetzt die Konfiguration in eine Provider-Kette
- `base.py` enthält nur die gemeinsame Schnittstelle und Validierungshelfer
- `__init__.py` stellt die bisherige öffentliche Importoberfläche bereit

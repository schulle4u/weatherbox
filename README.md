# Weatherbox

Weatherbox erzeugt standortbezogene Wetteransagen als vollständig vorproduzierte
Stereo-MP3-Dateien. Die Dateien werden vor ihrem Wiedergabezeitpunkt atomar
veröffentlicht und können von Raspberry-Pi-Clients vorab lokal gecacht werden.
Während der Wiedergabe besteht keine Abhängigkeit zum TTS- oder Wetterdienst.

## Funktionsumfang

- beliebig viele Standorte ausschließlich über YAML konfigurierbar
- halbstündliche und stündliche Ansagen mit standortspezifischen Templates
- Forecast für den geplanten Wiedergabezeitpunkt über Open-Meteo
- atomarer JSON-Wettercache mit konfigurierbarem Höchstalter
- Piper als primärer TTS-Provider, optionaler Fallback auf espeak-ng
- optionale Jingles, Stereo-Konvertierung, Loudness-Normalisierung und MP3-Encoding
- technische MP3-Prüfung mit FFprobe vor jeder Veröffentlichung
- versionierte Assets und stabile öffentliche Dateinamen
- Scheduler mit Vorbereitungshorizont, Retry-Intervall und persistentem Status
- unabhängige Fehlerbehandlung pro Standort

## Installation

Vorausgesetzt werden Python 3.11 oder neuer sowie die Systemprogramme `ffmpeg`,
`ffprobe`, Piper und optional `espeak-ng`.

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
cp config.example.yaml config.yaml
```

In `config.yaml` müssen insbesondere das Piper-Modell, Jingle-Pfade und die
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
| `{time}` | Geplante Wiedergabezeit in deutschen Wörtern, zum Beispiel `vierzehn Uhr dreißig` |
| `{hour}` | Stunde der geplanten Wiedergabe in deutschen Wörtern, zum Beispiel `vierzehn` |
| `{minute}` | Minute der geplanten Wiedergabe als Zahl, zum Beispiel `30` |
| `{date}` | Datum der geplanten Wiedergabe, zum Beispiel `18. August 2026` |
| `{location}` | Konfigurierter Anzeigename des Standorts |
| `{latitude}` | Breitengrad des Standorts |
| `{longitude}` | Längengrad des Standorts |
| `{temperature}` | Vorhergesagte Temperatur in Grad Celsius |
| `{apparent_temperature}` | Vorhergesagte gefühlte Temperatur in Grad Celsius |
| `{dew_point}` | Vorhergesagter Taupunkt in Grad Celsius |
| `{humidity}` | Relative Luftfeuchtigkeit in Prozent |
| `{pressure}` | Luftdruck an der Oberfläche in Hektopascal |
| `{weather_description}` | Deutsche Beschreibung des Open-Meteo-Wettercodes, zum Beispiel `teilweise bewölkt` |
| `{weather_code}` | Numerischer Open-Meteo-Wettercode |
| `{cloud_cover}` | Bewölkungsgrad in Prozent |
| `{wind_speed}` | Windgeschwindigkeit in Kilometern pro Stunde |
| `{wind_direction}` | Windrichtung als deutsche Himmelsrichtung, zum Beispiel `Südwesten` |
| `{wind_direction_degrees}` | Windrichtung in Grad |
| `{wind_gusts}` | Geschwindigkeit der Windböen in Kilometern pro Stunde |
| `{precipitation}` | Vorhergesagte Niederschlagsmenge in Millimetern |
| `{precipitation_probability}` | Niederschlagswahrscheinlichkeit in Prozent |
| `{sunrise}` | Sonnenaufgang in deutschen Zeitwörtern, zum Beispiel `fünf Uhr achtundvierzig` |
| `{sunset}` | Sonnenuntergang in deutschen Zeitwörtern |
| `{forecast_time}` | Zeitpunkt, für den die verwendeten Wetterdaten gelten, in deutschen Zeitwörtern |

Numerische Werte werden auf eine Nachkommastelle gerundet, überflüssige
Nachkommastellen werden entfernt und das Dezimalkomma wird deutsch formatiert.
Eine unbekannte Variable, eine Formatangabe wie `{temperature:.1f}` oder ein im
konkreten Forecast nicht verfügbarer verwendeter Wert bricht die Generierung
kontrolliert ab. Das bisher veröffentlichte Audio-Asset bleibt dabei erhalten.

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

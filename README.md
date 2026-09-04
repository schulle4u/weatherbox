# Weatherbox

Weatherbox erzeugt standortbezogene Wetteransagen als vollständig vorproduzierte
Stereo-Audiodateien. Die Dateien werden vor ihrem Wiedergabezeitpunkt atomar
veröffentlicht und können von Raspberry-Pi-Clients vorab lokal gecacht werden.
Während der Wiedergabe besteht keine Abhängigkeit zum TTS- oder Wetterdienst.

## Funktionsumfang

- beliebig viele Standorte ausschließlich über YAML konfigurierbar
- Temperatureinheit (`c` oder `f`) je Standort konfigurierbar
- halbstündliche und stündliche Ansagen mit standortspezifischen Templates
- YAML-basierte deutsche und englische Sprachausgabe je Standort
- Forecast für den geplanten Wiedergabezeitpunkt über Open-Meteo oder DWD
- parallele, feldweise Zusammenführung mehrerer Wetterprovider mit Fallback
- amtliche, stationsbezogene DWD-Warnmeldungen in Ansage-Templates
- atomarer JSON-Wettercache mit konfigurierbarem Höchstalter
- gTTS-Cloudausgabe sowie Piper und espeak-ng, frei als Primär- und Fallback-Provider kombinierbar
- optionale Intros, Outros und Musikbetten, Stereo-Konvertierung, Loudness-Normalisierung und Multi-Format-Encoding
- MP3, WAV, FLAC, Ogg Vorbis, Opus und AAC in M4A-Containern
- technische Codec-Prüfung mit FFprobe vor jeder Veröffentlichung
- versionierte Assets und stabile öffentliche Dateinamen
- Scheduler mit Vorbereitungshorizont, Retry-Intervall und persistentem Status
- unabhängige Fehlerbehandlung pro Standort
- Docker-Compose-Deployment mit persistenten Daten und integriertem Dauerbetrieb

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
Piper-Modell, Audio-Asset-Pfade und die
Ausgabeverzeichnisse angepasst werden. Nicht gewünschte Audioelemente werden
einfach weggelassen oder mit `null` deaktiviert.
Standort-IDs sind URL- und dateisystemsichere Slugs aus Buchstaben, Zahlen,
Bindestrichen und Unterstrichen (zum Beispiel `wittstock_nord`).

## Intros, Outros und Musikbetten

Für Halb- und Vollstundenansagen können unabhängig voneinander ein Intro, ein
Outro und ein Musikbett konfiguriert werden:

```yaml
audio:
  jingles:
    half_hour:
      intro: assets/intro.wav
      outro: assets/outro.wav
      music: assets/music.wav
    full_hour:
      intro: assets/full-hour-intro.wav
    music_attenuation: -10
    music_fade_out: 2.5
```

Relative Dateipfade werden relativ zur Konfigurationsdatei aufgelöst. Das
Musikbett wird bei Bedarf wiederholt, um `music_attenuation` Dezibel abgesenkt
und während der Ansage zugemischt. `music_fade_out` gibt an, wie viele Sekunden
es nach dem Sprachende weiterläuft und ausfadet; anschließend beginnt das Outro.
`music_attenuation` muss kleiner oder gleich null und `music_fade_out` größer
oder gleich null sein. Standorte können einzelne Dateien unter
`locations.<id>.audio.jingles.<half_hour|full_hour>` überschreiben oder durch
einen leeren Wert gezielt deaktivieren.

## Audio-Ausgabeformate

Ohne Formatangabe erzeugt Weatherbox wie bisher ausschließlich MP3. Mehrere
Formate lassen sich in einer kompakten Schreibweise aktivieren:

```yaml
audio:
  output:
    format: mp3, flac, opus
    sample_rate: 48000
    channels: 2
    bitrate: 192k
```

Alternativ erlaubt `formats` eine eigene Bitrate je verlustbehaftetem Format:

```yaml
audio:
  output:
    sample_rate: 48000
    channels: 2
    formats:
      mp3:
        bitrate: 192k
      wav: {}
      flac: {}
      ogg:
        bitrate: 160k
      opus:
        bitrate: 96k
      m4a:
        bitrate: 192k
```

Unterstützt werden `mp3`, `wav` (PCM 16 Bit), `flac`, `ogg` (Vorbis), `opus`
und `m4a` (AAC). `vorbis` und `aac` werden als Alias für `ogg` beziehungsweise
`m4a` akzeptiert. `format` akzeptiert neben der kommagetrennten Schreibweise
auch eine YAML-Liste. `format` und `formats` dürfen nicht gleichzeitig gesetzt
werden. WAV und FLAC sind verlustfrei und besitzen daher keine
Bitratenkonfiguration. Opus unterstützt als Abtastrate 8000, 12000, 16000,
24000 oder 48000 Hz. Erst wenn alle konfigurierten Formate erfolgreich erzeugt
und mit FFprobe validiert wurden, beginnt die Veröffentlichung.

## Template-Variablen

Templates verwenden Platzhalter in geschweiften Klammern, zum Beispiel
`Es ist {time} in {location}. Die Temperatur beträgt {temperature} Grad.`
Derzeit sind folgende Variablen implementiert:

| Variable | Inhalt und Ausgabeformat |
| --- | --- |
| `{greeting}` | Begrüßung nach lokaler Standortzeit: morgens bis 11:59 Uhr, tagsüber ab 12:00 Uhr und abends ab 18:00 Uhr; die Texte werden in der Sprachdatei unter `greetings` konfiguriert |
| `{time}` | Geplante Wiedergabezeit in Wörtern der Standortsprache, zum Beispiel `vierzehn Uhr dreißig` |
| `{hour}` | Stunde der geplanten Wiedergabe in Wörtern der Standortsprache, zum Beispiel `vierzehn` |
| `{minute}` | Minute der geplanten Wiedergabe als Zahl, zum Beispiel `30` |
| `{date}` | Lokalisiertes Datum der geplanten Wiedergabe, zum Beispiel `18. August 2026` |
| `{location}` | Konfigurierter Anzeigename des Standorts |
| `{latitude}` | Breitengrad des Standorts |
| `{longitude}` | Längengrad des Standorts |
| `{temperature}` | Vorhergesagte Temperatur in der für den Standort konfigurierten Einheit |
| `{apparent_temperature}` | Vorhergesagte gefühlte Temperatur in der für den Standort konfigurierten Einheit |
| `{dew_point}` | Vorhergesagter Taupunkt in der für den Standort konfigurierten Einheit |
| `{humidity}` | Relative Luftfeuchtigkeit in Prozent |
| `{pressure}` | Luftdruck an der Oberfläche in Hektopascal |
| `{weather_description}` | Lokalisierte Beschreibung des providerunabhängigen WMO-Wettercodes, zum Beispiel `teilweise bewölkt` |
| `{weather_code}` | Numerischer, intern vereinheitlichter WMO-Wettercode |
| `{cloud_cover}` | Bewölkungsgrad in Prozent |
| `{wind_speed}` | Windgeschwindigkeit in Kilometern pro Stunde |
| `{wind_direction}` | Windrichtung als lokalisierte Himmelsrichtung, zum Beispiel `Südwesten` |
| `{wind_direction_degrees}` | Windrichtung in Grad |
| `{wind_gusts}` | Geschwindigkeit der Windböen in Kilometern pro Stunde |
| `{precipitation}` | Vorhergesagte Niederschlagsmenge in Millimetern |
| `{precipitation_probability}` | Niederschlagswahrscheinlichkeit in Prozent |
| `{day_temperature_min}` | Tiefste Temperatur des lokalen Kalendertags in der konfigurierten Temperatureinheit |
| `{day_temperature_max}` | Höchste Temperatur des lokalen Kalendertags in der konfigurierten Temperatureinheit |
| `{day_precipitation_sum}` | Erwartete Niederschlagssumme des lokalen Kalendertags in Millimetern |
| `{day_precipitation_probability_max}` | Höchste stündliche Niederschlagswahrscheinlichkeit des lokalen Kalendertags in Prozent |
| `{day_precipitation_hours}` | Anzahl der Stunden mit erwartetem Niederschlag am lokalen Kalendertag |
| `{day_cloud_cover_mean}` | Mittlerer Bewölkungsgrad über den gesamten lokalen Kalendertag in Prozent |
| `{day_weather_description}` | Lokalisierte Beschreibung der markantesten Wetterlage des lokalen Kalendertags |
| `{day_wind_speed_max}` | Höchste Windgeschwindigkeit des lokalen Kalendertags in Kilometern pro Stunde |
| `{day_wind_gusts_max}` | Höchste Böengeschwindigkeit des lokalen Kalendertags in Kilometern pro Stunde |
| `{day_weather_summary}` | Lokalisierte Zusammenfassung aus Tageswetterlage sowie Tagesminimum und -maximum |
| `{day_cloud_summary}` | Lokalisierte, aus dem mittleren Bewölkungsgrad abgeleitete Tageszusammenfassung |
| `{day_precipitation_summary}` | Lokalisierte Zusammenfassung aus maximaler Niederschlagswahrscheinlichkeit und erwarteter Niederschlagssumme |
| `{sunrise}` | Sonnenaufgang in den Zeitwörtern der Standortsprache, zum Beispiel `fünf Uhr achtundvierzig` |
| `{sunset}` | Sonnenuntergang in den Zeitwörtern der Standortsprache |
| `{forecast_time}` | Zeitpunkt der verwendeten Wetterdaten in den Zeitwörtern der Standortsprache |
| `{warning_count}` | Anzahl der zum Wiedergabezeitpunkt aktiven DWD-Warnungen |
| `{warning_level}` | DWD-Warnstufe der höchstpriorisierten aktiven Warnung |
| `{warning_event}` | Ereignisbezeichnung der höchstpriorisierten Warnung |
| `{warning_headline}` | Überschrift der höchstpriorisierten Warnung |
| `{warning_description}` | Ausführliche Beschreibung der höchstpriorisierten Warnung |
| `{warning_instruction}` | Handlungshinweis der höchstpriorisierten Warnung |
| `{warning_start}` | Beginn der höchstpriorisierten Warnung in lokalisierten Zeitwörtern |
| `{warning_end}` | Ende der höchstpriorisierten Warnung in lokalisierten Zeitwörtern |
| `{warning_text}` | Überschriften aller aktiven Warnungen oder lokalisierter Hinweis, dass keine Warnung aktiv ist |
| `{temperature_source}` | Provider des verwendeten Temperaturwerts, zum Beispiel `dwd` |
| `{weather_source}` | Provider des verwendeten Wettercodes und der Wetterbeschreibung |
| `{warning_source}` | Provider der höchstpriorisierten aktiven Warnung |

Numerische Werte werden auf eine Nachkommastelle gerundet, überflüssige
Nachkommastellen werden entfernt und das Dezimaltrennzeichen wird lokalisiert.
Eine unbekannte Variable, eine Formatangabe wie `{temperature:.1f}` oder ein im
konkreten Forecast nicht verfügbarer verwendeter Wert bricht die Generierung
kontrolliert ab. Das bisher veröffentlichte Audio-Asset bleibt dabei erhalten.
`{warning_count}` und `{warning_text}` sind immer belegt. Die übrigen Warnfelder
sind nur verwendbar, wenn zum Wiedergabezeitpunkt mindestens eine entsprechende
Warnung aktiv ist. Bei mehreren Warnungen liefert das Modul für die einzelnen
Warnfelder die höchste Warnstufe; `{warning_text}` verbindet alle Überschriften.
Die `day_`-Variablen beziehen sich auf das lokale Kalenderdatum der geplanten
Wiedergabe. Die Tageszusammenfassungen sind vollständige Sätze und können direkt
aneinandergereiht werden, zum Beispiel:

```yaml
template: >
  Es ist {time} in {location}. {day_weather_summary}
  {day_cloud_summary} {day_precipitation_summary}
```

## Wetterprovider

Weatherbox bezieht Wetterdaten aus den unter `weather.providers` konfigurierten
Quellen. Open-Meteo arbeitet direkt mit den Koordinaten eines Standorts, der
DWD-Provider mit der stationsbasierten WarnWetter-API. Die Quellen werden
feldweise zusammengeführt. Sobald DWD konfiguriert ist, benötigt jeder aktive
Standort eine DWD-Stationskennung:

```yaml
weather:
  providers:
    open-meteo:
      endpoint: https://api.open-meteo.com/v1/forecast
    dwd:
      endpoint: https://app-prod-ws.warnwetter.de/v30/stationOverviewExtended
  update_interval_minutes: 30
  max_cache_age_minutes: 60
  request_timeout_seconds: 15
  merge:
    tolerance_minutes: 30
    default_priority: [open-meteo, dwd]
    field_priority:
      temperature: [dwd, open-meteo]
      humidity: [dwd, open-meteo]
      pressure: [dwd, open-meteo]
      warnings: [dwd, open-meteo]

locations:
  wittstock:
    name: Wittstock
    latitude: 53.16
    longitude: 12.48
    timezone: Europe/Berlin
    temperature_unit: c
    weather:
      # WarnWetter-/MOS-Kennung für Wittstock-Rote Mühle
      dwd_station_id: F143
    announcements:
      full_hour:
        template: >
          Es ist {time} in {location}. {weather_description}.
          {warning_text}.
```

Die Provider werden parallel abgerufen. Das Zeitraster stammt vom ersten
verfügbaren Provider in `default_priority`; Werte der übrigen Quellen werden
innerhalb von `tolerance_minutes` dem jeweils nächsten Zeitpunkt zugeordnet.
Für jedes Feld wird der erste vorhandene Wert aus seiner `field_priority`
verwendet. Nicht genannte Provider werden automatisch als Fallback angehängt.
Eine Mittelwertbildung findet bewusst nicht statt. Warnungen werden vereinigt
und Duplikate entsprechend der Warnpriorität entfernt. Wenn nur ein Provider
erreichbar ist, wird dessen Ergebnis weiterverwendet; erst der Ausfall aller
Provider lässt den Abruf fehlschlagen.

Temperaturwerte werden providerunabhängig und im Cache stets in Grad Celsius
gehalten. Erst beim Aufbau einer Ansage rechnet Weatherbox `temperature`,
`apparent_temperature`, `dew_point`, `day_temperature_min` und
`day_temperature_max` anhand von
`locations.<id>.temperature_unit` in Celsius (`c`, Standard) oder Fahrenheit
(`f`) um. So können mehrere Standorte mit unterschiedlichen Einheiten dieselben
Wetterprovider verwenden. Das jeweilige Template sollte die Einheit passend als
„Grad Celsius“ beziehungsweise „Grad Fahrenheit“ benennen.

Die Stationskennung ist nicht automatisch die numerische `Stations_id` aus den
CDC-Open-Data-Dateien. `stationOverviewExtended` liefert nur WarnWetter-/MOS-
Stationen; phänologische Kennungen wie `12471` für Wittstock/Dosse funktionieren
dort nicht. Für den konfigurierten Standort Wittstock ist `F143`
(`Wittstock-Rote Mühle`) eine passende Kennung. Geeignete MOS-Kennungen lassen
sich ersatzweise im frei zugänglichen
[Stationskatalog von Tiny Weather Forecast Germany](https://tinyweatherforecastgermanygroup.gitlab.io/index/stations.html)
recherchieren, falls die in der
[DWD-API-Dokumentation](https://dwd.api.bund.dev/) verlinkte DWD-Liste nicht
erreichbar ist. Temperaturen, Feuchte, Druck, Niederschlag und Wind werden aus
den DWD-Zehntelwerten in die gleichen Einheiten wie bei Open-Meteo umgerechnet.
Der DWD-Provider übernimmt zusätzlich die täglichen Minimal- und
Maximaltemperaturen, Niederschlagssumme, Wetterlage sowie Wind- und Böenmaxima
aus dem `days`-Abschnitt und ermittelt Niederschlagsstunden aus der stündlichen
Reihe. Da die DWD-Antwort nicht alle Open-Meteo-Felder liefert, bleiben
insbesondere `{apparent_temperature}`, `{cloud_cover}`,
`{precipitation_probability}`, `{day_cloud_cover_mean}` und
`{day_precipitation_probability_max}` beim DWD unbesetzt. Bei gemeinsamem
Betrieb ergänzt Open-Meteo diese Werte entsprechend der Merge-Priorität.

## Sprachen und Aussprachewörterbücher

Weatherbox liefert die Sprachen Deutsch (`de`) und Englisch (`en`) mit. Die
zugehörigen YAML-Wörterbücher liegen unter `src/weatherbox/lang/`. Sie enthalten:

- Zahlen von null bis neunzehn und die Zehner bis fünfzig
- Regeln und Ausnahmen für zusammengesetzte Zahlen
- kontextabhängige Formen wie `ein Uhr` gegenüber `eins`
- Zeit- und Datumsmuster sowie Monatsnamen
- Dezimaltrennzeichen
- Beschreibungen der providerunabhängigen WMO-Wettercodes
- Satzmuster für Wetter-, Bewölkungs- und Niederschlagszusammenfassungen
- 16 Windrichtungen

Die eingebauten Zusammenfassungen ordnen die mittlere Tagesbewölkung festen
Bewölkungsstufen und die maximale Niederschlagswahrscheinlichkeit festen
Wahrscheinlichkeitsstufen zu. Sämtliche ausgegebenen Sätze stehen unter
`summaries` in der jeweiligen Sprachdatei und können dort ersetzt werden. Bei
älteren eigenen Sprachdateien darf der Abschnitt fehlen; die übrige Sprache
bleibt dann nutzbar, während die drei Zusammenfassungsvariablen unbelegt sind.

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
    temperature_unit: c
    language: de

  london:
    name: London
    latitude: 51.51
    longitude: -0.13
    timezone: Europe/London
    temperature_unit: f
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

## Docker-Betrieb

Docker ist eine zusätzliche Deploy-Option zum systemd-Timer. Benötigt werden
Docker mit Linux-Containern und das
[Compose-Plugin](https://docs.docker.com/compose/). Alle folgenden Befehle werden
im Repository-Verzeichnis ausgeführt. Das Image enthält Python 3.14, FFmpeg,
FFprobe, eSpeak NG, CA-Zertifikate und Zeitzonendaten; gTTS wird mit Weatherbox
installiert. Auf dem Host ist keine Python- oder Audio-Tool-Installation nötig.

### Start mit Compose

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
Die Docker-Beispielkonfiguration verwendet Open-Meteo sowie gTTS mit lokalem
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

### Konfiguration, Dateien und persistente Daten

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
öffentliche Dokumentenwurzel. Die Header aus `deploy/Caddyfile.example` gelten
auch für diese Variante.

### Status, manuelle Befehle und Updates

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

### Optional: Piper im Image

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

## Architekturregel

Weatherbox erzeugt keine Live-Audioausgabe. Alle konfigurierten Formate werden
zuerst erzeugt und mit FFprobe validiert. Erst danach wird jede Datei atomar an
ihre stabile öffentliche Stelle verschoben. Schlägt Synthese, Verarbeitung oder
Validierung fehl, bleiben sämtliche bisherigen öffentlichen Assets unverändert.

Die Wetter-Implementierung liegt im Paket `src/weatherbox/weather/`:

- `open_meteo.py` und `dwd.py` enthalten die Provider und ihre API-Abbildungen
- `merged.py` richtet mehrere Quellen zeitlich aus und führt sie feldweise zusammen
- `factory.py` baut den einzelnen oder zusammengeführten Provider aus YAML
- `base.py` enthält die gemeinsame Schnittstelle
- `cache.py` speichert Forecasts und Warnungen providerunabhängig

Die TTS-Implementierung liegt im Paket `src/weatherbox/tts/`:

- `piper.py`, `espeak_ng.py` und `gtts.py` enthalten jeweils genau einen Provider
- `fallback.py` steuert die primäre und sekundäre Ausgabe
- `factory.py` übersetzt die Konfiguration in eine Provider-Kette
- `base.py` enthält nur die gemeinsame Schnittstelle und Validierungshelfer
- `__init__.py` stellt die bisherige öffentliche Importoberfläche bereit

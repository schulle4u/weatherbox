# Konfiguration

[Projektübersicht und Schnellstart](../README.md) · [Dokumentationsübersicht](README.md)

## Konfigurationsdatei und Vorlagen

Weatherbox liest eine YAML-Datei, die mit `wb-announcer --config config.yaml`
ausgewählt wird. Alle Befehlsbeispiele gehen vom Projektverzeichnis aus.
Kopiere eine Vorlage dorthin, bevor du sie verwendest:

| Vorlage | Verwendung |
| --- | --- |
| [config.quickstart.yaml](config.quickstart.yaml) | Einfacher Start mit Open-Meteo und gTTS, ohne Modelle und Audiodateien |
| [config.example.yaml](config.example.yaml) | Umfangreiches Beispiel mit DWD, Piper-Fallback und Jingles |
| [Docker-Konfiguration](../deploy/docker/config.example.yaml) | Compose-Betrieb mit absoluten Containerpfaden und eSpeak-Fallback |

```bash
cp docs/config.example.yaml config.yaml
```

Die umfangreiche Vorlage ist vor dem Start anzupassen: Sie verweist auf ein
Piper-Modell und Audiodateien, die nicht mitgeliefert werden. Installiere und
konfiguriere diese Dateien oder wähle einen anderen TTS-Provider/Fallback und
entferne die optionalen Jingle-Einträge. `fallback_provider: null` deaktiviert
den Fallback. Ein Jingle kann weggelassen oder mit `null` deaktiviert werden.

Relative Datei- und Verzeichnispfade beziehen sich immer auf den Ordner der
verwendeten Konfigurationsdatei, nicht auf das Arbeitsverzeichnis.
Nach Änderungen den Dauerbetrieb (`serve` oder Docker) neu starten.

## Aufbau und Standorte

| Abschnitt | Zweck |
| --- | --- |
| `application` | Log-Level und JSON-Logs |
| `localization` | Standardsprache und eigene Sprachdateien |
| `weather` | Wetterquellen, Cache-Alter und Zusammenführung |
| `scheduler` | Vorbereitungszeit und Wiederholungsversuche |
| `tts` | Sprachausgabe, Fallback und Stimmen je Sprache |
| `audio` | FFmpeg/FFprobe, Lautstärke, Formate und Jingles |
| `output` | Datenverzeichnisse und Aufbewahrungsdauer |
| `announcements` | Gemeinsame Texte für volle und halbe Stunden |
| `locations` | Orte und standortspezifische Einstellungen |

Jeder Standort benötigt `name`, `latitude`, `longitude` und `timezone`.
Die Standort-ID bestimmt das Unterverzeichnis der Ausgabedateien. Sie beginnt
mit einem Buchstaben oder einer Zahl und enthält ausschließlich ASCII-Buchstaben,
Zahlen, Bindestriche und Unterstriche, zum Beispiel `wittstock_nord`.

```yaml
locations:
  wittstock:
    name: Wittstock
    latitude: 53.16
    longitude: 12.48
    timezone: Europe/Berlin
    language: de
    temperature_unit: c
    enabled: true
```

Weitere Orte werden als zusätzliche Einträge unter `locations` angelegt.
`enabled: false` nimmt einen Standort aus der regulären Verarbeitung.
`temperature_unit` erlaubt `c` (Standard) oder `f`.
Bei aktiviertem DWD ist zusätzlich `weather.dwd_station_id` je aktivem Ort
erforderlich. Eigene Ansagen stehen unter
`locations.<id>.announcements.<half_hour|full_hour>` und überschreiben die
globalen Einstellungen. Texte und Sprachwahl beschreibt die
[Template-Referenz](templates.md).

## Zeitplanung und Datenverzeichnisse

`scheduler.preparation_minutes` legt fest, wie viele Minuten vor dem
Wiedergabezeitpunkt die Erzeugung beginnt (Standard: 10).
`scheduler.retry.interval_seconds` und `max_attempts` steuern Wiederholungen
fehlgeschlagener Ansagen (Standard: 60 Sekunden und 5 Versuche).
Weatherbox muss dafür regelmäßig per `run` oder fortlaufend per `serve`
ausgeführt werden; die [Betriebsanleitung](operations.md) erläutert die Befehle.

`output.cache_dir` speichert Wetterdaten, `state_dir` den Scheduler-Status,
`generated_dir` versionierte Audiodateien und `public_dir` die Dateien mit
stabilen Namen. Alle vier Verzeichnisse müssen schreibbar sein. Hinweise zur
Bereinigung stehen unter [Ausgabe](operations.md#ausgabe).

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

Ohne Formatangabe erzeugt Weatherbox ausschließlich MP3. Mehrere
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
